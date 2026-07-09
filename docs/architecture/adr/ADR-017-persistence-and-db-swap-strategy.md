# ADR-017: Persistence & DB Swap Strategy

- **Status:** Accepted — *SQLite-first, ORM-isolated, PostgreSQL-ready; ownership scoping, soft-delete, and app-level encryption ratified*
- **Date:** 2026-07-09
- **Deciders:** Architecture Review Board
- **Related:** ADR-001, ADR-003, ADR-013, ADR-015

## 1. Context

The persistence strategy must serve Zero-Cost/Local-First now while keeping a credible path to PostgreSQL/multi-user later. `design.md` §4/§8 specifies: SQLite default, single `DATABASE_URL` swap to PostgreSQL, ORM-only (no raw SQL) to isolate dialect differences, UUID PKs, JSON columns, soft-delete with defined cascade rules, app-level symmetric encryption for secrets, and an ownership-scoping model.

The Board must ratify these and settle one subtlety the design itself corrected: **where `user_id` lives.** The naive "every table has `user_id`" is both false to the ERD and partly undesirable; the design's refinement (aggregate roots own `user_id`; children scope through parents; hot-path children denormalize `user_id`) is the right call and should be locked.

## 2. Decision

**Adopt SQLite-first, ORM-isolated persistence with a single-env-var swap to PostgreSQL, and lock the following data invariants.**

1. **SQLite for personal/local; PostgreSQL for scale.** Switch via `DATABASE_URL` only (CON-3). SQLite runs single-writer/single-worker (CON-4).
2. **ORM-only, no raw SQL** (CON-2). All queries are SQLAlchemy ORM/Core expressions so SQLite↔PostgreSQL dialect differences (UUID, JSON/JSONB, boolean, timestamp) are absorbed at the ORM layer.
3. **Ownership scoping (Property 1) via a refined model:** aggregate-root tables carry `user_id` directly; child tables scope through their parent (repository enforces via join); **hot-path children** (messages, memories, chapters) **denormalize `user_id`** for index-only isolation, kept always-consistent with the parent (write-time, immutable). Every query is user-scoped; cross-user access is impossible by construction.
4. **Soft-delete for important aggregates** (`deleted_at`) with explicitly defined cascade/propagation rules (`design.md` §4.7); child tables use explicit `ON DELETE` policies; SQLite runs with `PRAGMA foreign_keys=ON`.
5. **App-level symmetric encryption for secrets** (provider API keys, OAuth tokens) keyed by `APP_SECRET_KEY`; decryption only in backend memory at provider-call time; plaintext never in responses or logs (Property 8, ADR-011-adjacent security).
6. **Message immutability / append-only** (INV-4): edits and regenerations are new rows, never mutations — giving audit/branch history without a bus (ADR-001).
7. **Forward-only migrations** (Alembic), non-destructive (ADR-015).

## 3. Alternatives Considered

- **A. PostgreSQL from day one.**
- **B. A document/NoSQL store** (e.g. MongoDB) for schema flexibility.
- **C. Raw SQL / query builder** tuned per database.
- **D. `user_id` on every table** (uniform denormalization) — or conversely, `user_id` only on roots (no hot-path denormalization).

## 4. Why Rejected

- **A — Postgres from day one:** Requires running a server process for a single local user — violates Zero-Cost/Local-First and complicates the one-command startup. SQLite is sufficient and trivial locally; the swap path preserves the Postgres future. Rejected as the default.
- **B — NoSQL:** Sacrifices relational integrity, transactions, and the clean SQLite↔Postgres story; reintroduces schema-flexibility temptations already rejected (ADR-003 EAV). Rejected.
- **C — Raw SQL:** Dialect-couples the code, breaking the swap guarantee and CON-2. Rejected.
- **D — Uniform `user_id` everywhere / roots-only:** Uniform-everywhere is false to real ownership (children *are* owned via parents) and adds redundant columns/consistency burden on cold-path tables. Roots-only would force joins on hot read paths (messages/chapters), hurting the performance/simplicity of the most frequent isolation queries. The **hybrid** (roots + hot-path denormalization) is the pragmatic optimum. Rejected in favor of the hybrid.

## 5. Consequences

**Positive**
- Zero-cost, single-file, offline-capable local persistence; one-command startup.
- Credible, low-friction path to PostgreSQL/multi-user without code changes.
- Strong ownership isolation with good index performance on hot paths.
- Reversible deletes, auditable message history, and encrypted secrets by construction.

**Negative**
- SQLite single-writer limits concurrency (fine for one user; a ceiling for multi-user — mitigated by the Postgres path).
- Denormalized `user_id` on hot-path children must be kept consistent (write-time discipline; it is immutable, lowering risk).
- ORM-only occasionally means less-optimal queries than hand-tuned SQL (acceptable at personal scale).

**Future risks**
- Subtle SQLite/PostgreSQL behavioral differences (collation, JSON semantics, concurrency) can surface at swap time; a migration test against Postgres is advisable before relying on it.
- `APP_SECRET_KEY` loss makes encrypted data unrecoverable (CON-7); key management is a real operational responsibility even for a personal app.

## 6. Future Revisit Conditions

- Execute/validate the PostgreSQL swap before any multi-user (Phase 3) launch; revisit concurrency settings and connection pooling then.
- If personal-scale data grows large enough that SQLite performance degrades, revisit indexing or an earlier Postgres move.
- Revisit encryption approach if key rotation or hardware-backed key storage becomes a requirement.
