# AI Author OS / gorafan — AI Handoff

> **Canonical handoff document for a new AI session.**
>
> **Verified at:** 2026-07-31T16:01:29+09:00
> **Verified `main`:** `1a9a57e2f9653c99989c9c19355bcaba0b9a3c7c`

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
10. [Immediate next task: P1-6](#10-immediate-next-task-p1-6)
11. [P1-6 expected files and validation](#11-p1-6-expected-files-and-validation)
12. [First-run checklist for a new AI](#12-first-run-checklist-for-a-new-ai)
13. [Completion-report rules](#13-completion-report-rules)
14. [Copyable P1-6 execution prompt](#14-copyable-p1-6-execution-prompt)

## 1. To the AI reading this

This is the starting point for a new AI session. Treat the checked code, Git history, GitHub PR state, and authoritative architecture documents as stronger evidence than any prior chat, report, or this snapshot.

Before changing anything:

- Read this file **and** the relevant ADR/RFC originals in `docs/architecture/`.
- Confirm the verification timestamp and `main` SHA above.
- If `origin/main` has advanced after `1a9a57e2f9653c99989c9c19355bcaba0b9a3c7c`, re-verify the affected GitHub, code, task/status, and test facts before relying on this handoff.
- Do not infer implementation completion from file presence. Follow executed production paths, API exposure, and passing tests.

## 2. Repository identity

| Item | Verified value |
|---|---|
| GitHub repository | [`cococute88/gorofan`](https://github.com/cococute88/gorofan) |
| Local repository | `C:\gv\rfrf` |
| Default branch | `main` |
| Verification time | `2026-07-31T16:01:29+09:00` |
| Verified `origin/main` / local `main` | `1a9a57e2f9653c99989c9c19355bcaba0b9a3c7c` |
| PR #19 | [`feat(entry): add authoring and audit read API`](https://github.com/cococute88/gorofan/pull/19), merged 2026-07-31 |
| PR #19 merge commit | `1a9a57e2f9653c99989c9c19355bcaba0b9a3c7c` |
| Open PRs at verification | None (`GET /pulls?state=open` returned `[]`) |
| Working tree before this documentation branch | Clean (`git status --short` produced no paths) |
| Backend | Python 3.11+; FastAPI; async SQLAlchemy 2; Alembic; SQLite-first with PostgreSQL seam; pytest, Hypothesis, Ruff, MyPy |
| Frontend | TypeScript; Next.js 14 App Router; React 18; TanStack Query; TipTap; Tailwind; Vitest; PWA |
| CI | GitHub Actions on Ubuntu, Python 3.12 and Node 20; backend + frontend jobs in `.github/workflows/ci.yml` |

GitHub REST, GitHub remote refs, and local Git agree that PR #19 is merged at the listed `main` commit. GitHub CLI GraphQL repository lookup was unreliable in this environment; use GitHub REST or `git fetch`/remote refs if that occurs again.

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

### Implemented behavior at the verified main

- **Entry persistence/lifecycle:** Entry scope/type/status constraints, ownership, canonical lifecycle, orphan-anchor filtering, correction through supersession, and single-current handling for `relationship.state` / `story.summary` are implemented.
- **`retrieve()`:** `EntryService.retrieve()` calls the Store retrieval seam. It defaults to canon, enforces owner/scope/type/subject/status constraints, excludes orphaned anchors, ranks deterministically, selects whole Entries under a knowledge budget, and returns retrieval trace data.
- **Context Assembly:** `assemble_entry_context()` is a pure bridge over a selected `EntryRetrievalResult`. It re-estimates complete rendered blocks, never truncates an Entry, and keeps assembly exclusions separate from retrieval exclusions.
- **Review:** Review read/accept/reject/edit/supersede APIs exist, and the frontend provides one non-blocking type-agnostic Review Queue/Card.
- **Prompt assets:** `chat.default`, `novel.continue`, and `summary.rolling` are UTF-8 repository assets loaded by the allow-listed loader. `PromptTemplate` remains API/data compatibility only, never an architecture prompt-body fallback.
- **User authoring and audit reads:** User-authored Entry creation is server-provenanced; default Entry lists expose live canon only, while `include_history=true` permits labelled audit/history data. Cursor pagination and immutable supersession correction are implemented.

### Explicitly not complete

P1-6 is not implemented. Production search found `assemble_entry_context()` only in its own module and tests/golden tests, and `EntryService().retrieve(...)` only in retrieval/golden tests. `ChatService` and `NovelService` do not import or invoke either seam. Existing Chat and Novel generation therefore still consume the legacy character/world/lore context path only.

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
| Context Assembly | `backend/app/engines/prompt/entry_context.py` | Pure selected Entry result to prompt-block conversion and assembly trace. |
| Prompt blocks | `backend/app/engines/prompt/blocks.py` | Current block kinds, ordering, priority defaults, and `PromptBlock` structure. |
| Prompt engine | `backend/app/engines/prompt/engine.py` | Deterministic collect → resolve → order → budget → final provider-neutral assembly. |
| Prompt assets | `backend/app/engines/prompt/assets.py` | Allow-listed repository asset loader with asset identity/version/digest. |
| Prompt asset bodies | `backend/prompts/chat/default.v1.md`, `backend/prompts/novel/continue.v1.md`, `backend/prompts/shared/rolling-summary.v1.md` | UTF-8 repository prompt bodies for the `chat.default`, `novel.continue`, and `summary.rolling` assets. |
| Chat service | `backend/app/services/chat_service.py` | Chat SSE orchestration, idempotency/serialization, memory lifecycle, and legacy lore loading. |
| Chat engine | `backend/app/engines/chat/engine.py` | Chat prompt assembly and provider streaming over PromptEngine/MemoryEngine. |
| Novel service | `backend/app/services/novel_service.py` | Work/chapter service and SSE continuation; currently builds legacy story context. |
| Novel engine | `backend/app/engines/novel/engine.py` | `ChapterContext`, continuation prompt assembly, and provider stream. |
| Review frontend API | `frontend/src/lib/api/endpoints.ts` | Typed frontend endpoint wrappers, including Entry Review operations. |
| Review frontend hook | `frontend/src/hooks/use-entry-review.ts` | Queue mutations/cache transitions for review actions. |
| Review frontend UI | `frontend/src/components/review/review-queue.tsx` | Existing Home-screen review queue. |
| Review card UI | `frontend/src/components/review/review-card.tsx` | Type-agnostic proposed Entry display and actions. |
| Review frontend test | `frontend/src/components/review/review-utils.test.ts` | Queue/cache transition and error handling coverage. |
| Configuration | `backend/app/config.py` | Pydantic settings, UTF-8 `.env` reading, and `FEATURES` feature-flag map. |
| Backend tests | `backend/tests/unit/`, `backend/tests/integration/`, `backend/tests/golden/`, `backend/tests/property/` | Unit, integration, golden regression, migration, streaming, and property coverage. |
| CI | `.github/workflows/ci.yml` | Backend and frontend GitHub Actions jobs. |
| Current status | `.kiro/specs/ai-creative-workspace/implementation-status.md` | Verified execution-path status snapshot and known local environment issues. |
| Remaining work plan | `.kiro/specs/ai-creative-workspace/tasks.md` | Architecture-frozen Phase 1–6 implementation order and boundaries. |

## 7. Tests and validation baseline

### Commands confirmed in this repository

Run each command as a separate process with the stated working directory; do not chain shell commands.

| Check | Working directory | Command | Verified result at this handoff |
|---|---|---|---|
| Backend full pytest | `backend` | `.\.venv\Scripts\python.exe -m pytest -q` | Passed on 2026-07-31. |
| Entry/retrieval/assembly target tests | `backend` | `.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_entry_retrieval.py tests/unit/test_entry_context_assembly.py tests/integration/test_entry_retrieval.py tests/golden/test_retrieval_context_golden.py` | Repository command paths verified; use for Store/context work. |
| Ruff | `backend` | `.\.venv\Scripts\python.exe -m ruff check app tests` | Passed on 2026-07-31. |
| Scoped P1-6 MyPy | `backend` | `.\.venv\Scripts\python.exe -m mypy app/config.py app/services/chat_service.py app/services/novel_service.py app/engines/chat/engine.py app/engines/novel/engine.py app/engines/prompt/engine.py app/engines/prompt/blocks.py app/engines/prompt/entry_context.py` | Required for the P1-6 Python scope; compare with the pre-change scope baseline and extend the command if an additional Python file changes. |
| Frontend test | `frontend` | `npm run test` | Passed: 3 files / 13 tests on 2026-07-31. |
| Frontend lint | `frontend` | `npm run lint` | Passed on 2026-07-31; emits a TypeScript-version support warning. |
| Frontend production build | `frontend` | `npm run build` | Passed: 15 routes on 2026-07-31. |
| Alembic revisions | `backend` | `.\.venv\Scripts\python.exe -m alembic heads` | `0002_entry_store (head)` on 2026-07-31. |
| Whitespace/patch integrity | repository root | `git diff --check` | Passed before this document was created. |

The full command `.\.venv\Scripts\python.exe -m mypy app tests` currently reports **36 pre-existing errors in 11 files** at the verified main, including `app/engines/prompt/engine.py` and `app/services/novel_service.py`. Full MyPy is not the clean merge gate. For a scoped change, record the current errors for precisely the changed scope and do not introduce or increase them; fix new errors in that scope before review.

GitHub CI runs:

- **Backend:** install `.[dev]`, run `ruff check app || true`, run `alembic upgrade head`, then `pytest -q`.
- **Frontend:** `npm install`, `npm run lint`, `npm run test`, `npm run build`.

For PR #19's merge commit, GitHub Actions `backend` and `frontend` checks both completed with `success`. Note that the CI Ruff step uses `|| true`, so a local Ruff pass remains required.

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
| **P1-6** `retrieve()` → Context Assembly → real generation path | Not started. Retrieval and assembly are test-only; Chat/Novel have no production call site. | P1-5 complete; P1-3 prompt asset boundary is already complete. | Writer loop, Analyst, Story Bible store/UI, Character Chat redesign, migration, frontend changes, legacy lore deletion. | **Next.** |
| **P1-7** edit-diff capture | Not implemented; `EDIT_DIFF` exists only as a provenance enum value. Capture is time-sensitive because missed diffs cannot be reconstructed later. | Persistence design decision; no P1-6 dependency. | Distillation/learning, canon writes, blocking author flows. | After P1-6 unless a separately approved data-capture decision reprioritizes it. |
| **P1-8** legacy Character/World/Lore ↔ Entry equivalence bridge | Not implemented. Existing legacy fields/lore remain active generation sources. | P1-5 and P1-6. | Backfill, legacy deletion, read cutover, migration. | After P1-6. Read-only deterministic comparison first. |
| **P1-9** review audit persistence decision | Not implemented. Current Entries have lifecycle/provenance but no approved actor/action history design. | P1-1 complete. | Unapproved JSON schema, implementation migration in the design PR. | After P1-6/P1-8 unless architecture review chooses earlier. |
| **P1-10** local development environment cleanup | Optional and blocked by user-data safety. Local DB stamp is stale; protected stashes exist. | Explicit user approval for data/stash actions. | Automatic DB recreation, `alembic stamp`, stash application/deletion. | Last, and only with approval. |

## 10. Immediate next task: P1-6

### Objective

Connect this exact chain to actual generation while preserving the established substrate:

```text
EntryService.retrieve()
  → assemble_entry_context()
  → real Chat/Novel Prompt Assembly
```

At verified main, neither Chat nor Novel receives Entry Store knowledge. P1-6 is the narrowly-scoped additive integration that changes that fact.

### Required behavior

- Add a feature flag that defaults **OFF**.
- With the flag OFF, preserve the existing Chat and Novel prompt result exactly; make **zero** additional Entry retrieval queries.
- With the flag ON, run Entry retrieval **once per request** before streaming starts.
- Convert returned Entry context into a distinct Entry PromptBlock; do not represent it as Memory.
- Keep chat-private Memory and shared Entry Store context as separately traceable blocks.
- Preserve legacy Character/World/Lore context and the existing legacy lore scanner; P1-6 adds Entry context and does not cut over or delete legacy sources.
- Retrieve only canon; retain owner, reachable scope, subject, work/character/world isolation, and orphan filtering through `EntryService.retrieve()`.
- Proposed, rejected, superseded, or orphaned Entries must not enter a generation prompt.
- Preserve whole-Entry selection and whole-rendered-block budget rules. Never truncate Entry content.
- Keep retrieval trace and Context Assembly trace separate; final prompt trace must keep their boundary observable.
- Complete retrieval and assembly before Chat/Novel SSE streaming begins.
- Preserve Chat/Novel SSE semantics, idempotency/stream serialization, and Novel CAS/append behavior.
- Retain repository prompt-asset authority. Do not use DB PromptTemplate for architecture prompt body resolution.
- Add **no migration**.

### Explicit non-goals

- Writer stage loop, plan/draft/validate/revise work, or Analyst implementation.
- A new Story Bible store or a Story Bible UI.
- Character Chat product/IA conversion.
- P1-7 edit-diff capture, P1-8 legacy equivalence bridge, or P1-9 audit persistence.
- Legacy lore deletion, legacy backfill, or Entry-authoritative read cutover.
- Memory → Entry conversion or any chat-private Memory unification.
- DB PromptTemplate adoption for prompt bodies.
- Frontend changes.

## 11. P1-6 expected files and validation

### Expected change points

These are based on the current production call paths, not a promise that every file must change.

| File | Why it is an expected P1-6 change point |
|---|---|
| `backend/app/config.py` | Existing `FEATURES` map is the feature-flag configuration boundary; add an OFF-by-default flag here. |
| `backend/app/services/chat_service.py` | Current T1 prompt assembly loads character/persona/world/lore and invokes ChatEngine before streaming; this is the Chat retrieval boundary. |
| `backend/app/services/novel_service.py` | `_continue_impl()` currently calls `_build_story_context()` then `NovelEngine.assemble_continue()` before streaming; this is the Novel retrieval boundary. |
| `backend/app/engines/chat/engine.py` | Must accept/inject externally assembled Entry blocks without owning Entry retrieval. |
| `backend/app/engines/novel/engine.py` | Must accept/inject externally assembled Entry blocks without replacing legacy `ChapterContext`. |
| `backend/app/engines/prompt/engine.py` | `AssembleInput` / collection path is the central block intake and final trace/budget path. |
| `backend/app/engines/prompt/blocks.py` | Current block kinds have `memory` but no Entry kind; P1-6 needs an explicit distinct Entry block kind/order/priority rather than relabelling Entry as Memory. |
| `backend/app/engines/prompt/entry_context.py` | Reuse its pure rendering/whole-block budgeting seam; change only if the governed explicit Entry block contract requires it. |
| `backend/tests/integration/test_streaming.py` | Protect Chat/Novel SSE, one-save behavior, error/partial preservation, and ordering around pre-stream retrieval. |
| `backend/tests/property/test_prompt_budget.py` | Protect final prompt budget invariants as an Entry block joins the block collection. |
| `backend/tests/golden/test_retrieval_context_golden.py` | Retain deterministic retrieval/context assembly fixtures and trace expectations. |
| New focused backend tests under `backend/tests/unit/` and `backend/tests/integration/` | Cover feature-flag OFF/ON integration without frontend or migration scope. |

### Required P1-6 validation matrix

- Flag OFF Chat prompt regression: byte-identical existing assembled prompt behavior.
- Flag OFF Novel prompt regression: byte-identical existing assembled prompt behavior.
- Flag OFF retrieval invocation count: **0**.
- Flag ON retrieval invocation count: **1 per request**, before streaming.
- Owner/work/character/world/scope/subject isolation.
- Canon-only inclusion; no proposed/rejected/superseded/orphaned Entry reaches generated context.
- Separate Memory, Entry, and legacy lore blocks with distinguishable trace identity.
- Deterministic selection and budget decisions; whole Entries/blocks only.
- Golden retrieval/context regression fixtures.
- Prompt-budget property tests.
- Chat and Novel streaming/idempotency/CAS regression tests.
- Backend full pytest, Ruff, changed-scope MyPy baseline comparison, frontend CI, Alembic head unchanged, and `git diff --check`.

## 12. First-run checklist for a new AI

1. Read `AI-HANDOFF.md`, then ADR-001/002/003, RFC-001/002/003/009/012, and the relevant P1-6 section of `tasks.md`.
2. Fetch and compare `origin/main`; if this handoff SHA is no longer current, re-validate GitHub state, code call sites, and status documents.
3. Check the working tree and list stashes without modifying either. Keep user work, the local DB, and stashes untouched.
4. Re-run the P1-6 production call-site search. Confirm `EntryService.retrieve()` and `assemble_entry_context()` still have no Chat/Novel production caller before implementing.
5. Create a new feature branch from current `origin/main`.
6. Implement only P1-6, with the flag OFF by default and the non-goals above enforced.
7. Run the focused tests first, then backend/full frontend validations and `git diff --check`.
8. Independently review the final diff against the invariants, OFF behavior, query counts, trace separation, streaming safety, and migration prohibition.
9. Create a **Draft** PR; include the required completion report in the PR body or user report.
10. Do not merge. Report results to the user and wait for the requested review/merge decision.

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

## 14. Copyable P1-6 execution prompt

```text
You are continuing AI Author OS / gorafan at C:\gv\rfrf.

Start by reading C:\gv\rfrf\AI-HANDOFF.md and the governing ADR/RFC originals it names. Do not trust this prompt over current GitHub, Git, architecture, code, or test state: fetch origin/main, inspect the working tree, list stashes without touching them, verify the repository is cococute88/gorofan, and re-check whether P1-6 is still unimplemented by searching production Chat/Novel call sites for EntryService.retrieve() and assemble_entry_context(). If main changed since the handoff snapshot, update your evidence first.

Implement only P1-6: connect EntryService.retrieve() -> assemble_entry_context() -> actual Chat and Novel prompt assembly. Work on a new feature branch from the current main. Use an OFF-by-default feature flag. With the flag OFF, existing Chat and Novel prompt outputs must remain byte-identical and make zero Entry retrieval queries. With the flag ON, retrieve exactly once per request before SSE streaming, inject selected canon Entries as a distinct PromptBlock (not Memory), preserve separate Memory/Entry/lore blocks and retrieval/assembly traces, preserve owner/scope/subject isolation and canon-only/orphan exclusion, whole-Entry budgeting, legacy lore, prompt assets, Chat/Novel SSE, idempotency, and Novel CAS behavior.

Do not implement Writer, Analyst, Story Bible storage/UI, Character Chat conversion, P1-7/P1-8/P1-9, legacy lore deletion/backfill, Memory-to-Entry conversion, DB PromptTemplate bodies, migrations, or frontend work. Do not delete user data or modify the local DB. Do not apply, pop, or drop stashes. Do not auto-merge. Do not ask for intermediate approval; complete the bounded implementation autonomously.

Run focused regressions plus backend full pytest, Ruff, scoped MyPy with no newly introduced scope errors, frontend test/lint/build, Alembic heads unchanged, and git diff --check. Use one PowerShell command per process; if the wrapper corrupts a command, use Python subprocess.run(argv, cwd=..., shell=False) rather than retrying the same broken shell string.

Perform an independent self-review against AI-HANDOFF.md, commit, push, and create a Draft PR only. Then report: root cause, files read/changed, implementation, all test results, issues, PR URL, next work, whether a new chat is recommended, Ready-for-Review/merge judgment, a next-AI prompt, and recommended model/reasoning.
```

**Recommended execution model:** Claude Code — Opus High; Codex — high reasoning; Cursor — strongest available reasoning model. A bounded follow-up/fix may use Terra or another mid-tier model.
