# Production promotion checklist

Before approval, require a valid manifest and matching staging attestation,
healthy staging flows/worker, a recent restore drill, backward-compatible
migrations, healthy production DB/S3 monitoring, and the previous manifest.

Promotion:

1. dispatch `Promote production` with the full SHA;
2. approve the `production` GitHub Environment;
3. for first production only, create pinned PostgreSQL and verify the initial
   pre-migration backup; otherwise back up the active database first;
4. allow one-shot migration and bounded health-gated exact-digest replacement;
5. verify Django/Next health, worker heartbeat/egress, exact image references,
   readiness, Feed/Bridge/posts, CMS/Admin redirects, session/CSRF,
   OAuth initiation, comments/reactions, subscriptions, Draft Mode,
   revalidation, and heartbeat;
6. replace edge only after application gates, run public smoke, then atomically
   record current/previous manifests and active digests.

Rollback uses prior compatible digests. Never rebuild, select `latest`,
automatically reverse migrations, or restore over production. Follow the
deployment and backup/restore runbooks.
