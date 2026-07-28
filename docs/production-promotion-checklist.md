# Production promotion checklist

Before approval, require a valid manifest and matching staging attestation,
healthy staging flows/worker, a recent restore drill, backward-compatible
migrations, healthy production DB/S3 monitoring, and the previous manifest.

Promotion:

1. dispatch `Promote production` with the full SHA;
2. approve the `production` GitHub Environment;
3. for first production only, create pinned PostgreSQL and verify the initial
   `initial-empty` backup under a durable operation ID; otherwise take a
   `pre-migration` backup first;
4. allow one-shot migration and bounded health-gated exact-digest replacement;
5. verify Django/Next health, worker heartbeat/egress, exact image references,
   readiness, Feed/Bridge/posts, CMS/Admin redirects, session/CSRF,
   OAuth initiation, comments/reactions, subscriptions, Draft Mode,
   revalidation, and heartbeat;
6. replace edge only after application gates, run public smoke, then atomically
   switch the one authoritative state document for application and edge.

If public smoke fails, record failure evidence and run the reviewed recovery
operation to the exact base application and edge snapshot; do not use previous
as the recovery target. Normal rollback uses prior compatible application and
edge digests. Never rebuild, select `latest`, automatically reverse migrations,
delete/adopt a volume, or restore over production. Follow the deployment and
backup/restore runbooks.
