# Story Summary Chronology Contract

- **Status:** Proposed — documentation-only contract; independent architecture review required
- **Date:** 2026-09-06
- **Baseline:** `main` at `ac791ba8369aa1a7f6856cd9f573e0650995ea74` (PR #28 merged)
- **Scope:** Chapter-scoped `Entry(type="story.summary")` eligibility and ordering for Novel/Chapter prose-generation context
- **Governing sources:** ADR-003, ADR-005, ADR-009, ADR-017, ADR-018; RFC-002, RFC-003, RFC-004, RFC-009; [P1-8 Legacy Context ↔ Entry Equivalence Bridge](legacy-entry-equivalence-design.md)

> **Contract, not implementation.** This change defines the correctness boundary that a later implementation PR must enforce. It changes no Python, API, schema, migration, feature flag, prompt, provider call, or local database.

## 1. Status

This is the post-P1-8 chronology correctness gate. PR #28 merged the read-only equivalence diagnostic at `ac791ba`; it measured, but deliberately did not repair, the fact that Entry retrieval can select future or chronology-unknown `story.summary` rows.

The contract becomes accepted only after independent review and merge. Production implementation has not started. `FEATURES["entry_store_context"]` remains default OFF, legacy Chapter summaries remain authoritative, and this document does not authorize an Entry authority cutover.

## 2. Problem

Current Novel continuation builds legacy history with:

```text
Chapter.work_id == target.work_id
AND Chapter.index < target.index
ORDER BY Chapter.index ASC
```

It therefore treats story order, not database write time, as the boundary. The additive Entry path does not carry the target Chapter position into `EntryRetrieveRequest`. `EntryService.retrieve()` filters owner/scope/status/liveness, then `rank_entries()` gives every candidate a recency score derived from `Entry.updated_at` or `Entry.created_at`. A later Chapter summary can consequently outrank and consume budget ahead of a prior summary. P1-8 integration tests reproduce both a selected future summary and a selected chronology-unknown Work summary.

A Chapter 7 summary entering a Chapter 3 generation prompt is not a ranking-quality issue. It is future information leakage and a continuity correctness failure. A high relevance score, priority, confidence, recent DB timestamp, or small token size must never make an ineligible summary eligible.

## 3. Scope

This contract defines:

- the explicit chronology anchor required by Novel/Chapter prose generation;
- classification of Chapter-level `story.summary` as prior, current, future, or unknown;
- pre-ranking eligibility and lifecycle checks;
- deterministic selection and provider-visible ordering among eligible summaries;
- current-Chapter behavior for existing and future generation operations;
- unknown, tie, duplicate, legacy-overlap, deleted, foreign, and orphan handling;
- responsibility boundaries across Retrieval, Context Assembly, and PromptEngine;
- token-budget and DB-timestamp roles;
- the behavioral tests and smallest follow-up implementation sequence.

The immediate production consumer is Chapter continuation. The contract also constrains future initial generation and regeneration so they cannot introduce a weaker rule when Generation Preparation is added.

## 4. Non-goals

This contract does not implement or authorize:

- production Python changes, API changes, schema changes, or migrations;
- Entry authority cutover, backfill, dual-write, or legacy scanner removal/deprecation;
- a new summary table, chronology metadata table, Scene table, or Story Bible service;
- P1-9, Analyst ingestion, shared Generation Preparation, Provider adapters, Gemini integration, Prompt Packets, Scene Brief, Novel UI, or Chapter apply/import;
- Taste, Voice, Reference File Ingestion, Kiwi/Gemini style analysis, Hybrid Style Engine, Pixiv ingestion, or Character Chat changes;
- multi-level arc/story-so-far summary selection. Those levels need their own bounded coverage-horizon contract before use in Chapter-summary context.

## 5. Current Production Findings

### 5.1 Model and lifecycle facts

- `Work` is the production Novel aggregate. It has `SoftDeleteMixin`; `Chapter` does not.
- `Chapter.work_id` is a database foreign key with `ON DELETE CASCADE`; `Chapter.index` is non-null and protected by `UNIQUE(work_id, index)`. Gaps are allowed. Reordering rewrites `index`, so the current row value is the current story order.
- `Chapter.summary` is one legacy text field on the Chapter. `NovelService._build_story_context()` loads only non-empty summaries from strictly lower indexes and orders them ascending.
- `Entry.created_at_chapter_id` is an optional FK with `ON DELETE SET NULL`. RFC-002 defines it as optional story-order origin for work-scoped facts; it is not the stored identity of the summarized aggregate.
- A `story.summary` Entry must use Work scope and either a Work or Chapter subject. `data.level` is not schema-governed. P1-8 treats absent/`chapter` as Chapter-summary-compatible and other levels as different payload semantics.
- `story.summary` is single-current per persisted Entry identity at the service boundary. The database does not add a matching composite uniqueness constraint, so retrieval still needs a fail-closed corruption/legacy-data rule.
- Default generation retrieval is canon-only. Current liveness filtering rejects missing/deleted/foreign scope and subject anchors, but does not perform a story-position eligibility check.

### 5.2 Generation facts

- The only production Novel generation operation is `POST /works/chapters/{chapter_id}/continue`.
- The authenticated owner and explicit `chapter_id` load the target `Chapter`; that row is the real generation target. The service does not use the latest-created or latest-updated Chapter as an implicit target.
- The target Chapter can be any owned Chapter, including one with later Chapters already present. “Latest committed Chapter” is not a model concept: Chapter has no draft/committed/status column.
- Continuation supplies the final 1,200 characters of the target Chapter as current prose and appends generated text to that Chapter. It excludes the target Chapter's own legacy summary.
- There is no production Novel initial-generation or Chapter-regeneration endpoint. Chat regeneration is unrelated and must not be used to infer Novel semantics.

### 5.3 Entry retrieval and assembly facts

- `build_novel_retrieve_request()` declares user/work/world/character scopes, cast, beat, budget, `task_kind=scene`, and limit. It does not declare target Work/Chapter chronology as an as-of input.
- Candidate repository reads are owner-, scope-, status-, type-, and subject-filtered. `EntryService.retrieve()` removes orphaned anchors before calling the pure ranker.
- `entry_retrieval._chronology()` is currently a misleading name for database recency: it returns `updated_at` or `created_at` as a Unix timestamp. That value contributes to score and tie-breaking for all Entry types.
- Whole-Entry token budget and count limit are applied after ranking. A future/unknown summary can therefore affect score normalization, selection, limit, and budget before any prompt exists.
- Context Assembly accepts only the selected retrieval result, renders whole non-truncatable Entry blocks, rechecks a rendered-block budget, and preserves retrieval order.
- PromptEngine collects Entry blocks, performs final layer ordering and final budget fitting. It does not know the source Chapter and is the wrong place for chronology policy.
- The feature flag is checked before the request factory or any Entry query. OFF means zero Entry retrieval and an unchanged legacy prompt.

### 5.4 P1-8 evidence

P1-8 resolves Chapter positions only for diagnostics. It labels DB timestamp recency and reports selected/not-selected future or unknown summaries, but never changes the real retrieval result. Its tests demonstrate:

- a future Chapter summary selected on the Entry shadow while legacy excludes it;
- a Work-subject summary selected with unknown story position;
- a future summary rejected only by budget, proving chronology is currently evidence rather than eligibility;
- a Chapter-subject summary whose different `created_at_chapter_id` creates inconsistent positional evidence.

## 6. Terminology

| Term | Contract meaning |
|---|---|
| generation target | the concrete Chapter whose prose is being initially generated, continued, or regenerated |
| chronology anchor | immutable request evidence `{owner_id, work_id, chapter_id, chapter_index, operation}` resolved from the owned active target snapshot before retrieval |
| source Chapter | the live Chapter named by a Chapter-level summary's `subject_id` |
| Chapter-level summary | `type=story.summary`, Work scope, Chapter subject, and `data.level` absent or equal to `chapter` |
| chronology disposition | exactly one of `prior`, `current`, `future`, or `unknown` |
| eligible | allowed to enter ranking, count-limit competition, token-budget selection, Context Assembly, and final prompt assembly |
| legacy overlap | a non-empty `Chapter.summary` and an Entry Chapter summary name the same source Chapter during the additive pre-cutover period |

“Recent” without qualification is not story chronology. Database recency means only `created_at`/`updated_at` audit time.

## 7. Generation Chronology Anchor

### 7.1 Authority

The authority is the explicit generation target `Chapter` loaded by stable id in the same pre-stream transaction/snapshot used to build context. Its current `work_id` and `index` form the story-order anchor.

The following are not chronology authorities:

- the generation request's arrival time;
- Chapter or Entry `created_at`/`updated_at`;
- maximum Chapter index in the Work;
- latest committed Chapter (no such production state exists);
- the Chapter most recently edited;
- Entry retrieval score, priority, confidence, or provenance timestamp.

Reordering changes canonical story order. A later generation uses the Chapters' current `index` values in its snapshot; it does not preserve the order that existed when an Entry was created.

### 7.2 Anchor validity

Before any chronology-sensitive retrieval, the target must be:

- owned by the authenticated user;
- attached to an owned, non-soft-deleted Work;
- the same Chapter id/index/work tuple carried into the retrieval request;
- unambiguous under `UNIQUE(work_id, index)`.

Missing, foreign, deleted, soft-deleted-Work, or internally inconsistent anchors fail the generation preparation before retrieval, budgeting, prompt assembly, or provider execution. No “latest Chapter” fallback is allowed.

## 8. Prior / Current / Future / Unknown

For a valid anchor `A` and Chapter-level summary source `S`:

| Disposition | Exact rule |
|---|---|
| prior | `S.work_id == A.work_id` and `S.index < A.chapter_index` |
| current | same Work and `S.id == A.chapter_id`; equivalently, valid data has `S.index == A.chapter_index` |
| future | same Work and `S.index > A.chapter_index` |
| unknown | source Chapter cannot be proved from a live, owned, same-Work Chapter subject, the level is not Chapter-compatible, or persisted references conflict |

Because valid data enforces unique Chapter index per Work, a distinct Chapter at the same index is not `current`; it is an invariant violation handled by §12.

For Chapter-level summary identity, `subject_type=chapter` and `subject_id` are authoritative. `created_at_chapter_id` is optional origin/consistency evidence, not an alternate source locator. If present on a Chapter-level summary, it must equal the Chapter subject. A different, foreign, missing, or cross-Work value makes the summary `unknown` and ineligible. This closes the ambiguity P1-8 exposed without treating DB capture time as narrative truth.

A Work-subject `story.summary`, including `data.level=arc` or `story`, has no governed start/end Chapter coverage in today's model. It is `unknown` for this Chapter-summary layer even when `created_at_chapter_id` exists. A later multi-level-summary contract may define explicit coverage horizons; this contract does not guess them.

## 9. Eligibility Contract

For Novel/Chapter prose generation, a `story.summary` may enter the candidate set only when all conditions hold:

1. the feature flag permits Entry generation context;
2. owner, declared Work scope, canon status, supersession state, and all required live anchors pass RFC-002/RFC-003 filters;
3. it is a Chapter-level summary under §6;
4. its source Chapter belongs to the anchor Work;
5. its chronology disposition is exactly `prior`;
6. no inconsistent source/origin/provenance Chapter reference exists;
7. no duplicate/tie/legacy-authority exclusion in §12 applies.

`current`, `future`, and `unknown` are hard pre-ranking exclusions. They receive no relevance score, no recency normalization, no budget estimate for selection, no count-limit slot, and no PromptBlock. Their trace reason remains observable without exposing prose.

Adding any ineligible summary must not change the rank, selected IDs, selected order, budget use, or rendered prompt of otherwise identical eligible candidates.

## 10. Ordering Contract

Eligibility and ordering are separate from relevance selection:

1. classify and remove ineligible candidates;
2. rank/select only eligible canon within the caller's knowledge budget;
3. emit selected Chapter summaries in ascending `(Chapter.index)` story order;
4. preserve that order through Context Assembly and PromptEngine.

Relevance, explicit priority, confidence, or a summary-specific story-recency preference may determine which eligible summaries survive a constrained budget, but cannot reorder the survivors in provider-visible context. If a later selector prefers the most recent prior Chapters, it may select by descending source index and then must render the selected set ascending.

Stable Entry id may order trace records after truth has already been determined. It may not resolve two competing canonical summaries or two Chapters claiming the same position.

## 11. Current Chapter Semantics

The target Chapter's own summary is always ineligible for prose generation.

| Operation | Contract |
|---|---|
| current production continuation | exclude current summary; use the target Chapter's existing content tail as current prose context |
| initial generation into an already-created empty Chapter | exclude current summary; it can describe an intended or completed Chapter rather than established prior story |
| continuation with an existing draft | exclude current summary; the draft/tail is the current source and the summary can be stale or reveal the Chapter's later ending |
| regeneration of a target Chapter | exclude current summary; regeneration must not condition on a completion summary of the prose it is replacing |
| any operation where a summary already exists | exclusion is unchanged; existence and recent update do not make it prior |
| future generation without a persisted target Chapter | unsupported until the operation supplies an explicit, reviewed chronology anchor; never infer one from timestamps or maximum index |

This single strict rule matches current legacy continuation behavior and avoids operation-specific exceptions that the production model cannot currently justify.

## 12. Unknown / Tie / Duplicate Policy

### 12.1 Unknown

Unknown chronology is fail-safe exclusion, not fallback ranking. The trace must identify the reason, such as `missing_chapter_subject`, `unsupported_summary_level`, `inconsistent_chapter_reference`, `foreign_source_chapter`, or `orphan_source_chapter`. It must never silently fall back to DB timestamp recency.

### 12.2 Equal position and corrupted Chapter order

`UNIQUE(work_id, index)` makes equal positions impossible in valid data. If a read snapshot nevertheless contains distinct Chapters with the same Work/index:

- if one is the target anchor, abort preparation as unsupported before provider execution;
- otherwise exclude all summaries at the ambiguous position and retain trace evidence;
- never select by Chapter id, Entry id, creation time, or update time.

Gaps in indexes are valid and require no fallback.

### 12.3 Multiple Entry summaries for one source Chapter

The service's single-current lifecycle rule should leave at most one active canon `story.summary` per Work/Chapter identity. If multiple active canon rows are observed, exclude the entire identity group as `duplicate_active_chapter_summary`. Do not choose the newest, highest-scored, or lexically first row. Historical rejected/superseded rows remain ineligible history and do not create a generation duplicate.

The same Entry reached through multiple scope/query paths is deduplicated by Entry id, as RFC-003 already requires.

### 12.4 Legacy + Entry overlap before authority cutover

Legacy `Chapter.summary` remains the authoritative production source in this rollout. When it is non-empty for an eligible prior source Chapter, the same Chapter's Entry summary is excluded from provider context as `legacy_summary_authority_overlap`, regardless of payload equality. This is stable identity-based suppression, not fuzzy text deduplication.

If the legacy field is empty, one otherwise eligible Entry summary may supply that Chapter's context while the Entry flag is ON. If legacy and Entry content conflict, production still keeps legacy and P1-8 reports the mismatch; this contract does not decide an authority cutover. A later reviewed cutover must replace this precedence deliberately rather than remove it incidentally.

## 13. Deleted / Orphan / Lifecycle Boundary

Chronology never weakens existing owner/lifecycle rules:

- only active canon without a canonical replacement is generation-eligible;
- captured, proposed, rejected, and superseded Entries never participate;
- the Entry Work scope must be the anchor Work;
- the Chapter subject must exist, belong to the same owner and Work, and be visible in the request snapshot;
- a hard-deleted Chapter leaves a Chapter-subject Entry as an orphan and it is excluded;
- a soft-deleted Work invalidates both the target anchor and summary candidates;
- a foreign/cross-Work Chapter subject is excluded even if its numeric index looks prior;
- a broken Chapter provenance/origin reference is not used to re-anchor the summary and makes a claimed Chapter-derived summary ineligible;
- no missing reference is repaired or reassigned during retrieval.

`Chapter` has no soft-delete or status column. The contract must not invent draft/committed lifecycle from title, content length, version, or timestamps.

## 14. Retrieval vs Context Assembly Responsibility

### 14.1 Retrieval owns policy

The single Store retrieval boundary owns:

- accepting the explicit generation chronology anchor;
- resolving source Chapter evidence in an owner-scoped snapshot;
- classification and hard eligibility filtering;
- duplicate/legacy-overlap exclusion supplied by the generation situation;
- eligible-candidate ranking, budget selection, and summary output ordering;
- exclusion and selection trace.

This is a type- and task-specific pre-ranking policy inside the one `retrieve()` seam, not a second retriever.

### 14.2 Context Assembly preserves and asserts

Context Assembly continues to convert already-selected Entries to PromptBlocks and apply rendered-block budget. It must preserve the selected summary chronology order. A defense-in-depth assertion may require retrieval-issued anchor/disposition evidence and fail closed if a `story.summary` block lacks `prior` eligibility for this generation anchor.

The assertion must consume the classifier's result; it must not independently query Chapters or reimplement classification. Its purpose is to detect an internal boundary violation, not to create a second policy owner.

### 14.3 PromptEngine and formatters do not decide

PromptEngine only collects, orders context layers, fits the final prompt budget, and traces block survival. Provider adapters and future Prompt Packet formatters consume the same prepared blocks. None may inspect summary prose, infer Chapter numbers, apply timestamp recency, deduplicate content, or repair chronology.

## 15. Budget Interaction

The mandatory sequence is:

```text
anchor validation
→ owner/scope/status/liveness eligibility
→ story-summary chronology/duplicate/overlap eligibility
→ ranking and whole-Entry knowledge-budget selection
→ Context Assembly rendered-block budget
→ PromptEngine final budget
→ provider-neutral prepared context
```

Future, current, unknown, orphaned, foreign, duplicated, and legacy-overlapped Entry summaries consume zero selection budget and zero count-limit capacity. They must not affect recency normalization or push an eligible candidate below a threshold. Budget traces distinguish chronology exclusion from retrieval-budget, assembly-budget, and final-prompt drops.

Final PromptEngine pressure may still drop an eligible prior summary block according to governed block priority. That is a budget outcome, not a change in chronology eligibility.

## 16. DB Timestamp Role

For Chapter-level `story.summary` in Novel/Chapter generation:

- `created_at` and `updated_at` remain audit and diagnostic evidence;
- they do not define prior/current/future/unknown;
- they do not contribute a summary recency score;
- they do not order provider-visible summaries;
- they do not break equal-position or duplicate-canon ambiguity;
- they do not provide a fallback when Chapter position is unknown.

The follow-up implementation should remove DB-time recency from this summary family and use source `Chapter.index` only where a summary-recency selection factor is desired. This contract does not change timestamp treatment for unrelated Entry types.

## 17. Legacy ↔ Entry Relationship

Legacy and Entry share these Chapter-summary chronology semantics:

- the explicit target Chapter is the anchor;
- only same-Work, strictly prior source Chapters are eligible;
- provider-visible summary order is ascending Chapter index;
- current/future/unknown never become eligible by timestamp or score.

They differ today:

- legacy stores one string directly on each Chapter and structurally loads every non-empty prior summary before final PromptEngine budgeting;
- Entry stores reviewed canon with provenance/lifecycle, participates in retrieval and two earlier knowledge budgets, and supports future multi-level summary concepts;
- legacy has source identity by construction; Entry must resolve and validate its Chapter subject;
- legacy remains authoritative until a separate cutover. The overlap rule in §12 prevents double injection without deleting either source.

The legacy scanner and `Chapter.summary` field are neither removed nor deprecated by this contract.

## 18. P1-8 Diagnostic Implications

P1-8 remains a read-only measurement layer. This architecture PR changes none of its code, schemas, tests, projection rules, or API output.

The implementation PR must assess a minimal diagnostic alignment so reports remain meaningful after production policy changes:

- reuse the same chronology classifier rather than maintain a second interpretation;
- report production chronology exclusions distinctly from budget/limit exclusions;
- keep coverage independent from runtime eligibility;
- preserve `database_timestamp_recency` as historical-policy evidence only where the old policy is being compared;
- update the test where a prior Chapter subject has a different `created_at_chapter_id`: under this contract it is `unknown/inconsistent`, not a trustworthy prior summary;
- keep diagnostics non-mutating and provider-free.

No diagnostic result authorizes backfill, deletion, flag activation, or cutover.

## 19. Feature Flag / Rollout

- `FEATURES["entry_store_context"]` remains default OFF.
- OFF preserves current production behavior exactly: no Entry query, no request construction, legacy prior summaries only.
- ON applies this chronology contract before any Entry `story.summary` competes for ranking or budget.
- The implementation must be testable on controlled data and expose trace reasons for every excluded summary without logging content.
- The implementation is not an authority cutover. Legacy continues to supply prior summaries and wins same-Chapter overlap.
- Legacy removal, Entry default-ON, authority precedence reversal, or multi-level summary enablement each require separately reviewed scope.

## 20. Test Contract

The follow-up implementation is incomplete unless the following behavioral matrix passes through pure classifier/retrieval tests and the real Novel generation path where applicable.

| Case | Setup | Required result |
|---|---|---|
| prior summary | Chapter 1 summary; target Chapter 3 | eligible; may be selected; disposition `prior` |
| future leak prevention | target Chapter 3; Chapter 7 summary has newest DB timestamp, highest relevant score/priority | excluded before scoring/budget; absent from Entry blocks and provider prompt |
| unknown chronology | Work-subject/missing-source/unsupported-level summary | fail-safe excluded with deterministic reason |
| multiple prior summaries | Chapter 1 and 2 summaries; target Chapter 3 | selected survivors render Chapter 1 → Chapter 2 regardless of DB timestamps or retrieval scores |
| current: empty initial target | target Chapter 3 empty, its summary exists | current summary excluded |
| current: continuation | target Chapter 3 has draft/tail and summary | current summary excluded; tail remains current prose context |
| current: regeneration contract | regeneration fixture for target Chapter 3 | current summary excluded before preparation; no production endpoint is implied |
| equal position | two Chapter rows appear at one Work/index via corrupted test fixture | target ambiguity aborts; source group ambiguity excludes all; no id/timestamp winner |
| duplicate Entry | two active canon summaries name the same source Chapter | entire identity group excluded and traced |
| legacy overlap | non-empty legacy and Entry summary name the same prior Chapter | legacy appears once; Entry is excluded as authority overlap without fuzzy comparison |
| legacy empty | legacy summary empty; one eligible Entry summary exists | Entry may participate when flag ON |
| deleted/orphan | subject Chapter missing, Work deleted, or required Chapter provenance broken | excluded before ranking |
| foreign/cross-Work | source Chapter belongs to another owner or Work | excluded; no index comparison grants access |
| timestamp inversion | Chapter 1 summary updated after Chapter 2 summary | provider order remains Chapter 1 → Chapter 2 |
| budget isolation | future/unknown summary would otherwise fit first or fill the count limit | it consumes no budget/slot and cannot alter eligible selection |
| final budget | eligible prior summary is dropped by final PromptEngine pressure | traced as final budget drop, not chronology exclusion |
| feature flag OFF | canon summaries exist | zero Entry retrieval and byte-equivalent legacy production behavior |
| feature flag ON | mixed prior/current/future/unknown summaries | only non-overlapped, unambiguous prior Entry summaries can reach assembly |
| legacy regression | existing legacy continuation and Prompt rendering tests | no changed legacy selection/order/rendering |
| deterministic rerun | fixed snapshot/request/tokenizer/policy | identical dispositions, exclusions, selected IDs, order, budget, and trace |
| property: ineligible addition | add arbitrary future/current/unknown summary | all eligible result and prompt identities remain unchanged |

Migration tests must confirm no new revision and no change to frozen `0001`, `0002`, or `0003`.

## 21. Migration Decision

**Decision B — existing fields are sufficient, but application invariants and validation are required.**

Evidence:

- stable target/source identity already exists as `Chapter.id`;
- Work ownership/scope already exists as `Work.id`, `Chapter.work_id`, and Entry Work scope;
- canonical story position already exists as non-null `Chapter.index`;
- `UNIQUE(work_id, index)` already supplies a total, unambiguous valid-data order;
- Entry Chapter subject already represents the summarized aggregate;
- status, supersession, owner, and Work soft-delete data already exist.

The missing pieces are request propagation, source resolution, pre-ranking classification, trace, and service validation. The implementation should strengthen Chapter-level summary acceptance so a present `created_at_chapter_id` matches the Chapter subject and should reject unsupported/conflicting identities without adding columns. A migration, new table, stored chronology copy, or denormalized summary index would duplicate mutable Chapter order and create drift.

If future arc/story-so-far summaries need inclusive start/end coverage, their absent range semantics must be proven in a separate consumer contract before any schema proposal. That future possibility is not evidence for migration now.

## 22. Implementation Plan

Use one small implementation PR after this contract is independently reviewed and merged:

1. **Chronology value/helper.** Add a pure classifier with typed anchor, source evidence, disposition, and exclusion reason. Candidate: `backend/app/services/story_summary_chronology.py` with unit tests.
2. **Request and source resolution.** Carry the owned target `{work_id, chapter_id, index, operation}` from `NovelService` through `build_novel_retrieve_request()` and the internal retrieval request; load required source Chapter ids in one owner-scoped query. Candidates: `services/novel_service.py`, `services/entry_generation_context.py`, `schemas/entry.py`, `repositories/entry_repository.py`.
3. **Eligibility and duplicate/overlap filtering.** Apply the classifier in `EntryService.retrieve()` before `rank_entries()`/`select_entries()`, and emit safe exclusion trace. Candidate: `services/entry_service.py`; keep the pure keyword ranker free of database access.
4. **Deterministic selection/order.** Remove DB-time recency from Chapter summaries, select only eligible candidates, and emit selected summaries in ascending source index while leaving unrelated Entry ranking behavior unchanged. Candidate: `services/entry_retrieval.py` plus typed evidence on retrieval items/results.
5. **Defensive assembly assertion.** If needed, consume retrieval-issued chronology evidence in `engines/prompt/entry_context.py`; do not query or reclassify there.
6. **Tests.** Add focused unit/integration/property cases from §20, especially real Novel SSE prompt capture, timestamp inversion, budget isolation, duplicates, lifecycle, overlap, flag OFF/ON, and P1-8 diagnostic alignment.
7. **P1-8/status docs.** Make only the minimal diagnostic reuse/update required by §18 and record implementation status. Do not modify authority, schemas, or the legacy scanner.

Expected test homes include:

- `backend/tests/unit/test_story_summary_chronology.py` (new);
- `backend/tests/unit/test_entry_retrieval.py`;
- `backend/tests/unit/test_entry_generation_context.py`;
- `backend/tests/unit/test_entry_context_assembly.py` only if the assertion is added;
- `backend/tests/integration/test_entry_context_generation.py`;
- `backend/tests/integration/test_entry_retrieval.py`;
- `backend/tests/integration/test_entry_service.py` for acceptance invariants;
- `backend/tests/integration/test_legacy_entry_equivalence_api.py` and golden fixtures only where shared-policy evidence changes;
- `backend/tests/property/test_prompt_budget.py` or a focused retrieval property test;
- `backend/tests/integration/test_api.py`, prompt asset/rendering, streaming, migration, and P1-8 regression suites.

## 23. Explicit Non-goals

The implementation following this contract must remain chronology-only. It must not absorb:

- Generation Preparation or its direct/external rendering seam;
- Scene input, provider credentials/adapters, Gemini calls, or Prompt Packet formatting;
- Novel workspace UI or Chapter apply/import;
- automatic summary generation or accepted-Chapter Analyst ingestion;
- Story Bible authority migration, Entry backfill, legacy summary removal, or feature default changes;
- generic ranking redesign for non-summary Entry types;
- Taste/Voice/style persistence or analysis;
- unrelated Work/Chapter CRUD redesign.

## 24. Open Questions

**None for Chapter-level summary chronology.**

The repository does not yet define bounded coverage horizons for arc/story-so-far summaries. That is an explicit non-goal and later contract, not an open question blocking strict Chapter-summary safety.

## 25. Author OS / Style Handoff

After independent review and merge of this contract, the product sequence remains:

```text
story.summary chronology implementation
→ shared provider-neutral Generation Preparation
→ minimum Scene Brief / generation input
→ Direct Gemini provider path
→ external ChatGPT / Claude / Generic Prompt Packet
→ Novel workspace
→ Chapter apply/import
→ edit-diff loop use
→ minimal Voice support
→ Reference File Ingestion
→ Korean Kiwi quantitative Feature Extractor
→ language-specific extractor seam
→ Gemini Semantic Style Analyzer
→ Hybrid Style Baseline
→ generated prose ↔ baseline comparison
→ edit-diff personalization
```

Taste and Voice/Style remain separate. Reference Style extracts high-level characteristics rather than reproducing a named author or work. Style work must not delay the first usable Novel generation loop.
