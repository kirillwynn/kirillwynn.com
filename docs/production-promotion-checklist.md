# Production promotion checklist

Before approval, require a valid manifest and matching staging attestation,
healthy staging flows/worker, a recent restore drill, backward-compatible
migrations, healthy production DB/S3 monitoring, and the previous manifest.

Promotion:

1. dispatch `Promote production` with the full SHA;
2. approve the `production` GitHub Environment;
3. require the custom-format backup/integrity gate;
4. allow one-shot migration and exact-digest app replacement;
5. verify readiness, Feed/Bridge/posts, CMS/Admin redirects, session/CSRF,
   OAuth initiation, comments/reactions, subscriptions, Draft Mode,
   revalidation, and heartbeat;
6. record active digests and migration state.

Rollback uses prior compatible digests. Never rebuild, select `latest`,
automatically reverse migrations, or restore over production. Follow the
deployment and backup/restore runbooks.
