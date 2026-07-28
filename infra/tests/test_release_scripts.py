import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "infra" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load_script(name):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def runtime_environment(environment):
    module = load_script("render_runtime_env.py")
    host = "staging.kirillwynn.com" if environment == "staging" else "kirillwynn.com"
    values = {name: f"value-for-{name.lower()}" for name in module.REQUIRED_INPUTS}
    values.update(
        {
            "RELEASE_SHA": "a" * 40,
            "DEPLOY_SEQUENCE": "1234",
            "POSTGRES_IMAGE": f"postgres@sha256:{'1' * 64}",
            "DJANGO_IMAGE": f"django@sha256:{'2' * 64}",
            "NEXT_IMAGE": f"next@sha256:{'3' * 64}",
            "DJANGO_ALLOWED_HOSTS": host,
            "DJANGO_CSRF_TRUSTED_ORIGINS": f"https://{host}",
            "PUBLIC_SITE_URL": f"https://{host}",
            "WAGTAIL_ADMIN_BASE_URL": f"https://{host}/cms",
            "FRONTEND_PREVIEW_URL": f"https://{host}/api/draft",
            "REVALIDATION_URL": "http://next:3000/api/revalidate",
            "POSTGRES_DB": f"kirillwynn_{environment}",
            "POSTGRES_USER": f"kirillwynn_{environment}",
            "S3_MEDIA_PREFIX": f"{environment}/media",
            "S3_MEDIA_BUCKET": f"kirillwynn-{environment}-media",
            "S3_MEDIA_ENDPOINT_URL": "https://s3.example.invalid",
            "S3_MEDIA_PUBLIC_ORIGIN": "https://media.example.invalid",
            "EMAIL_PROVIDER_ADAPTER": (
                "apps.subscriptions.providers.resend.ResendEmailProvider"
            ),
            "EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE": (f"resend/{environment}/account"),
            "EMAIL_FROM_ADDRESS": "Test <test@example.com>",
            "RESEND_API_URL": "https://api.resend.com/emails",
            "WORKER_EGRESS_PROBE_URL": "https://api.resend.com",
        }
    )
    return values


def set_runtime_environment(monkeypatch, environment):
    for name, value in runtime_environment(environment).items():
        monkeypatch.setenv(name, value)


def release_manifest(path, sha="a" * 40):
    payload = {
        "schema_version": 1,
        "release_sha": sha,
        "repository": "kirillwynn/kirillwynn.com",
        "built_at": "2026-07-27T00:00:00Z",
        "images": {
            "django": f"ghcr.io/kirillwynn/django@sha256:{'1' * 64}",
            "next": f"ghcr.io/kirillwynn/next@sha256:{'2' * 64}",
            "edge": f"ghcr.io/kirillwynn/edge@sha256:{'3' * 64}",
        },
    }
    path.write_text(json.dumps(payload))
    return payload


def test_release_manifest_requires_three_real_digests(tmp_path):
    module = load_script("validate_release_manifest.py")
    manifest = tmp_path / "release.json"
    release_manifest(manifest)
    assert module.load_manifest(manifest)["release_sha"] == "a" * 40

    data = json.loads(manifest.read_text())
    data["images"]["next"] = "ghcr.io/kirillwynn/next:latest"
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="not pinned"):
        module.load_manifest(manifest)

    data["images"]["next"] = f"ghcr.io/kirillwynn/next@sha256:{'0' * 64}"
    manifest.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="forbidden placeholder"):
        module.load_manifest(manifest)


def test_runtime_roles_are_minimal_and_preserve_raw_bytes(monkeypatch):
    module = load_script("render_runtime_env.py")
    set_runtime_environment(monkeypatch, "production")
    sentinel = r"""sentinel $ ${UNCHANGED} # "quotes" 'single' \ spaces """
    monkeypatch.setenv("DJANGO_SECRET_KEY", sentinel)
    monkeypatch.setenv("POSTGRES_PASSWORD", sentinel)
    monkeypatch.setenv("REVALIDATION_SECRET", sentinel)

    roles = module.runtime_values("production")
    assert roles["django.env"]["DJANGO_SECRET_KEY"] == sentinel
    assert roles["postgres.env"]["POSTGRES_PASSWORD"] == sentinel
    assert roles["next.env"]["REVALIDATION_SECRET"] == sentinel
    assert set(roles["postgres.env"]) == module.POSTGRES_FIELDS
    assert set(roles["next.env"]) == module.NEXT_FIELDS
    assert not (
        set(roles["next.env"])
        & {
            "POSTGRES_PASSWORD",
            "DJANGO_SECRET_KEY",
            "S3_MEDIA_SECRET_ACCESS_KEY",
            "GOOGLE_OAUTH_CLIENT_SECRET",
            "GITHUB_OAUTH_CLIENT_SECRET",
            "RESEND_API_KEY",
            "RESEND_WEBHOOK_SECRET",
        }
    )
    assert "GOOGLE_OAUTH_CLIENT_SECRET" not in roles["worker.env"]
    assert "RESEND_WEBHOOK_SECRET" not in roles["worker.env"]
    assert "RESEND_API_KEY" not in roles["django.env"]


def test_runtime_files_round_trip_and_reject_shape_errors(monkeypatch, tmp_path):
    render = load_script("render_runtime_env.py")
    validator = load_script("validate_runtime_env_file.py")
    set_runtime_environment(monkeypatch, "staging")
    sentinel = r"""$ ${literal} # "quotes" 'single' \ trailing space """
    monkeypatch.setenv("POSTGRES_PASSWORD", sentinel)
    roles = render.runtime_values("staging")
    source = tmp_path / "source"
    for filename, role_values in roles.items():
        render.write_raw_environment(source / filename, role_values)
    parsed = validator.validated_directory("staging", source)
    assert parsed["postgres.env"]["POSTGRES_PASSWORD"] == sentinel

    with (source / "next.env").open("a") as handle:
        handle.write("RESEND_API_KEY=leak\n")
    with pytest.raises(ValueError, match="unexpected"):
        validator.validated_directory("staging", source)

    (source / "next.env").write_text("PUBLIC_SITE_URL=https://staging.kirillwynn.com\n")
    with pytest.raises(ValueError, match="missing"):
        validator.validated_directory("staging", source)


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("first\nsecond", "single-line"),
        ("first\rsecond", "single-line"),
        ("first\0second", "NUL-free"),
        ("x" * 8193, "exceeds"),
    ],
)
def test_runtime_values_reject_multiline_nul_and_oversized(value, message):
    module = load_script("render_runtime_env.py")
    with pytest.raises(ValueError, match=message):
        module.validate_value("SENTINEL", value)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("POSTGRES_USER", "shared"),
        ("S3_MEDIA_BUCKET", "shared-media"),
        ("EMAIL_PROVIDER_IDEMPOTENCY_NAMESPACE", "resend/shared/account"),
        ("POSTGRES_IMAGE", "postgres:17-alpine"),
        ("DJANGO_IMAGE", f"django@sha256:{'0' * 64}"),
    ],
)
def test_runtime_environment_rejects_shared_or_mutable_boundaries(
    monkeypatch, name, value
):
    module = load_script("render_runtime_env.py")
    set_runtime_environment(monkeypatch, "production")
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match=name):
        module.runtime_values("production")


def test_backup_metadata_is_required_and_checksum_verified(tmp_path):
    module = load_script("verify_backup_metadata.py")
    dump = tmp_path / "backup.dump"
    dump.write_bytes(b"custom-format-placeholder")
    checksum = module.sha256(dump)
    metadata = Path(f"{dump}.json")
    metadata.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "environment": "production",
                "release_sha": "a" * 40,
                "created_at": "20260727T120000Z",
                "sha256": checksum,
                "dump_file": dump.name,
            }
        )
    )
    assert module.verify(dump, metadata, "production")["sha256"] == checksum
    dump.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        module.verify(dump, metadata, "production")
    metadata.unlink()
    result = subprocess.run(
        [sys.executable, SCRIPTS / "verify_backup_metadata.py", "production", dump],
        text=True,
        capture_output=True,
    )
    assert result.returncode == 2
    assert "metadata is missing" in result.stderr


def test_database_operations_do_not_load_application_images():
    database_compose = (ROOT / "infra" / "compose" / "database.yml").read_text()
    for forbidden in ("DJANGO_IMAGE", "NEXT_IMAGE", "django:", "next:", "worker:"):
        assert forbidden not in database_compose
    for script_name in ("backup_postgres.sh", "restore_postgres.sh"):
        script = (SCRIPTS / script_name).read_text()
        assert "infra/compose/database.yml" in script
        assert "infra/compose/application.yml" not in script


@pytest.mark.parametrize(
    ("version", "expected"),
    [("2.30.0", 0), ("v2.40.1", 0), ("2.29.9", 2), ("invalid", 2)],
)
def test_minimum_compose_version_is_enforced(tmp_path, version, expected):
    docker = tmp_path / "docker"
    docker.write_text(f"#!/bin/sh\nprintf '%s\\n' '{version}'\n")
    docker.chmod(0o700)
    result = subprocess.run(
        [SCRIPTS / "require_compose_version.sh"],
        env={"PATH": f"{tmp_path}:/usr/bin:/bin"},
        capture_output=True,
        text=True,
    )
    assert result.returncode == expected


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_committed_compose_control_paths_resolve_and_use_nonzero_digests(environment):
    env_values = load_script("env_value.py").values(
        ROOT / "infra" / "env" / f"{environment}.control.env.example"
    )
    compose_directory = ROOT / "infra" / "compose"
    for name in (
        "POSTGRES_ENV_FILE",
        "DJANGO_ENV_FILE",
        "WORKER_ENV_FILE",
        "NEXT_ENV_FILE",
    ):
        assert (compose_directory / env_values[name]).resolve().is_file()
    for name in ("POSTGRES_IMAGE", "DJANGO_IMAGE", "NEXT_IMAGE"):
        digest = env_values[name].rsplit("sha256:", 1)[-1]
        assert len(digest) == 64
        assert digest != "0" * 64


def test_restore_authenticates_sidecar_before_createdb():
    script = (SCRIPTS / "restore_postgres.sh").read_text()
    assert script.index("verify_backup_metadata.py") < script.index(
        "exec -T postgres createdb"
    )
    assert "RESTORE production $target_database" in script
    assert "restore_*" in script


def test_rollout_order_health_gates_and_active_state_policy():
    deploy = (SCRIPTS / "deploy_environment.sh").read_text()
    backup = deploy.index("backup_postgres.sh")
    migrate = deploy.index("python manage.py migrate --noinput")
    wait = deploy.index("--wait-timeout")
    pending = deploy.index("record_rollout_state.py")
    assert backup < migrate < wait < pending
    assert deploy.count("python manage.py migrate --noinput") == 1
    for proof in (
        "/api/readiness/",
        "/internal/health",
        "heartbeat.json",
        "WORKER_EGRESS_PROBE_URL",
        ".Config.Image",
    ):
        assert proof in deploy
    assert "finalize" not in deploy
    finalize = (SCRIPTS / "finalize_rollout.sh").read_text()
    assert "record_rollout_state.py" in finalize
    assert "finalize" in finalize


def test_first_bootstrap_starts_only_pinned_postgres_then_backup():
    script = (SCRIPTS / "bootstrap_database.sh").read_text()
    assert '-f "$repository_root/infra/compose/database.yml"' in script
    assert "pull postgres" in script
    assert "up -d --wait" in script
    assert script.index("up -d --wait") < script.index("backup_postgres.sh")
    for forbidden in ("django", "next", "worker", "application.yml"):
        assert forbidden not in script


def test_staging_attestation_requires_every_gate_and_exact_images(tmp_path):
    manifest = tmp_path / "manifest.json"
    release_manifest(manifest)
    attestation = tmp_path / "attestation.json"
    create = load_script("create_attestation.py")
    old_argv = sys.argv
    try:
        sys.argv = ["create_attestation.py", str(manifest), str(attestation)]
        create.main()
    finally:
        sys.argv = old_argv
    result = subprocess.run(
        [
            sys.executable,
            SCRIPTS / "validate_attestation.py",
            attestation,
            manifest,
        ]
    )
    assert result.returncode == 0
    payload = json.loads(attestation.read_text())
    payload["checks"]["worker_egress"] = False
    attestation.write_text(json.dumps(payload))
    result = subprocess.run(
        [
            sys.executable,
            SCRIPTS / "validate_attestation.py",
            attestation,
            manifest,
        ]
    )
    assert result.returncode == 2


def test_pending_to_active_state_keeps_previous_manifest(tmp_path):
    module = load_script("record_rollout_state.py")
    state = tmp_path / "state"
    manifest_one = tmp_path / "one.json"
    release_manifest(manifest_one, "a" * 40)
    args = SimpleNamespace(
        state_directory=state,
        environment="staging",
        release_sha="a" * 40,
        deployment_sequence="1",
        runtime_directory=tmp_path / "runtime-a",
        manifest=manifest_one,
        operation="deploy",
    )
    module.pending(args)
    module.finalize(args)
    assert (
        json.loads((state / "staging" / "active-release.json").read_text())["status"]
        == "active"
    )

    manifest_two = tmp_path / "two.json"
    release_manifest(manifest_two, "b" * 40)
    args.release_sha = "b" * 40
    args.deployment_sequence = "2"
    args.runtime_directory = tmp_path / "runtime-b"
    args.manifest = manifest_two
    module.pending(args)
    module.finalize(args)
    assert (
        json.loads((state / "staging" / "previous-manifest.json").read_text())[
            "release_sha"
        ]
        == "a" * 40
    )


def test_ssh_deployment_persists_bundle_and_uses_cross_workflow_lock():
    script = (SCRIPTS / "ci_ssh_deploy.sh").read_text()
    assert "install_release_bundle.sh" in script
    assert "/srv/kirillwynn/releases/$RELEASE_SHA" in script
    assert "flock -w 900 /srv/kirillwynn/locks/release.lock" in script
    assert script.index("deploy_environment.sh") < script.index("finalize_rollout.sh")
    assert "SERVER_REPOSITORY_PATH" not in script


def test_rollback_uses_previous_durable_manifest_without_migration():
    script = (SCRIPTS / "rollback_environment.sh").read_text()
    assert "previous-manifest.json" in script
    assert "/srv/kirillwynn/releases" in script
    assert "backup_postgres.sh" in script
    assert "--wait-timeout" in script
    assert "record_rollout_state.py" in script
    assert "manage.py migrate" not in script
    assert "git " not in script
