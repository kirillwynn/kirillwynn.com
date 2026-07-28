from __future__ import annotations

import os
import subprocess
import zipfile
from pathlib import Path

import pytest

SCANNER = Path(__file__).with_name("scan_test_artifacts.sh")


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


def test_unknown_plain_artifact_format_fails_closed(tmp_path):
    (tmp_path / "artifact.bin").write_bytes(b"safe-looking")

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
