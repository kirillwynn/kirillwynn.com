from __future__ import annotations

import importlib.util
import os
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

SCANNER = Path(__file__).with_name("scan_test_artifacts.sh")
FIXTURES = Path(__file__).with_name("fixtures")
CI_WORKFLOW = Path(__file__).parents[2] / ".github" / "workflows" / "ci.yml"
SCANNER_SPEC = importlib.util.spec_from_file_location(
    "scan_test_artifacts", SCANNER.with_suffix(".py")
)
assert SCANNER_SPEC is not None and SCANNER_SPEC.loader is not None
scanner = importlib.util.module_from_spec(SCANNER_SPEC)
sys.modules[SCANNER_SPEC.name] = scanner
SCANNER_SPEC.loader.exec_module(scanner)

CREDENTIAL_REPRESENTATIONS = [
    pytest.param(
        b'{"url":"https://example.test/api/draft?credential=preview-sentinel"}',
        id="url-query-credential",
    ),
    pytest.param(
        b'{"url":"https://example.test/subscriptions/confirm#credential=signed-sentinel"}',
        id="url-fragment-credential",
    ),
    pytest.param(
        b'{"url":"https://example.test/subscriptions/unsubscribe#credential=signed-sentinel"}',
        id="url-fragment-unsubscribe-credential",
    ),
    pytest.param(
        b'{"url":"https://provider.test/callback?access_token=access-sentinel"}',
        id="url-access-token",
    ),
    pytest.param(
        b'{"url":"https://provider.test/callback#refresh_token=refresh-sentinel"}',
        id="url-refresh-token",
    ),
    pytest.param(
        b'{"url":"https://example.test/accounts/provider/login/callback/?code=code-sentinel"}',
        id="url-authorization-code",
    ),
    pytest.param(
        b'{"cookies":[{"name":"sessionid","value":"session-sentinel"}]}',
        id="json-session-cookie",
    ),
    pytest.param(
        b'{"cookies":[{"name":"csrftoken","value":"csrf-sentinel"}]}',
        id="json-csrf-cookie",
    ),
    pytest.param(
        b'{"cookies":[{"name":"kw_preview_credential","value":"preview-sentinel"}]}',
        id="json-preview-cookie",
    ),
    pytest.param(
        b'{"cookies":[{"name":"__Host-sessionid","value":"session-sentinel"}]}',
        id="json-host-session-cookie",
    ),
    pytest.param(
        b'{"cookies":[{"name":"__Host-csrftoken","value":"csrf-sentinel"}]}',
        id="json-host-csrf-cookie",
    ),
    pytest.param(
        b'{"cookies":[{"name":"__Host-kw_preview_credential","value":"preview-sentinel"}]}',
        id="json-host-preview-cookie",
    ),
    pytest.param(
        b'{"headers":[{"name":"Cookie","value":"theme=dark"}]}',
        id="json-cookie-header",
    ),
    pytest.param(
        b'{"headers":[{"name":"Set-Cookie","value":"theme=dark"}]}',
        id="json-set-cookie-header",
    ),
    pytest.param(
        b'{"rawHeader":"Cookie: sessionid=session-sentinel"}',
        id="json-raw-cookie-header",
    ),
    pytest.param(
        b'{"rawHeader":"Set-Cookie: sessionid=session-sentinel"}',
        id="json-raw-set-cookie-header",
    ),
    pytest.param(b"Cookie: theme=dark\r\n", id="raw-cookie-header"),
    pytest.param(b"Set-Cookie: theme=dark\r\n", id="raw-set-cookie-header"),
    pytest.param(
        b'{"headers":{"authorization":"Bearer bearer-sentinel"}}',
        id="json-authorization-header",
    ),
    pytest.param(
        b'{"access_token":"provider-access-sentinel"}',
        id="json-access-token",
    ),
    pytest.param(
        b'{"refresh_token":"provider-refresh-sentinel"}',
        id="json-refresh-token",
    ),
    pytest.param(
        b'{"code":"provider-authorization-code-sentinel"}',
        id="json-authorization-code",
    ),
    pytest.param(b"provider-boundary-code", id="provider-boundary-code"),
    pytest.param(
        b"provider-boundary-access-token",
        id="provider-boundary-access-token",
    ),
    pytest.param(
        b'{"credential":"eyJ2IjoxLCJwdXJwb3NlIjoiY29uZmlybSJ9:1abcde:signature-sentinel-value"}',
        id="json-signed-subscription-credential",
    ),
    pytest.param(
        b"abcdefghijklmnopqrstuvwxyzABCDEF:1abcde:signature-sentinel-value",
        id="raw-signed-credential",
    ),
    pytest.param(
        b'{"DJANGO_SECRET_KEY":"configuration-secret-sentinel"}',
        id="json-secret-name",
    ),
]


def run_scanner(root: Path, *args: str, failure: str | None = None):
    env = os.environ.copy()
    if failure is not None:
        env["ARTIFACT_SCANNER_INJECT_FAILURE"] = failure
    return subprocess.run(
        [str(SCANNER), *args, str(root)],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )


def write_artifact(root: Path, representation: bytes, container: str) -> Path:
    if container == "plain":
        artifact = root / "artifact.json"
        artifact.write_bytes(representation)
    else:
        artifact = root / "trace.zip"
        with zipfile.ZipFile(
            artifact, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            archive.writestr("0-trace.network", representation)
    return artifact


@pytest.mark.parametrize("container", ["plain", "zip"])
@pytest.mark.parametrize("representation", CREDENTIAL_REPRESENTATIONS)
def test_credential_representation_matrix_is_rejected(
    tmp_path,
    representation,
    container,
):
    write_artifact(tmp_path, representation, container)

    result = run_scanner(tmp_path)

    assert result.returncode == 1
    assert "forbidden byte pattern" in result.stderr


@pytest.mark.parametrize("container", ["plain", "zip"])
def test_real_playwright_trace_json_fixture_is_rejected(tmp_path, container):
    representation = b"\n".join(
        (FIXTURES / name).read_bytes()
        for name in ("playwright-trace.trace", "playwright-trace.network")
    )
    write_artifact(tmp_path, representation, container)

    assert run_scanner(tmp_path).returncode == 1


@pytest.mark.parametrize("failure", ["find", "unzip", "read", "remove"])
def test_operational_failures_are_fail_closed(tmp_path, failure):
    artifact = tmp_path / ("trace.zip" if failure == "unzip" else "report.txt")
    if failure == "unzip":
        with zipfile.ZipFile(artifact, "w") as archive:
            archive.writestr("trace.json", "{}")
    else:
        artifact.write_text(
            "sessionid=unsafe" if failure == "remove" else "safe report",
            encoding="utf-8",
        )

    result = run_scanner(
        tmp_path,
        *(("--remove-unsafe",) if failure == "remove" else ()),
        failure=failure,
    )

    assert result.returncode == 1
    assert "failed closed" in result.stderr
    assert artifact.exists()


def test_corrupt_zip_fails_closed(tmp_path):
    (tmp_path / "trace.zip").write_bytes(b"not a zip")

    assert run_scanner(tmp_path).returncode == 1


def test_plain_artifact_declared_size_is_bounded_before_read(tmp_path, monkeypatch):
    artifact = tmp_path / "report.txt"
    artifact.write_bytes(b"safe-looking")
    monkeypatch.setattr(scanner, "MAX_PLAIN_ARTIFACT_BYTES", 4)
    monkeypatch.setattr(
        Path,
        "open",
        lambda *args, **kwargs: pytest.fail("oversized plain artifact was opened"),
    )

    with pytest.raises(scanner.ScanFailure, match="exceeds the inspection limit"):
        scanner.is_unsafe(artifact)


def test_zip_archive_size_is_bounded_before_open(tmp_path, monkeypatch):
    artifact = tmp_path / "trace.zip"
    artifact.write_bytes(b"not-a-zip")
    monkeypatch.setattr(scanner, "MAX_ZIP_ARCHIVE_BYTES", 4)
    monkeypatch.setattr(
        scanner.zipfile,
        "ZipFile",
        lambda *args, **kwargs: pytest.fail("oversized ZIP was opened"),
    )

    with pytest.raises(scanner.ScanFailure, match="exceeds the inspection limit"):
        scanner.is_unsafe(artifact)


@pytest.mark.parametrize(
    "boundary",
    ["entry-size", "entry-count", "compressed-size", "total-size"],
)
def test_zip_declared_limits_are_checked_before_entry_read(
    tmp_path, monkeypatch, boundary
):
    artifact = tmp_path / "trace.zip"
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.writestr("first.json", "{}")
        if boundary in {"entry-count", "total-size"}:
            archive.writestr("second.json", "{}")

    if boundary == "entry-size":
        monkeypatch.setattr(scanner, "MAX_ZIP_ENTRY_BYTES", 1)
    elif boundary == "entry-count":
        monkeypatch.setattr(scanner, "MAX_ZIP_ENTRIES", 1)
    elif boundary == "compressed-size":
        monkeypatch.setattr(scanner, "MAX_ZIP_COMPRESSED_BYTES", 1)
    else:
        monkeypatch.setattr(scanner, "MAX_ZIP_UNCOMPRESSED_BYTES", 3)
    original_zip_file = zipfile.ZipFile

    class NoEntryReadZipFile(original_zip_file):
        def open(self, *args, **kwargs):
            pytest.fail("ZIP entry was read before declared limits passed")

    monkeypatch.setattr(scanner.zipfile, "ZipFile", NoEntryReadZipFile)

    with pytest.raises(scanner.ScanFailure):
        scanner.is_unsafe(artifact)


def test_encrypted_zip_flag_is_checked_before_entry_read(tmp_path, monkeypatch):
    artifact = tmp_path / "trace.zip"
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.writestr("trace.json", "{}")
    payload = bytearray(artifact.read_bytes())
    local = payload.index(b"PK\x03\x04")
    central = payload.index(b"PK\x01\x02")
    struct.pack_into(
        "<H", payload, local + 6, struct.unpack_from("<H", payload, local + 6)[0] | 1
    )
    struct.pack_into(
        "<H",
        payload,
        central + 8,
        struct.unpack_from("<H", payload, central + 8)[0] | 1,
    )
    artifact.write_bytes(payload)
    original_zip_file = zipfile.ZipFile

    class NoEntryReadZipFile(original_zip_file):
        def open(self, *args, **kwargs):
            pytest.fail("encrypted ZIP entry was read")

    monkeypatch.setattr(scanner.zipfile, "ZipFile", NoEntryReadZipFile)

    with pytest.raises(scanner.ScanFailure, match="encrypted ZIP entry"):
        scanner.is_unsafe(artifact)


def test_corrupt_zip_entry_fails_closed_during_streaming(tmp_path):
    artifact = tmp_path / "trace.zip"
    with zipfile.ZipFile(artifact, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("trace.json", b"safe payload")
    payload = bytearray(artifact.read_bytes())
    local = payload.index(b"PK\x03\x04")
    name_length, extra_length = struct.unpack_from("<HH", payload, local + 26)
    payload[local + 30 + name_length + extra_length] ^= 0xFF
    artifact.write_bytes(payload)

    assert run_scanner(tmp_path).returncode == 1


def test_actual_zip_cumulative_limit_is_enforced(tmp_path, monkeypatch):
    artifact = tmp_path / "trace.zip"
    artifact.write_bytes(b"placeholder")

    class Entry:
        filename = "trace.json"
        file_size = 4
        compress_size = 4
        flag_bits = 0

        @staticmethod
        def is_dir():
            return False

    class OversizedStream:
        chunks = iter((b"safe", b"extra", b""))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, _size):
            return next(self.chunks)

    class Archive:
        def __init__(self, _path):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        @staticmethod
        def infolist():
            return [Entry()]

        @staticmethod
        def open(_entry, _mode):
            return OversizedStream()

    monkeypatch.setattr(scanner.zipfile, "ZipFile", Archive)
    monkeypatch.setattr(scanner, "MAX_ZIP_UNCOMPRESSED_BYTES", 6)

    with pytest.raises(scanner.ScanFailure, match="exceeds the inspection limit"):
        scanner.is_unsafe(artifact)


def test_actual_zip_size_must_match_declared_size(tmp_path, monkeypatch):
    artifact = tmp_path / "trace.zip"
    artifact.write_bytes(b"placeholder")

    class Entry:
        filename = "trace.json"
        file_size = 4
        compress_size = 4
        flag_bits = 0

        @staticmethod
        def is_dir():
            return False

    class ShortStream:
        def __init__(self):
            self.chunks = iter((b"sa", b""))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, _size):
            return next(self.chunks)

    class Archive:
        def __init__(self, _path):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        @staticmethod
        def infolist():
            return [Entry()]

        @staticmethod
        def open(_entry, _mode):
            return ShortStream()

    monkeypatch.setattr(scanner.zipfile, "ZipFile", Archive)

    with pytest.raises(scanner.ScanFailure, match="size disagrees"):
        scanner.is_unsafe(artifact)


def test_forbidden_pattern_split_across_chunks_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(scanner, "READ_CHUNK_BYTES", 16)
    artifact = tmp_path / "report.txt"
    artifact.write_bytes(b"x" * 12 + b"sessionid=credential")

    assert scanner.is_unsafe(artifact)


def test_unknown_plain_artifact_format_fails_closed(tmp_path):
    (tmp_path / "artifact.bin").write_bytes(b"safe-looking")

    assert run_scanner(tmp_path).returncode == 1


@pytest.mark.parametrize(
    "filename",
    [
        "trace-viewer.js",
        "playwright-logo.svg",
        "codicon.ttf",
        "manifest.webmanifest",
    ],
)
def test_recognized_playwright_report_assets_are_scanned(tmp_path, filename):
    artifact = tmp_path / filename
    artifact.write_bytes(b"safe bundled Playwright report asset")
    assert run_scanner(tmp_path).returncode == 0

    artifact.write_bytes(b"Cookie: sessionid=sensitive")
    assert run_scanner(tmp_path).returncode == 1


def test_unsafe_plain_and_zip_artifacts_are_rejected(tmp_path):
    (tmp_path / "report.html").write_text("sessionid=sensitive", encoding="utf-8")
    with zipfile.ZipFile(tmp_path / "trace.zip", "w") as archive:
        archive.writestr("trace.json", "http://django:8000")

    assert run_scanner(tmp_path).returncode == 1


def test_remove_unsafe_deletes_only_unsafe_files_and_safe_set_rechecks(tmp_path):
    safe_text = tmp_path / "safe.json"
    safe_image = tmp_path / "safe.png"
    unsafe_text = tmp_path / "unsafe.html"
    unsafe_zip = tmp_path / "unsafe.zip"
    safe_zip = tmp_path / "safe.zip"
    safe_text.write_text('{"status":"safe"}', encoding="utf-8")
    safe_image.write_bytes(b"\x89PNG\r\nsafe retained bytes")
    unsafe_text.write_text("Set-Cookie: sessionid=secret", encoding="utf-8")
    with zipfile.ZipFile(unsafe_zip, "w") as archive:
        archive.writestr("trace.json", "Authorization: Bearer secret")
    with zipfile.ZipFile(safe_zip, "w") as archive:
        archive.writestr("trace.json", '{"status":"safe"}')

    sanitized = run_scanner(tmp_path, "--remove-unsafe")
    rechecked = run_scanner(tmp_path)

    assert sanitized.returncode == 0
    assert rechecked.returncode == 0
    assert {path.name for path in tmp_path.iterdir()} == {
        "safe.json",
        "safe.png",
        "safe.zip",
    }


def test_failure_artifact_upload_requires_successful_sanitization_and_recheck():
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert workflow.count("steps.artifacts.outcome == 'success'") == 2
    assert workflow.count("steps.e2e.outcome == 'failure'") == 2
    assert workflow.count("Sanitize and recheck retained browser artifacts") == 2
