# Staging activation checklist

Repository implementation does not activate staging. Complete externally:

- create the `staging` GitHub Environment;
- add unique Django, DB, signing, S3, OAuth, Resend, SSH, host-key, and Basic
  Auth secrets plus the documented non-secret variables;
- provision restricted `/srv/kirillwynn/runtime` and backup directories;
- install Docker Compose and authenticate the server to GHCR;
- create environment edge networks by starting validated app projects;
- provide TLS/ACME mounts and the staging htpasswd file to shared edge;
- create the staging S3 bucket/prefix with versioning/lifecycle;
- create staging-only Google/GitHub apps and callbacks;
- verify staging Resend sender/DNS and register the exact signed webhook;
- run simultaneous app `docker compose config` and shared edge config;
- run `nginx -t`, empty-database migrations, and start shared edge;
- keep `STAGING_DEPLOY_ENABLED` false until all checks pass;
- enable it for a controlled `main` release, then verify attestation, worker
  heartbeat, backup, and restore drill.

Do not create a production administrator or promote production here.
