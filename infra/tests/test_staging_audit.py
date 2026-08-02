import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "infra" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load_compare_module():
    path = SCRIPTS / "compare_staging_data_audits.py"
    spec = importlib.util.spec_from_file_location("compare_staging_data_audits", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_release_module():
    path = SCRIPTS / "staging_release_state_audit.py"
    spec = importlib.util.spec_from_file_location("staging_release_state_audit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report():
    return {
        "schema": "stage18-staging-data-audit/v1",
        "migrations": {"applied": 42, "leaves": ["users.0002"]},
        "identity": {
            "users": 3,
            "verified_emails": 2,
            "social_tokens": 0,
        },
        "posts": {
            "total": 13,
            "ownerless": 0,
            "public_author_serializer_mismatches": 0,
        },
        "discussions": {"comments": 4, "post_reactions": 6},
        "reaction_catalog": {
            "items": 228,
            "manifest_hash_matches": True,
            "rights_statuses": {"staging-only/unverified": 228},
        },
        "subscriptions": {"outbox": {"delivered": 1}},
        "auth_email": {"outbox": {"delivered": 2}},
        "revalidation": {"delivered": 13},
        "violations": {},
    }


def test_data_audit_is_read_only_and_does_not_emit_record_values():
    script = (SCRIPTS / "staging_data_audit.py").read_text()
    assert "SET TRANSACTION READ ONLY" in script
    assert "SocialToken.objects.count()" in script
    assert "staging-only/unverified" in script
    assert "EXPECTED_CATALOG_ITEMS = 228" in script
    assert 'values_list("email"' not in script
    assert 'values_list("nickname"' not in script
    assert "snapshot_recipient_email" not in script
    assert "provider_message_id" not in script

    performance = (SCRIPTS / "staging_performance_audit.py").read_text()
    assert "SET TRANSACTION READ ONLY" in performance
    for probe in (
        "feed_page_1",
        "feed_page_2",
        "unicode_search",
        "tag_filter",
        "post_detail",
        "comments",
        "post_reactions_batch",
    ):
        assert probe in performance
    assert "statistics.median" in performance


def test_comparison_requires_equal_values_when_active_snapshot_is_stable():
    module = load_compare_module()
    before = report()
    restored = report()
    after = report()
    restored["posts"]["total"] = 12

    result = module.compare(before, restored, after)

    assert result["mismatches"] == {
        "posts.total": {"before": 13, "restored": 12, "after": 13}
    }


def test_comparison_reports_concurrent_user_activity_without_false_failure():
    module = load_compare_module()
    before = report()
    restored = report()
    after = report()
    restored["discussions"]["comments"] = 5
    after["discussions"]["comments"] = 5

    result = module.compare(before, restored, after)

    assert result["mismatches"] == {}
    assert result["concurrent_changes"]["discussions.comments"] == {
        "before": 4,
        "restored": 5,
        "after": 5,
    }


def test_comparison_fails_closed_for_catalog_or_reported_invariant_drift(tmp_path):
    module = load_compare_module()
    before = report()
    restored = report()
    after = report()
    after["reaction_catalog"]["items"] = 227
    restored["violations"] = {"social_tokens": 1}

    result = module.compare(before, restored, after)

    assert "reaction_catalog.items" in result["mismatches"]
    assert result["violation_reports"] == {"restored": {"social_tokens": 1}}

    path = tmp_path / "report.json"
    path.write_text(json.dumps(report()))
    assert module.load_report(path)["schema"] == "stage18-staging-data-audit/v1"


def test_release_state_audit_binds_immutable_paths_and_shared_edge(tmp_path):
    module = load_release_module()
    release_sha = "a" * 40
    release_root = tmp_path / "releases"
    runtime_root = tmp_path / "runtime"
    release_path = release_root / release_sha
    runtime_path = runtime_root / release_sha / "staging"
    release_path.mkdir(parents=True)
    runtime_path.mkdir(parents=True)
    manifest_path = release_path / "release-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "release_sha": release_sha,
                "repository": "kirillwynn/kirillwynn.com",
                "built_at": "2026-08-01T00:00:00+00:00",
                "images": {
                    "django": f"django@sha256:{'1' * 64}",
                    "next": f"next@sha256:{'2' * 64}",
                    "edge": f"edge@sha256:{'3' * 64}",
                },
            }
        )
    )
    reference = module.record_rollout_state.release_reference(
        manifest_path,
        runtime_path,
    )
    state = {
        "schema_version": 3,
        "revision": 7,
        "active": {
            "application": reference,
            "edge": None,
            "deployment_sequence": 123,
            "activated_by_operation_id": "deploy-123-staging-aaaaaaaa",
        },
        "previous": None,
        "database": {
            "lifecycle_state": "ready",
            "volume_name": "kirillwynn-staging-postgres",
            "postgres_image": f"postgres@sha256:{'4' * 64}",
            "bootstrap_operation_id": "deploy-100-staging-aaaaaaaa",
            "last_backup": None,
            "last_migration": None,
        },
        "attempts": {},
        "in_progress_operation_id": None,
        "recovery_required_for": None,
    }

    result = module.build_report(
        state,
        release_sha,
        f"edge@sha256:{'3' * 64}",
        release_root,
        runtime_root,
    )

    assert result["active"]["edge"] is None
    assert result["active_shared_edge"]["image"].endswith("3" * 64)
    assert result["active_shared_edge"]["matching_manifests"] == [
        {
            "release_sha": release_sha,
            "manifest_path": str(manifest_path),
            "manifest_sha256": module.record_rollout_state.sha256(manifest_path),
        }
    ]
    assert result["in_progress_operation_id"] is None

    with pytest.raises(ValueError, match="no immutable release manifest"):
        module.build_report(
            state,
            release_sha,
            f"edge@sha256:{'9' * 64}",
            release_root,
            runtime_root,
        )

    manifest_path.write_text("{}")
    with pytest.raises(ValueError, match="manifest"):
        module.build_report(
            state,
            release_sha,
            f"edge@sha256:{'3' * 64}",
            release_root,
            runtime_root,
        )


def test_stage18_recovery_drill_is_scratch_only_and_retains_evidence():
    remote = (SCRIPTS / "run_staging_stabilization_audit_remote.sh").read_text()
    backup = remote.index('"$repository_root/infra/scripts/backup_postgres.sh"')
    restore = remote.index('"$repository_root/infra/scripts/restore_postgres.sh"')
    compare = remote.index('python3 "$comparison_script"')
    assert backup < restore < compare
    assert "restore_stage18_" in remote
    assert "--active-edge-image" in remote
    assert "active_shared_edge" in remote
    assert "docker ps --no-trunc -q" in remote
    assert "com.docker.compose.project=kirillwynn-edge" in remote
    assert "com.docker.compose.service=edge" in remote
    assert "docker inspect --format '{{.Config.Image}}'" in remote
    assert "shared_production_edge_network=owned-by-shared-edge" in remote
    assert "shared_production_edge_network_attachments=active-edge-only" in remote
    assert "production_application_private_networks=absent" in remote
    assert "network:kirillwynn-production-edge" not in remote
    assert 'edge_compose="$repository_root/infra/compose/edge.yml"' not in remote
    assert "scratch_database_retained=true" in remote
    assert "restored_database_public_attachment=none" in remote
    assert (
        "SET TRANSACTION READ ONLY" in (SCRIPTS / "staging_data_audit.py").read_text()
    )
    for forbidden in (
        "dropdb",
        "docker volume rm",
        "reaction catalog sync",
        "run_catalog_sync_remote.sh",
    ):
        assert forbidden not in remote


def test_external_actions_use_reviewed_node24_release_shas():
    expected = {
        "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
        "actions/setup-node": "820762786026740c76f36085b0efc47a31fe5020",
        "actions/setup-python": "5fda3b95a4ea91299a34e894583c3862153e4b97",
        "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
        "actions/download-artifact": "3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
        "docker/setup-buildx-action": "bb05f3f5519dd87d3ba754cc423b652a5edd6d2c",
        "docker/build-push-action": "53b7df96c91f9c12dcc8a07bcb9ccacbed38856a",
        "docker/login-action": "dbcb813823bdd20940b903addbd779551569679f",
    }
    workflows = ROOT / ".github" / "workflows"
    observed = set()
    for workflow in workflows.glob("*.yml"):
        source = workflow.read_text()
        for action, revision in re.findall(
            r"uses:\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([0-9a-f]{40})",
            source,
        ):
            observed.add(action)
            assert revision == expected[action]
    assert observed == set(expected)


def test_stabilization_workflow_is_manual_staging_only_and_never_deploys():
    workflow = (
        ROOT / ".github" / "workflows" / "staging-stabilization-audit.yml"
    ).read_text()
    assert "workflow_dispatch:" in workflow
    assert "environment: staging" in workflow
    assert "expected_active_release_sha" in workflow
    assert "kirillwynn-server-release-operations" in workflow
    assert workflow.index("concurrency:") < workflow.index("jobs:")
    assert workflow.count("kirillwynn-server-release-operations") == 1
    assert "ci_ssh_staging_stabilization_audit.sh" in workflow
    assert "test:staging-audit" in workflow
    assert "scan_test_artifacts.sh" in workflow
    assert workflow.index("STAGING_AUDIT_OUTPUT_DIR") > workflow.index("- id: browser")
    assert '"$RUNNER_TEMP/stage18-live-browser"' in workflow
    config = (
        ROOT / "frontend" / "next" / "playwright.staging-audit.config.ts"
    ).read_text()
    assert "STAGING_AUDIT_OUTPUT_DIR" in config
    assert 'screenshot: "off"' in config
    assert 'trace: "off"' in config
    assert 'video: "off"' in config
    live_spec = (
        ROOT
        / "frontend"
        / "next"
        / "e2e"
        / "staging-audit"
        / "staging-readonly.spec.ts"
    ).read_text()
    for mutation in (".post(", ".put(", ".patch(", ".delete("):
        assert mutation not in live_spec
    for forbidden in (
        "deploy_environment.sh",
        "ci_ssh_deploy.sh",
        "STAGING_DEPLOY_ENABLED",
        "STAGING_REACTION_CATALOG_SYNC_ENABLED",
        "environment: production",
    ):
        assert forbidden not in workflow
