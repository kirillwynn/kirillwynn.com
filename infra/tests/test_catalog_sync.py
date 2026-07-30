import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "infra" / "scripts"


def load_script(name):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_tar_bytes(archive, name, body=b"fixture"):
    member = tarfile.TarInfo(name)
    member.size = len(body)
    archive.addfile(member, io.BytesIO(body))


def create_transfer(path, *, object_name=None, object_kind="file"):
    object_name = object_name or (
        f"objects/reactions/test-reaction/{'a' * 64}/asset.webp"
    )
    with tarfile.open(path, "w:gz") as archive:
        add_tar_bytes(archive, "reaction-catalog-attestation.json", b"{}")
        if object_kind == "file":
            add_tar_bytes(archive, object_name)
        else:
            member = tarfile.TarInfo(object_name)
            member.type = tarfile.SYMTYPE
            member.linkname = "reaction-catalog-attestation.json"
            archive.addfile(member)


def test_catalog_transfer_extractor_accepts_only_bounded_explicit_objects(tmp_path):
    module = load_script("extract_catalog_transfer.py")
    archive = tmp_path / "catalog.tar.gz"
    output = tmp_path / "output"
    create_transfer(archive)

    module.extract(archive, output)

    assert (output / "reaction-catalog-attestation.json").read_bytes() == b"{}"
    assert (
        output / "objects" / "reactions" / "test-reaction" / ("a" * 64) / "asset.webp"
    ).read_bytes() == b"fixture"


@pytest.mark.parametrize(
    ("object_name", "object_kind", "message"),
    (
        ("../escaped.webp", "file", "unsafe archive member"),
        (
            f"objects/reactions/test/{'a' * 64}/unexpected.exe",
            "file",
            "unexpected catalog transfer member",
        ),
        (
            f"objects/reactions/test/{'a' * 64}/asset.webp",
            "symlink",
            "non-regular archive member",
        ),
        (
            f"objects//reactions/test/{'a' * 64}/asset.webp",
            "file",
            "unsafe archive member",
        ),
    ),
)
def test_catalog_transfer_extractor_rejects_unsafe_members(
    tmp_path,
    object_name,
    object_kind,
    message,
):
    module = load_script("extract_catalog_transfer.py")
    archive = tmp_path / "catalog.tar.gz"
    create_transfer(
        archive,
        object_name=object_name,
        object_kind=object_kind,
    )

    with pytest.raises(ValueError, match=message):
        module.extract(archive, tmp_path / "output")


def catalog_result(*, activated, created):
    return {
        "environment": "staging",
        "prefix": "staging/media",
        "manifest_sha256": "b" * 64,
        "attestation_sha256": "c" * 64,
        "items": 228,
        "objects": 276,
        "created": created,
        "updated": 0,
        "activated": activated,
    }


def test_catalog_sync_attestation_requires_upload_activation_and_idempotence(
    tmp_path,
    monkeypatch,
):
    module = load_script("create_catalog_sync_attestation.py")
    upload = tmp_path / "upload.txt"
    activation = tmp_path / "activation.txt"
    idempotent = tmp_path / "idempotent.txt"
    output = tmp_path / "attestation.json"
    upload.write_text(f"command log\n{catalog_result(activated=False, created=0)!r}\n")
    activation.write_text(f"{catalog_result(activated=True, created=228)!r}\n")
    idempotent.write_text(f"{catalog_result(activated=True, created=0)!r}\n")
    monkeypatch.setattr(
        "sys.argv",
        [
            "create_catalog_sync_attestation.py",
            "--upload",
            str(upload),
            "--activate",
            str(activation),
            "--idempotent",
            str(idempotent),
            "--output",
            str(output),
            "--release-sha",
            "a" * 40,
            "--run-id",
            "1234",
            "--archive-sha256",
            "d" * 64,
            "--manifest-sha256",
            "b" * 64,
            "--catalog-attestation-sha256",
            "c" * 64,
        ],
    )

    module.main()

    payload = json.loads(output.read_text())
    assert payload["operation_id"] == f"catalog-sync-1234-staging-{'a' * 40}"
    assert all(payload["checks"].values())
    assert payload["results"]["activation"]["created"] == 228


def test_catalog_sync_attestation_rejects_non_idempotent_repeat(tmp_path):
    module = load_script("create_catalog_sync_attestation.py")
    result = tmp_path / "result.txt"
    result.write_text(f"{catalog_result(activated=True, created=1)!r}\n")

    value = module.parse_result(result)
    with pytest.raises(ValueError, match="unexpected catalog sync result"):
        module.validate_result(
            value,
            manifest_sha256="b" * 64,
            attestation_sha256="c" * 64,
            activated=True,
            created=0,
        )


def test_catalog_sync_workflow_is_staging_only_and_fail_closed():
    workflow = (
        ROOT / ".github" / "workflows" / "staging-reaction-catalog.yml"
    ).read_text()
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    remote = (SCRIPTS / "run_catalog_sync_remote.sh").read_text()
    transport = (SCRIPTS / "ci_ssh_catalog_sync.sh").read_text()

    assert "environment: staging" in workflow
    assert 'test "$DEPLOY_GATE" = false' in workflow
    assert "refs/heads/rewrite/wagtail-next" in workflow
    assert "releases/assets/$CATALOG_ASSET_ID" in workflow
    assert "extract_catalog_transfer.py" in workflow
    assert "contents: read" in workflow
    assert "STAGING_REACTION_CATALOG_SYNC_ENABLED == 'true'" in ci
    assert "needs: ci-required" in ci
    assert "uses: ./.github/workflows/staging-reaction-catalog.yml" in ci
    assert "production" not in workflow.lower()
    assert "flock -w 900 9" in remote
    assert 'find "$input_dir" -type d -exec chmod 0755 {} +' in remote
    assert 'find "$input_dir" -type f -exec chmod 0444 {} +' in remote
    assert remote.index("run_sync upload.txt") < remote.index(
        "run_sync activate.txt --activate"
    )
    assert remote.index("run_sync activate.txt --activate") < remote.index(
        "run_sync idempotent.txt --activate"
    )
    assert "EXPECTED_ACTIVE_RELEASE_SHA" in transport
    assert "active.application.release_sha" in remote
    assert "rm -rf -- '$remote_dir'" in transport
