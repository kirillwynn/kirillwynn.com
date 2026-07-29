import importlib.util
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

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


def test_retained_artifact_scanner_checks_plain_image_metadata_and_zip_entries(
    tmp_path,
):
    scanner = ROOT / "infra" / "tests" / "scan_test_artifacts.sh"
    safe = tmp_path / "safe"
    safe.mkdir()
    (safe / "trace.txt").write_text("deterministic test result")
    assert subprocess.run([scanner, safe], check=False).returncode == 0

    (safe / "failure.png").write_bytes(b"\x89PNG\r\n\x1a\nmetadata=http://django:8000")
    assert subprocess.run([scanner, safe], check=False).returncode != 0
    (safe / "failure.png").unlink()

    with zipfile.ZipFile(safe / "trace.zip", "w") as archive:
        archive.writestr("network.log", "Authorization: Bearer leaked")
    assert subprocess.run([scanner, safe], check=False).returncode != 0
    assert (
        subprocess.run(
            [scanner, "--remove-unsafe", safe],
            check=False,
        ).returncode
        == 0
    )
    assert not (safe / "trace.zip").exists()
    assert subprocess.run([scanner, safe], check=False).returncode == 0


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
    assert roles["django.env"]["DJANGO_ALLOWED_HOSTS"] == (
        "kirillwynn.com,django,127.0.0.1"
    )
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
        ("DJANGO_ALLOWED_HOSTS", "shared.example"),
        ("POSTGRES_USER", "shared"),
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


def test_runtime_environment_accepts_provider_assigned_bucket_name(monkeypatch):
    module = load_script("render_runtime_env.py")
    set_runtime_environment(monkeypatch, "staging")
    monkeypatch.setenv(
        "S3_MEDIA_BUCKET",
        "ae45930d-8f972d69-0fec-4a82-99fc-18aa222510b0",
    )
    roles = module.runtime_values("staging")
    assert (
        roles["django.env"]["S3_MEDIA_BUCKET"]
        == "ae45930d-8f972d69-0fec-4a82-99fc-18aa222510b0"
    )
    assert roles["django.env"]["S3_MEDIA_PREFIX"] == "staging/media"


def test_backup_metadata_is_required_and_checksum_verified(tmp_path):
    module = load_script("verify_backup_metadata.py")
    dump = tmp_path / "backup.dump"
    dump.write_bytes(b"custom-format-placeholder")
    checksum = module.sha256(dump)
    metadata = Path(f"{dump}.json")
    metadata.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "environment": "production",
                "release_sha": "a" * 40,
                "created_at": "20260727T120000Z",
                "sha256": checksum,
                "dump_file": dump.name,
                "backup_kind": "pre-migration",
                "operation_id": "deploy-12345678",
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
    attempt = deploy.index('python3 "$state_script" begin')
    backup = deploy.index('"$repository_root/infra/scripts/backup_postgres.sh"')
    migrate = deploy.index("python manage.py migrate --noinput")
    wait = deploy.index("--wait-timeout")
    healthy = deploy.index("checkpoint application-healthy")
    assert attempt < backup < migrate < wait < healthy
    assert deploy.count("checkpoint migration-started") == 1
    assert deploy.count("checkpoint migration-completed") == 1
    assert "python manage.py migrate --plan" in deploy
    for proof in (
        "verify_application_rollout.sh",
        "migration-started",
        "migration-completed",
        "checkpoint-status",
        "operation_id",
    ):
        assert proof in deploy
    assert "finalize" not in deploy
    health = (SCRIPTS / "verify_application_rollout.sh").read_text()
    for proof in (
        "/api/readiness/",
        "/internal/health",
        "heartbeat.json",
        "WORKER_EGRESS_PROBE_URL",
        ".Config.Image",
    ):
        assert proof in health
    assert "X-Forwarded-Proto" in health
    finalize = (SCRIPTS / "finalize_rollout.sh").read_text()
    assert "record_rollout_state.py" in finalize
    assert "finalize" in finalize
    assert "verify_application_rollout.sh" in finalize
    assert "verify_active_edge.sh" in finalize


def test_first_bootstrap_starts_only_pinned_postgres_then_backup():
    script = (SCRIPTS / "bootstrap_database.sh").read_text()
    assert '-f "$database_compose"' in script
    assert "pull postgres" in script
    assert "up -d --wait" in script
    assert script.index("up -d --wait") < script.index("backup_postgres.sh")
    assert script.index("bootstrap-volume-authorized") < script.index("up -d --wait")
    assert "existing PostgreSQL volume has no durable bootstrap/rollout state" in script
    assert "checkpoint-status" in script
    assert "2>/dev/null" not in script
    assert "docker volume create" in script
    assert "com.kirillwynn.bootstrap-operation-id" in script
    assert "com.kirillwynn.role=postgres-data" in script
    assert "after-volume-authorization" in script
    assert "after-volume-create" in script
    assert "after-container-start" in script
    assert "initial-empty" in script
    for compose_name in ("database.yml", "application.yml"):
        compose = (ROOT / "infra" / "compose" / compose_name).read_text()
        postgres_volume = compose.split("postgres_data:", 1)[1]
        assert "external: true" in postgres_volume
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
        sys.argv.append(f"deploy-12345678-staging-{'a' * 40}")
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


def test_ssh_deployment_persists_bundle_and_uses_cross_workflow_lock():
    script = (SCRIPTS / "ci_ssh_deploy.sh").read_text()
    assert "install_release_bundle.sh" in script
    assert "/srv/kirillwynn/releases/$RELEASE_SHA" in script
    assert "flock -w 900 /srv/kirillwynn/locks/release.lock" in script
    assert script.index("bootstrap_edge_if_absent.sh") < script.index(
        "deploy_environment.sh"
    )
    assert script.index("deploy_environment.sh") < script.index("finalize_rollout.sh")
    assert "A lost SSH response" in script
    assert script.count('"$finalize_command"') == 2
    assert "mark_rollout_failed.sh" in script
    assert "SERVER_REPOSITORY_PATH" not in script
    assert "docker login ghcr.io" in script
    assert "DOCKER_CONFIG='$remote_docker_config'" in script
    assert "--password-stdin" in script
    assert "RESOLUTION_KIND" in script
    assert "FAILED_OPERATION_ID" in script
    assert "resolve_failed_rollout.sh" in script
    assert script.index("resolve_failed_rollout.sh") < script.index(
        "deploy_edge.sh '$durable_release/release-manifest.json'"
    )


def test_staging_dispatch_exposes_only_explicit_reviewed_resolution_inputs():
    workflow = (
        ROOT / ".github" / "workflows" / "staging-release.yml"
    ).read_text()
    assert "resolution_kind:" in workflow
    assert "failed_operation_id:" in workflow
    assert "ordinary" in workflow
    assert "retry" in workflow
    assert "fix-forward" in workflow
    assert "RESOLUTION_KIND: ${{ inputs.resolution_kind }}" in workflow
    assert "FAILED_OPERATION_ID: ${{ inputs.failed_operation_id }}" in workflow


def test_edge_bootstrap_binds_manifest_digest_before_compose_inspection():
    script = (SCRIPTS / "bootstrap_edge_if_absent.sh").read_text()
    bind = script.index("release_image.py")
    inspect = script.index("docker compose")
    deploy = script.index("deploy_edge.sh")
    assert bind < inspect
    assert "export EDGE_IMAGE" in script[bind:inspect]
    assert "reviewed ingress migration is required" in script[inspect:deploy]
    assert "ss -H -ltn" in script[inspect:deploy]


def test_ssh_remote_rollout_failure_records_evidence_and_preserves_exit_status(
    tmp_path,
):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    manifest = tmp_path / "manifest.json"
    release_manifest(manifest)
    runner_temp = tmp_path / "runner"
    runner_temp.mkdir()
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    ssh_log = tmp_path / "ssh.log"
    ssh = binary_dir / "ssh"
    ssh.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$*\" >> '{ssh_log}'\n"
        'case "$*" in\n'
        "  *deploy_environment.sh*) exit 42 ;;\n"
        "  *) exit 0 ;;\n"
        "esac\n"
    )
    ssh.chmod(0o700)
    scp = binary_dir / "scp"
    scp.write_text("#!/bin/sh\nexit 0\n")
    scp.chmod(0o700)
    result = subprocess.run(
        [SCRIPTS / "ci_ssh_deploy.sh", "production", runtime, manifest],
        cwd=ROOT,
        env={
            **os.environ,
            "PATH": f"{binary_dir}:{os.environ['PATH']}",
            "SERVER_HOST": "example.invalid",
            "SERVER_USER": "deploy",
            "SSH_PRIVATE_KEY": "test-key",
            "SERVER_KNOWN_HOSTS": "example.invalid test-key",
            "RELEASE_SHA": "a" * 40,
            "GITHUB_RUN_ID": "12345678",
            "GITHUB_RUN_ATTEMPT": "1",
            "RUNNER_TEMP": str(runner_temp),
            "GHCR_USERNAME": "kirillwynn",
            "GHCR_TOKEN": "test-token",
        },
        text=True,
        capture_output=True,
    )
    assert result.returncode == 42
    log = ssh_log.read_text()
    assert "mark_rollout_failed.sh" in log
    assert "remote-rollout" in log
    assert "flock -w 900 /srv/kirillwynn/locks/release.lock" in log


def test_rollback_uses_previous_durable_manifest_without_migration():
    script = (SCRIPTS / "rollback_environment.sh").read_text()
    assert "previous.application.manifest_path" in script
    assert "candidate.application.manifest_path" in script
    assert "backup_postgres.sh" in script
    assert "--wait-timeout" in script
    assert "record_rollout_state.py" in script
    assert "advance_edge_rollout.sh" in script
    assert "manage.py migrate" not in script
    assert "git " not in script


def test_recovery_restores_failed_base_application_and_production_edge():
    script = (SCRIPTS / "recover_failed_rollout.sh").read_text()
    assert "begin-recovery" in script
    assert "candidate.application.runtime_directory" in script
    assert "candidate.application.manifest_path" in script
    assert "recovery-backup-completed" in script
    assert "verify_application_rollout.sh" in script
    assert "advance_edge_rollout.sh" in script
    assert "manage.py migrate" not in script
    edge = (SCRIPTS / "advance_edge_rollout.sh").read_text()
    assert "deploy_edge.sh" in edge
    assert "edge-healthy" in edge
    assert "pending-public-smoke" in edge


def test_reviewed_retry_and_fix_forward_use_separate_resolution_entrypoint():
    script = (SCRIPTS / "resolve_failed_rollout.sh").read_text()
    assert "retry|fix-forward" in script
    assert "<deployment-sequence>" in script
    assert "deploy_environment.sh" in script
    assert "advance_edge_rollout.sh" in script
    deploy = (SCRIPTS / "deploy_environment.sh").read_text()
    assert "begin-resolution" in deploy
    assert "resolution_deploy_sequence" in deploy
    assert "recovery-backup-started" in deploy
    assert "initial-empty" not in script


def test_minio_initialization_has_bounded_readiness_retry():
    compose = (ROOT / "infra" / "compose" / "integration.yml").read_text()
    assert "mc ready integration" in compose
    assert 'if [ "$$attempts" -ge 60 ]' in compose


def test_minio_fixture_uses_the_django_s3_credentials():
    compose = (ROOT / "infra" / "compose" / "integration.yml").read_text()
    django_environment = (
        ROOT / "infra" / "tests" / "integration-env" / "django.env"
    ).read_text()
    s3_secret = next(
        line.split("=", 1)[1]
        for line in django_environment.splitlines()
        if line.startswith("S3_MEDIA_SECRET_ACCESS_KEY=")
    )

    assert f"MINIO_ROOT_PASSWORD: {s3_secret}" in compose
    assert f"minio:9000 integration {s3_secret}" in compose


def test_deploy_workflows_map_github_oauth_from_allowed_secret_names():
    for workflow_name in ("build.yml", "deploy-production.yml"):
        workflow = (ROOT / ".github" / "workflows" / workflow_name).read_text()
        assert (
            "GITHUB_OAUTH_CLIENT_ID: "
            "${{ secrets.OAUTH_GITHUB_CLIENT_ID }}" in workflow
        )
        assert (
            "GITHUB_OAUTH_CLIENT_SECRET: "
            "${{ secrets.OAUTH_GITHUB_CLIENT_SECRET }}" in workflow
        )
        assert "secrets.GITHUB_OAUTH_CLIENT_" not in workflow


def test_rebuild_branch_calls_staging_release_only_from_push_ci():
    ci_workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "github.event_name == 'push'" in ci_workflow
    assert "github.ref == 'refs/heads/rewrite/wagtail-next'" in ci_workflow
    assert "uses: ./.github/workflows/staging-release.yml" in ci_workflow
    assert "secrets: inherit" in ci_workflow

    staging = (
        ROOT / ".github" / "workflows" / "staging-release.yml"
    ).read_text()
    assert "workflow_call:" in staging
    assert "needs: ci-required" in ci_workflow
    assert "needs:\n      - release-manifest\n      - server-preflight" in staging
    assert "if: vars.STAGING_DEPLOY_ENABLED == 'true'" in staging
    assert "GHCR_TOKEN: ${{ github.token }}" in staging

    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text()
    assert "github.event.workflow_run.event == 'push'" in workflow
    assert "GHCR_TOKEN: ${{ github.token }}" in workflow
    production = (
        ROOT / ".github" / "workflows" / "deploy-production.yml"
    ).read_text()
    assert "gh run list --workflow build.yml --branch main" in production


def test_staging_preflight_does_not_activate_rollout():
    workflow = (
        ROOT / ".github" / "workflows" / "staging-release.yml"
    ).read_text()
    script = (SCRIPTS / "ci_ssh_preflight.sh").read_text()
    assert "environment: staging" in workflow
    assert "packages: read" in workflow
    assert "docker login ghcr.io" in script
    assert "require_compose_version.sh" in script
    assert "/srv/kirillwynn/state/staging" in script
    assert "/srv/kirillwynn/backups/staging" in script
    assert "kirillwynn-staging-postgres" in script
    assert "/etc/letsencrypt/live/staging.kirillwynn.com/fullchain.pem" in script
    assert "/etc/letsencrypt/live/kirillwynn.com/fullchain.pem" in script
    assert "certbot certonly" in script
    assert "--cert-name staging.kirillwynn.com" in script
    assert "ports 80/443 are in use" in script
    assert "openssl passwd -apr1 -stdin" in script
    assert "install -m 0600" in script
    assert "test ! -d /etc/nginx/.htpasswd" in script
    assert "test -f /etc/nginx/.htpasswd" in script
    assert "/srv/kirillwynn/runtime/edge.env" in script
    assert "edge_runtime=ready" in script
    assert "host_http_listeners" in script
    assert "com.docker.compose.project=kirillwynn-edge" in script
    assert "com.docker.compose.service=edge" in script
    assert "reviewed ingress migration is required" in script
    assert "deploy_environment.sh" not in script


def test_edge_gates_require_a_regular_staging_htpasswd_mount():
    candidate = (SCRIPTS / "verify_edge_candidate.sh").read_text()
    assert "STAGING_HTPASSWD_FILE" in candidate
    assert 'test -f "$staging_htpasswd_file"' in candidate
    assert 'test -s "$staging_htpasswd_file"' in candidate

    active = (SCRIPTS / "verify_active_edge.sh").read_text()
    assert "test -f /etc/nginx/auth/staging.htpasswd" in active
    assert "test -s /etc/nginx/auth/staging.htpasswd" in active

    deploy = (SCRIPTS / "deploy_edge.sh").read_text()
    assert "--force-recreate" in deploy


def test_staging_runtime_preflight_runs_before_activation_flag():
    workflow = (
        ROOT / ".github" / "workflows" / "staging-release.yml"
    ).read_text()
    render = workflow.index("Render bounded runtime environment")
    deploy = workflow.index("Deploy release digests")
    assert render < deploy
    assert "if: vars.STAGING_DEPLOY_ENABLED == 'true'" in workflow[deploy:]
    assert "if: vars.STAGING_DEPLOY_ENABLED != 'true'" in workflow
