import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_script(name):
    path = ROOT / "infra" / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def runtime_environment(environment):
    host = "staging.kirillwynn.com" if environment == "staging" else "kirillwynn.com"
    values = {
        name: f"value-for-{name.lower()}"
        for name in load_script("render_runtime_env.py").REQUIRED
    }
    values.update(
        {
            "RELEASE_SHA": "a" * 40,
            "DJANGO_ALLOWED_HOSTS": host,
            "POSTGRES_DB": f"kirillwynn_{environment}",
            "POSTGRES_USER": f"kirillwynn_{environment}",
            "S3_MEDIA_PREFIX": f"{environment}/media",
            "S3_MEDIA_BUCKET": f"kirillwynn-{environment}-media",
            "EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE": f"resend/{environment}/account",
            "EDGE_NETWORK": f"kirillwynn-{environment}-edge",
            "DJANGO_EDGE_ALIAS": f"{environment}-django",
            "NEXT_EDGE_ALIAS": f"{environment}-next",
            "RUNTIME_ENV_FILE": f"/srv/kirillwynn/runtime/{environment}.env",
            "POSTGRES_IMAGE": f"postgres@sha256:{'1' * 64}",
        }
    )
    return values


def test_release_manifest_requires_three_real_digests(tmp_path):
    module = load_script("validate_release_manifest.py")
    manifest = tmp_path / "release.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "release_sha": "a" * 40,
                "repository": "kirillwynn/kirillwynn.com",
                "built_at": "2026-07-27T00:00:00Z",
                "images": {
                    name: f"ghcr.io/kirillwynn/{name}@sha256:{index * 64}"
                    for name, index in (("django", "1"), ("next", "2"), ("edge", "3"))
                },
            }
        )
    )

    assert module.load_manifest(manifest)["release_sha"] == "a" * 40

    data = json.loads(manifest.read_text())
    data["images"]["next"] = "ghcr.io/kirillwynn/next:latest"
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="not pinned"):
        module.load_manifest(manifest)


def test_runtime_environment_rejects_cross_environment_names(monkeypatch):
    module = load_script("render_runtime_env.py")
    for name, value in runtime_environment("staging").items():
        monkeypatch.setenv(name, value)
    assert module.validated_values("staging")["POSTGRES_DB"] == "kirillwynn_staging"

    monkeypatch.setenv("S3_MEDIA_PREFIX", "production/media")
    with pytest.raises(ValueError, match="S3_MEDIA_PREFIX"):
        module.validated_values("staging")


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("POSTGRES_USER", "shared"),
        ("S3_MEDIA_BUCKET", "shared-media"),
        ("EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE", "resend/shared/account"),
        ("EDGE_NETWORK", "shared-edge"),
        ("POSTGRES_IMAGE", "postgres:17-alpine"),
    ],
)
def test_runtime_environment_rejects_shared_or_mutable_boundaries(
    monkeypatch, name, value
):
    module = load_script("render_runtime_env.py")
    for environment_name, environment_value in runtime_environment(
        "production"
    ).items():
        monkeypatch.setenv(environment_name, environment_value)
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError, match=name):
        module.validated_values("production")


def test_runtime_environment_rejects_multiline_values(monkeypatch):
    module = load_script("render_runtime_env.py")
    for name, value in runtime_environment("production").items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("DJANGO_SECRET_KEY", "first\nsecond")

    with pytest.raises(ValueError, match="single-line"):
        module.validated_values("production")


def test_ssh_deployment_uses_release_bundle_not_server_checkout():
    script = (ROOT / "infra" / "scripts" / "ci_ssh_deploy.sh").read_text()

    assert "tar -czf" in script
    assert "infra/compose infra/scripts" in script
    assert "SERVER_REPOSITORY_PATH" not in script
    assert "runtime.env" in script
    assert "release-manifest.json" in script
