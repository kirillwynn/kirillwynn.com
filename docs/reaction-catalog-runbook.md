# Reaction catalog asset runbook

This runbook operates only on an explicit reviewed manifest. Never point a
publishing command at a directory without a manifest entry for every file.
Never place source or normalized reaction binaries in Git, browser bundles, or
container images.

## Current staging catalog

- manifest: `docs/reaction-catalog/stage16-staging-v1.json`;
- catalog version: `stage16-staging-v1`;
- allowlist: 228 explicit items (180 static, 48 animated);
- quick reactions: `pepeclap`, `pepehmm`, `pepelove`;
- approval: `staging-only/unverified`;
- production: prohibited by the sync command.

The recorded source/author/license are unknown because the supplied corpus has
no README, attribution, license, or upstream source. The owner approved all
items for staging evaluation only. Search-engine availability and
noncommercial use do not elevate that status.

## Prepare locally

Run from `backend/django`:

```bash
python3 -m uv run --frozen python manage.py prepare_reaction_catalog \
  --manifest ../../docs/reaction-catalog/stage16-staging-v1.json \
  --source-root /absolute/reviewed/source/root \
  --output-dir /absolute/private/prepared/root
```

Keep the output outside Git. Record the manifest SHA-256, canonical
`reaction-catalog-attestation.json` SHA-256, item/object counts, and normalizer
version. A second identical run into the same directory must succeed without
changing any byte. A run into a second empty directory must produce the same
attestation and object hashes.

The prepare command checks:

- exact manifest schema and 3-item quick configuration;
- safe relative source paths and absence of symlinks;
- source SHA-256 and byte-detected format;
- exact PNG/WebP/GIF EOF plus Pillow verify/full-frame decode;
- source/output size, dimensions, frame count, duration, and decoded cost;
- sRGB output, metadata removal, delay normalization, loop and poster;
- exact output hashes and immutable content-addressed paths.

## Sync and activate staging

Do not sync until the expansion release containing migration
`discussions.0003_reaction_catalog_expansion` is active and verified. Make the
private prepared directory and exact manifest available to a one-off Django
process using the staging runtime and existing S3 credentials; do not bake them
into an image.

First verify/upload without database activation:

```bash
python manage.py sync_reaction_catalog \
  --manifest /private/input/stage16-staging-v1.json \
  --attestation /private/input/reaction-catalog-attestation.json \
  --environment staging
```

Then run the same command with `--activate`. The command verifies
`staging/media` prefix isolation, conditionally creates missing objects,
reads every object back, checks bytes and immutable headers, and only then
updates catalog/settings rows in one transaction:

```bash
python manage.py sync_reaction_catalog \
  --manifest /private/input/stage16-staging-v1.json \
  --attestation /private/input/reaction-catalog-attestation.json \
  --environment staging \
  --activate
```

Repeat the command to prove idempotence. Existing versioned objects must not be
overwritten, renamed, or deleted. Record the full prefixed object count and
sample a static asset, animation, and poster with:

```text
Content-Type: image/webp or image/gif
Cache-Control: public, max-age=31536000, immutable
x-amz-meta-sha256: <content digest>
x-amz-meta-catalog-id: <stable ID>
x-amz-meta-asset-version: sha256-<normalized asset digest>
```

## Production promotion

The current manifest must fail before any production write. Promotion requires
a new explicit manifest in which the root and every item are
`production-approved`, with documented provenance/license or other reviewed
rights basis.

Reuse, rather than regenerate, staging-attested bytes:

```bash
python manage.py prepare_reaction_catalog \
  --manifest /private/input/production-approved.json \
  --source-root /absolute/reviewed/source/root \
  --reuse-attestation /private/staging/reaction-catalog-attestation.json \
  --output-dir /private/production-promotion
```

Verify that every normalized object SHA-256 matches the staging attestation.
Only then may the normal production backup, release approval, and
`--environment production` process be considered. Production sync must use the
configured `production/media` prefix and must never read or copy unverified
source bytes into a fresh encoder.

## Rollback and cleanup

During activation, roll application code back only to the verified expansion
release. Do not roll back the expansion migration while custom reaction rows
exist. The expansion digest ignores catalog rows and continues serving
preserved Unicode rows.

Never delete old Unicode rows or immutable S3 objects during a rollback.
Removing the legacy columns, archiving unmapped Unicode data, or garbage
collecting unreferenced content-addressed objects is a separate contract
migration/runbook change.
