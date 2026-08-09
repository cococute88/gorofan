# AI Author OS / gorafan — AI Handoff

> **Canonical handoff document for a new AI session.**
>
> **Verified at:** 2026-08-09T17:15:00+09:00
> **Verified `main`:** `39cf740af3df62680e29111a9d39ed2e7c168842`

## Contents

1. [To the AI reading this](#1-to-the-ai-reading-this)
2. [Repository identity](#2-repository-identity)
3. [Document precedence](#3-document-precedence)
4. [Architecture invariants](#4-architecture-invariants)
5. [Verified completed implementation](#5-verified-completed-implementation)
6. [Code map](#6-code-map)
7. [Tests and validation baseline](#7-tests-and-validation-baseline)
8. [Environment cautions](#8-environment-cautions)
9. [Remaining Phase 1 work](#9-remaining-phase-1-work)
10. [Immediate next task: P1-7 implementation](#10-immediate-next-task-p1-7-implementation)
11. [The approved P1-7 design contract](#11-the-approved-p1-7-design-contract)
12. [First-run checklist for a new AI](#12-first-run-checklist-for-a-new-ai)
13. [Completion-report rules](#13-completion-report-rules)
14. [Copyable P1-7 implementation prompt](#14-copyable-p1-7-implementation-prompt)

## 1. To the AI reading this

This is the starting point for a new AI session. Treat the checked code, Git history, GitHub PR state, and authoritative architecture documents as stronger evidence than any prior chat, report, or this snapshot.

Before changing anything:

- Read this file **and** the relevant ADR/RFC originals in `docs/architecture/`.
- Confirm the verification timestamp and `main` SHA above.
- If `origin/main` has advanced after `39cf740af3df62680e29111a9d39ed2e7c168842`, re-verify the affected GitHub, code, task/status, and test facts before relying on this handoff.
- Do not infer implementation completion from file presence. Follow executed production paths, API exposure, and passing tests.

## 2. Repository identity

| Item | Verified value |
|---|---|
| GitHub repository | [`cococute88/gorofan`](https://github.com/cococute88/gorofan) |
| Local repository | `C:\gv\rfrf` |
| Default branch | `main` |
| Verification time | `2026-08-09T17:15:00+09:00` |
| Verified `origin/main` / local `main` | `39cf740af3df62680e29111a9d39ed2e7c168842` |
| PR #21 | [`feat(entry): wire retrieval context into generation paths`](https://github.com/cococute88/gorofan/pull/21), merged 2026-08-09 — **P1-6** |
| PR #21 merge commit | `1b2a850b2732778fecb8944f03a8d12020aa588a` |
| PR #23 | [`docs(architecture): design edit-diff capture`](https://github.com/cococute88/gorofan/pull/23), merged 2026-08-09 — **P1-7 design, approved. Documentation only.** |
| PR #23 merge commit | `39cf740af3df62680e29111a9d39ed2e7c168842` |
| PR #23 final head before merge | `8c67ab7cdfde5788498a5c259aa44febc2177bd7` |
| Open PRs at verification | None remaining for Phase 1 implementation work |
| Working tree before this documentation branch | Clean (`git status --short` produced no paths) |
| Backend | Python 3.11+; FastAPI; async SQLAlchemy 2; Alembic; SQLite-first with PostgreSQL seam; pytest, Hypothesis, Ruff, MyPy |
| Frontend | TypeScript; Next.js 14 App Router; React 18; TanStack Query; TipTap; Tailwind; Vitest; PWA |
| CI | GitHub Actions on Ubuntu, Python 3.12 and Node 20; backend + frontend jobs in `.github/workflows/ci.yml` |

GitHub REST, GitHub remote refs, and local Git agree that PR #21 and PR #23 are merged at the listed commits, and that `main` is at PR #23's merge commit. Feature PRs in this repository are **squash-merged**, with the merge commit subject `<PR title> (#N)`. GitHub CLI GraphQL repository lookup has been unreliable in this environment; use GitHub REST or `git fetch`/remote refs if that occurs again.

## 3. Document precedence

Use the repository's actual architecture precedence in this order:

1. `docs/architecture/adr/*`
2. `docs/architecture/rfc/RFC-001-Core-Architecture.md`
3. The relevant RFC after RFC-001, including `RFC-002` through `RFC-012`
4. `docs/architecture/README.md`
5. `.kiro/specs/ai-creative-workspace/implementation-status.md`
6. `.kiro/specs/ai-creative-workspace/tasks.md`
7. Historical plans, old `.kiro` design material, chat transcripts, completion reports, and informal notes

The ADRs are the architectural constitution. `RFC-001` is the system-level reference; later RFCs refine components under it. The architecture README is an onboarding map, not a higher authority. If an older `.kiro` plan conflicts with ADR/RFC architecture, **ADR/RFC wins**. In particular, do not resurrect the old separate Story Bible, Reference, or Planning engine/table direction.

## 4. Architecture invariants

Every change must preserve the following. The cited files are the governing sources, not optional background reading.

| Invariant | Required interpretation | Governing sources |
|---|---|---|
| Store → Analyst → Writer | The creative layer is Store, Analyst, Writer plus a dev-only Bench. Store persists/retrieves knowledge; Analyst turns text into proposals; Writer consumes knowledge to write. Do not create named feature engines. | `adr/ADR-001-overall-architecture-philosophy.md`, `adr/ADR-002-store-analyst-writer-architecture.md`, `rfc/RFC-001-Core-Architecture.md` |
| Everything is Entry | Creative knowledge uses the prose-first `Entry` model and governed `type` vocabulary. New knowledge kinds are new approved types, not separate knowledge tables or `misc`. True aggregates retain their own lifecycle. | `adr/ADR-003-entry-first-data-model.md`, `rfc/RFC-002-Entry-Model-Contract.md` |
| AI cannot directly edit canon | AI-derived knowledge is `proposed`; only the human review gate promotes it to canon. No silent Analyst, Writer, Chat, or Bible write path exists. | `adr/ADR-002-store-analyst-writer-architecture.md`, `adr/ADR-004-living-story-bible.md`, `adr/ADR-011-review-card-ux.md`, `rfc/RFC-011-Human-Review.md` |
| Explicit user authoring can be the human gate | Deliberate user-authored knowledge may become canon through that explicit human action; it must remain owner-scoped, server-provenanced, and use immutable supersession for corrections. | `rfc/RFC-002-Entry-Model-Contract.md`, `rfc/RFC-011-Human-Review.md` |
| Character DNA, Relationship, Story Event differ | DNA is enduring identity; a relationship is a pair's evolving shared state; Story Bible entries record what happened in one work. Momentary emotion is working knowledge, not canon. | `adr/ADR-006-relationship-system.md`, `adr/ADR-007-character-dna-philosophy.md`, `rfc/RFC-005-Story-Bible.md`, `rfc/RFC-006-Relationship.md`, `rfc/RFC-007-Character-DNA.md` |
| Relationship = Shared Narrative State | Relationship state belongs to neither individual character nor Writer; it is work-scoped shared canon read by novel and chat. | `adr/ADR-006-relationship-system.md`, `rfc/RFC-006-Relationship.md` |
| Story Bible is a canonical view | The Story Bible is the work-scoped canonical view over Entry Store data. It is not a separate table, store, service, or retriever. | `adr/ADR-004-living-story-bible.md`, `rfc/RFC-005-Story-Bible.md` |
| Character Chat is independent | Character Chat is a first-class product capability with its own generation path, not a Writer subfeature. It shares Store knowledge and the review gate. | `rfc/RFC-012-Character-Chat.md`, `adr/ADR-014-minimal-ui-philosophy.md` |
| Private Memory is separate | Chat-private `Memory` remains conversation-private and does not become an Entry. It meets shared Entry context only as a separate assembled prompt block. | `adr/ADR-003-entry-first-data-model.md`, `adr/ADR-018-memory-and-retrieval-strategy.md`, `rfc/RFC-002-Entry-Model-Contract.md`, `rfc/RFC-003-Store-Retrieval-Contract.md` |
| Retrieval and assembly are separate | `retrieve()` filters, ranks, selects whole Entries, and returns trace data; Context Assembly turns already-selected Entries into blocks. Retrieval never emits provider messages or reuses chat-private memory. | `rfc/RFC-003-Store-Retrieval-Contract.md`, `adr/ADR-009-prompt-architecture-philosophy.md`, `rfc/RFC-009-Prompt-System.md` |
| Prompt bodies are repository assets | Architecture-owned prompt body text lives in versioned files, not database `PromptTemplate` rows. Legacy PromptTemplate remains a compatibility boundary only. | `adr/ADR-013-prompt-files-vs-database.md`, `rfc/RFC-009-Prompt-System.md` |
| Bench is developer-only | Bench measures prompt/stage/retrieval changes out of band. It never gates a live user generation or becomes a runtime product path. | `adr/ADR-012-bench-evaluation-system.md`, `rfc/RFC-010-Bench.md` |
| Preserve the substrate | Reuse and wrap PromptEngine, MemoryEngine, NovelEngine, adapters, auth, PWA, and other established substrate. Do not rewrite them while adding architecture work. | `adr/ADR-001-overall-architecture-philosophy.md`, `adr/ADR-009-prompt-architecture-philosophy.md`, `rfc/RFC-001-Core-Architecture.md` |
| Preserve migrations and data | `0001_initial` is frozen. Migrations are additive and forward-only; existing data and legacy substrate remain until a separately approved compatibility transition. | `adr/ADR-017-persistence-and-db-swap-strategy.md`, `rfc/RFC-002-Entry-Model-Contract.md` |

## 5. Verified completed implementation

### Related merged PRs

All rows below were checked against GitHub REST metadata and the current code/history. The merge SHA is the GitHub merge commit on `main`.

| PR | Title | Core delivered capability | Merge commit | Current code evidence |
|---|---|---|---|---|
| [#9](https://github.com/cococute88/gorofan/pull/9) | `fix(store): harden Entry canon lifecycle before retrieval` | Canon lifecycle hardening, owner/anchor safety, atomic supersession foundations | `1c9326fb12c4dbac21c425938da6b1771abbbb46` | `backend/app/services/entry_service.py`, `backend/tests/integration/test_entry_service.py` |
| [#10](https://github.com/cococute88/gorofan/pull/10) | `feat(store): add Entry retrieval foundation` | Owner-safe, canonical-default, deterministic whole-Entry retrieval and trace | `d68ed2b42840a610715f55f2d89e0467f9885fff` | `backend/app/services/entry_retrieval.py`, `backend/app/services/entry_service.py`, retrieval tests |
| [#11](https://github.com/cococute88/gorofan/pull/11) | `feat(store): add Context Assembly bridge` | Pure selected-Entry → PromptBlock bridge, whole-block budget and independent traces | `a8955c3566b8453a7d9261209d62ec368f20c9c7` | `backend/app/engines/prompt/entry_context.py`, assembly and golden tests |
| [#14](https://github.com/cococute88/gorofan/pull/14) | `docs(spec): reconcile implementation status with frozen architecture` | Reconciled status/tasks to the frozen ADR/RFC architecture | `5a8b3f98c490e821a5f68c465459c1869436c3cb` | `.kiro/specs/ai-creative-workspace/implementation-status.md`, `tasks.md` |
| [#15](https://github.com/cococute88/gorofan/pull/15) | `feat(review): add supersede endpoint` | Review Card supersede endpoint with owner/anchor/lifecycle checks | `9aaa7ed365dcf4216b6e02d27604a01fbff7eeb2` | `backend/app/api/v1/entries.py`, `EntryService.supersede()` |
| [#16](https://github.com/cococute88/gorofan/pull/16) | `feat(prompt): add repository-managed prompt assets` | Versioned UTF-8 prompt assets and allow-listed loader/trace identity | `93231d2db6db67bc0e43ad91b7c4d4239477c06f` | `backend/prompts/`, `backend/app/engines/prompt/assets.py` |
| [#17](https://github.com/cococute88/gorofan/pull/17) | `chore(prompt): harden PromptTemplate compatibility boundary` | Repository asset authority while preserving frozen legacy PromptTemplate data/API | `4e318b33656b19e066629bba535a812b440cdb59` | `backend/app/api/v1/ai_config.py`, `backend/app/services/ai_config_service.py`, boundary test |
| [#18](https://github.com/cococute88/gorofan/pull/18) | `feat(review): add Entry Review Card frontend` | One type-agnostic review queue/card, actions and cache behavior | `170f383d707b1919be310457d48f85d7e7c87924` | `frontend/src/components/review/`, `frontend/src/hooks/use-entry-review.ts` |
| [#19](https://github.com/cococute88/gorofan/pull/19) | `feat(entry): add authoring and audit read API` | Human authoring, canon default/read history, cursor pagination, supersession-safe correction | `1a9a57e2f9653c99989c9c19355bcaba0b9a3c7c` | `backend/app/api/v1/entries.py`, Entry schema/service/repository, authoring tests |
| [#21](https://github.com/cococute88/gorofan/pull/21) | `feat(entry): wire retrieval context into generation paths` | **P1-6.** Retrieval → Context Assembly → real Chat/Novel prompt assembly behind an OFF-by-default flag; first-class `entry` PromptBlock | `1b2a850b2732778fecb8944f03a8d12020aa588a` | `backend/app/services/entry_generation_context.py`, `chat_service.py`, `novel_service.py`, `engines/prompt/blocks.py`, `engines/prompt/engine.py`, P1-6 unit/integration tests |
| [#23](https://github.com/cococute88/gorofan/pull/23) | `docs(architecture): design edit-diff capture` | **P1-7 design only — approved, zero production change.** The additive `edit_diff_captures` persistence contract, ratified by independent architecture review | `39cf740af3df62680e29111a9d39ed2e7c168842` | `docs/architecture/edit-diff-capture-design.md` (the approved contract), `docs/architecture/README.md`, `.kiro/.../tasks.md`, `.kiro/.../implementation-status.md`. **No `backend/` or `frontend/` file was touched.** |

### Implemented behavior at the verified main

- **Entry persistence/lifecycle:** Entry scope/type/status constraints, ownership, canonical lifecycle, orphan-anchor filtering, correction through supersession, and single-current handling for `relationship.state` / `story.summary` are implemented.
- **`retrieve()`:** `EntryService.retrieve()` calls the Store retrieval seam. It defaults to canon, enforces owner/scope/type/subject/status constraints, excludes orphaned anchors, ranks deterministically, selects whole Entries under a knowledge budget, and returns retrieval trace data.
- **Context Assembly:** `assemble_entry_context()` is a pure bridge over a selected `EntryRetrievalResult`. It re-estimates complete rendered blocks, never truncates an Entry, and keeps assembly exclusions separate from retrieval exclusions.
- **Review:** Review read/accept/reject/edit/supersede APIs exist, and the frontend provides one non-blocking type-agnostic Review Queue/Card.
- **Prompt assets:** `chat.default`, `novel.continue`, and `summary.rolling` are UTF-8 repository assets loaded by the allow-listed loader. `PromptTemplate` remains API/data compatibility only, never an architecture prompt-body fallback.
- **User authoring and audit reads:** User-authored Entry creation is server-provenanced; default Entry lists expose live canon only, while `include_history=true` permits labelled audit/history data. Cursor pagination and immutable supersession correction are implemented.
- **P1-6 production wiring (PR #21):** `backend/app/services/entry_generation_context.py` is the single production call site chaining `EntryService.retrieve()` → `assemble_entry_context()` → `PromptEngine`. Chat and Novel each invoke it inside T1, before any token is streamed, exactly once per request — including the Chat regenerate path.

### P1-6 contract as merged

Later phases inherit these decisions. Change them only through an explicit architecture decision, not incidentally.

| Decision | Value as merged | Rationale source |
|---|---|---|
| Feature flag | `FEATURES["entry_store_context"]`, read via `Settings.entry_store_context_enabled`, default **OFF** | `docs/architecture/entry-context-integration.md` §2 |
| Flag OFF behavior | Zero Entry queries — the flag is checked before the retrieval request is constructed. Provider-visible payload (`messages`, `system`, `token_count`) is byte-identical to pre-P1-6; the only delta is a diagnostic `trace["entry_context"]` marker | §2, §6 |
| Block kind | First-class `entry` `BlockKind`. Entry canon is **never** relabelled `memory` and never merged into legacy `lore` text | ADR-018, RFC-003 §13.1 |
| `DEFAULT_PRIORITY["entry"]` | **65** — above `memory` (60) and `lore` (50) because human-gated canon should outlive rolling chat memory and the legacy keyword scan; below `world` (70) / `chapter` (75) / `persona` (80) / `character` (90) because P1-6 is additive and legacy stays authoritative until P1-8 | §3 |
| `LAYER_ORDER` | `entry` between `lore` and `memory`. One insertion; every pre-existing kind keeps its relative position | §3 |
| Truncatability | `truncatable=False`. A partially rendered Entry is a fabricated fact, so the BudgetManager drops the whole block | §3 |
| Variable substitution | Entry content is **not** `{{...}}`-resolved. Stored canon is data, not an authored template | `engines/prompt/engine.py` |
| Knowledge-slice budget | `max(256, context_window * 0.15)`, safety cap `limit=20`. Deliberately below the chat memory hint (`0.4`) during coexistence, so Entry cannot starve `memory` | RFC-003 §11.1, §4 |
| Chat scopes | `user`, the active `character`, that character's `world`. **Chat never declares a `work` scope** — a `ChatSession` holds no work and RFC-003 §13.3 forbids guessing among works | RFC-003 §13.3, §5 |
| Novel scopes | `user`, this `work`, its `world`, each linked `character`; `task_kind=scene` | §5 |
| Status handling | Inherited, never widened: no `status_filters`, `include_rejected=False`, `include_superseded=False`. Canon only; orphaned anchors excluded by `retrieve()` | RFC-003 §7.4, §7.5 |
| Trace | `trace["entry_context"]` keeps retrieval and assembly exclusions separately attributable (`retrieval_exclusions.*` vs `assembly_exclusions[].stage == "context_assembly"`) and distinguishes flag-off / nothing-eligible / canon-injected. `considered_candidate_count` counts only what the ranker scored: selected + budget-rejected + limit-rejected | RFC-003 §12, §6 |
| Error policy | Retrieval failures **propagate**; they are not swallowed. This matches the existing pre-stream stage (`MemoryEngine.build_memory_context()`, legacy lore load). Nothing is streamed or persisted on that path | §7 |
| Separation preserved | chat-private `Memory`, legacy `_make_lore_blocks()` scanner, and Entry canon remain three distinct block kinds with distinct trace identity | ADR-018, RFC-003 §13.1 |

### Explicitly not complete

- **Legacy remains authoritative.** P1-6 added Entry context as an *additional* block; it did not move authority. `Character.personality`/`speech_style`, the `World` fields, and `Lorebook`/`LoreEntry` are still the authoritative generation context, and `PromptEngine._make_lore_blocks()` still runs. RFC-003 §16.8's "two authoritative retrieval paths" concern is **intentionally unresolved** and belongs to P1-8.
- **The flag is OFF in every environment.** Until an operator sets `FEATURES='{"entry_store_context": true}'`, real generation prompts are unchanged from pre-P1-6. Leave it off until the Bench (P6-1) can measure the retrieval policy against golden scenes.
- **Chat cannot reach work canon or `relationship.state`**, because chat declares no work scope. That needs an explicit work selection (P5-1/P5-3), not a heuristic.
- **P1-7 edit-diff capture is designed and approved, but not implemented.** `EDIT_DIFF` still exists only as a provenance enum value in `backend/app/schemas/entry.py`. There is no code, column, or table computing or storing a draft↔accepted diff, and `alembic heads` is still `0002_entry_store`. PR #23 merged the *contract*; the implementation is the next task. Verify this yourself before starting — do not infer from the design document's existence that anything is built.

## 6. Code map

| Area | File or directory | Responsibility at verified main |
|---|---|---|
| Entry model | `backend/app/models/entry.py` | ORM Entry entity and persisted scope/type/status/provenance shape. |
| Entry schema | `backend/app/schemas/entry.py` | Pydantic contracts for creation, authoring, review, listing, retrieval, and trace data. |
| Entry repository | `backend/app/repositories/entry_repository.py` | Owner-scoped persistence and retrieval-candidate query access. |
| Entry service | `backend/app/services/entry_service.py` | Validation, lifecycle, supersession, review helpers, audit listing, and `retrieve()`. |
| Retrieval policy | `backend/app/services/entry_retrieval.py` | Pure ranking, policy version, whole-Entry selection, and exclusion decisions. |
| Entry API | `backend/app/api/v1/entries.py` | Authenticated authoring, canonical/audit reads, Review Card routes, and pagination boundary. |
| Entry migration | `backend/app/db/migrations/versions/0002_entry_store.py` | Additive Entry Store migration after frozen `0001_initial`. |
| Context Assembly | `backend/app/engines/prompt/entry_context.py` | Pure selected Entry result to prompt-block conversion, whole-block assembly budget, and the flattened `entry_context` prompt-trace section. |
| **Entry generation seam** | `backend/app/services/entry_generation_context.py` | **The single production call site** for `retrieve()` + `assemble_entry_context()`. Owns the feature-flag check, the Chat/Novel retrieval situations, and the knowledge-slice budget. Chat and Novel build no Entry prompt text and re-implement no ranking. |
| Prompt blocks | `backend/app/engines/prompt/blocks.py` | Block kinds (including `entry`), `LAYER_ORDER`, `DEFAULT_PRIORITY`, and `PromptBlock` structure. |
| Prompt engine | `backend/app/engines/prompt/engine.py` | Deterministic collect → resolve → order → budget → final provider-neutral assembly. Accepts pre-assembled `entry_blocks` and skips variable substitution for them. |
| Prompt assets | `backend/app/engines/prompt/assets.py` | Allow-listed repository asset loader with asset identity/version/digest. |
| Prompt asset bodies | `backend/prompts/chat/default.v1.md`, `backend/prompts/novel/continue.v1.md`, `backend/prompts/shared/rolling-summary.v1.md` | UTF-8 repository prompt bodies for the `chat.default`, `novel.continue`, and `summary.rolling` assets. |
| Chat service | `backend/app/services/chat_service.py` | Chat SSE orchestration, idempotency/serialization, memory lifecycle, legacy lore loading, and the T1 Entry-context call. |
| Chat engine | `backend/app/engines/chat/engine.py` | Chat prompt assembly and provider streaming over PromptEngine/MemoryEngine; relays externally assembled Entry blocks. |
| Novel service | `backend/app/services/novel_service.py` | Work/chapter service and SSE continuation; builds legacy story context and issues the T1 Entry-context call. |
| Novel engine | `backend/app/engines/novel/engine.py` | `ChapterContext`, continuation prompt assembly, and provider stream; relays externally assembled Entry blocks. |
| Review frontend API | `frontend/src/lib/api/endpoints.ts` | Typed frontend endpoint wrappers, including Entry Review operations. |
| Review frontend hook | `frontend/src/hooks/use-entry-review.ts` | Queue mutations/cache transitions for review actions. |
| Review frontend UI | `frontend/src/components/review/review-queue.tsx` | Existing Home-screen review queue. |
| Review card UI | `frontend/src/components/review/review-card.tsx` | Type-agnostic proposed Entry display and actions. |
| Review frontend test | `frontend/src/components/review/review-utils.test.ts` | Queue/cache transition and error handling coverage. |
| Configuration | `backend/app/config.py` | Pydantic settings, UTF-8 `.env` reading, the `FEATURES` feature-flag map, and the typed `feature_enabled()` / `entry_store_context_enabled` read boundary. |
| Backend tests | `backend/tests/unit/`, `backend/tests/integration/`, `backend/tests/golden/`, `backend/tests/property/` | Unit, integration, golden regression, migration, streaming, and property coverage. |
| CI | `.github/workflows/ci.yml` | Backend and frontend GitHub Actions jobs. |
| Current status | `.kiro/specs/ai-creative-workspace/implementation-status.md` | Verified execution-path status snapshot and known local environment issues. |
| Remaining work plan | `.kiro/specs/ai-creative-workspace/tasks.md` | Architecture-frozen Phase 1–6 implementation order and boundaries. |

## 7. Tests and validation baseline

### Commands confirmed in this repository

Run each command as a separate process with the stated working directory; do not chain shell commands.

| Check | Working directory | Command | Verified result at this handoff |
|---|---|---|---|
| Backend full pytest | `backend` | `.\.venv\Scripts\python.exe -m pytest -q` | **156 passed, 0 failed** on 2026-08-09 (pre-P1-6 baseline was 115; P1-6 added 41). |
| P1-6 target tests | `backend` | `.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_entry_prompt_integration.py tests/unit/test_entry_generation_context.py tests/integration/test_entry_context_generation.py` | **41 passed** on 2026-08-09. The integration file drives the real SSE endpoints with a recording provider. |
| Entry/retrieval/assembly target tests | `backend` | `.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_entry_retrieval.py tests/unit/test_entry_context_assembly.py tests/integration/test_entry_retrieval.py tests/golden/test_retrieval_context_golden.py` | Repository command paths verified; use for Store/context work. |
| Ruff | `backend` | `.\.venv\Scripts\python.exe -m ruff check app tests` | `All checks passed!` on 2026-08-09. |
| Frontend test | `frontend` | `npm run test` | Passed: 3 files / 13 tests on 2026-07-31; unchanged by P1-6 (no frontend change). |
| Frontend lint | `frontend` | `npm run lint` | Passed on 2026-07-31; emits a TypeScript-version support warning. |
| Frontend production build | `frontend` | `npm run build` | Passed: 15 routes on 2026-07-31. |
| Alembic revisions | `backend` | `.\.venv\Scripts\python.exe -m alembic heads` | `0002_entry_store (head)` on 2026-08-09 — unchanged by P1-6 and by the documentation-only PR #23. P1-7 implementation will move this to `0003_edit_diff_capture`. |
| Whitespace/patch integrity | repository root | `git diff --check` | Clean on 2026-08-09. |

The full command `.\.venv\Scripts\python.exe -m mypy app tests` reports **36 pre-existing errors in 11 files** at the verified main — unchanged by P1-6. The distribution is `tests/unit/test_prompt_assets.py` (9), `app/repositories/base.py` (8), `tests/integration/test_prompt_template_boundary.py` (5), `app/engines/prompt/engine.py` (5), `app/services/world_service.py` (3), and one each in `tests/integration/test_migrations.py`, `app/services/novel_service.py`, `app/main.py`, `app/core/storage.py`, `app/auth/service.py`, `app/api/sse.py`. The new `app/services/entry_generation_context.py` contributes **0**.

Full MyPy is not the clean merge gate. For a scoped change, record the current errors for precisely the changed scope and do not introduce or increase them; fix new errors in that scope before review.

GitHub CI runs:

- **Backend:** install `.[dev]`, run `ruff check app || true`, run `alembic upgrade head`, then `pytest -q`.
- **Frontend:** `npm install`, `npm run lint`, `npm run test`, `npm run build`.

For PR #21's final head `3d30a663ff8c7ae6bb1854f3ca9d688baa97b3ec` and PR #23's final head `8c67ab7cdfde5788498a5c259aa44febc2177bd7`, GitHub Actions `backend` and `frontend` checks both completed with `success`. Note that the CI Ruff step uses `|| true`, so a local Ruff pass remains required.

The four baselines above were re-verified against PR #23's final head on 2026-08-09: **156 passed**, Ruff `All checks passed!`, MyPy **36 errors in 11 files**, `alembic heads` `0002_entry_store`. PR #23 changed documentation only, so none of them moved.

## 8. Environment cautions

Only confirmed local facts are listed here.

1. **PowerShell/Kiro wrapper behavior:** direct short commands and concurrent shell calls have been interrupted or malformed in this workspace. If a wrapper damages a command, do not keep retrying the same shell string. Use Python `subprocess.run([...], cwd=..., shell=False)` with an argv list instead. Example pattern:

   ```powershell
   python -c "__import__('sys').exit(__import__('subprocess').run(['git','status','--short'],cwd=r'C:\gv\rfrf').returncode)"
   ```

   This is the verified fallback used successfully for Git status and Alembic inspection.

2. **Local database stamp differs from repository migrations:** read-only `alembic current` currently fails with `Can't locate revision identified by '0002_story_bible'`. Repository migration files themselves report `0002_entry_store (head)`. `backend/data/app.db` may contain user data; do **not** delete, recreate, stamp, migrate, or otherwise modify it without explicit user approval.

3. **Stashes are protected:** `stash@{0}` is `codex/phase1-review-card-api`; `stash@{1}` is `codex/new`. They were only listed. Do not apply, pop, drop, or rewrite either without explicit user approval.

4. **Do not revive the old architecture:** the `codex/new` stash is the Architecture-Frozen-predecessor direction described in `implementation-status.md`: separate reference/planning code and `0002_story_bible` / `0003_reference` migrations. It conflicts with ADR-002, ADR-003, and ADR-004. Do not merge or selectively transplant it.

5. **UTF-8 is mandatory:** read and save every text file as UTF-8. Prompt assets and Settings `.env` handling already depend on UTF-8.

## 9. Remaining Phase 1 work

The current `tasks.md`, `implementation-status.md`, and production code agree on this order.

| Task | Current state | Dependencies | Do not expand into | Recommended order |
|---|---|---|---|---|
| ~~**P1-6**~~ `retrieve()` → Context Assembly → real generation path | **Complete** (PR #21, merged `1b2a850b2732778fecb8944f03a8d12020aa588a`). Single production call site wired for Chat and Novel behind an OFF-by-default flag. | — | — | Done. |
| **P1-7** edit-diff capture | **Design APPROVED (PR #23, `39cf740`); implementation NOT STARTED.** `EDIT_DIFF` is still only a provenance enum value. Capture remains time-sensitive: missed diffs cannot be reconstructed, so this is the only remaining gap where data is **permanently lost with every day it stays unimplemented**. | The persistence design decision is now made and merged. No P1-6 dependency. | Distillation/learning, canon writes, blocking author flows, re-litigating the merged design. | **Next — implement the approved design.** |
| **P1-8** legacy Character/World/Lore ↔ Entry equivalence bridge | Not implemented. Legacy fields/lore remain the authoritative generation sources and `_make_lore_blocks()` still runs. This is the approved gate for turning the P1-6 flag on permanently. | P1-5 and P1-6 (both complete). | Backfill, legacy deletion, read cutover, migration. | After P1-7 design. Read-only deterministic comparison first. |
| **P1-9** review audit persistence decision | Not implemented. Current Entries have lifecycle/provenance but no approved actor/action history design. | P1-1 complete. | Unapproved JSON schema, implementation migration in the design PR. | After P1-7/P1-8 unless architecture review chooses earlier. |
| **P1-10** local development environment cleanup | Optional and blocked by user-data safety. Local DB stamp is stale; protected stashes exist. | Explicit user approval for data/stash actions. | Automatic DB recreation, `alembic stamp`, stash application/deletion. | Last, and only with approval. |

## 10. Immediate next task: P1-7 implementation

> **The design phase is over.** `docs/architecture/edit-diff-capture-design.md` was merged by PR #23 (`39cf740`) after an independent architecture review that ratified every open item. This step **implements that approved contract**. Do not redesign it, and do not expand it.

### Why P1-7 is next

P1-6 closed the last "built but disconnected" gap in the Store. The remaining Phase 1 items are P1-7 (edit-diff capture), P1-8 (legacy equivalence), and P1-9 (review audit persistence). P1-7 goes first for one reason: **it is the only remaining gap that permanently destroys data while it stays unimplemented.** A draft↔accepted edit diff can only be captured at the moment the human edits; it cannot be reconstructed retroactively. ADR-010 §2.2 and RFC-001 §8.8 require day-one capture, and the design's §14 records that **no backfill is possible** — every edit made before this ships has already destroyed its pre-image.

### Current state — verify it, do not trust this snapshot

`ProvenanceSourceKind.EDIT_DIFF` exists in `backend/app/schemas/entry.py` as an enum value only. No code computes a diff, no column or table stores one, no API surfaces one, and `alembic heads` is `0002_entry_store`. The merged design document changes none of that; it is documentation.

The two production paths that destroy data today, both confirmed in code:

1. **`EntryService.edit_review_entry()`** ([`entry_service.py:281`](backend/app/services/entry_service.py#L281)) assigns submitted fields onto the persisted row and commits, overwriting the AI-proposed `content` in place. The frontend performs edit-then-accept as **two separate requests** ([`use-entry-review.ts:67`](frontend/src/hooks/use-entry-review.ts#L67)), so the original is already gone when the accept request runs. **Any capture that hooks the accept call captures nothing.**
2. **`NovelService._append_chapter()`** ([`novel_service.py:259`](backend/app/services/novel_service.py#L259)) merges the streamed output into `Chapter.content_text` with no boundary marker, so no later query can tell what the model wrote from what the author changed.

### Objective of this step

Implement the approved design: one additive migration, one ORM model, the two capture call sites, the settle path, and the tests. Nothing else.

### Explicit non-goals for this step

- Distillation, preference learning, style statistics, or any read consumer beyond the design's §13 service-level contract.
- Any HTTP endpoint, request/response DTO, or frontend change. P1-7 adds **no API surface at all**.
- Any Entry creation, mutation, promotion, or status transition. Capture never writes canon.
- Changes to `retrieve()`, ranking, Context Assembly, prompt blocks, or any P1-6 decision (`DEFAULT_PRIORITY["entry"] = 65`, `LAYER_ORDER`, the 0.15 budget ratio, flag semantics, the propagate-don't-swallow error policy). Those are settled.
- P1-8 legacy equivalence, or turning `FEATURES["entry_store_context"]` on.
- P1-9 review audit persistence — see the boundary rules below.
- Retroactive backfill. It is impossible and would fabricate the signal being measured.
- Modifying `0001_initial`, `0002_entry_store`, or the local `backend/data/app.db`.
- Reopening the merged design. If the implementation finds a genuine defect in it, stop and report rather than silently deviating.

## 11. The approved P1-7 design contract

`docs/architecture/edit-diff-capture-design.md` is authoritative and must be read in full before writing code. This section is the summary of what the architecture review fixed, so a new session can tell at a glance what is settled.

### 11.1 Persistence decision

| Decision | Approved value |
|---|---|
| Entry or non-Entry? | **Non-Entry operational record.** An edit diff asserts nothing, is not prompt-ready, has no scope in which it is "true", and has no coherent meaning for `accept`. It fails all six Entry obligations (design §5.2). `note` is not a loophole — it is a low-structure kind of *knowledge*. |
| Storage | **One additive `edit_diff_captures` table** with a `source_kind` discriminator serving both capture paths. Rejected: Entry-row JSON (fatal — chapters are not Entries; also violates RFC-002 §8.1), a new Entry type (damages the Store contract), and ADR-010's literal Chapter column pair (fatal — each continuation would overwrite the last). |
| Escape-valve question | **Ratified: a non-knowledge operational table does not consume the ADR-003 §6 promote-a-type valve.** RFC-002 §10's five preconditions are all about a deterministic consumer parsing Entry prose and cannot even be evaluated here; ADR-015 §2.2 separately sanctions new tables; and RFC-001 names edit-diff capture as substrate code alongside the entry store and the retrieval function. **No ADR is required before implementing.** |
| Format | **Full `before_text` + `after_text`, plus SHA-256 and code-point lengths. No structured diff.** Every other representation is derivable from the pair; the pair is derivable from none of them. Text is stored byte-exact with no Unicode normalization. |
| Feature flag | **None.** A default-OFF flag on a capture feature collects nothing (ADR-010 §4-C); a default-ON flag is not a flag. |

### 11.2 Capture semantics — Path A (Entry review edit)

- Capture inside `edit_review_entry()`, **in the same transaction as the destructive write**, after `_get_for_update()` and before the field assignment reads the pre-image.
- Write a row only when `content` actually changed. `before_sha256 == after_sha256` writes nothing, which also makes a duplicated request inert.
- `title` / `data` changes are recorded as field names in `context.fields_changed`, never as text pairs.
- A Path A row is **born settled** — both sides exist at INSERT time.
- Accept-without-edit, reject-without-edit, `supersede()`, direct user authoring, and chat regenerate capture **nothing**.

### 11.3 Capture semantics — Path B (Novel continuation)

- **Draft side:** captured in `_append_chapter()`, in the same transaction as the chapter write, with `settled_at IS NULL`. `context` records `insert_offset`, `chapter_version`, the prompt asset identity, and `partial_stream` for the stream-error path.
- **Settle trigger — decided:** **the next continuation of the same chapter**, at T1 of `_continue_impl()` before any token streams, guarded by `settled_at IS NULL`. No other write-path trigger exists. The author's autosave (`update_chapter`) is deliberately **not** hooked.
- **The trailing unsettled row is a normal terminal state, not a gap.** Only the before-side is irrecoverable; the after-side lives in `chapters.content_text`, which nothing destroys. The settle snapshot's only job is *bracketing* segment *N* against segment *N+1*. For the final segment there is no later boundary, so its after-side is resolved **at read time** from live `chapters.content_text` plus the stored offsets (design §6.3.1, §13 rule 2).
- Settling on the author's save was rejected on correctness grounds, not convenience: the first autosave lands ~1.2 s into revision, so it would systematically record "the human changed nothing" in a corpus whose whole purpose is measuring how the human changes it. Missing data is honest; biased data is not.

### 11.4 Transaction and failure policy — three tiers

| Tier | Data | Policy |
|---|---|---|
| 1 — **atomic** | Path A pre-image | Same transaction as the destructive write. **If the INSERT fails, the edit fails and rolls back.** |
| 2 — **atomic** | Path B draft side | Same transaction as `_append_chapter()`. |
| 3 — **best-effort** | Path B settle snapshot | May fail without failing the request. Log a structured warning, leave the row unsettled. |

The dividing rule: **capture that holds the only copy is atomic with the write that would destroy it; capture that duplicates surviving data is best-effort.**

"Non-blocking" (ADR-011 §2.2, RFC-011 §6) means no added user step, round trip, LLM call, or queue wait. It does **not** mean `except Exception: pass`, which is explicitly forbidden. The failures are benign: a rolled-back Review Card edit leaves the author's text in React local state with an error shown, and a rolled-back continuation costs one re-request while destroying nothing the author wrote. Note that a Tier-2 rollback makes the just-streamed text visibly disappear after `reloadFromServer()` — that is expected and must not be papered over.

### 11.5 Schema shape — as corrected by the review

Descriptive; the migration is not authored yet. Full detail in design §8.

- Columns: `id`, `user_id` (FK `users.id` CASCADE), `source_kind`, nullable `entry_id` / `chapter_id` (both FK CASCADE, exactly one set), `sequence`, `before_state`, `after_state`, `before_text`, `after_text`, `before_sha256`, `after_sha256`, `before_chars`, `after_chars`, `producer`, `context` (portable JSON), `settled_at`, `created_at`, `updated_at`.
- **`before_state` and `after_state` are independent** (`stored` | `oversize`), and **"pending" is not a state value — it is `settled_at IS NULL`.** The review found that the original single `payload_state` conflated two orthogonal axes and made a legal row unrepresentable: a Path B row whose AI segment exceeds the size cap is written both oversize *and* unsettled, which the old `CHECK` rejected.
- **`MAX(sequence) + 1` must be derived under a row lock.** Path A already holds one via `_get_for_update()`. **Path B does not** — `_owned_chapter()` uses a plain `session.get()` and `_active_continue` is an in-process set, not a database lock. `_append_chapter()` and the settle path must load the chapter `with_for_update()`, mirroring `EntryRepository.get_for_update()`. Without it, two concurrent continuations can collide on `uq_edit_diff_captures_chapter_sequence` and roll back the author's generated prose.
- **Deletion cascades stay at the database level.** Declaring a SQLAlchemy `relationship()` to the capture rows without `passive_deletes=True` would null out `chapter_id` instead of cascading, silently orphaning captured prose. Declare no relationship, or declare it with `passive_deletes=True`.
- Portability: reuse `0002`'s `sa.JSON().with_variant(postgresql.JSONB(), "postgresql")`; plain `CHECK` predicates only; no partial indexes, no `NULLS NOT DISTINCT`, no `IS DISTINCT FROM`, no expression indexes. The two `UNIQUE` constraints rely on NULLs being distinct, which holds on both engines.

### 11.6 Retention, size, and privacy

- `EDIT_DIFF_MAX_CHARS = 100_000` **per side**, in code. It is a configuration default, **not a schema contract** — no column, CHECK, or index depends on it, so it can change with no migration and existing rows stay valid.
- **Truncation is prohibited.** An oversize side stores NULL text with its hash and length retained. A truncated pair looks complete and is wrong; it would report deletions the author never made and bias every statistic toward chapter openings.
- Retention is **indefinite with no automatic expiry**. The data cannot be recollected, and a retroactive purge would destroy it. Bounding comes from the per-row cap, the cascades, and the owner's unconditional delete path.
- User deletion and chapter hard-deletion cascade captures away; Work **soft**-deletion retains rows but excludes them from reads. Captured text never enters a prompt, log, error message, trace, or Bench fixture. P1-7 adds no HTTP endpoint, so none of it is reachable from the API.

### 11.7 P1-9 boundary — do not blur these

P1-7 answers *what did the AI write and what did the human make of it*. P1-9 answers *who did what, when, and can it be undone*. The separation rules:

1. P1-7 defines **no** actor vocabulary and **no** action vocabulary. `user_id` is present only for ownership scoping, as ADR-017 §2.3 requires of every table — that is data integrity, not audit.
2. P1-7 writes **no** row for accept, reject, or supersede. An "accepted with no edit" row means the boundary has been violated.
3. P1-7 is not the review history, and no feature may come to depend on it as such.
4. When P1-9 lands, a capture row **may** gain a nullable FK to a review-event row. P1-7 must not pre-invent that column, that table's name, or its vocabulary.
5. P1-9 must not store text pairs; if it needs them it joins to this table.

### 11.8 Expected migration

| Item | Value |
|---|---|
| Revision id | `0003_edit_diff_capture` |
| `down_revision` | `0002_entry_store` |
| Head after | `0003_edit_diff_capture` |
| Upgrade | `op.create_table("edit_diff_captures", ...)` plus its named indexes and unique constraints. **No `ALTER` on any existing table.** |
| Downgrade | `op.drop_table(...)`, to satisfy the round-trip assertions in `tests/integration/test_migrations.py` — not an operational procedure. |
| Backfill | **None, and none is possible.** Every past edit already destroyed its pre-image. |

### 11.9 Recommended rollout

Steps 2–4 are separate PRs over one migration; splitting the migration would create three revisions for one table.

1. Migration `0003_edit_diff_capture` only — no behavior change.
2. Path A capture. Smallest surface, sharpest data loss, no UX effect.
3. Path B draft capture in `_append_chapter()`, including the `with_for_update()` change.
4. Path B settle trigger at T1 of `_continue_impl()`.
5. The §13 read contract, when P2-5 begins — not before.

### 11.10 Open questions — all closed

All eight design §19 questions are resolved; **none blocks implementation.**

| | Question | Disposition |
|---|---|---|
| Q1 | Path B settle trigger | **RESOLVED** — next continuation + read-time resolution of the trailing row |
| Q2 | `EDIT_DIFF` provenance validator expects an owned Chapter, which a multi-chapter distilled preference cannot supply | **DEFERRED WITH SAFE DEFAULT** — real, but a P2-5 problem. P1-7 writes no Entry, so the validator is never exercised. **Change nothing.** |
| Q3 | Capture on canon supersession | **RESOLVED — no capture.** `superseded_by_entry_id` already preserves the pair, so §4.1's predicate (b) is false. |
| Q4 | Keep oversize rows | **RESOLVED — keep them**, metadata-only. Invisible loss is worse than measured loss. |
| Q5 | ADR-010's "one column pair on the substrate" | **RESOLVED — illustrative, not binding DDL.** It is scoped "per chapter" and cannot express Path A at all; ADR-003 §2 disclaims DDL, and RFC-008 §5/§7 defer the substrate elsewhere. No ADR-010 revision needed. |
| Q6 | Retention ceiling | **RESOLVED — indefinite, no automatic expiry.** |
| Q7 | Kill switch | **RESOLVED — no feature flag.** |
| Q8 | Table name | **RESOLVED — `edit_diff_captures`**, source-neutral because it serves both anchors. |

### 11.11 Acceptance criteria and test plan

Design §17 (test plan) and §20 (28 acceptance criteria) were written before implementation precisely so the implementation cannot define its own success criteria afterward. Read both and treat them as the definition of done. The four items the review added — §20.24 through §20.28 — cover the chapter row lock, the `passive_deletes` rule, the split state columns, the terminal-unsettled state, and the constant/schema independence. Two tests deserve particular attention because they are easy to write vacuously:

- The **mutation test**: deleting the capture call from `edit_review_entry()` must fail a test. Without it the suite does not protect the feature.
- The **row-lock test**: SQLite ignores `FOR UPDATE`, so a SQLite-only assertion proves nothing. Assert on the compiled statement or the repository call.

## 12. First-run checklist for a new AI

1. Read `AI-HANDOFF.md`, then **`docs/architecture/edit-diff-capture-design.md` in full** — it is the approved contract this task implements — plus ADR-003/010/011/015/017, RFC-001 §8.8/§8.10, RFC-002, RFC-011, and the P1-7 section of `tasks.md`.
2. Fetch and compare `origin/main`; if this handoff SHA is no longer current, re-validate GitHub state, code call sites, and status documents.
3. Check the working tree and list stashes without modifying either. Keep user work, the local DB, and stashes untouched.
4. Confirm the P1-7 starting state yourself: search for `EDIT_DIFF` / `edit-diff`, verify it is still enum-only with no computing or storing code, and confirm `alembic heads` is still `0002_entry_store`.
5. Read the two destructive call paths before changing them — `EntryService.edit_review_entry()` and `NovelService._append_chapter()` / `_continue_impl()` — and confirm the locking facts in [section 11.5](#115-schema-shape--as-corrected-by-the-review) still hold in the current code.
6. Confirm P1-6 is still wired as described — `backend/app/services/entry_generation_context.py` exists and is imported by both `chat_service.py` and `novel_service.py` — and that the flag is still OFF by default.
7. Create a new branch from current `origin/main`.
8. **Implement** the approved design, following the [rollout order](#119-recommended-rollout). Enforce the non-goals in [section 10](#10-immediate-next-task-p1-7-implementation). Do not redesign; if you find a real defect in the merged design, stop and report it.
9. Verify against design §17 and §20: the migration chain applies and round-trips on SQLite and compiles for PostgreSQL, `0001`/`0002` are byte-unchanged, no existing table is altered, the mutation and row-lock tests actually fail when the feature is removed, Ruff is clean, MyPy adds no error in the changed scope, full pytest passes with no reduction in count, `git diff --check` is clean, and all files are UTF-8.
10. Create a **Draft** PR; include the required completion report in the PR body or user report.
11. Do not merge. Report results to the user and wait for the requested review/merge decision.

Use one PowerShell command per process and set the terminal working directory instead of shell-chaining commands. If the wrapper corrupts a command, use the `subprocess.run(argv, cwd=..., shell=False)` fallback described in [Environment cautions](#8-environment-cautions), not another identical wrapper retry.

## 13. Completion-report rules

The user's preferred completion report always includes:

1. Root-cause analysis.
2. Files read.
3. Files modified.
4. What changed.
5. Test results.
6. Issues encountered.
7. PR information.
8. Next work.
9. Whether to continue the same chat or start a new chat.
10. Ready-for-Review / merge judgment.
11. A copyable prompt for the next AI.
12. Recommended model and reasoning level.

## 14. Copyable P1-7 implementation prompt

```text
You are continuing AI Author OS / gorafan at C:\gv\rfrf.

Start by reading C:\gv\rfrf\AI-HANDOFF.md, then docs/architecture/edit-diff-capture-design.md in full, then the governing ADR/RFC originals they name. Do not trust this prompt over current GitHub, Git, architecture, code, or test state: fetch origin/main, inspect the working tree, list stashes without touching them, and verify the repository is cococute88/gorofan. The handoff snapshot is main 39cf740af3df62680e29111a9d39ed2e7c168842, where P1-6 (PR #21) is merged and the P1-7 design (PR #23) is merged and APPROVED. If main has advanced, re-verify before relying on any of it.

This is an IMPLEMENTATION task. The design phase is over: PR #23 was independently reviewed, every open question was closed, and four defects were corrected before merge. Implement that approved contract. Do not redesign it. If you find a genuine defect in it, stop and report rather than silently deviating.

First confirm the starting state yourself: search for EDIT_DIFF / edit-diff and verify it is still only a ProvenanceSourceKind enum value in backend/app/schemas/entry.py with no code computing or storing a diff, and that alembic heads is still 0002_entry_store. Then read the two destructive paths before touching them: EntryService.edit_review_entry() in backend/app/services/entry_service.py, and NovelService._append_chapter() plus _continue_impl() in backend/app/services/novel_service.py. Capture is time-critical because a diff not captured at edit time cannot be reconstructed later (ADR-010 section 2.2, RFC-001 section 8.8), and no backfill is possible.

Build it in this order, as separate commits or PRs over one migration: (1) migration 0003_edit_diff_capture with down_revision 0002_entry_store, creating only the edit_diff_captures table plus its named indexes and constraints, altering no existing table; (2) Path A capture inside edit_review_entry(), in the same transaction as the destructive write, reading the pre-image after _get_for_update() and writing no row when the content hash is unchanged; (3) Path B draft capture inside _append_chapter(), in the same transaction, with settled_at NULL; (4) the Path B settle at T1 of _continue_impl(), guarded by settled_at IS NULL.

Honor these decisions exactly, because the review fixed them deliberately. before_state and after_state are independent columns valued stored or oversize; there is no single payload_state column, and pending is expressed only as settled_at IS NULL. _append_chapter() and the settle path must load the chapter with with_for_update() before deriving MAX(sequence)+1 — the existing session.get() takes no lock and _active_continue is an in-process set, so without this two concurrent continuations can collide on the unique constraint and roll back the author's prose. Declare no SQLAlchemy relationship to the capture rows, or declare it with passive_deletes=True, so deletion cascades stay at the database level instead of nulling chapter_id. An unsettled chapter-continuation row is a normal terminal state, not an error: the trailing segment's after-side is resolved at read time from live chapters.content_text. Tier 1 and Tier 2 captures are atomic with the write they protect and must fail loudly; the Tier 3 settle is best-effort. No bare except Exception: pass anywhere near capture. Store full before/after text byte-exact with SHA-256 and code-point lengths, never a structured diff and never truncated; an oversize side stores NULL text with hash and length retained. EDIT_DIFF_MAX_CHARS = 100_000 per side is a code constant with no schema dependency. There is no feature flag.

Do not add any HTTP endpoint, DTO, or frontend change. Do not create, mutate, promote, or block any Entry. Do not write a row for accept, reject, or supersede. Do not start P1-8 legacy equivalence, do not turn the P1-6 feature flag on, and do not absorb P1-9 review audit persistence — P1-7 defines no actor or action vocabulary, and user_id exists only for ownership scoping. Do not reopen approved P1-6 decisions: DEFAULT_PRIORITY["entry"] = 65, LAYER_ORDER with entry between lore and memory, feature-flag semantics, the 0.15 knowledge-slice budget ratio, and the propagate-do-not-swallow error policy. Do not attempt a backfill. Do not modify 0001_initial, 0002_entry_store, or the local backend/data/app.db. Do not apply, pop, or drop stashes. Do not auto-merge. Do not ask for intermediate approval; complete the bounded implementation autonomously.

Write the tests from design sections 17 and 20 rather than inventing your own success criteria. Two of them are easy to write vacuously and must not be: the mutation test, where deleting the capture call from edit_review_entry() must fail a test, and the row-lock test, where a SQLite-only assertion proves nothing because SQLite ignores FOR UPDATE — assert on the compiled statement or the repository call. Also assert that an oversize, not-yet-settled Path B row inserts successfully; that is the regression test for the constraint defect the review corrected.

Verify before opening the PR: the 0001 to 0002 to 0003 chain applies and round-trips on a fresh isolated SQLite database and 0003 compiles for the PostgreSQL dialect; 0001_initial and 0002_entry_store are byte-unchanged and no existing table is altered; alembic heads reports 0003_edit_diff_capture as the single head; backend pytest passes with no reduction from the 156-test baseline; Ruff is clean; MyPy introduces no new error in the changed scope against the 36-errors-in-11-files baseline; git diff --check is clean; all files UTF-8. Use one PowerShell command per process; if the wrapper corrupts a command, use Python subprocess.run(argv, cwd=..., shell=False) rather than retrying the same broken shell string.

Perform an independent self-review against AI-HANDOFF.md and design section 20's acceptance criteria, commit, push, and create a Draft PR only. Then report: what was implemented and how it maps to the approved design, files read/changed, all verification results, issues, PR URL, next work, whether a new chat is recommended, Ready-for-Review/merge judgment, a next-AI prompt, and recommended model/reasoning.
```

**Recommended execution model:** Claude Code — Opus High; Codex — high reasoning; Cursor — strongest available reasoning model. This is an irreversible schema change on a data-loss-sensitive path; do not delegate it to a mid-tier model.
