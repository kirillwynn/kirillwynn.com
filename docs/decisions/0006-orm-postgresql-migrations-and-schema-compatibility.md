# 0006: ORM, PostgreSQL Migrations, and Schema Compatibility

- **Status:** Accepted
- **Date:** 2026-08-23
- **Owners:** Control Tower

## Context

[ADR 0001](0001-version-baseline-and-update-policy.md) accepts Node.js 24.19.0, PostgreSQL 18.6, TypeScript 6.0.3, ESM, and exact direct dependency pins. [ADR 0002](0002-react-router-ssr-runtime-deployment-model.md) accepts a portable Web `Request` to `Response` boundary and keeps database access server-only. [ADR 0003](0003-bundler-build-development-model.md) requires the browser graph to fail closed against database packages and other server-only reachability. [ADR 0004](0004-repository-package-runtime-topology.md) assigns the Node persistence graph and its direct runtime dependencies to the future `packages/server` workspace; `packages/shared`, `packages/web`, and the future worker cannot own or import that graph. [ADR 0005](0005-backend-api-framework-and-contracts.md) carries the exact application `request.signal` to downstream work and leaves database driver behavior, transactions, cancellation, migrations, and database readiness to M07.

M07 selects a typed PostgreSQL access layer and makes its ownership, pool, query, cancellation, transaction, migration, schema-compatibility, and readiness contracts precise enough for later implementation and executable validation. The initial independent M07 Reviewer returned `Remediation required` with **P0/P1/P2 = 0/3/0**. M07-R1 addressed those findings, and its independent Reviewer returned `Accepted` with **P0/P1/P2 = 0/0/0**. Control Tower accepted M07 on 2026-08-24; M07-A1 records that lifecycle decision without revisiting technical content, authorizing implementation or M08, or claiming runtime compatibility. The accepted result remains documentation only: it adds no dependency, manifest, lockfile, configuration, schema, migration, source, script, workflow, generated artifact, database, or runtime claim.

Official primary evidence was checked at the single cutoff **2026-08-23T16:25:28Z**. Exact registry documents and immutable tagged source identify published artifacts; rolling official documentation describes behavior visible at the cutoff and can later change. Published engine, export, dependency, and type metadata establishes only a compatibility envelope. It does not prove installation, typechecking, pooling, queries, cancellation, transactions, migrations, PostgreSQL 18.6 behavior, security, or runtime compatibility.

### Official evidence matrix

| Claim | Direct official source | Evidence class and exact identity | Exact verified result |
| --- | --- | --- | --- |
| Kysely has an exact stable artifact inside the accepted Node and TypeScript envelope. | [registry](https://registry.npmjs.org/kysely/0.29.5), [release](https://github.com/kysely-org/kysely/releases/tag/v0.29.5), [tag ref](https://api.github.com/repos/kysely-org/kysely/git/ref/tags/v0.29.5), [manifest](https://github.com/kysely-org/kysely/blob/f24018c789c3cf7ad03ccc672ada63a1ded87f88/package.json) | Exact metadata and tagged source: `kysely@0.29.5`; annotated tag object `a297ee6aa7c0485a76b05a53defb2000f6c61eed`; commit `f24018c789c3cf7ad03ccc672ada63a1ded87f88` | ESM-only; Node `>=22`; zero runtime dependencies; tagged development matrix includes TypeScript 6.0.3. The annotated tag is unsigned; GitHub reports the commit signature as verified. |
| The selected Kysely patch carries the required cancellation and security posture, but its stock cancellation lifecycle is insufficient here. | [0.29.0 release](https://github.com/kysely-org/kysely/releases/tag/v0.29.0), [0.29.4 release](https://github.com/kysely-org/kysely/releases/tag/v0.29.4), [0.29.5 release](https://github.com/kysely-org/kysely/releases/tag/v0.29.5), [query executor](https://github.com/kysely-org/kysely/blob/f24018c789c3cf7ad03ccc672ada63a1ded87f88/src/query-executor/query-executor-base.ts#L73-L156), [runtime driver](https://github.com/kysely-org/kysely/blob/f24018c789c3cf7ad03ccc672ada63a1ded87f88/src/driver/runtime-driver.ts#L59-L95), [PostgreSQL cancellation](https://github.com/kysely-org/kysely/blob/f24018c789c3cf7ad03ccc672ada63a1ded87f88/src/dialect/postgres/postgres-driver.ts#L282-L325), [abort logging](https://github.com/kysely-org/kysely/blob/f24018c789c3cf7ad03ccc672ada63a1ded87f88/src/util/abort.ts#L158-L163), [JSON-path advisory](https://github.com/kysely-org/kysely/security/advisories/GHSA-wmrf-hv6w-mr66) | Immutable release history and tagged source at `f24018c...`, plus the official advisory | 0.29 introduced query signals; 0.29.4 fixed control-client password propagation; 0.29.5 fixed missing abort-handler callbacks. The selected patch is outside the JSON-path advisory's affected range. The stock path does not await physical `controlClient.end()` settlement or require the cancellation row's boolean to be true; abort/acquisition cleanup can detach and route failures to raw `console.error`; the project cannot use that path. |
| Kysely exposes the interfaces required for a project-owned runtime assembly. | [public exports](https://github.com/kysely-org/kysely/blob/f24018c789c3cf7ad03ccc672ada63a1ded87f88/src/index.ts#L45-L106), [constructor assembly](https://github.com/kysely-org/kysely/blob/f24018c789c3cf7ad03ccc672ada63a1ded87f88/src/kysely.ts#L103-L136) | Immutable tagged source at `f24018c...` | Public exports include the executor, driver, connection, dialect, adapter, compiler, introspector, and `KyselyProps` contracts needed to replace the stock runtime cancellation path without private imports or package patches. |
| Callback transactions provide a provider-level release path but no transaction-level signal option. | [transaction implementation](https://github.com/kysely-org/kysely/blob/f24018c789c3cf7ad03ccc672ada63a1ded87f88/src/kysely.ts#L862-L1076), [open ControlledTransaction issue](https://github.com/kysely-org/kysely/issues/1990) | Immutable tagged source plus rolling official issue state | `TransactionBuilder.execute(callback)` has no options parameter and releases through provider cleanup. The controlled transaction path can bypass release when `BEGIN`, `COMMIT`, or `ROLLBACK` throws. |
| Core Kysely bootstraps migration metadata before invoking its adapter lock. | [metadata bootstrap](https://github.com/kysely-org/kysely/blob/f24018c789c3cf7ad03ccc672ada63a1ded87f88/src/migration/migrator.ts#L314-L327), [lock and transaction path](https://github.com/kysely-org/kysely/blob/f24018c789c3cf7ad03ccc672ada63a1ded87f88/src/migration/migrator.ts#L540-L579), [PostgreSQL adapter](https://github.com/kysely-org/kysely/blob/f24018c789c3cf7ad03ccc672ada63a1ded87f88/src/dialect/postgres/postgres-adapter.ts#L5-L39) | Immutable tagged source at `f24018c...` | The built-in metadata creation precedes `acquireMigrationLock`. A project session lock must therefore fence metadata inspection and mutation before `Migrator` begins; the adapter lock remains an inner transaction lock. |
| The selected node-postgres artifact is compatible by metadata and supplies no bundled declarations. | [registry](https://registry.npmjs.org/pg/8.23.0), [tag ref](https://api.github.com/repos/brianc/node-postgres/git/ref/tags/pg%408.23.0), [manifest](https://github.com/brianc/node-postgres/blob/df274d1ba9ad9d11a8f1079314faeafde7208207/packages/pg/package.json) | Exact metadata and tagged source: `pg@8.23.0`; annotated tag object `f6ae396d9e638a182bd61998f0ea1850d475dd57`; commit and npm `gitHead` `df274d1ba9ad9d11a8f1079314faeafde7208207` | Node `>=16`; ESM import target plus CommonJS; six runtime dependencies; no bundled TypeScript declarations. `pg-native` is an optional peer and is not selected. The tag and commit are unsigned. |
| The exact node-postgres declarations require a separate type-only package. | [registry](https://registry.npmjs.org/%40types%2Fpg/8.23.1) | Exact registry metadata: `@types/pg@8.23.1`; DefinitelyTyped `ts6.0` line | Exact declarations are available through `pg-types`, `@types/node`, and `pg-protocol` declaration dependencies, but no immutable per-package tag or npm `gitHead` was established; that is a provenance limit rather than runtime code. |
| A cancellation control-client shutdown is owned work rather than a fire-and-forget call. | [`Client.end`](https://github.com/brianc/node-postgres/blob/df274d1ba9ad9d11a8f1079314faeafde7208207/packages/pg/lib/client.js#L781-L817) | Immutable tagged source at `df274d1...` | `Client.end()` returns the connection-end promise; a deadline can bound an owner's wait but cannot prove that the underlying socket has physically settled. The project must await or retain ownership of that promise. |
| Pool acquisition, lifecycle, and background failures require explicit ownership. | [Pool API](https://node-postgres.com/apis/pool), [pool sizing guide](https://node-postgres.com/guides/pool-sizing) | Rolling official node-postgres documentation | A pool has finite sizing and acquisition controls only when configured; checked-out clients must be released; idle-client errors require a listener; total capacity depends on every application instance and other consumers. |
| Query values are parameterized while identifiers and PostgreSQL codecs remain project concerns. | [queries](https://node-postgres.com/features/queries), [data types](https://node-postgres.com/features/types) | Rolling official node-postgres documentation | Parameter placeholders protect values, not dynamic identifiers. Unmapped values and PostgreSQL numeric/time types require an explicit application type/codec contract. |
| PostgreSQL supplies independent server-side timeout backstops. | [client timeout settings](https://www.postgresql.org/docs/18/runtime-config-client.html) | Versioned PostgreSQL 18 documentation | Positive finite `transaction_timeout`, `statement_timeout`, `lock_timeout`, and `idle_in_transaction_session_timeout` bound distinct failure modes and cannot be replaced by a JavaScript signal alone. |
| PostgreSQL advisory-lock polling can fence metadata bootstrap under a finite deadline. | [advisory-lock functions](https://www.postgresql.org/docs/18/functions-admin.html) | Versioned PostgreSQL 18 documentation | `pg_try_advisory_lock` is session-scoped and returns immediately; `pg_try_advisory_xact_lock` is transaction-scoped. They share one lock namespace and permit an outer same-session fence plus an inner transaction lock. |
| RFC 8785 defines a deterministic JSON representation for hashing. | [JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785) | Immutable standards-track RFC 8785 | JCS canonicalizes JSON-compatible values into deterministic bytes; closed tuple validation and explicit UTF-8/BOM rules remain project obligations before hashing. |
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
| `kysely@0.29.5`, `pg@8.23.0`, and `@types/pg@8.23.1` | Small ESM typed-SQL layer; zero Kysely runtime dependencies; explicit external pool; public driver/executor extension surface; core transactional migrator | Stock cancellation and migration-lock ordering are insufficient; no code generator or digest ledger; no named prepared-plan cache; project driver, compiler, runner, and failure ownership remain substantial | Selected with the contracts below. |
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

Every request-scoped query and raw statement receives the exact application `request.signal` retained by M06 and the explicit semantic `inflightQueryAbortStrategy: "cancel query"`. The default `"ignore query"` behavior is prohibited. The facade passes that signal unchanged; narrower database bounds use the operation's existing deadline and project-owned database/server timeout controls rather than replacing or composing a different query signal. `"kill session"` is prohibited for ordinary request cancellation and reserved for separately proven bounded shutdown or recovery.

The runtime `Kysely<Database>` is constructed through the public `KyselyProps` extension surface with a project-owned `QueryExecutor`, `Driver`, `DatabaseConnection`, and `Dialect`. The custom dialect composes the public PostgreSQL adapter, compiler, and introspector contracts, while the project driver and connection own query dispatch, session identity, cancellation, release, and destruction. Runtime assembly must not instantiate the stock `PostgresDialect`, `PostgresDriver`, `DefaultQueryExecutor`, `QueryExecutorBase`, or stock `RuntimeDriver`; import a private Kysely path; monkey-patch an object; or patch the package. If the exact public exports cannot implement this contract, implementation stops for a new decision instead of falling back to stock or private behavior.

Each request-scoped database operation owns a lease containing opaque correlation, the exact M06 signal, pinned main-session identity and generation, the main-query promise, any control job, and one terminal classification. Cancellation has this lifecycle:

1. An already-aborted signal performs no acquisition, query, or cancellation. Pool acquisition remains finite and owned; a client acquired after abort runs no statement and is released or destroyed through the tracked lease.
2. Once dispatch starts, the main session is unavailable for reuse until the cleanup fence opens. The exact backend identity used for cancellation must match the lease's pinned live session and generation.
3. Before constructing an explicit `pg.Client`, the lease acquires a permit from a dedicated bounded cancellation semaphore. Control clients never use the ordinary application pool and cannot exceed their reserved connection budget.
4. The control client issues one parameterized `pg_cancel_backend($1)` request. Success requires exactly one row and `cancelled === true`; an empty, additional, malformed, or false result is cancellation failure.
5. The main query, control connect/query, and `Client.end()` each have an owner. `Client.end()` is actually awaited, and neither its semaphore permit nor its registry entry is released before physical settlement. No promise is fire-and-forget.
6. A finite deadline bounds how long the caller or shutdown owner waits, but cannot turn an unsettled socket close into a bounded-teardown claim. Overdue jobs transfer to a lifecycle-root registry that continues observing them.
7. The cleanup fence opens only after all main-query, control, and `Client.end()` work settles, or after the main session is irreversibly quarantined, destruction has been requested, and every overdue job has transferred to the root registry.
8. For an in-flight transaction statement, ordinary rollback may begin only after `cancelled === true` and main/control work has settled. A false result, error, timeout, backend-identity mismatch, or ambiguous control outcome permits no further SQL, including `ROLLBACK`; the main session is quarantined and destroyed, and connection close supplies PostgreSQL rollback.
9. An aborted autocommit operation conservatively destroys its main session even after successful cancellation. It cannot return that session to the pool on a best-effort cleanliness assumption.
10. Any overdue root-registry entry makes database admission and readiness fail closed until it settles or M14's process-replacement boundary takes ownership. Server-side timeouts remain independent backstops.

Quarantine is irreversible for that lease generation. The project driver marks the client ineligible for ordinary release, requests destructive pool release exactly once, and observes the pool's removal event; until removal is observed, the lifecycle record remains root-owned and readiness remains false. A destroy request or void release call alone is not evidence of physical removal.

The project observer accepts only allowlisted category, phase, outcome, duration, and opaque correlation. Neither that observer, public responses, nor ordinary logs may receive a raw `Error`, message, cause, stack, SQL, parameters, backend PID, host, port, database, schema, table, constraint, connection configuration, URL, or credential. The stable M06 public problem contract remains the only HTTP representation of these failures.

### Transaction and retry contract

Only a project-owned wrapper over `db.transaction().execute(callback)` is allowed. `startTransaction()`, `ControlledTransaction`, transaction objects that escape their callback, unmanaged clients, and parallel statements on the same transaction are prohibited.

The wrapper has these exact semantics:

1. Check the exact request signal before starting acquisition, immediately on callback entry, before every statement, and immediately before the commit fence.
2. Every statement inside the callback goes through the same signal-injecting facade with `"cancel query"`; direct query-builder execution is unavailable to callers.
3. Abort before the commit fence throws inside the callback. With no in-flight statement, the project driver performs non-abortable rollback. With an in-flight statement, the execute path does not return to Kysely until the cancellation cleanup fence allows ordinary rollback or has quarantined and destroyed the session; a quarantined session receives no rollback SQL.
4. An abort while waiting for a saturated pool cannot make transaction acquisition itself signal-aware at this version. The finite acquisition deadline remains the outer bound. If a connection arrives after the abort, the entry guard executes no application statement, cleanup releases it, and the wrapper settles only after that tracked cleanup rather than detaching the acquisition promise.
5. Once `COMMIT` starts, the wrapper cannot truthfully report that the transaction rolled back. It awaits and classifies the result. Lost transport or timeout during commit is outcome ambiguity: no blind retry, success response, or compensating assumption is allowed.
6. Safe-path rollback and connection cleanup are non-abortable infrastructure work with their own bound. Rollback failure quarantines and destroys the session; unresolved cleanup enters the root registry and keeps database admission and readiness fail closed rather than claiming safe reuse.
7. Transaction-local domain results are returned only after a confirmed commit. No external side effect is performed inside a replayable database transaction unless a later durable-idempotency contract, owned by M10, makes replay safe.

Automatic retry is opt-in per operation. It retries the complete callback, including fresh reads, only for SQLSTATE `40001` and explicitly classified `40P01`, only when the operation declares database replay safety, and only under a finite attempt count, jittered backoff, and the original operation deadline. It never retries statement fragments, validation errors, cancellation, connection loss during commit, or another ambiguous outcome.

### Migration source, ledger, and locking

The core Kysely `Migrator` is used only behind a project-owned strict provider, PostgreSQL migration adapter, and runner. `FileMigrationProvider`, filesystem enumeration order, schema synchronization, schema push, automatic startup migration, and production `down` are not sufficient or permitted.

The canonical source is an append-only ordered manifest whose definitions use this exact fail-closed envelope:

```text
[
  "migration-v2",
  <immutable ASCII migration name>,
  "operation-catalog-v0",
  <operations>,
  <compiledFingerprints>
]
```

For `operation-catalog-v0`, both `operations` and `compiledFingerprints` are exactly empty arrays. The initial operation union is deliberately empty: a non-empty operation, executable migration, or dependency-bearing implementation requires a separately reviewed contract first. Raw SQL or text, a statement array, callback, function, generic expression or query builder, arbitrary object, transaction/session command, and any descriptor that performs multiple operations are not representable. A definition imports no current application, entity, query-facade, generated database, environment, or network code.

Each envelope is recursively frozen and encoded as UTF-8 without BOM using [RFC 8785 JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785). Unknown, extra, reordered, differently typed, or non-canonical elements are rejected. SHA-256 covers the exact canonical bytes; the persisted form is `sha256:` followed by 64 lowercase hexadecimal characters. Names compare in bytewise lexical order, are unique, never reused, and identify forward-only `up` behavior. A format or catalog version is append-only and never reinterpreted.

The first future non-empty catalog must define a closed tagged-tuple union with exact field types and an exhaustive project compiler mapping each descriptor to exactly one public, non-raw Kysely builder operation and one driver dispatch. Its `compiledFingerprints` must commit, in operation order, to the exact compiled SQL string and canonical parameter values produced by that accepted compiler. Those fingerprints are drift evidence only and can never be executed as the migration source. A Kysely or compiler upgrade must reproduce every accepted fingerprint or preserve its old mapping; otherwise the upgrade stops for review.

The provider validates manifest membership, unique names, strict order, envelope and catalog versions, canonical encoding, digests, and compiled evidence before exposing forward-only `up` closures. In addition to Kysely's name/timestamp history, a project-owned digest ledger records the migration name, format/catalog versions, and digest. Missing, extra, changed, duplicated, reordered, malformed, or unknown history is fatal and cannot be repaired automatically.

The migration runner binds a migration-only Kysely instance to one already checked-out `pg.Client`; every lock, inspection, transaction, mutation, reread, and release action uses that pinned PostgreSQL session. Before any database mutation it validates the complete manifest, canonical digests, and compiler fingerprints. It then executes this exact protocol:

1. Record the pinned session identity and acquire the session-scoped outer lock by polling `pg_try_advisory_lock(3853314791062309107)` only until a monotonic absolute deadline. Deadline expiry performs no database mutation. The numeric duration is deferred to M14 but must be finite and positive.
2. After the outer lock is held, classify migration metadata as exactly one state. **Virgin** means all three M07 metadata tables and the required lock row are absent. **Established** means the Kysely history table, Kysely lock table and required row, and project digest ledger are all present with the exact accepted shape and history. Partial, malformed, missing-row, extra-row, or mixed state is fatal and receives no automatic repair. Unrelated objects already present in the configured schema do not by themselves make the state partial.
3. Open one callback transaction on the same pinned session. Inside that transaction, create all missing M07 metadata for virgin state, create none for established state, and construct the core `Migrator` with that transaction as `db`.
4. The custom migration adapter acquires its inner lock with `pg_try_advisory_xact_lock(3853314791062309107)` on that session and requires exactly one boolean `true` result. Its release hook is a deliberate no-op because PostgreSQL releases the transaction-level lock at commit or rollback.
5. Keep `allowUnorderedMigrations` false and `disableTransactions` false. Bootstrap, every pending forward operation, each digest row, Kysely history, and the exact final ledger reread occur in the one master transaction. The reread must match the immutable manifest before the callback may return.
6. Convert every thrown error, `MigrationResultSet.error`, non-success status, state mismatch, digest mismatch, lock fault, or reread mismatch to an exception before commit. No failure path reports success or repairs history.
7. Hold the outer session lock through confirmed commit or rollback and the final transactional reread. A transaction outcome ambiguity, unexpected backend identity, or inability to prove the pinned session remains live poisons the migration session and forbids reuse.
8. On release, make exactly one parameterized `pg_advisory_unlock` attempt for this lock key on the same verified session and require exactly one boolean `true` result. Never retry an ambiguous unlock. A false, empty, extra, malformed, failed, impossible, or identity-mismatched release closes the poisoned session without reuse.

The migration session applies finite positive `transaction_timeout`, `statement_timeout`, `lock_timeout`, and `idle_in_transaction_session_timeout`. Kysely's stock one-hour lock wait is never the effective project bound. M14 selects exact timeout and invocation values but cannot make them zero or unbounded, weaken the pinned-session protocol, or run competing automatic migrators.

Nontransactional DDL such as `CREATE INDEX CONCURRENTLY` is prohibited on this ordinary path. If a later change requires it, a separately reviewed two-phase maintenance operation must define its own lock, durable phase ledger, observation, retry, repair, old/new artifact compatibility, and acceptance evidence. It cannot enable `disableTransactions` globally.

Introspection and code generation are not schema authorities. No generator is selected. A later verification-only introspection tool requires its own exact package and supply-chain review and may compare observed schema to the committed manifest, but cannot rewrite accepted history or mutate production.

### Schema compatibility, deployment, and readiness

Schema evolution follows `expand -> backfill/switch -> contract`:

1. **Expand:** add backwards-compatible nullable structures, defaults, indexes, or dual-read/dual-write support without removing behavior required by the currently deployable artifact.
2. **Backfill and switch:** run a bounded, resumable, observable, separately authorized data transition; prove new reads/writes and staging behavior while old compatibility remains. M10 owns durable worker/idempotency machinery if the transition requires it.
3. **Contract:** remove old structures only after deployment evidence proves no rollback candidate, active runtime, job, or supported artifact still reads or writes them and M14's promotion/rollback policy authorizes the compatibility loss.

A migration is not an application release, and an application deploy is not a migration runner. M14 decides provider, roles, credentials, network, process/service count, invocation, release ordering, promotion, rollback, backup, and restore. The runtime role is logically separate from the migration role and has no DDL authority; M07 does not select concrete PostgreSQL roles or credentials.

Database readiness is bounded and mutation-free. It performs a simple database round trip through the owned pool and verifies that Kysely history and the digest ledger exactly match the build's expected migration name, envelope/catalog versions, and digest head. Missing, extra, behind, ahead, malformed, or changed schema history makes readiness false. Readiness also fails while the cancellation root registry is non-empty. It never creates a database, takes a migration lock, migrates, repairs, backfills, rewrites a ledger, or drains cancellation work. Liveness remains independent of database availability as defined by M06.

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
- Request cancellation can ask PostgreSQL to cancel work without relying on Kysely's detached stock path; public extension interfaces preserve the selected query layer while making every main/control/close promise project-owned.
- Cancellation and transaction semantics remain intentionally conservative: aborted autocommit sessions are destroyed, ambiguous cancellation prohibits rollback SQL, overdue cleanup fails admission/readiness closed, acquisition cannot be claimed signal-aware, and commit ambiguity never becomes a guessed success or rollback.
- Callback-only transactions and operation-specific facades reduce escape hatches but require project-owned wrappers and more negative validation.
- The closed `migration-v2` envelope removes raw and multi-statement execution escape hatches and supplies deterministic drift evidence, but its empty initial catalog intentionally blocks executable migrations until a further reviewed operation catalog exists.
- An outer pinned-session lock fences Kysely metadata bootstrap; the inner transaction lock, state vector, master transaction, digest ledger, and finite deadlines make ordinary migration failure atomic and fail closed, at the cost of a substantial project-owned runner and exclusion of nontransactional DDL.
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
- a structural/runtime negative proof that application assembly reaches only the project `KyselyProps`, `QueryExecutor`, `Driver`, `DatabaseConnection`, and custom `Dialect` path; stock `PostgresDialect`, `PostgresDriver`, `DefaultQueryExecutor`, `QueryExecutorBase`, stock `RuntimeDriver`, private Kysely imports, monkey patches, and package patches must be unreachable;
- exact propagation of the M06 `request.signal`; cancellation before dispatch and during query dispatch; saturated-pool abort and late acquisition with zero statements; cancel results that are true, false, empty, extra, malformed, rejected, timed out, or backend-identity mismatched; and no ordinary `"ignore query"` or `"kill session"` path;
- bounded cancellation-semaphore exhaustion; delayed, rejecting, and never-settling control connect/query and `Client.end()` promises; ownership after caller deadline; no rollback, release, or reuse before the cleanup fence; autocommit destruction; quarantine, exactly-once destructive release, observed pool removal, and no reuse; root-registry transfer; database admission/readiness failure while overdue work exists; and orderly shutdown accounting with no fire-and-forget promise;
- observer and logging canaries proving zero raw `console.error`, unhandled rejection, `Error`, message, cause, stack, SQL, parameter, backend PID, connection field, private path, or credential reaches public or ordinary diagnostic output;
- callback transaction success; statement failure and safe rollback; abort immediately before and after the commit fence; cancel failure with connection-close rollback and no rollback SQL; failed `BEGIN`, `COMMIT`, and `ROLLBACK`; connection return or removal on every path; no escaped transaction object; no same-transaction parallelism; and classified outcome ambiguity without blind retry;
- whole-transaction retry for replay-safe `40001` and selected `40P01` failures under attempt/deadline bounds, plus negative fixtures for partial-statement retry, non-replay-safe work, cancellation, and ambiguous commit;
- RFC 8785/JCS golden vectors, UTF-8/BOM handling, recursive freeze, digest stability, compiled-fingerprint drift, strict order, duplicates and unknown fields; rejection of every non-empty `operation-catalog-v0`, raw or multi-statement SQL, generic builder/callback/object escape, and transaction/session command;
- virgin, established, partial, malformed, missing-lock-row, and unrelated-object metadata states; concurrent runners; the exact same backend PID across outer lock, inspection, bootstrap, migration, reread, and unlock; finite outer-lock expiry with zero mutations; and exact inner transaction-lock acquisition/release semantics;
- bootstrap, migration, Kysely-history, digest-ledger, reread, commit, rollback, and outer-unlock failure injection; atomic rollback of metadata and all pending work; false, malformed, ambiguous, and identity-mismatched unlock; session poison/close/no-reuse; and no automatic history repair;
- a separately reviewed two-phase fixture before any nontransactional DDL can run;
- expand/backfill/switch/contract compatibility with the previous and new artifact, staged promotion, rollback-candidate inventory, resumable backfill, and a destructive-change gate that fails while an old consumer remains; and
- bounded, mutation-free readiness for healthy, unavailable, behind, ahead, missing, extra, and digest-mismatched database states, with liveness unaffected and no startup/readiness migration or repair.

M13 chooses tools, commands, fixtures, PostgreSQL service setup, CI jobs, and enforcement. M14 supplies valid operational values and topology. Listing these behaviors creates blocking validation debt; it does not authorize implementation or claim that a proof has passed.

## Risks

- Kysely 0.29 cancellation is new and its stock detached cleanup does not satisfy this lifecycle. The public custom executor/driver/connection assembly is larger, security-sensitive, and coupled to exact exported interfaces; an export or semantic change stops implementation rather than enabling a private fallback.
- A cancellation storm can consume connection headroom outside the ordinary pool. A dedicated bounded concurrency budget and server timeouts are mandatory.
- Request abort cannot cancel pool acquisition or transaction control statements directly, and a deadline cannot prove physical socket teardown. The root registry and quarantine policy trade availability for no detached or unsafely reused database work; commit can still become outcome-ambiguous.
- A project-owned facade, transaction wrapper, migration provider, outer/inner lock adapter, operation compiler, digest ledger, JCS encoder, and observer are security- and durability-sensitive code. Golden vectors, failure injection, concurrency tests, and strict encapsulation are blocking before runtime acceptance.
- The empty `operation-catalog-v0` deliberately cannot express the first schema operation. That implementation remains blocked until a reviewed closed catalog and compiler fingerprint contract exists.
- TypeScript database types can lie about node-postgres runtime codecs. Pool-local codec fixtures and no global parser mutation keep the type boundary honest.
- Long transactions or schema locks can disrupt production even when atomic. Finite timeouts, staged evidence, compatibility sequencing, and separately governed nontransactional maintenance limit the blast radius.
- Advisory locks are cooperative, and the exact key `3853314791062309107` must have one owner in the selected database. An alternate migration tool, colliding lock user, or manual DDL path can bypass or interfere with the protocol, so production schema mutation has one operational owner under M14.
- Append-only digests detect drift but do not prove SQL correctness, data preservation, performance, or reversibility. Review, staging, backup, restore, and forward repair remain required.
- Expand/backfill/contract can still fail if old artifacts or jobs are misidentified. Contract-phase evidence must include every active and rollback-capable consumer.
- Exact-head readiness intentionally makes an artifact for an earlier migration head unready after a later head appears. M14 release ordering must account for that fail-closed behavior; expand/backfill/contract does not by itself claim mixed-head rolling readiness.
- Exact registry integrity does not establish full provenance. The Kysely attestation was not validated, node-postgres tags are unsigned, and `@types/pg` lacks a per-package immutable source identity.

## Follow-ups

- The initial independent M07 Reviewer returned `Remediation required` with **P0/P1/P2 = 0/3/0**. M07-R1 addressed all three findings, and its independent Reviewer returned `Accepted` with **P0/P1/P2 = 0/0/0**. Control Tower accepted M07 separately on 2026-08-24; M07-A1 records that decision without revisiting technical content, authorizing implementation or M08, or claiming runtime compatibility.
- A later dependency-bearing milestone must recheck the exact artifacts, public extension exports, and security state; add only the three accepted packages to the server owner; update the frozen lockfile; inspect lifecycle scripts and the transitive graph; and implement the persistence lifecycle without an implicit extra package or stock/private cancellation fallback.
- Before any executable migration exists, a separate review must replace the empty `operation-catalog-v0` with a closed append-only operation catalog, exhaustive public Kysely compiler mapping, and accepted compiled-fingerprint golden vectors. This ADR authorizes none of those operations.
- M08-M12 must define identity, editor, worker/backfill/outbox, media, resource, query, search, pagination, and cache contracts without bypassing the persistence facade or weakening transaction, migration, readiness, or public-error boundaries.
- M13 must turn every validation item above into executable typecheck, PostgreSQL 18.6 integration, failure-injection, concurrency, browser-boundary, migration, compatibility, and CI evidence.
- M14 must select provider and operational values, allocate connection budgets, create separate runtime/migration privileges, define migration invocation and schema/application ordering, and prove staging-first promotion, rollback limits, backup, restore, and disaster recovery.
- A different ORM, driver, cursor, generator, schema authority, migration runner, global codec, transaction API, nontransactional path, database-access owner, or schema compatibility protocol requires new evidence and, if it changes this decision, a superseding ADR.

## Supersedes / Superseded by

None.
