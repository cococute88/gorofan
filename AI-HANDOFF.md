# AI Author OS / gorafan — AI Handoff

> **Canonical handoff document for a new AI session.**
>
> **Verified at:** 2026-09-06T14:14:08+09:00
> **Verified `main`:** `ac791ba8369aa1a7f6856cd9f573e0650995ea74`
> **Current docs-only branch:** `docs/story-summary-chronology-contract`

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
10. [The P1-7 contract as merged](#10-the-p1-7-contract-as-merged)
11. [P1-8 merged result and chronology contract gate](#11-p1-8-merged-result-and-chronology-contract-gate)
12. [First-run checklist for a new AI](#12-first-run-checklist-for-a-new-ai)
13. [Completion-report rules](#13-completion-report-rules)
14. [Copyable next-task prompt](#14-copyable-next-task-prompt)

## 1. To the AI reading this

This is the starting point for a new AI session. Treat the checked code, Git history, GitHub PR state, and authoritative architecture documents as stronger evidence than any prior chat, report, or this snapshot.

Before changing anything:

- Read this file **and** the relevant ADR/RFC originals in `docs/architecture/`.
- Confirm the verification timestamp and `main` SHA above.
- If `origin/main` has advanced after `ac791ba8369aa1a7f6856cd9f573e0650995ea74`, re-verify the affected GitHub, code, task/status, and test facts before relying on this handoff.
- Do not infer implementation completion from file presence. Follow executed production paths, API exposure, and passing tests.

## 2. Repository identity

| Item | Verified value |
|---|---|
| GitHub repository | [`cococute88/gorofan`](https://github.com/cococute88/gorofan) |
| Local repository | `C:\gv\rfrf` |
| Default branch | `main` |
| Verification time | `2026-09-06T14:14:08+09:00` |
| Verified `origin/main` / local `main` | `ac791ba8369aa1a7f6856cd9f573e0650995ea74` |
| PR #21 | [`feat(entry): wire retrieval context into generation paths`](https://github.com/cococute88/gorofan/pull/21), merged 2026-08-09 — **P1-6** |
| PR #21 merge commit | `1b2a850b2732778fecb8944f03a8d12020aa588a` |
| PR #23 | [`docs(architecture): design edit-diff capture`](https://github.com/cococute88/gorofan/pull/23), merged 2026-08-09 — **P1-7 design, approved. Documentation only.** |
| PR #23 merge commit | `39cf740af3df62680e29111a9d39ed2e7c168842` |
| PR #25 | [`feat(entry): implement edit-diff capture`](https://github.com/cococute88/gorofan/pull/25), merged 2026-08-09 — **P1-7 implementation** |
| PR #25 merge commit | `271e27c4d1f409b7b0cd32e28f1c407ac2308be0` |
| PR #25 final head before merge | `a0d6bad298b63f91dca5addcc7a9f17c1193fd79` |
| PR #26 | [`docs(handoff): refresh for merged P1-7 and pivot next task to P1-8`](https://github.com/cococute88/gorofan/pull/26), merged 2026-08-09 |
| PR #26 merge commit | `10683313321be4ee9d81d634943d55fa67f3f4cb` |
| PR #27 | [`docs(architecture): design P1-8 equivalence bridge`](https://github.com/cococute88/gorofan/pull/27), merged 2026-09-04 — **P1-8 architecture contract** |
| PR #27 merge commit | `9deb643c1c506e604f1341a6d3e072c30220ab88` |
| PR #28 | [`feat(entry): implement P1-8 legacy equivalence diagnostics`](https://github.com/cococute88/gorofan/pull/28), merged — **P1-8 diagnostic implementation** |
| PR #28 merged head / merge commit | `e1ae734959815ae02cb9e6fd105a40dd85a254b9` / `ac791ba8369aa1a7f6856cd9f573e0650995ea74` |
| Current work | docs-only `story.summary` chronology Architecture Contract; production implementation not started |
| Backend | Python 3.11+; FastAPI; async SQLAlchemy 2; Alembic; SQLite-first with PostgreSQL seam; pytest, Hypothesis, Ruff, MyPy |
| Frontend | TypeScript; Next.js 14 App Router; React 18; TanStack Query; TipTap; Tailwind; Vitest; PWA |
| CI | GitHub Actions on Ubuntu, Python 3.12 and Node 20; backend + frontend jobs in `.github/workflows/ci.yml` |

Feature PRs in this repository are **squash-merged**, with the merge commit subject `<PR title> (#N)`. GitHub CLI GraphQL repository lookup has occasionally been unreliable in this environment; note that the repository is `gorofan`, **not** `gorafan` — a wrong spelling produces a confusing "Could not resolve to a Repository" error. Use GitHub REST or `git fetch`/remote refs if GraphQL fails.

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

Three merged implementation notes now sit beside the ADR/RFC set as binding contracts for shipped work: `docs/architecture/entry-context-integration.md` (P1-6), `docs/architecture/edit-diff-capture-design.md` (P1-7), and `docs/architecture/legacy-entry-equivalence-design.md` (P1-8, accepted in PR #27 and implemented by PR #28). The proposed `docs/architecture/story-summary-chronology.md` is the next docs-only correctness contract and requires independent review before implementation. These notes record decisions made *inside* the space the ADR/RFC set fixed; where they appear to conflict with an ADR or RFC, those govern.

## 4. Architecture invariants

Every change must preserve the following. The cited files are the governing sources, not optional background reading.

| Invariant | Required interpretation | Governing sources |
|---|---|---|
| Store → Analyst → Writer | The creative layer is Store, Analyst, Writer plus a dev-only Bench. Store persists/retrieves knowledge; Analyst turns text into proposals; Writer consumes knowledge to write. Do not create named feature engines. | `adr/ADR-001-overall-architecture-philosophy.md`, `adr/ADR-002-store-analyst-writer-architecture.md`, `rfc/RFC-001-Core-Architecture.md` |
| Everything is Entry | Creative knowledge uses the prose-first `Entry` model and governed `type` vocabulary. New knowledge kinds are new approved types, not separate knowledge tables or `misc`. True aggregates retain their own lifecycle. **Non-knowledge operational records are not Entries** — see the P1-7 precedent in [section 10](#10-the-p1-7-contract-as-merged). | `adr/ADR-003-entry-first-data-model.md`, `rfc/RFC-002-Entry-Model-Contract.md` |
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
| Preserve migrations and data | `0001_initial` and `0002_entry_store` are frozen. Migrations are additive and forward-only; existing data and legacy substrate remain until a separately approved compatibility transition. | `adr/ADR-017-persistence-and-db-swap-strategy.md`, `rfc/RFC-002-Entry-Model-Contract.md` |

## 5. Verified completed implementation

### Related merged PRs

All rows below were checked against GitHub metadata and the current code/history. The merge SHA is the GitHub merge commit on `main`.

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
| [#23](https://github.com/cococute88/gorofan/pull/23) | `docs(architecture): design edit-diff capture` | **P1-7 design only — approved, zero production change.** The additive `edit_diff_captures` persistence contract, ratified by independent architecture review | `39cf740af3df62680e29111a9d39ed2e7c168842` | `docs/architecture/edit-diff-capture-design.md` (the approved contract) |
| [#25](https://github.com/cococute88/gorofan/pull/25) | `feat(entry): implement edit-diff capture` | **P1-7 implementation.** Migration `0003_edit_diff_capture`, the `EditDiffCapture` model, both capture call sites, the settle path, and 43 new tests. Independently reviewed before merge: 0 confirmed defects, 7/7 mutations detected | `271e27c4d1f409b7b0cd32e28f1c407ac2308be0` | `backend/app/models/edit_diff.py`, `backend/app/services/edit_diff_capture.py`, `backend/app/repositories/edit_diff_repository.py`, `backend/app/repositories/chapter_repository.py`, `backend/app/db/migrations/versions/0003_edit_diff_capture.py`, `entry_service.py`, `novel_service.py`, three `test_edit_diff_capture_*.py` files |
| [#27](https://github.com/cococute88/gorofan/pull/27) | `docs(architecture): design P1-8 equivalence bridge` | **P1-8 design — approved.** Independent stored coverage/runtime selection axes, exact projection/precedence contract, read-only API and cutover gates | `9deb643c1c506e604f1341a6d3e072c30220ab88` | `docs/architecture/legacy-entry-equivalence-design.md` |
| [#28](https://github.com/cococute88/gorofan/pull/28) | `feat(entry): implement P1-8 legacy equivalence diagnostics` | **P1-8 implementation — merged.** Read-only owner-scoped coverage/runtime diagnostics, final-selection chronology evidence, and fail-closed ambiguous regenerate handling; no authority cutover | `ac791ba8369aa1a7f6856cd9f573e0650995ea74` | `backend/app/services/legacy_entry_equivalence.py`, schemas/API and focused tests |

### Implemented behavior at the verified main

- **Entry persistence/lifecycle:** Entry scope/type/status constraints, ownership, canonical lifecycle, orphan-anchor filtering, correction through supersession, and single-current handling for `relationship.state` / `story.summary` are implemented.
- **`retrieve()`:** `EntryService.retrieve()` calls the Store retrieval seam. It defaults to canon, enforces owner/scope/type/subject/status constraints, excludes orphaned anchors, ranks deterministically, selects whole Entries under a knowledge budget, and returns retrieval trace data.
- **Context Assembly:** `assemble_entry_context()` is a pure bridge over a selected `EntryRetrievalResult`. It re-estimates complete rendered blocks, never truncates an Entry, and keeps assembly exclusions separate from retrieval exclusions.
- **Review:** Review read/accept/reject/edit/supersede APIs exist, and the frontend provides one non-blocking type-agnostic Review Queue/Card.
- **Prompt assets:** `chat.default`, `novel.continue`, and `summary.rolling` are UTF-8 repository assets loaded by the allow-listed loader. `PromptTemplate` remains API/data compatibility only, never an architecture prompt-body fallback.
- **User authoring and audit reads:** User-authored Entry creation is server-provenanced; default Entry lists expose live canon only, while `include_history=true` permits labelled audit/history data. Cursor pagination and immutable supersession correction are implemented.
- **P1-6 production wiring (PR #21):** `backend/app/services/entry_generation_context.py` is the single production call site chaining `EntryService.retrieve()` → `assemble_entry_context()` → `PromptEngine`. Chat and Novel each invoke it inside T1, before any token is streamed, exactly once per request — including the Chat regenerate path.
- **P1-7 edit-diff capture (PR #25):** both data-destroying paths now preserve the AI pre-image. `EntryService.edit_review_entry()` reads the pre-image under the existing Entry row lock and inserts the capture in the same transaction as the destructive field assignment; `NovelService._append_chapter()` captures the streamed segment before concatenating it into `Chapter.content_text`, under an explicit chapter row lock. The prior segment is settled at T1 of the next continuation of the same chapter. See [section 10](#10-the-p1-7-contract-as-merged) for the full contract.
- **P1-8 diagnostic implementation (PR #28 merged):** `legacy_entry_equivalence.py` and the authenticated compare endpoint implement PR #27's pure projections, coverage precedence, and provider-free Chat/Novel shadows. Future/unknown summary selection remains measured rather than repaired, and regenerate assistant/user timestamp ties fail closed before ambiguous content reaches downstream diagnostic work. It does not change authority.
- **Chronology correctness contract (current docs branch):** `docs/architecture/story-summary-chronology.md` defines the explicit target-Chapter anchor, strict-prior Entry summary eligibility, current/future/unknown fail-safe exclusion, ascending story order, duplicate/legacy-overlap handling, Retrieval ownership, budget isolation, Migration Decision B, and the follow-up test matrix. Production implementation is intentionally zero until independent review and merge.

### P1-6 contract as merged

Later phases inherit these decisions. Change them only through an explicit architecture decision, not incidentally.

| Decision | Value as merged | Rationale source |
|---|---|---|
| Feature flag | `FEATURES["entry_store_context"]`, read via `Settings.entry_store_context_enabled`, default **OFF** | `docs/architecture/entry-context-integration.md` §2 |
| Flag OFF behavior | Zero Entry queries — the flag is checked before the retrieval request is constructed. Provider-visible payload (`messages`, `system`, `token_count`) is byte-identical to pre-P1-6; the only delta is a diagnostic `trace["entry_context"]` marker | §2, §6 |
| Block kind | First-class `entry` `BlockKind`. Entry canon is **never** relabelled `memory` and never merged into legacy `lore` text | ADR-018, RFC-003 §13.1 |
| `DEFAULT_PRIORITY["entry"]` | **65** — above `memory` (60) and `lore` (50) because human-gated canon should outlive rolling chat memory and the legacy keyword scan; below `world` (70) / `chapter` (75) / `persona` (80) / `character` (90) because P1-6 is additive and legacy stays authoritative until a separately approved cutover | §3 |
| `LAYER_ORDER` | `entry` between `lore` and `memory`. One insertion; every pre-existing kind keeps its relative position | §3 |
| Truncatability | `truncatable=False`. A partially rendered Entry is a fabricated fact, so the BudgetManager drops the whole block | §3 |
| Variable substitution | Entry content is **not** `{{...}}`-resolved. Stored canon is data, not an authored template | `engines/prompt/engine.py` |
| Knowledge-slice budget | `max(256, context_window * 0.15)`, safety cap `limit=20`. Deliberately below the chat memory hint (`0.4`) during coexistence, so Entry cannot starve `memory` | RFC-003 §11.1, §4 |
| Chat scopes | `user`, the active `character`, that character's `world`. **Chat never declares a `work` scope** — a `ChatSession` holds no work and RFC-003 §13.3 forbids guessing among works | RFC-003 §13.3, §5 |
| Novel scopes | `user`, this `work`, its `world`, each linked `character`; `task_kind=scene` | §5 |
| Status handling | Inherited, never widened: no `status_filters`, `include_rejected=False`, `include_superseded=False`. Canon only; orphaned anchors excluded by `retrieve()` | RFC-003 §7.4, §7.5 |
| Trace | `trace["entry_context"]` keeps retrieval and assembly exclusions separately attributable and distinguishes flag-off / nothing-eligible / canon-injected | RFC-003 §12, §6 |
| Error policy | Retrieval failures **propagate**; they are not swallowed. Nothing is streamed or persisted on that path | §7 |
| Separation preserved | chat-private `Memory`, legacy `_make_lore_blocks()` scanner, and Entry canon remain three distinct block kinds with distinct trace identity | ADR-018, RFC-003 §13.1 |

### Explicitly not complete

- **Legacy remains authoritative.** P1-8 measured equivalence but did not move authority. `Character.personality`/`speech_style`, the `World` fields, `Lorebook`/`LoreEntry`, and legacy prior `Chapter.summary` context remain intact; `PromptEngine._make_lore_blocks()` still runs.
- **The flag remains default OFF.** Until an operator enables `FEATURES='{"entry_store_context": true}'`, real generation prompts are unchanged from pre-P1-6. The chronology implementation must preserve this boundary and use legacy authority for same-Chapter summary overlap until a later cutover.
- **Chronology implementation is not complete.** Current Entry retrieval does not receive a target Chapter as-of anchor and still scores `story.summary` recency from `updated_at`/`created_at`; future/unknown summaries can rank and consume budget. The proposed contract fixes policy only.
- **Chat cannot reach work canon or `relationship.state`**, because chat declares no work scope. That needs an explicit work selection (P5-1/P5-3), not a heuristic.
- **Nothing reads the captured edit diffs.** P1-7 captures and stops. The design's §13 service-level read contract `list_edit_diff_captures` — including the live-resolution of a trailing unsettled row and the exclusion of soft-deleted Works — is **deliberately unimplemented and owned by P2-5**. There is no HTTP endpoint, DTO, reader, or frontend for captures, and adding one is out of scope until distillation is scoped.
- **P1-9 review audit persistence is undecided.** Entries carry lifecycle/provenance timestamps but there is no approved actor/action history design. P1-7 deliberately supplies none — see [section 10](#10-the-p1-7-contract-as-merged).

## 6. Code map

| Area | File or directory | Responsibility at verified main |
|---|---|---|
| Entry model | `backend/app/models/entry.py` | ORM Entry entity and persisted scope/type/status/provenance shape. |
| Entry schema | `backend/app/schemas/entry.py` | Pydantic contracts for creation, authoring, review, listing, retrieval, and trace data. |
| Entry repository | `backend/app/repositories/entry_repository.py` | Owner-scoped persistence, `get_for_update()` row locking, and retrieval-candidate query access. |
| Entry service | `backend/app/services/entry_service.py` | Validation, lifecycle, supersession, review helpers, audit listing, `retrieve()`, and the **Path A edit-diff capture call**. |
| Retrieval policy | `backend/app/services/entry_retrieval.py` | Pure ranking, policy version, whole-Entry selection, and exclusion decisions. |
| Entry API | `backend/app/api/v1/entries.py` | Authenticated authoring, canonical/audit reads, Review Card routes, and pagination boundary. |
| Entry migration | `backend/app/db/migrations/versions/0002_entry_store.py` | Additive Entry Store migration after frozen `0001_initial`. **Frozen.** |
| **Edit-diff migration** | `backend/app/db/migrations/versions/0003_edit_diff_capture.py` | **Current Alembic head.** Creates `edit_diff_captures` only; no `ALTER` on any existing table, no backfill. |
| **Edit-diff model** | `backend/app/models/edit_diff.py` | `EditDiffCapture` ORM entity, all 11 named CHECKs, two per-source UNIQUEs, three indexes. **Declares no `relationship()`** so deletion cascades stay at the database level. |
| **Edit-diff service** | `backend/app/services/edit_diff_capture.py` | `EDIT_DIFF_MAX_CHARS`, `measure_side()`, the closed `context` key validator, and the three capture operations (Path A, Path B draft, settle). |
| **Edit-diff repository** | `backend/app/repositories/edit_diff_repository.py` | Owner-scoped `add()`, `next_sequence()` (caller must hold the source row lock), and `list_unsettled_for_chapter()`. |
| **Chapter lock seam** | `backend/app/repositories/chapter_repository.py` | `chapter_for_update_stmt()` / `ChapterRepository.get_for_update()`. The statement builder is exposed separately so a test can assert `FOR UPDATE` on the compiled PostgreSQL form — SQLite ignores the clause. |
| Context Assembly | `backend/app/engines/prompt/entry_context.py` | Pure selected Entry result to prompt-block conversion, whole-block assembly budget, and the flattened `entry_context` prompt-trace section. |
| Entry generation seam | `backend/app/services/entry_generation_context.py` | **The single production call site** for `retrieve()` + `assemble_entry_context()`. Owns the feature-flag check, the Chat/Novel retrieval situations, and the knowledge-slice budget. |
| Equivalence diagnostic | `backend/app/services/legacy_entry_equivalence.py`, `backend/app/schemas/equivalence.py`, `backend/app/api/v1/entries.py` | P1-8 pure projection/coverage comparison and owner-safe, read-only Chat/Novel runtime shadow exposed as `POST /api/v1/entries/equivalence:compare`. |
| Chronology contract | `docs/architecture/story-summary-chronology.md` | Proposed post-P1-8 Chapter-summary eligibility/order contract. Documentation only; no production implementation yet. |
| Prompt blocks | `backend/app/engines/prompt/blocks.py` | Block kinds (including `entry`), `LAYER_ORDER`, `DEFAULT_PRIORITY`, and `PromptBlock` structure. |
| Prompt engine | `backend/app/engines/prompt/engine.py` | Deterministic collect → resolve → order → budget → final provider-neutral assembly. |
| Prompt assets | `backend/app/engines/prompt/assets.py` | Allow-listed repository asset loader with asset identity/version/digest. |
| Prompt asset bodies | `backend/prompts/chat/default.v1.md`, `backend/prompts/novel/continue.v1.md`, `backend/prompts/shared/rolling-summary.v1.md` | UTF-8 repository prompt bodies. |
| Chat service | `backend/app/services/chat_service.py` | Chat SSE orchestration, idempotency/serialization, memory lifecycle, legacy lore loading, and the T1 Entry-context call. |
| Chat engine | `backend/app/engines/chat/engine.py` | Chat prompt assembly and provider streaming; relays externally assembled Entry blocks. |
| Novel service | `backend/app/services/novel_service.py` | Work/chapter service and SSE continuation; builds legacy story context, issues the T1 Entry-context call, **settles the previous capture at T1**, and **captures the streamed segment inside the locked append transaction**. |
| Novel engine | `backend/app/engines/novel/engine.py` | `ChapterContext`, continuation prompt assembly, and provider stream. |
| Structured logging | `backend/app/core/logging.py` | JSON logger; `request_id` injected from a ContextVar. Secrets, plaintext keys, prompt bodies, **and captured author prose** are never logged. |
| Review frontend | `frontend/src/lib/api/endpoints.ts`, `frontend/src/hooks/use-entry-review.ts`, `frontend/src/components/review/` | Typed endpoint wrappers, queue mutations/cache transitions, Review Queue and type-agnostic Review Card. **Untouched by P1-7.** |
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
| Backend full pytest | `backend` | `.\.venv\Scripts\python.exe -m pytest` | **252 passed, 0 failed** after the regenerate tie fail-closed repair. |
| P1-8 target tests | `backend` | `.\.venv\Scripts\python.exe -m pytest tests/unit/test_legacy_entry_equivalence.py tests/integration/test_legacy_entry_equivalence_api.py tests/golden/test_legacy_entry_equivalence_golden.py` | **53 passed.** Covers the existing contract and previous blockers plus resolved-empty Character/World sources, multi-Character rendered-order match/mismatch, exact future-summary retrieval rejection chronology, and assistant/user regenerate timestamp-tie fail-closed spy checks (including Memory rows and evaluation-time variants). |
| Related regression bundle | `backend` | Entry lifecycle/retrieval/context/review, Chat/Novel/Memory/streaming, prompt budget/assets, edit-diff, golden, migrations | **230 passed, 0 failed.** |
| P1-7 target tests | `backend` | `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_edit_diff_capture_schema.py tests/integration/test_edit_diff_capture_entry.py tests/integration/test_edit_diff_capture_novel.py` | **41 passed** (schema 12, Path A 11, Path B 18). `tests/integration/test_migrations.py` grew from 3 to 5 for the remaining 2. |
| P1-6 target tests | `backend` | `.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_entry_prompt_integration.py tests/unit/test_entry_generation_context.py tests/integration/test_entry_context_generation.py` | **41 passed.** The integration file drives the real SSE endpoints with a recording provider. |
| Entry/retrieval/assembly target tests | `backend` | `.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_entry_retrieval.py tests/unit/test_entry_context_assembly.py tests/integration/test_entry_retrieval.py tests/golden/test_retrieval_context_golden.py` | Repository command paths verified; use for Store/context work. |
| Ruff | `backend` | `.\.venv\Scripts\python.exe -m ruff check app tests` | `All checks passed!` on the blocker-repair branch. |
| Frontend test | `frontend` | `npm run test` | Passed: 3 files / 13 tests on 2026-09-05; P1-8 did not touch the frontend. |
| Frontend lint | `frontend` | `npm run lint` | Passed on 2026-09-05. |
| Frontend production build | `frontend` | `npm run build` | Passed: 15 routes on 2026-09-05. |
| Alembic revisions | `backend` | `.\.venv\Scripts\python.exe -m alembic heads` | **`0003_edit_diff_capture (head)`** — single head, `down_revision = "0002_entry_store"`. |
| Whitespace/patch integrity | repository root | `git diff --check` | Clean on the blocker-repair branch. |

The verified `main` baseline was **36 pre-existing errors in 11 files**. On this blocker-repair branch, `.\.venv\Scripts\python.exe -m mypy app tests` reports **31 errors in 10 files** because the five pre-existing nullable annotations on `PromptEngine.AssembleInput` were corrected; the changed P1-8 scope reports zero errors. No new full-MyPy error was introduced.

Full MyPy is not the clean merge gate. For a scoped change, record the current errors for precisely the changed scope and do not introduce or increase them; fix new errors in that scope before review.

GitHub CI runs:

- **Backend:** install `.[dev]`, run `ruff check app || true`, run `alembic upgrade head`, then `pytest -q`.
- **Frontend:** `npm install`, `npm run lint`, `npm run test`, `npm run build`.

For PR #25's final head `a0d6bad298b63f91dca5addcc7a9f17c1193fd79`, GitHub Actions `backend` and `frontend` checks both completed with `success`. Note that the CI Ruff step uses `|| true`, so a local Ruff pass remains required.

### Migration verification pattern worth reusing

`tests/integration/test_migrations.py` now demonstrates the pattern any future additive migration should copy, and P1-8 should reuse it if it ever needs one:

- The chain applies on a fresh **isolated** SQLite database in `tmp_path`, never the developer's `backend/data/app.db`, whose fingerprint is asserted unchanged in a `finally` block.
- `0003` is asserted to be the single head with the expected `down_revision`.
- The revision source is parsed with `ast` to prove it calls `create_table`/`drop_table` and **never** `add_column`, `alter_column`, `drop_column`, `drop_constraint`, `execute`, or `batch_alter_table`.
- Every pre-existing object's `sqlite_master.sql` text is captured before and after the upgrade and asserted byte-identical.
- The whole chain is compiled for the PostgreSQL dialect and asserted to contain no `ALTER TABLE`, no `NULLS NOT DISTINCT`, and no `IS DISTINCT FROM`.
- Downgrade to `0002` and re-upgrade to head leave exactly the expected table sets.

## 8. Environment cautions

Only confirmed local facts are listed here.

1. **PowerShell/Kiro wrapper behavior:** direct short commands and concurrent shell calls have been interrupted or malformed in this workspace. If a wrapper damages a command, do not keep retrying the same shell string. Use Python `subprocess.run([...], cwd=..., shell=False)` with an argv list instead. Example pattern:

   ```powershell
   python -c "__import__('sys').exit(__import__('subprocess').run(['git','status','--short'],cwd=r'C:\gv\rfrf').returncode)"
   ```

   This is the verified fallback used successfully for Git status and Alembic inspection.

2. **Local database stamp differs from repository migrations:** read-only `alembic current` fails with `Can't locate revision identified by '0002_story_bible'`. Repository migration files themselves report `0003_edit_diff_capture (head)`. `backend/data/app.db` may contain user data; do **not** delete, recreate, stamp, migrate, or otherwise modify it without explicit user approval. This is P1-10 and remains deliberately untouched.

3. **Stashes are protected:** `stash@{0}` is `codex/phase1-review-card-api`; `stash@{1}` is `codex/new`. Do not apply, pop, drop, or rewrite either without explicit user approval.

4. **Do not revive the old architecture:** the `codex/new` stash is the Architecture-Frozen-predecessor direction described in `implementation-status.md`: separate reference/planning code and `0002_story_bible` / `0003_reference` migrations. It conflicts with ADR-002, ADR-003, and ADR-004, and it collides by name with the real `0003_edit_diff_capture`. Do not merge or selectively transplant it.

5. **UTF-8 is mandatory:** read and save every text file as UTF-8. Prompt assets and Settings `.env` handling already depend on UTF-8.

6. **Repository name:** `cococute88/gorofan`. Misspelling it as `gorafan` produces a "Could not resolve to a Repository" GraphQL error that looks like an auth failure.

## 9. Remaining Phase 1 work

The current `tasks.md`, `implementation-status.md`, and production code agree on this order.

| Task | Current state | Dependencies | Do not expand into | Recommended order |
|---|---|---|---|---|
| ~~**P1-6**~~ `retrieve()` → Context Assembly → real generation path | **Complete** (PR #21, `1b2a850`). Single production call site wired for Chat and Novel behind an OFF-by-default flag. | — | — | Done. |
| ~~**P1-7**~~ edit-diff capture | **Complete** (design PR #23 `39cf740`, implementation PR #25 `271e27c`). Both destroying paths capture the pair; `alembic heads` is `0003_edit_diff_capture`. The permanent-data-loss clock has stopped. | — | — | Done. The §13 read contract belongs to **P2-5**, not to a follow-up here. |
| ~~**P1-8**~~ legacy Character/World/Lore ↔ Entry equivalence bridge | **Complete** (design PR #27, implementation PR #28, merge `ac791ba`). Pure projections, coverage precedence, typed owner-safe API, and Chat/Novel runtime shadows are covered by 53 focused tests. Legacy remains authoritative and `_make_lore_blocks()` still runs. | — | Backfill, legacy deletion, read cutover, migration, or flipping the flag as part of the bridge. | Done; chronology evidence feeds the next gate. |
| **Story-summary chronology contract** | Docs-only contract written; independent architecture review/merge pending. Production implementation not started. | P1-8 merged. | Generation Preparation, migrations, authority cutover, legacy removal, provider/UI/style work. | Review/merge contract, then implement from a new branch/session. |
| **Story-summary chronology implementation** | Not started. Current Entry retrieval still lacks target-Chapter as-of eligibility and uses DB timestamp recency. | Accepted chronology contract. | AOS-1 or broader retrieval redesign. | Immediately before AOS-1. |
| **P1-9** review audit persistence decision | Not implemented. Current Entries have lifecycle/provenance but no approved actor/action history design. P1-7 deliberately defined no actor or action vocabulary. | P1-1 complete. | Unapproved JSON schema, implementation migration in the design PR, reusing `edit_diff_captures` as a review timeline. | Independent of the chronology/AOS path unless architecture review chooses earlier. |
| **P1-10** local development environment cleanup | Optional and blocked by user-data safety. Local DB stamp is stale; protected stashes exist. | Explicit user approval for data/stash actions. | Automatic DB recreation, `alembic stamp`, stash application/deletion. | Last, and only with approval. |

## 10. The P1-7 contract as merged

`docs/architecture/edit-diff-capture-design.md` is the authoritative contract; this section is the summary of what actually shipped, so a later task can tell at a glance what is settled and what it must not disturb.

### 10.1 What an edit-diff capture is

A **non-Entry operational learning-source record**. It asserts nothing, carries no scope, has no `captured → proposed → canon` lifecycle, never enters retrieval or a prompt, and has no coherent meaning for `accept`. It fails all six Entry obligations (design §5.2). `note` is not a loophole — it is a low-structure kind of *knowledge*.

The independent architecture review **ratified** that adding a non-knowledge operational table does not consume the ADR-003 §6 promote-a-type escape valve: that valve governs moving *knowledge* out of `entries`, whereas ADR-015 §2.2 separately sanctions new tables as non-destructive schema evolution, and RFC-001 names edit-diff capture as substrate code alongside the entry store and the retrieval function. **This precedent is narrow.** It licenses operational records, not knowledge libraries; a table named `dialogue_library` or `character_dna_attributes` is still forbidden.

### 10.2 Capture predicate

A row is written **if and only if both** hold: (a) an AI-produced text and a human replacement *for that same text* both exist at one identifiable moment, **and** (b) completing the current write makes one of them unrecoverable from the persisted schema. This predicate, not a list of endpoints, is the contract a new call site must be tested against.

Consequently these capture **nothing**: accept without edit, reject without edit, `supersede()` (the old canon survives via `superseded_by_entry_id`, so (b) is false), direct user authoring, human-first authoring, chat regenerate (`Message` rows are append-only), and an author's chapter autosave.

### 10.3 The two capture paths

| | Path A — Review Card edit | Path B — Novel continuation |
|---|---|---|
| Call site | `EntryService.edit_review_entry()` | `NovelService._append_chapter()` |
| Anchor | `entry_id` | `chapter_id` |
| `source_kind` | `entry-review-edit` | `chapter-continuation` |
| Pre-image read | `entry.content` before the field assignment loop | the streamed buffer before concatenation |
| Row lock | existing `_get_for_update()` on the Entry | **new** `ChapterRepository.get_for_update()` on the Chapter |
| Settledness at INSERT | **born settled** — both sides exist | **unsettled** (`settled_at IS NULL`) |
| Suppression | `before_sha256 == after_sha256` writes no row, which also makes a replayed request inert | an empty provider buffer writes no row |

Only `content` is captured on Path A. `title` / `data` changes are recorded as names in `context.fields_changed`, never as text pairs.

### 10.4 Settle — decided and implemented

The Path B after-side is settled by **the next continuation of the same chapter**, at T1 of `_continue_impl()` before any token is streamed, guarded by `settled_at IS NULL` and recording `context.settle_trigger = "next-continuation"`. There is no other write-path trigger. The author's 1.2 s autosave (`update_chapter`) is deliberately **not** hooked: the first save lands seconds into revision, so settling there would systematically record "the human changed nothing" in a corpus whose entire purpose is measuring how the human changes it. Missing data is honest; biased data is not.

**A trailing unsettled row is a normal terminal state, not a gap or an error.** Only the before-side is irrecoverable; the after-side lives in `chapters.content_text`, which nothing destroys. Its after-side is resolved at read time from live `content_text` plus the stored `insert_offset` and `chapter_version`. Do not "fix" trailing unsettled rows by force-settling or deleting them, and do not alarm on a plain count of them — that count measures how many chapters are still being written. The genuine health signal is an unsettled row on a chapter that has *since received another continuation*.

### 10.5 Transaction tiers

| Tier | Data | Policy as implemented |
|---|---|---|
| 1 — **atomic** | Path A pre-image | Same transaction as the destructive write. A failure propagates and rolls the edit back; the AI original survives and the author's text is still in React local state. |
| 2 — **atomic** | Path B draft side | Same transaction as `_append_chapter()`. A failure rolls the append back, so no untraceable segment is merged. In the provider-error branch the capture failure is logged separately and **must not replace the provider error the author needs to see**. |
| 3 — **best-effort** | Path B settle snapshot | May fail without failing the request. Logs a structured warning and leaves the row unsettled for a later continuation or read-time resolution. |

The dividing rule: **capture that holds the only copy is atomic with the write that would destroy it; capture that duplicates surviving data is best-effort.** "Non-blocking" means no added user step, round trip, LLM call, or queue wait — it does **not** mean `except Exception: pass`, which is forbidden and is asserted against at the source level by the tests.

### 10.6 Schema facts that must not be re-litigated

- `before_state` and `after_state` are **independent** columns valued `stored` | `oversize`. There is no `payload_state`, and **"pending" is not a state value — it is `settled_at IS NULL`.** A Path B row that is oversize *and* unsettled is legal and has a dedicated regression test.
- **Truncation is prohibited.** An oversize side stores NULL text with its SHA-256 and code-point length retained, decided per side independently. Text is byte-exact with no Unicode normalization; no structured diff is stored.
- `EDIT_DIFF_MAX_CHARS = 100_000` per side is a **code constant with no schema dependency**. No column, CHECK, or index refers to the number, so it can change with no migration and existing rows stay valid.
- **No SQLAlchemy `relationship()` points at `edit_diff_captures`.** Deletion cascades are enforced by database `ON DELETE CASCADE` from `users`, `entries`, and `chapters`. A relationship without `passive_deletes=True` would null `chapter_id` and silently orphan the author's prose; a registry-walking test fails if one is ever added without it.
- The two `UNIQUE` constraints rely on NULLs being distinct, which holds on both SQLite and PostgreSQL. `NULLS NOT DISTINCT` must not be used. No partial indexes, no expression indexes, no dialect-specific predicates.
- `sequence` is `MAX(sequence) + 1` per source, derived **only** while holding that source's row lock. `_active_continue` is a module-level in-process set, not a database lock, and is not accepted as the serialization mechanism.
- Retention is **indefinite with no automatic expiry**. There is **no feature flag** — a default-OFF flag on a capture feature collects nothing, and a default-ON flag is not a flag.
- Captured text never enters a prompt, log line, warning payload, trace, error message, API response, or Bench fixture. The Tier-3 warning logs `chapter_id` and the exception *class name* only — never `str(exc)`, whose SQLAlchemy form would echo bound parameters.

### 10.7 P1-9 boundary — do not blur these

P1-7 answers *what did the AI write and what did the human make of it*. P1-9 answers *who did what, when, and can it be undone*.

1. P1-7 defines **no** actor vocabulary and **no** action vocabulary. `user_id` is present only for ownership scoping, as ADR-017 §2.3 requires of every table. `source_kind` names the anchor path, not an action.
2. P1-7 writes **no** row for accept, reject, or supersede. An "accepted with no edit" row means the boundary has been violated.
3. P1-7 is not the review history, and no feature may come to depend on it as such.
4. When P1-9 lands, a capture row **may** gain a nullable FK to a review-event row. P1-7 did not pre-invent that column, that table's name, or its vocabulary.
5. P1-9 must not store text pairs; if it needs them it joins to this table.

### 10.8 Known deliberate gaps

Neither is a defect, and neither blocked the merge:

1. **`list_edit_diff_captures` (design §13) is unimplemented.** P2-5 owns it. The schema is sufficient for it: `insert_offset`, `chapter_version`, and both hashes are stored precisely so a later pass can align a segment against a chapter snapshot.
2. **Work soft-delete read exclusion is unimplemented.** P1-7 owns capture *retention* only, and soft-deleted Works correctly retain their rows because soft delete is reversible. Excluding them belongs to the same future reader. No `work_id` is denormalized onto the table; the exclusion is a read-time `chapters → works` join.

Three smaller observations recorded by the pre-merge review, all accepted as non-blocking: design §9.2's "increment a counter" is satisfied by the structured log because the repository has no metrics substrate and building one would exceed P1-7's scope; a Tier-2 failure on the success path ends the SSE stream without an `error` event, which the design's stated outcome permits; and `insert_offset` is `len(content_text)` *before* concatenation exactly as design §6.3 defines it, which is two characters ahead of the separator when the chapter is non-empty — an alignment detail for P2-5, not an error.

## 11. P1-8 merged result and chronology contract gate

PR #28 is merged at `ac791ba8369aa1a7f6856cd9f573e0650995ea74` (merged head `e1ae734959815ae02cb9e6fd105a40dd85a254b9`). Its owner-safe, read-only diagnostic preserves the repaired source attribution/order, final-selection chronology evidence, and regenerate timestamp-tie fail-closed behavior. P1-8 intentionally moved no authority and changed no production eligibility.

The production debt it proved is now specified in `docs/architecture/story-summary-chronology.md`. The current Novel operation is continuation of an explicitly addressed Chapter; the target Chapter's current `work_id/index` is the chronology anchor. Only live same-Work Chapter-subject summaries at a strictly lower `Chapter.index` are eligible. Current, future, unknown, duplicated, foreign, deleted/orphaned, and inconsistent summaries are excluded before ranking or budget. Selected prior summaries render in ascending Chapter index; Entry DB timestamps are audit/diagnostic evidence only. Legacy remains authoritative during coexistence and wins same-Chapter overlap.

Migration Decision **B** is fixed for review: the existing `Chapter.id/work_id/index`, `UNIQUE(work_id,index)`, Entry Chapter subject, and lifecycle fields are sufficient, but request propagation and application validation are missing. No migration is authorized. This docs-only contract requires independent architecture review and merge before any implementation begins.

## 12. First-run checklist for a new AI

1. Read `AI-HANDOFF.md`, `docs/architecture/story-summary-chronology.md`, the P1-8 design/implementation, RFC-002, RFC-003, RFC-004, and RFC-009. The next action is independent review of the chronology Architecture Contract, not implementation.
2. Fetch and compare `origin/main`; if this handoff SHA (`ac791ba`) is no longer current, re-validate GitHub state, code call sites, and status documents.
3. Check the working tree and list stashes without modifying either. Keep user work, the local DB, and stashes untouched.
4. Confirm `FEATURES["entry_store_context"]` still defaults OFF and Alembic head remains `0003_edit_diff_capture` without running or changing the user's local DB.
5. Trace the real production path: `NovelService._continue_impl()` / `_build_story_context()`, `build_novel_retrieve_request()`, `EntryService.retrieve()`, `entry_retrieval.rank_entries()/select_entries()`, Context Assembly, and PromptEngine.
6. Challenge the contract with target-not-latest, current-summary, future high-score/new-timestamp, Work-subject unknown, inconsistent `created_at_chapter_id`, Chapter reorder, duplicate canon, equal index corruption, deleted/foreign source, legacy overlap, and budget-isolation counterexamples.
7. Confirm Migration Decision B from actual constraints rather than proposing convenience metadata.
8. Keep the review docs-only. Do not implement, change schemas, create migrations, enable the flag, remove legacy paths, or begin AOS/Generation Preparation.
9. Verify `git diff --check`, strict UTF-8/no BOM, Markdown links, docs-only diff, no local DB/stash mutation, and the exact Draft PR base/head.
10. Report the independent verdict and required contract edits. Merge only after a separate explicit decision.

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

## 14. Preserved post-P1-8 Author OS / Style direction

This work does not implement the following direction, but later handoffs must preserve it:

- **Novel-first product:** rfrf is a personal long-form novel generation workspace; Character Chat remains an independent supporting feature.
- **Shared Generation Preparation:** `Story/Canon + Character/Relationship + recent Chapter + Scene input` feeds one provider-neutral selection/order/budget/trace preparation seam.
- **Two terminal routes:** the same preparation can drive (A) direct Provider API generation, with Gemini as the practical first direct-generation path, or (B) a complete Prompt Packet copied to ChatGPT, Claude, or a generic external model. Both routes converge on Chapter apply/import, user revision, edit-diff evidence, and the next generation.
- **Taste and Voice remain distinct:** Taste is user preference, while Voice/Narrative Style describes prose behavior; neither is Story Canon and neither is mandatory for the first usable novel loop.
- **Reference-based Style Baseline:** later work may register multiple novel references, analyze per-reference features, and derive a shared/preferred baseline. Korean quantitative candidates include Kiwi-backed morphology, endings, POS/POS n-grams, sentence length, dialogue ratio, spacing, punctuation, and lexical repetition. Other languages require a language-specific extractor seam.
- **Hybrid Style Engine:** deterministic/statistical features may combine with Gemini semantic Voice/Narrative Style analysis. Long references should use chunked/background analysis; generated prose should be compared with the Style Baseline for scene drift and long-form consistency.
- **Sequencing constraint:** reference ingestion, persistence, background analysis, and Style Engine implementation must not delay the first usable Novel generation loop.

## 15. Copyable next-task prompt

```text
You are continuing AI Author OS / gorafan at C:\gv\rfrf. The GitHub repository is
cococute88/gorofan (note the spelling: gorofan, not gorafan).

Start by reading C:\gv\rfrf\AI-HANDOFF.md, then the governing ADR/RFC originals it names.
Do not trust this prompt over current GitHub, Git, architecture, code, or test state: fetch
origin/main, inspect the working tree, and list stashes without touching them. The handoff
snapshot is main ac791ba8369aa1a7f6856cd9f573e0650995ea74, where P1-8 implementation
PR #28 is merged (merged head e1ae734959815ae02cb9e6fd105a40dd85a254b9).
If main has advanced, re-verify before relying on any of it.

Your task is an independent Architecture Review of the docs-only Story Summary Chronology
Contract. Read docs/architecture/story-summary-chronology.md completely and inspect the actual
models, Novel continuation path, Entry retrieval/ranking, Context Assembly, PromptEngine,
P1-8 diagnostics, governing RFCs, and tests. Do not rely only on the author's conclusions.

Challenge at least: explicit target Chapter authority versus latest Chapter, Chapter reorder,
strict-prior/current/future/unknown classification, Work-subject and non-chapter-level summaries,
conflicting created_at_chapter_id/provenance, future high-score/new-timestamp exclusion before
budget, current-summary behavior for continuation/initial/regeneration, equal-index corruption,
duplicate active canon, legacy+Entry overlap, deleted/foreign/orphan anchors, provider-visible
ascending order, and feature-flag OFF/ON behavior. Verify whether Migration Decision B is
supported by Chapter.id/work_id/index, UNIQUE(work_id,index), Entry subject, and lifecycle fields.

Keep the review documentation-only. Do not implement production logic, change APIs or schemas,
create a migration, enable the Entry flag, remove/deprecate legacy scanning, start AOS Generation
Preparation, or modify local DB/stashes. The contract must preserve this sequence: independent
review/merge, then a new branch/new Codex session for chronology implementation, then shared
Generation Preparation, Scene input, Gemini direct + external Prompt Packet, Novel workspace,
Chapter apply/import, and only later Voice/reference/Kiwi/semantic/hybrid style work.

Verify git diff --check, strict UTF-8/no BOM, Markdown links, docs-only diff, no migration or local
DB/stash mutation, and the Draft PR base/head/CI. Do not modify or merge the PR unless separately
asked. Report the independent verdict, any blocker with a concrete counterexample, and whether the
contract is safe to merge before implementation.
```

**Recommended execution model:** Claude Code — Opus High; Codex — high reasoning; Cursor — strongest available reasoning model. Chronology is a correctness boundary, so review must prefer fail-safe exclusion over timestamp or identifier guesses.
