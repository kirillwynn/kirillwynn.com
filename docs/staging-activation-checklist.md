# Staging activation checklist

Repository implementation does not activate staging. Complete externally:

- create the `staging` GitHub Environment;
- add unique Django, DB, signing, S3, OAuth, Resend, SSH, host-key, and Basic
  Auth secrets plus the documented non-secret variables;
- provision restricted `/srv/kirillwynn/{runtime,releases,state,backups,locks}`;
- install Docker Compose >= 2.30.0 and authenticate the server to GHCR;
- validate/start shared edge first so it owns both empty edge networks;
- provide TLS/ACME mounts and the staging htpasswd file to shared edge;
- create the staging S3 bucket/prefix with versioning/lifecycle;
- create staging-only Google/GitHub apps and callbacks;
- verify staging Resend sender/DNS and register the exact signed webhook;
- run staging/production application and database-only Compose config, shared
  edge config, and integration config in the same check;
- prove edge starts with both apps absent, run candidate `nginx -t`, then
  bootstrap the staging database and migrations;
- keep `STAGING_DEPLOY_ENABLED` false until all checks pass;
- enable it for a controlled `main` release, then verify schema-3 attestation,
  exact active digests, worker heartbeat/egress, dynamic DNS replacement,
  backup checksum, scratch restore, duplicate-finalize idempotency, and
  reviewed failed-smoke recovery under the same server lock.

Do not create a production administrator or promote production here.
