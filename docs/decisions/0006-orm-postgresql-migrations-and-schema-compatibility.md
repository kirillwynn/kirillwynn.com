# 0006: ORM, PostgreSQL Migrations, and Schema Compatibility

- **Status:** Proposed
- **Date:** 2026-08-23
- **Owners:** Control Tower

## Context

[ADR 0001](0001-version-baseline-and-update-policy.md) accepts Node.js 24.19.0, PostgreSQL 18.6, TypeScript 6.0.3, ESM, and exact direct dependency pins. [ADR 0002](0002-react-router-ssr-runtime-deployment-model.md) accepts a portable Web `Request` to `Response` boundary and keeps database access server-only. [ADR 0003](0003-bundler-build-development-model.md) requires the browser graph to fail closed against database packages and other server-only reachability. [ADR 0004](0004-repository-package-runtime-topology.md) assigns the Node persistence graph and its direct runtime dependencies to the future `packages/server` workspace; `packages/shared`, `packages/web`, and the future worker cannot own or import that graph. [ADR 0005](0005-backend-api-framework-and-contracts.md) carries the exact application `request.signal` to downstream work and leaves database driver behavior, transactions, cancellation, migrations, and database readiness to M07.

M07 selects a typed PostgreSQL access layer and makes its ownership, pool, query, cancellation, transaction, migration, schema-compatibility, and readiness contracts precise enough for later implementation and executable validation. The result remains documentation only: it adds no dependency, manifest, lockfile, configuration, schema, migration, source, script, workflow, generated artifact, database, or runtime claim.

Official primary evidence was checked at the single cutoff **2026-08-23T16:25:28Z**. Exact registry documents and immutable tagged source identify published artifacts; rolling official documentation describes behavior visible at the cutoff and can later change. Published engine, export, dependency, and type metadata establishes only a compatibility envelope. It does not prove installation, typechecking, pooling, queries, cancellation, transactions, migrations, PostgreSQL 18.6 behavior, security, or runtime compatibility.

### Official evidence matrix

| Claim | Direct official source | Evidence class and exact identity | Exact verified result |
| --- | --- | --- | --- |
| Kysely has an exact stable artifact inside the accepted Node and TypeScript envelope. | [registry](https://registry.npmjs.org/kysely/0.29.5), [release](https://github.com/kysely-org/kysely/releases/tag/v0.29.5), [tag ref](https://api.github.com/repos/kysely-org/kysely/git/ref/tags/v0.29.5), [manifest](https://github.com/kysely-org/kysely/blob/f24018c789c3cf7ad03ccc672ada63a1ded87f88/package.json) | Exact metadata and tagged source: `kysely@0.29.5`; annotated tag object `a297ee6aa7c0485a76b05a53defb2000f6c61eed`; commit `f24018c789c3cf7ad03ccc672ada63a1ded87f88` | ESM-only; Node `>=22`; zero runtime dependencies; tagged development matrix includes TypeScript 6.0.3. The annotated tag is unsigned; GitHub reports the commit signature as verified. |
| The selected Kysely patch carries the required cancellation and security posture. | [0.29.0 release](https://github.com/kysely-org/kysely/releases/tag/v0.29.0), [0.29.4 release](https://github.com/kysely-org/kysely/releases/tag/v0.29.4), [0.29.5 release](https://github.com/kysely-org/kysely/releases/tag/v0.29.5), [abort types](https://github.com/kysely-org/kysely/blob/f24018c789c3cf7ad03ccc672ada63a1ded87f88/src/util/abort.ts#L4-L50), [query executor](https://github.com/kysely-org/kysely/blob/f24018c789c3cf7ad03ccc672ada63a1ded87f88/src/query-executor/query-executor-base.ts#L73-L156), [JSON-path advisory](https://github.com/kysely-org/kysely/security/advisories/GHSA-wmrf-hv6w-mr66) | Immutable release history and tagged source at `f24018c...`, plus the official advisory | 0.29 introduced query signals and explicit in-flight strategies; 0.29.4 fixed control-client password propagation; 0.29.5 fixed missing abort-handler cleanup callbacks. The JSON-path advisory affects versions through 0.28.11, so the selected patch is outside its affected range. An abort can return before the original query and cancellation handler settle, while the connection remains held until both settle. |
| Kysely's PostgreSQL cancellation uses a separately constructed control client. | [dialect configuration](https://github.com/kysely-org/kysely/blob/f24018c789c3cf7ad03ccc672ada63a1ded87f88/src/dialect/postgres/postgres-dialect-config.ts#L7-L17), [driver cancellation](https://github.com/kysely-org/kysely/blob/f24018c789c3cf7ad03ccc672ada63a1ded87f88/src/dialect/postgres/postgres-driver.ts#L167-L238) | Immutable tagged source at `f24018c...` | The driver can use a control client for `pg_cancel_backend` or `pg_terminate_backend`; the project must supply and bound that path rather than treat pool capacity as unlimited. |
| Callback transactions provide a provider-level release path but no transaction-level signal option. | [transaction implementation](https://github.com/kysely-org/kysely/blob/f24018c789c3cf7ad03ccc672ada63a1ded87f88/src/kysely.ts#L862-L1076), [open ControlledTransaction issue](https://github.com/kysely-org/kysely/issues/1990) | Immutable tagged source plus rolling official issue state | `TransactionBuilder.execute(callback)` has no options parameter and releases through provider cleanup. The controlled transaction path can bypass release when `BEGIN`, `COMMIT`, or `ROLLBACK` throws. |
| Core Kysely provides ordered transactional migrations and a dialect migration lock. | [Migrator](https://github.com/kysely-org/kysely/blob/f24018c789c3cf7ad03ccc672ada63a1ded87f88/src/migration/migrator.ts#L540-L578), [PostgreSQL adapter](https://github.com/kysely-org/kysely/blob/f24018c789c3cf7ad03ccc672ada63a1ded87f88/src/dialect/postgres/postgres-adapter.ts#L5-L39) | Immutable tagged source at `f24018c...` | PostgreSQL pending migrations can run in one transaction under an advisory lock. The stock lock wait is one hour and migration identity does not include a project source digest, so both controls require project ownership. |
| The selected node-postgres artifact is compatible by metadata and supplies no bundled declarations. | [registry](https://registry.npmjs.org/pg/8.23.0), [tag ref](https://api.github.com/repos/brianc/node-postgres/git/ref/tags/pg%408.23.0), [manifest](https://github.com/brianc/node-postgres/blob/df274d1ba9ad9d11a8f1079314faeafde7208207/packages/pg/package.json) | Exact metadata and tagged source: `pg@8.23.0`; annotated tag object `f6ae396d9e638a182bd61998f0ea1850d475dd57`; commit and npm `gitHead` `df274d1ba9ad9d11a8f1079314faeafde7208207` | Node `>=16`; ESM import target plus CommonJS; six runtime dependencies; no bundled TypeScript declarations. `pg-native` is an optional peer and is not selected. The tag and commit are unsigned. |
| The exact node-postgres declarations require a separate type-only package. | [registry](https://registry.npmjs.org/%40types%2Fpg/8.23.1) | Exact registry metadata: `@types/pg@8.23.1`; DefinitelyTyped `ts6.0` line | Exact declarations are available through `pg-types`, `@types/node`, and `pg-protocol` declaration dependencies, but no immutable per-package tag or npm `gitHead` was established; that is a provenance limit rather than runtime code. |
| Pool acquisition, lifecycle, and background failures require explicit ownership. | [Pool API](https://node-postgres.com/apis/pool), [pool sizing guide](https://node-postgres.com/guides/pool-sizing) | Rolling official node-postgres documentation | A pool has finite sizing and acquisition controls only when configured; checked-out clients must be released; idle-client errors require a listener; total capacity depends on every application instance and other consumers. |
| Query values are parameterized while identifiers and PostgreSQL codecs remain project concerns. | [queries](https://node-postgres.com/features/queries), [data types](https://node-postgres.com/features/types) | Rolling official node-postgres documentation | Parameter placeholders protect values, not dynamic identifiers. Unmapped values and PostgreSQL numeric/time types require an explicit application type/codec contract. |
| PostgreSQL supplies independent server-side timeout backstops. | [client timeout settings](https://www.postgresql.org/docs/18/runtime-config-client.html) | Versioned PostgreSQL 18 documentation | `statement_timeout`, `lock_timeout`, and `idle_in_transaction_session_timeout` bound different failure modes and cannot be replaced by a JavaScript signal alone. |
| Advisory-lock polling can implement a finite migration-lock deadline. | [advisory-lock functions](https://www.postgresql.org/docs/18/functions-admin.html) | Versioned PostgreSQL 18 documentation | `pg_try_advisory_lock` is session-scoped and returns immediately, allowing bounded project-owned retry and same-session release. |
| Serializable failures require whole-transaction replay, not statement replay. | [serialization failure handling](https://www.postgresql.org/docs/18/mvcc-serialization-failure-handling.html) | Versioned PostgreSQL 18 documentation | SQLSTATE `40001`, and selected `40P01` cases, require retrying the complete transaction logic with fresh reads; retries must remain bounded and safe to replay. |
| Drizzle supplies stronger generation and named-statement facilities but a weaker exact cancellation/lifecycle fit. | [0.45.2 release](https://github.com/drizzle-team/drizzle-orm/releases/tag/0.45.2), [ORM manifest](https://github.com/drizzle-team/drizzle-orm/blob/273c78071d4841b497f5144734b38294df7ec64b/drizzle-orm/package.json), [Kit manifest](https://github.com/drizzle-team/drizzle-orm/blob/273c78071d4841b497f5144734b38294df7ec64b/drizzle-kit/package.json), [transaction source](https://github.com/drizzle-team/drizzle-orm/blob/273c78071d4841b497f5144734b38294df7ec64b/drizzle-orm/src/node-postgres/session.ts#L223-L241) | Exact `drizzle-orm@0.45.2` and `drizzle-kit@0.31.10` at commit `273c78071d4841b497f5144734b38294df7ec64b` | ORM has zero runtime dependencies and supports named prepared statements; Kit adds a CLI and four dependencies. No tagged Node/TypeScript floor or request-signal path was established, and a failed `BEGIN` can precede the pooled-client release guard. 0.45.2 also contains an identifier-escaping security correction, excluding older patches. |

### Exact candidate artifact snapshot

| Candidate | Published shape | Exact artifact identity | Decision |
| --- | --- | --- | --- |
| `kysely@0.29.5` | ESM, Node `>=22`, built-in types, zero runtime dependencies | SHA-1 `c07a51700a4b4db53c60bd373e6e098f919fccae`; SRI `sha512-ooa+eSbBNPTo3MycPEuW5jdrxQdQwdtB3LC3h43FiXQbIry5tR0C5lDG7eealK0E4D7XjrnOP5DIUg/LyjRMYQ==` | Selected runtime dependency. |
| `pg@8.23.0` | Node `>=16`, ESM and CommonJS targets, six runtime dependencies, no bundled declarations | SHA-1 `5c2026d32bd0cb4fbd9196bac1ecf5ae66607180`; SRI `sha512-Ip2EQCngowJLGOfCwkFhPXU7/ljlhn6Rxlmy4XYfL2Y+vyRM59+8uR2xqRWKdYmbXmxCFOAmKxBuSUCdF34qLg==` | Selected runtime dependency. |
| `@types/pg@8.23.1` | Type-only declarations with three declaration dependencies | SHA-1 `7e712ce02cf44ad100862127f10f52e9c6b9d227`; SRI `sha512-fKVHpikPdg4GKks3JuLEhvwSyvwzF23hnabPy6DD8ljVbC7+6J5dQzdv4arV6jqq57djnMgs1HKBxX4P8aBI3A==` | Selected server-workspace dev dependency. |
| `drizzle-orm@0.45.2` and `drizzle-kit@0.31.10` | Dual module ORM plus generation/migration CLI | Monorepo tag and commit `273c78071d4841b497f5144734b38294df7ec64b` | Rejected for this baseline. |

The Kysely registry record links a provenance attestation, but this milestone did not validate that attestation. No provenance guarantee is claimed from the link alone.

## Decision drivers

- Keep PostgreSQL access inside the server-owned graph and impossible to reach from browser, shared, or not-yet-authorized worker code.
- Use exact stable artifacts that fit the accepted Node 24.19.0, TypeScript 6.0.3, ESM, and PostgreSQL 18.6 metadata envelope.
- Preserve SQL visibility and PostgreSQL semantics without accepting an entity lifecycle, identity map, decorators, generated client, or mandatory CLI.
- Give every pool, query, transaction, retry, migration, compatibility transition, and readiness action one explicit project owner.
- Propagate the exact M06 application signal to request-scoped database statements and retain independent database-side timeout controls.
- Prevent request cancellation, transaction failure, migration-lock contention, or a cancellation storm from leaking or exhausting connections.
- Make committed migration history append-only and tamper-evident rather than trusting filenames or timestamps alone.
- Keep schema changes compatible with staging-first immutable artifact promotion and require explicit old/new consumer evidence before contraction.
- Separate documentation and metadata evidence from later install, typecheck, PostgreSQL, failure-injection, and runtime proof.

## Considered options

| Option | Strengths | Material costs or gaps | Outcome |
| --- | --- | --- | --- |
| `kysely@0.29.5`, `pg@8.23.0`, and `@types/pg@8.23.1` | Small ESM typed-SQL layer; zero Kysely runtime dependencies; explicit external pool; query-level cancellation API; core transactional migrator | No first-party code generator or digest ledger; no named prepared-plan cache API; transaction builder has no signal option; project wrappers remain substantial | Selected with the contracts below. |
| `drizzle-orm@0.45.2`, `drizzle-kit@0.31.10`, exact `pg`, and declarations | First-party schema generation and migration CLI; SQL-shaped API; named prepared statements | Kit/CLI and four more dependencies; no exact declared Node or TypeScript floor; no tagged request-signal path; failed-`BEGIN` release gap requires proof | Rejected because generation and named statements do not outweigh cancellation and lifecycle uncertainty here. |
| Native `pg@8.23.0` only | Maximum driver control and smallest conceptual abstraction | Project would own typed query construction, result mapping, dialect behavior, migration orchestration, and every safety rail | Rejected because it duplicates the selected typed query and migration foundation without a demonstrated benefit. |
| Prisma ORM `7.9.1` with `@prisma/client` and `@prisma/adapter-pg` | Strong declarative schema, introspection, migrations, and generated client; [official requirements](https://docs.prisma.io/docs/orm/reference/system-requirements) cover the accepted runtime envelope | Mandatory generation and CLI lifecycle, adapter plus client surface, and no selected stable per-query signal contract; exact tag commit [`787e3a8...`](https://github.com/prisma/prisma/commit/787e3a806ce7d2a4ce063b934c3f1ac5e35d5c67) | Rejected for this small server-owned SQL layer. |
| MikroORM `7.1.13` | [Official cancellation](https://mikro-orm.io/docs/query-cancellation), migrations, identity map, and Unit of Work | Broader entity lifecycle than required; exact [7.1.13 release](https://github.com/mikro-orm/mikro-orm/releases/tag/v7.1.13) package peers require additional reconciliation | Rejected. |
| TypeORM `1.1.0` | Broad ORM and migration features in the [exact registry artifact](https://registry.npmjs.org/typeorm/1.1.0) | Decorator/entity metadata, CLI and dependency surface, many optional drivers, and no selected public query-signal contract; verified tag commit [`8748b1b...`](https://github.com/typeorm/typeorm/commit/8748b1be17bf93fc9b62b3444e411e9055e9e017) | Rejected. |

Prerelease lines and earlier stable patches are not candidates. `pg-native`, `pg-cursor`, `kysely-codegen`, `kysely-ctl`, Drizzle Kit, Prisma CLI, or another ORM, driver, migration, cursor, introspection, or code-generation package is not selected. M12 may reconsider a cursor only if it selects PostgreSQL cursor streaming; doing so requires a new exact dependency review.

## Decision

### Exact package selection and ownership

The future `packages/server/package.json` owns these exact direct packages:

| Classification | Exact package | Ownership consequence |
| --- | --- | --- |
| Runtime dependency | `kysely@0.29.5` | Server persistence facade, typed database contract, PostgreSQL dialect, callback transaction base, and project-wrapped Migrator. |
| Runtime dependency | `pg@8.23.0` | Pure-JavaScript PostgreSQL pool, clients, wire driver, and explicit cancellation control-client constructor. |
| Development dependency | `@types/pg@8.23.1` | Type-only declarations in the owning server workspace; excluded from the production runtime closure. |

No other M07 direct package is accepted. A later dependency-bearing milestone must recheck exact registry metadata and security state, inspect the complete frozen transitive graph and lifecycle scripts, and add the exact pins and lockfile under ADRs 0001 and 0004. This ADR does not authorize that milestone.

The database graph remains server-only. `packages/shared` may define deliberately storage-agnostic domain values but cannot import Kysely, node-postgres, SQL, schema types generated from a database, credentials, or a persistence implementation. `packages/web` and every browser artifact must fail closed against the same reachability. The future `packages/worker` remains limited to `shared` until M10; M07 grants it no database dependency, connection, migration, or schema authority.

### Pool, connection, and codec ownership

- The server persistence boundary owns exactly one long-lived bounded `pg.Pool` and one long-lived `Kysely<Database>` for each server runtime instance. Request handlers cannot construct a pool, close it, or receive unrestricted raw `db`, dialect, pool, or client objects.
- One lifecycle owner initializes the pool, attaches its background error handler before use, admits readiness only after the bounded database gate succeeds, and destroys Kysely/pool exactly once after new work is denied and in-flight database work drains or reaches its shutdown bound.
- M14 selects numeric connection budgets because replica count, provider limits, and future worker demand remain unresolved. The selected configuration must nevertheless have finite positive pool maximum, connection-establishment timeout, acquisition deadline, idle-client lifetime, statement timeout, lock timeout, and idle-in-transaction timeout. A zero or unbounded acquisition or connection timeout is prohibited.
- Total pool capacity must be derived from the PostgreSQL connection budget after explicit reserves for administration, migrations, cancellation control clients, and future authorized consumers. Simultaneous control-client creation is separately bounded; cancellation cannot consume the ordinary pool reserve or exhaust the server connection budget.
- The pool owns codecs locally. Process-global `pg.types` mutation is prohibited. PostgreSQL `bigint` and `numeric` remain strings unless a later reviewed pool-local codec proves its range and precision policy. Date, time, timestamp, interval, JSON, bytea, array, enum, and nullable representations must match actual node-postgres behavior and the `Database` TypeScript contract.
- The selected Kysely driver sends parameterized SQL plus values and does not supply a stable node-postgres `QueryConfig.name`; no server-side named prepared-plan cache is promised. Dynamic values use parameters. Dynamic identifiers are prohibited unless selected from a closed project-owned allowlist and escaped by the dialect rather than concatenated from input.
- Application statements do not run in parallel on one checked-out client or transaction. Pipeline mode remains disabled. Cursor streaming is not selected.

### Query facade and cancellation

All application database access goes through a narrow project-owned persistence facade. Domain services request operations from that facade; route modules and handlers do not own SQL or a generic query-builder escape hatch. The facade provides an operation-specific result and hides Kysely, pool, client, SQL text, schema names, constraint names, and driver errors from the public HTTP boundary.

Every request-scoped query and raw statement must receive the exact application `request.signal` retained by M06 and must set `inflightQueryAbortStrategy: "cancel query"` explicitly. The default `"ignore query"` behavior is prohibited. The facade passes that signal unchanged; narrower database bounds use the operation's existing deadline and project-owned database/server timeout controls rather than replacing or composing a different query signal.

The PostgreSQL dialect receives the explicit `pg.Client` constructor as `controlClient`; it must not depend on an undocumented constructor reached through the pool. Control-client creation, connection time, concurrent cancellation, and shutdown are bounded. `"kill session"` is prohibited for ordinary request cancellation and reserved for separately proven bounded shutdown or recovery when cancel-query cannot restore a safe session.

Cancellation is best effort, not an atomic database rollback promise. An abort may settle the caller before the original query and control handler finish; the checked-out connection stays unavailable until both settle and cleanup completes. Server-side `statement_timeout`, `lock_timeout`, and `idle_in_transaction_session_timeout` remain independent backstops. A cancellation failure is an internal lifecycle fault: the affected session is not considered reusable until the original query and driver cleanup settle, and an implementation that cannot prove safe reuse must recycle its persistence owner before readiness returns.

Public responses use the stable M06 problem contract and never expose SQL, parameters, database names, schema or table names, constraint names, migration names, credentials, hosts, ports, driver codes, server messages, stacks, or internal cancellation details. Internal diagnostics may retain sanitized correlation and classified causes but not secrets or raw credential-bearing connection strings.

### Transaction and retry contract

Only a project-owned wrapper over `db.transaction().execute(callback)` is allowed. `startTransaction()`, `ControlledTransaction`, transaction objects that escape their callback, unmanaged clients, and parallel statements on the same transaction are prohibited.

The wrapper has these exact semantics:

1. Check the exact request signal before starting acquisition, immediately on callback entry, before every statement, and immediately before the commit fence.
2. Every statement inside the callback goes through the same signal-injecting facade with `"cancel query"`; direct query-builder execution is unavailable to callers.
3. Abort before the commit fence throws inside the callback. Kysely then performs rollback without using the aborted request signal and releases the connection only after cleanup settles.
4. An abort while waiting for a saturated pool cannot make transaction acquisition itself signal-aware at this version. The finite acquisition deadline remains the outer bound. If a connection arrives after the abort, the entry guard executes no application statement, cleanup releases it, and the wrapper settles only after that tracked cleanup rather than detaching the acquisition promise.
5. Once `COMMIT` starts, the wrapper cannot truthfully report that the transaction rolled back. It awaits and classifies the result. Lost transport or timeout during commit is outcome ambiguity: no blind retry, success response, or compensating assumption is allowed.
6. Rollback and connection cleanup are non-abortable infrastructure work with their own bound. Failure raises a sanitized lifecycle fault and prevents readiness from returning until the implementation proves safe session reuse or recycles its persistence owner.
7. Transaction-local domain results are returned only after a confirmed commit. No external side effect is performed inside a replayable database transaction unless a later durable-idempotency contract, owned by M10, makes replay safe.

Automatic retry is opt-in per operation. It retries the complete callback, including fresh reads, only for SQLSTATE `40001` and explicitly classified `40P01`, only when the operation declares database replay safety, and only under a finite attempt count, jittered backoff, and the original operation deadline. It never retries statement fragments, validation errors, cancellation, connection loss during commit, or another ambiguous outcome.

### Migration source, ledger, and locking

The core Kysely `Migrator` is used only behind a project-owned strict provider, PostgreSQL migration adapter, and runner. `FileMigrationProvider`, filesystem enumeration order, schema synchronization, schema push, automatic startup migration, and production `down` are not sufficient or permitted.

The canonical migration source is an append-only manifest of ordered definitions. Each definition has an immutable ASCII name, an exact ordered array of SQL statements, and a lowercase SHA-256 digest. Names compare by bytewise lexical order, are unique, never reused, and identify forward-only `up` behavior. A migration imports no current application, entity, query-facade, generated database, environment, or network code.

Digest input uses one versioned, unambiguous serialization. For version `migration-v1`, UTF-8 bytes are emitted without a BOM or Unicode normalization by this exact concatenation, including the final LF:

```text
"migration-v1\n"
+ "name " + ASCII_DECIMAL(UTF8_BYTE_LENGTH(name)) + "\n" + UTF8(name) + "\n"
+ "statements " + ASCII_DECIMAL(statements.length) + "\n"
+ for each statement in order:
  "statement " + ASCII_DECIMAL(UTF8_BYTE_LENGTH(statement)) + "\n" + UTF8(statement) + "\n"
```

Decimal fields contain only ASCII digits with no sign or leading zero except the value zero. Raw length-delimited name and statement bytes are not rewritten. The persisted form is `sha256:` followed by 64 lowercase hexadecimal characters. A serialization-version change is a separately reviewed compatibility decision.

The provider validates manifest membership, unique names, strict order, serialization version, and digests before exposing any migration. In addition to Kysely's name/timestamp table, a project-owned digest ledger records migration name, serialization version, and digest. Under the same migration lock, the runner requires exact agreement among the immutable manifest, every Kysely applied row, and every digest row. Missing, extra, changed, duplicated, reordered, or unknown applied history is fatal and cannot be repaired automatically.

For ordinary migrations:

- `allowUnorderedMigrations` remains false and `disableTransactions` remains false;
- all currently pending migrations run in one master PostgreSQL transaction on one migration connection;
- each `up` runs its exact statement array and inserts its digest row in that transaction; Kysely records the migration name/timestamp in the same transaction;
- after success the runner rereads both ledgers and requires their exact expected head before reporting success;
- every thrown error, `MigrationResultSet.error`, non-success status, lock timeout, ledger mismatch, or post-run mismatch is fatal and reports only sanitized internal diagnostics.

The project PostgreSQL migration adapter uses `pg_try_advisory_lock` on the same session that resolves history and runs the transaction. It retries only until a finite configured deadline, fails without schema changes on expiry, and releases the session lock in `finally`. Kysely's stock one-hour wait is not the effective project bound. M14 selects the exact deadline and migration invocation topology; it cannot make the wait unbounded or run competing automatic migrators.

Nontransactional DDL such as `CREATE INDEX CONCURRENTLY` is prohibited on this ordinary path. If a later change requires it, a separately reviewed two-phase maintenance operation must define its own lock, durable phase ledger, observation, retry, repair, old/new artifact compatibility, and acceptance evidence. It cannot enable `disableTransactions` globally.

Introspection and code generation are not schema authorities. No generator is selected. A later verification-only introspection tool requires its own exact package and supply-chain review and may compare observed schema to the committed manifest, but cannot rewrite accepted history or mutate production.

### Schema compatibility, deployment, and readiness

Schema evolution follows `expand -> backfill/switch -> contract`:

1. **Expand:** add backwards-compatible nullable structures, defaults, indexes, or dual-read/dual-write support without removing behavior required by the currently deployable artifact.
2. **Backfill and switch:** run a bounded, resumable, observable, separately authorized data transition; prove new reads/writes and staging behavior while old compatibility remains. M10 owns durable worker/idempotency machinery if the transition requires it.
3. **Contract:** remove old structures only after deployment evidence proves no rollback candidate, active runtime, job, or supported artifact still reads or writes them and M14's promotion/rollback policy authorizes the compatibility loss.

A migration is not an application release, and an application deploy is not a migration runner. M14 decides provider, roles, credentials, network, process/service count, invocation, release ordering, promotion, rollback, backup, and restore. The runtime role is logically separate from the migration role and has no DDL authority; M07 does not select concrete PostgreSQL roles or credentials.

Database readiness is bounded and mutation-free. It performs a simple database round trip through the owned pool and verifies that both ledgers exactly match the build's expected migration name, serialization version, and digest head. Missing, extra, behind, ahead, or changed schema history makes readiness false. Readiness never creates a database, takes a migration lock, migrates, repairs, backfills, or rewrites a ledger. Liveness remains independent of database availability as defined by M06.

### Explicit decision boundaries

| Milestone | Deferred decision |
| --- | --- |
| Dependency-bearing implementation | Exact manifest/lockfile edits, lifecycle-script review, source paths, database types, facades, configuration schema, executable migration files, and runtime compatibility. |
| M08 | Sessions, identity, OAuth, CSRF, credentials carried by identity operations, and authorization context. |
| M09 | Tiptap document schema, sanitization, renderer compatibility, and editor persistence operations. |
| M10 | Worker database access, scheduler, durable outbox, backfill execution, idempotency, retries across external side effects, and executable worker topology. |
| M11 | Object storage, media metadata, CDN, and media processing. |
| M12 | Concrete resources, endpoint schemas, search, pagination, cache, query shapes, cursor need, and application-level uniqueness/conflict semantics. |
| M13 | Typecheck/test tools, database fixtures, migration harnesses, commands, CI jobs, and enforcement. |
| M14 | Provider, connection values, pool numbers, PostgreSQL roles and credentials, migration invocation/deadline, process/replica count, probes, release ordering, promotion, rollback, backup, restore, and disaster recovery. |

M07 defines no database name, host, port, URL, credential, secret, provider, role name, schema or table inventory, column, index, constraint, endpoint, entity model, repository API, source path, query, migration file, seed data, tenant model, replication mode, cursor, cache, or deployed process. It does not authorize M08-M14 or any implementation.

## Consequences

- The server graph receives a small SQL-shaped type layer and one explicit pure-JavaScript PostgreSQL driver rather than an entity lifecycle or generated client.
- Exact ownership prevents route, browser, shared, and not-yet-authorized worker code from becoming persistence entry points.
- Request cancellation can ask PostgreSQL to cancel work while database-side timeouts and bounded control-client capacity prevent a JavaScript abort from being the only safety control.
- Cancellation and transaction semantics remain intentionally conservative: connection reuse waits for cleanup, acquisition cannot be claimed signal-aware, and commit ambiguity never becomes a guessed success or rollback.
- Callback-only transactions and operation-specific facades reduce escape hatches but require project-owned wrappers and more negative validation.
- Append-only source plus a second digest ledger detects changed or missing applied migrations that Kysely's name/timestamp ledger alone cannot detect.
- One master transaction and a finite advisory-lock deadline make ordinary migration failure atomic and bounded, at the cost of excluding nontransactional DDL from the normal path.
- Expand/backfill/contract creates explicit release-compatibility gates but requires additional phases and blocks destructive cleanup until deployment evidence exists.
- Readiness detects incompatible schema without mutating it; operational migration invocation and recovery stay separate.
- Exact metadata and source review narrow the implementation target but do not establish that Node 24.19.0, TypeScript 6.0.3, Kysely, node-postgres, and PostgreSQL 18.6 work together.

## Validation

M07 validation is documentation-only. No package manager, Corepack, dependency install, typecheck, build, test, linter, formatter, generator, codegen, database client, PostgreSQL server, query, migration, readiness probe, application runtime, worker, deployment, or provider command is authorized or run.

Before implementation can claim compatibility, separately authorized milestones must provide executable proof for all of the following:

- exact frozen resolution, integrity, exports, ESM loading, Node 24.19.0 engine checks, TypeScript 6.0.3 typechecking, transitive source review, provenance limits, and zero unreviewed lifecycle scripts for all three selected packages;
- a negative browser-reachability fixture and emitted-artifact scan proving Kysely, node-postgres, SQL/schema identifiers, Node built-ins, credentials, private paths, the server facade, and migration code cannot enter browser output;
- one lifecycle-owned pool/Kysely instance per server runtime; finite startup, acquisition, statement, lock, idle-in-transaction, idle-client, and shutdown bounds; required pool error handling; saturation; orderly destroy; and no per-request or leaked clients;
- PostgreSQL 18.6 codec fixtures for every selected scalar and collection representation, including range/precision edges, nullability, time zones, invalid input, and proof that no process-global parser mutation occurs;
- parameterized values, rejected input-derived identifiers, operation-specific facade results, no generic database escape hatch, and sanitized public/log output under query, constraint, connection, cancellation, migration, and credential-canary failures;
- exact propagation of the M06 `request.signal`, explicit `"cancel query"`, bounded explicit `pg.Client` control clients, independent server timeouts, cancellation before dispatch and during reads/writes, control-client exhaustion, cancellation failure, held-connection accounting until both handlers settle, no unsafe session reuse or readiness before bounded recovery, and no ordinary `"ignore query"` or `"kill session"` path;
- saturated-pool abort followed by late acquisition and release without statements; callback transaction success; statement failure and rollback; abort immediately before and after the commit fence; failed `BEGIN`, `COMMIT`, and `ROLLBACK`; connection return or removal on every path; no escaped transaction object; no same-transaction parallelism; and classified outcome ambiguity without blind retry;
- whole-transaction retry for replay-safe `40001` and selected `40P01` failures under attempt/deadline bounds, plus negative fixtures for partial-statement retry, non-replay-safe work, cancellation, and ambiguous commit;
- canonical serialization vectors, digest stability, strict ordering, duplicate names, changed applied SQL, missing/extra ledger rows, unknown/ahead/behind history, failed statements, failed ledger writes, and reread mismatch, each failing closed without repair;
- concurrent migration runners, same-session advisory lock identity, finite lock expiry without changes, transaction rollback of all pending migrations and both ledgers, guaranteed lock release, and a negative fixture proving ordinary migrations cannot enable unordered or nontransactional execution;
- a separately reviewed two-phase fixture before any nontransactional DDL can run;
- expand/backfill/switch/contract compatibility with the previous and new artifact, staged promotion, rollback-candidate inventory, resumable backfill, and a destructive-change gate that fails while an old consumer remains; and
- bounded, mutation-free readiness for healthy, unavailable, behind, ahead, missing, extra, and digest-mismatched database states, with liveness unaffected and no startup/readiness migration or repair.

M13 chooses tools, commands, fixtures, PostgreSQL service setup, CI jobs, and enforcement. M14 supplies valid operational values and topology. Listing these behaviors creates blocking validation debt; it does not authorize implementation or claim that a proof has passed.

## Risks

- Kysely 0.29 cancellation is new and patch history already contains control-client and cleanup corrections. Exact pins, source review, stress fixtures, and conservative connection accounting control that risk.
- A cancellation storm can consume connection headroom outside the ordinary pool. A dedicated bounded concurrency budget and server timeouts are mandatory.
- Request abort cannot cancel Kysely's pool acquisition or transaction control statements directly, and commit can become outcome-ambiguous. The project wrapper narrows claims and keeps late work tracked through cleanup.
- A project-owned facade, transaction wrapper, migration provider, adapter, digest ledger, and canonical serializer are security- and durability-sensitive code. Golden vectors, failure injection, concurrency tests, and strict encapsulation are blocking before runtime acceptance.
- TypeScript database types can lie about node-postgres runtime codecs. Pool-local codec fixtures and no global parser mutation keep the type boundary honest.
- Long transactions or schema locks can disrupt production even when atomic. Finite timeouts, staged evidence, compatibility sequencing, and separately governed nontransactional maintenance limit the blast radius.
- Advisory locks are cooperative. Any alternate migration tool or manual DDL path can bypass them, so production schema mutation must have one operational owner under M14.
- Append-only digests detect drift but do not prove SQL correctness, data preservation, performance, or reversibility. Review, staging, backup, restore, and forward repair remain required.
- Expand/backfill/contract can still fail if old artifacts or jobs are misidentified. Contract-phase evidence must include every active and rollback-capable consumer.
- Exact-head readiness intentionally makes an artifact for an earlier migration head unready after a later head appears. M14 release ordering must account for that fail-closed behavior; expand/backfill/contract does not by itself claim mixed-head rolling readiness.
- Exact registry integrity does not establish full provenance. The Kysely attestation was not validated, node-postgres tags are unsigned, and `@types/pg` lacks a per-package immutable source identity.

## Follow-ups

- After independent review and explicit Control Tower acceptance, a separately authorized M07-A1 may accept this ADR, update the architecture summary and backlog, and record the lifecycle transition. M07 itself does not accept the decision.
- A later dependency-bearing milestone must recheck the exact artifacts and security state, add only the three accepted packages to the server owner, update the frozen lockfile, inspect lifecycle scripts and the transitive graph, and implement the persistence and migration boundaries without an implicit extra package.
- M08-M12 must define identity, editor, worker/backfill/outbox, media, resource, query, search, pagination, and cache contracts without bypassing the persistence facade or weakening transaction, migration, readiness, or public-error boundaries.
- M13 must turn every validation item above into executable typecheck, PostgreSQL 18.6 integration, failure-injection, concurrency, browser-boundary, migration, compatibility, and CI evidence.
- M14 must select provider and operational values, allocate connection budgets, create separate runtime/migration privileges, define migration invocation and schema/application ordering, and prove staging-first promotion, rollback limits, backup, restore, and disaster recovery.
- A different ORM, driver, cursor, generator, schema authority, migration runner, global codec, transaction API, nontransactional path, database-access owner, or schema compatibility protocol requires new evidence and, if it changes this decision, a superseding ADR.

## Supersedes / Superseded by

None.
