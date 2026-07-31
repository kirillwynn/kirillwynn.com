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

When the repository is public, a release used only as transport must contain
the encrypted archive, never the plaintext prepared directory. Generate a
one-time 256-bit lowercase-hex key, encrypt with AES-256-CTR plus PBKDF2-SHA256
at 200,000 iterations and a fresh OpenSSL salt, and pin both the ciphertext and
plaintext SHA-256 values. Store the key only as the temporary protected staging
Environment secret `STAGING_REACTION_CATALOG_TRANSFER_KEY`; the workflow keeps
`contents: read`, verifies the ciphertext before decryption, verifies the
attested archive after decryption, and extracts through the bounded safe
extractor. The public prerelease/tag, transfer secret, ciphertext digest, and
asset ID are one-operation transport state and must be deleted immediately
after the attested sync. Never reuse the key or publish the plaintext archive.

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

The automated staging sync serializes against deployment operations. On the
current bounded staging host it records a non-sensitive memory snapshot, checks
that catalog rows are either absent or the complete 228-item allowlist, and
temporarily stops only the outbox worker before starting the one-off Django
container. An EXIT trap always restarts the worker and waits for healthy state.
Post/comment web traffic remains active. The sync then requires exactly 228
catalog rows and an unchanged count of preserved legacy Unicode post/comment
rows before it can produce an attestation.

## Recorded staging activation

The `stage16-staging-v1` catalog was synchronized on 2026-07-30 by run
`30588326706`, operation
`catalog-sync-30588326706-staging-2d3c04faa08835e2b1d8cadb4eb1649870633f17`.
Artifact `8777666567` contains the successful sync attestation; its canonical
JSON SHA-256 is
`ca6452ef8a0bb995cdb21ab7771484a6677cec9ba5955913fff3d0c921d94a61`.
The attestation records:

- 228 activated rows: 180 static and 48 animated;
- 276 verified immutable objects under `staging/media`;
- upload `created=0`, activation `created=228, updated=0`, and idempotent repeat
  `created=0, updated=0`;
- preserved legacy counts of two post Unicode rows and zero comment Unicode
  rows before and after activation;
- worker restart and healthy state after the bounded one-off importer.

The encrypted transport prerelease/tag and asset, transfer key secret,
temporary variables, local key, plaintext archive, and ciphertext were deleted
after that attestation. `STAGING_REACTION_CATALOG_SYNC_ENABLED=false` is the
recorded final gate state.

Application activation migration
`discussions.0004_activate_catalog_reaction_identity` was applied by run
`30589404234`. The final live-QA fix release was deployed by run
`30591503850`, operation
`deploy-30591503850-staging-43f5a05213f13d7c5129ddebd05955fc3186de82`.
Release artifact `8778617590` contains `release-manifest.json` with SHA-256
`1bc7a1350cf231a7d01d1742dd30aca82666f8e61fb7d23b941e35070f03f316`;
attestation artifact `8778654379` contains `staging-attestation.json` with
SHA-256
`45657ec2ec8d07830f6f80a68f69f3b0aaf24ae98998c17f5afe7535373b0b82`.
Both repository and staging Environment deployment gates were restored to
`false`.

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
release. The activation migration's reverse changes Django's migration state
but deliberately leaves the partial legacy uniqueness indexes in place:
recreating the former unconditional uniqueness would reject multiple custom
rows whose retained legacy value is empty. Reapplying activation explicitly
replaces either prior physical form and is safe with populated legacy and
custom rows. Do not roll back the expansion migration while catalog or custom
reaction rows exist. The expansion digest ignores catalog rows and continues
serving preserved Unicode rows.

Never delete old Unicode rows or immutable S3 objects during a rollback.
Removing the legacy columns, archiving unmapped Unicode data, or garbage
collecting unreferenced content-addressed objects is a separate contract
migration/runbook change.
