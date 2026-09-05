# P1-8 Legacy Context ↔ Entry Equivalence Bridge

- **Status:** Accepted in PR #27; implemented by the P1-8 implementation change
- **Scope:** P1-8 architecture contract and implementation conformance reference
- **Baseline:** accepted on `main` at merge commit `9deb643c1c506e604f1341a6d3e072c30220ab88`
- **Governing decisions:** ADR-003, ADR-009, ADR-017, ADR-018; RFC-002 §12, RFC-003 §12 and §16.8, RFC-009

## 1. Decision summary

P1-8 will add a read-only, deterministic diagnostic bridge with two separate outputs:

1. a **coverage projection**, which expresses legacy Character, World, Lore, Glossary, and Chapter-summary knowledge in the existing Entry vocabulary without writing Entry rows; and
2. a **runtime comparison**, which records whether the knowledge actually selected by today's legacy prompt path is also represented by eligible Entry canon for the same generation situation.

The bridge is evidence for a later authority/cutover decision. It is not a backfill, dual-write path, migration, flag change, or read cutover. A P1-8 result may legitimately be red. Completing the diagnostic does not mean that Entry Store is already equivalent.

The implementation PR must not create a new table, mutate any legacy row or Entry, call a provider, or change Chat/Novel prompt output. `FEATURES["entry_store_context"]` remains default OFF.

## 2. Why a design decision is required

RFC-002 fixes the destination vocabulary and migration order, but current code leaves several implementation-defining questions unresolved:

- `World.races`, `nations`, and `taboos` are stored but not rendered by `PromptEngine`; `World.era` is available to template substitution but no current repository asset references it.
- `Lorebook.enabled` exists, but both `ChatService._load_lore()` and `NovelService._build_story_context()` filter only `LoreEntry.enabled`. A disabled book is therefore still effective in production today.
- legacy Lore uses keyword matching and carries `scan_depth`; Entry retrieval uses a different whole-Entry rank-and-budget policy. In the executed Chat/Novel callers `history=[]`, so `scan_depth` currently selects no prior messages: Chat scans the current user text and Novel scans the current chapter tail plus instruction. Equal stored text still does not prove equal runtime inclusion.
- prior `Chapter.summary` values are all collected as structural `chapter` blocks before final PromptEngine budgeting, while `story.summary` Entries first compete inside the Entry retrieval budget and then face later assembly/final budgets.
- RFC-002 names compatible target types but does not define projection granularity, stable source identity, normalization, duplicate handling, or the meaning of "equivalent".

Coding those choices first would make a comparison utility silently decide architecture. This note fixes the comparison contract before implementation.

## 3. Current production facts

The comparison baseline is the executed code, not the intended future model.

| Source | Current production consumer | Current behavior |
|---|---|---|
| `Character.personality`, `speech_style` | `PromptEngine._ctx()`, `_collect()`; `NovelEngine.assemble_continue()` | always-on when the Character participates |
| `World.name`, `description` | `PromptEngine._ctx()`, `_collect()` | always-on when a World is present |
| `World.era` | variable context only | available, but unused by current repository prompt assets |
| `World.races`, `nations`, `taboos` | none in Chat/Novel generation | persisted CRUD data, currently not prompt-visible |
| `GlossaryTerm` | none in Chat/Novel generation | persisted CRUD data, currently not prompt-visible |
| `LoreEntry` | Chat/Novel service load + `PromptEngine._make_lore_blocks()` | loaders keep only enabled entries; the scanner uses case-sensitive substring keyword matching and one global maximum `scan_depth`, but current callers pass empty `history`, so only current user/tail/instruction text is searched; final lore-block priority/budget still applies |
| `Lorebook.enabled` | no production filter | currently ignored by generation loaders |
| prior `Chapter.summary` | `NovelService._build_story_context()` → `PromptEngine` | all non-empty prior summaries become `chapter` blocks |
| Entry canon | `entry_generation_context.py` | retrieved once and assembled when feature flag is ON; flag defaults OFF |

For equal-priority Lore blocks, current SQL loaders have no `ORDER BY`; Python's stable sort therefore preserves incidental database row order. The bridge must report this as `legacy_equal_priority_order_unspecified` rather than inventing a deterministic production order. It must also report the unused fields and ignored Lorebook flag as gaps and must not "fix" them while measuring them.

## 4. Boundaries

### 4.1 In scope

- deterministic projection of supported legacy values into an immutable Entry-shaped diagnostic value;
- comparison against existing owned Entries without mutating either side;
- separate coverage and runtime-selection results;
- stable source keys and machine-readable reasons;
- golden fixtures for Chat and Novel situations;
- explicit visibility of missing, conflicting, ineligible, duplicate, and runtime-policy differences;
- an owner-scoped read service and authenticated read-only diagnostic API for real local data.

### 4.2 Out of scope

- creating, accepting, superseding, or deleting Entries;
- backfill, dual-write, migration, or a new compatibility table;
- changing legacy Character/World/Lore/Chapter reads;
- changing Entry retrieval ranking, prompt-block priority, budget ratio, or feature-flag semantics;
- disabling `_make_lore_blocks()`;
- turning Entry context on by default;
- Generation Preparation, Taste, Voice, Scene Brief, Prompt Packet, result import, or edit-diff learning code;
- P1-9 review audit persistence;
- semantic equivalence inferred by an LLM.

## 5. Projection contract

### 5.1 Diagnostic value, not a persisted Entry

The implementation will use an immutable `LegacyEntryProjection` value. It is Entry-shaped enough to compare the closed structural identity and source-specific payload defined below. Priority and selection metadata are evidence, not automatically content equality. The value is not an ORM `Entry` and must never be passed to `EntryService.create()`.

Minimum fields:

```text
source_key
source_kind
source_id
source_field
source_order
scope_kind / scope_id
subject_type / subject_id / subject_data
entry_type
title
content
priority
comparison_payload
story_position
legacy_runtime_visibility
legacy_selection_metadata
```

`source_key` is diagnostic identity, not a future Entry id and not persisted provenance. Its exact UTF-8 form is:

```text
scalar/list field  <source_kind>:<record_id>:<field>:<occurrence>
GlossaryTerm       glossary_term:<term_id>:definition:0
LoreEntry          lore_entry:<lore_entry_id>:content:0
Chapter.summary    chapter:<chapter_id>:summary:0
```

`occurrence` is zero for a scalar and the zero-based list index for an array. A list reorder may therefore change source keys; that is acceptable because the key identifies one diagnostic snapshot, not durable provenance. `source_order` separately carries the same list index or the Chapter index. Record identifiers and prose are never concatenated ambiguously or hashed into identity.

### 5.2 Normalization

- trim leading/trailing whitespace;
- normalize line endings to `\n` for comparison only;
- preserve internal whitespace, punctuation, case, and Korean text;
- discard blank scalar values and blank list elements, recording their source keys as `blank_source` trace entries;
- preserve list order and chapter index order in evidence;
- do not apply Unicode compatibility folding to prose;
- do not perform paraphrase, embedding, fuzzy, or LLM comparison.

This deliberately makes the first bridge strict and explainable. A later Bench experiment may add a separately labelled semantic metric, but it cannot replace exact deterministic results.

### 5.3 Mapping table

| Legacy source | Diagnostic Entry projection | Exact comparison payload | Report-only metadata |
|---|---|---|---|
| `Character.personality` | character scope, same character subject, `character.identity` | normalized content only; title is not required | Character name and source field |
| `Character.speech_style` | character scope, same character subject, `character.voice` | normalized content only; title is not required | Character name and source field |
| `World.description` | world scope, same world subject, `world.fact` | normalized description content only; title is not required | World name and source field |
| `World.era` | world scope, same world subject, `world.fact` | normalized `시대: <value>` | World name and source field |
| each `World.races[]` item | world scope, same world subject, `world.fact` | normalized `종족: <value>` | list index |
| each `World.nations[]` item | world scope, same world subject, `world.fact` | normalized `국가: <value>` | list index |
| each `World.taboos[]` item | world scope, same world subject, `world.fact` | normalized `금기: <value>` | list index |
| `GlossaryTerm` | world scope, same world subject, `world.term` | normalized title = term **and** normalized content = definition | term id |
| `LoreEntry` | world scope, owning world subject, `world.fact` | normalized content only; title is not required | keywords, legacy priority, effective/global scan depth, entry/book enabled state, lorebook id |
| `Chapter.summary` | work scope, same chapter subject, `story.summary` | normalized content; `Entry.data.level` must be absent or `chapter` | Chapter index, `created_at_chapter_id`, Entry `data.level` |

Aggregate identity remains on aggregates: Character name, World name, Work title, and Chapter document are not converted into Entries. `Work.synopsis`, genre, and tags are not silently added to P1-8; their missing use belongs to the Prompt Packet Story Core design.

The comparison deliberately excludes Entry provenance, confidence, capture/update timestamps, and title where the table says title is not required. It also excludes priority from **coverage payload equality** because `LoreEntry.priority`, Entry retrieval priority, and final `entry` PromptBlock priority are three different controls in current code. Differences in those controls remain explicit runtime/metadata diagnostics. `subject_data` and `Entry.data` are reported but do not affect equality except for the Chapter-summary level rule above.

Character `name`, `greeting`, `tags`, and avatar data are not projected: name is aggregate identity, greeting seeds a persisted Chat message when a session is created, and the remaining fields are not current Chat/Novel knowledge context. `World.name` remains aggregate identity. Lorebook name, Work title/synopsis/genre/tags, Chapter title/content, and WorkCharacter role are also outside the comparison payload.

### 5.4 Why array items are separate

An array item such as one taboo or nation is an independently reviewable assertion, not an arbitrary per-attribute EAV row. Keeping items separate allows a missing or conflicting fact to be reported precisely and stays within RFC-002's prose-first, independently reviewable Entry rule.

Coverage is order-insensitive across independent array/Lore facts, but preserves `source_order` for evidence. Chapter subjects and runtime prompt sequences are order-sensitive. Duplicate legacy payloads are grouped under `duplicate_legacy_payload` while retaining every source key. One exact canon Entry may cover multiple identical legacy occurrences for **stored knowledge coverage**; runtime comparison preserves occurrence counts, so rendering the same legacy Lore content twice while Entry renders it once is a `selection_mismatch`. Multiple exact eligible Entry rows for one structural payload are never deduplicated and produce `ambiguous_match`.

## 6. Matching and result states

Matching uses the closed structural key first:

```text
owner + scope + subject + Entry type
```

Within that candidate set, the source-specific exact payload in §5.3 is compared. Entry eligibility means owned, live-anchor, active `canon`; captured, proposed, rejected, superseded, and orphaned candidates remain history evidence and are never eligible. Legacy enabled/disabled flags do not change coverage eligibility and must never be called `ineligible_only`; they are runtime-selection metadata.

Each projection has **two independent primary axes**, plus zero or more diagnostic codes. A single primary state across coverage and runtime is forbidden because it would hide simultaneous problems.

### 6.1 Coverage state and precedence

Exactly one `coverage_state` is assigned in this order:

1. more than one eligible exact candidate → `ambiguous_match`;
2. exactly one eligible exact candidate → `equivalent`;
3. no eligible exact candidate but at least one eligible structural candidate → `content_mismatch`;
4. no eligible structural candidate but at least one exact ineligible candidate → `ineligible_only`;
5. any remaining structural candidate exists, even if all are ineligible and payload-different → `content_mismatch` with `all_structural_candidates_ineligible`;
6. no structural candidate exists → `missing_entry`.

Mismatched extra candidates do not turn one eligible exact match into ambiguity. An exact rejected/superseded proposal does not hide a mismatched live canon: step 3 wins. Candidate ids, status, anchor liveness, and differing payload fields are retained so the precedence is auditable.

### 6.2 Runtime state

Exactly one `runtime_state` is assigned per requested surface:

| State | Meaning |
|---|---|
| `not_applicable` | the source has no current consumer on this surface, such as World arrays or Glossary |
| `equivalent` | the ordered occurrence/membership outcome is the same on both shadow paths, including both excluded for explained equivalent reasons |
| `selection_mismatch` | only one side survives a selection stage, selected multiplicity differs, or the stable selected order differs |
| `unsupported_legacy_semantics` | the current legacy outcome cannot be reproduced deterministically, including equal-priority Lore whose production order is unspecified |

`legacy_not_runtime_visible` is a diagnostic code/visibility value, not a coverage result. Other codes may coexist, including `duplicate_legacy_payload`, `ignored_disabled_lorebook`, `legacy_disabled_entry`, `legacy_keyword_miss`, `legacy_equal_priority_order_unspecified`, `entry_status_excluded`, `entry_orphan_excluded`, `entry_limit_rejected`, `entry_retrieval_budget_rejected`, `entry_rendered_budget_rejected`, `final_prompt_budget_drop`, `future_story_position_selected`, `future_story_position_not_selected`, `unknown_story_position`, `unknown_story_position_selected`, `unknown_story_position_not_selected`, `database_timestamp_recency`, `memory_evaluation_time_required`, `regenerate_assistant_timestamp_tie`, and `regenerate_user_timestamp_tie`.

Entry-only live canon is returned separately as `entry_only`; it is useful new knowledge and is not a failure. Counts must never collapse the detailed records.

## 7. Coverage and runtime comparison are different

### 7.1 Coverage comparison

Coverage asks: "Can the existing Entry corpus express every non-empty legacy knowledge item?"

It compares projections with owned Entries regardless of a particular prompt budget. Character Chat coverage loads the owned Character and its linked World data. Novel coverage loads the owned Work's linked cast, linked World data, and **all** non-empty Chapter summaries in that Work; runtime then narrows summaries to the target Chapter position. Coverage exposes missing or conflicting data and fields that legacy stores but current generation never reads.

### 7.2 Runtime comparison

Runtime comparison asks: "For this exact Chat or Novel request, did both paths select the same knowledge?"

It reuses, without modifying:

- the current legacy Lore matching rules;
- `EntryService.retrieve()`;
- `assemble_entry_context()`;
- the same declared owner, scopes, cast, beat, and budget used by P1-6;
- the same non-knowledge Chat memory/history or Novel tail/instruction and final PromptEngine budget inputs.

The comparison builds two in-memory shadow assemblies from the same snapshot: (a) current legacy knowledge with Entry context absent and (b) Entry knowledge with the projected legacy personality/voice/world-description/Lore/summary payloads absent while aggregate identity and all unrelated inputs remain. It never flips the feature flag and never sends either prompt to a provider. It compares logical payload occurrence, order, and survival at legacy selection, Entry retrieval, Entry Context Assembly, and final PromptEngine budgeting; it does not require byte-identical provider messages because headings and block kinds differ by design.

Final-budget survival is attributed at source level. For aggregate Character, World, and Novel system blocks, the diagnostic carries the exact resolved character offsets and full normalized payload digest for each source field through the shadow assembly. It never infers one source's survival from `payload in aggregate_block`, from a bounded preview, or from another source containing the same text. Identical and partially overlapping values therefore retain distinct source identity and occurrence count. One-source Lore and Chapter blocks require full normalized block equality after final budgeting, so a truncated prefix is not treated as survival. This trace is diagnostic-only and does not add markers to, or otherwise change, provider-visible prompt text.

Sources whose legacy runtime visibility is `not_applicable` remain present in stored coverage and retain their own `not_applicable` runtime records, but are excluded from both sides of the applicable runtime ordering sequence. Their Entry rows cannot create an order mismatch for World description, Lore, Character, or any other applicable source.

The runtime report must keep these exclusion reasons distinct:

- legacy keyword miss;
- legacy disabled entry;
- ignored disabled Lorebook flag;
- Entry status or orphan exclusion;
- Entry limit rejection (current retrieval has no low-relevance threshold; a zero-keyword candidate may still rank and fit);
- Entry retrieval budget rejection;
- Entry rendered-block budget rejection;
- final PromptEngine budget drop.

For Novel, the report resolves both a summary subject Chapter index and `created_at_chapter_id` index when present. Any runtime-selected `story.summary` tied to a Chapter at or after the target Chapter is `future_story_position_selected`; an eligible but non-selected row instead receives `future_story_position_not_selected`. Missing/unresolvable position retains the general `unknown_story_position` evidence and is additionally distinguished as `unknown_story_position_selected` or `unknown_story_position_not_selected`. The current ranker's use of `updated_at`/`created_at` is reported as `database_timestamp_recency` and is never normalized into story chronology by the bridge.

## 8. Known non-equivalences frozen by this design

P1-8 is expected to reveal at least these gaps on current main:

1. World arrays and Glossary are not consumed by current generation.
2. Lorebook-level disable is not honored by current generation loaders.
3. Lore keyword selection and Entry ranking are not equivalent policies. `scan_depth` is stored and globally computed, but current Chat/Novel callers pass empty `history`, so it presently has no prior-message effect; this dormant behavior still requires an explicit cutover decision.
4. Chapter summaries are structural legacy blocks collected before final PromptEngine budgeting, while the new path first subjects them to Entry retrieval/assembly budgets as well as the final budget.
5. Entry context is default OFF, so normal user generation does not retrieve it.
6. Novel prompt assembly does not currently include Work synopsis, genre, or tags.
7. Entry retrieval recency currently uses database `updated_at`/`created_at`, not RFC-003's preferred work story chronology, and does not itself prove that a later-chapter summary cannot be selected for an earlier chapter.

These are findings, not permission for scope expansion in the implementation PR.

## 9. Read boundary

The implementation PR must provide one owner-scoped application service that:

1. loads only explicitly requested, owned anchors;
2. snapshots the needed legacy rows and eligible/history Entry candidates;
3. closes database access before pure projection/comparison where practical;
4. returns a typed report;
5. performs zero writes and zero provider calls.

The production diagnostic caller is one authenticated, non-mutating `POST /api/v1/entries/equivalence:compare` endpoint. A request body avoids placing user prose in a query string. It accepts exactly one concrete situation:

- Chat: `chat_id` plus `mode`. `new_message` requires the same non-blank `user_message` as `MessageCreate`; `regenerate` forbids a supplied message and derives the last user text from the owned session. An optional offset-aware `evaluation_time` defines the diagnostic Memory-ranking instant.
- Novel: `chapter_id`, `instruction` (default empty), and `target_words` with the same default/range as `ContinueRequest` (`800`, `50..5000`).

The Chat shadow must reproduce the production pre-assembly view without writing it: `new_message` inserts an ephemeral user message into the in-memory message sequence at the position where the flushed row would be observed, while `regenerate` omits the last active assistant exactly as the service does before rebuilding Memory and uses the derived last user text. Production selects regenerate assistant and user targets with `created_at DESC` and no further tie-break. If the maximum timestamp is shared by multiple eligible rows, the diagnostic must not invent an `id` ordering as production truth; it returns `unsupported_legacy_semantics` with `regenerate_assistant_timestamp_tie` or `regenerate_user_timestamp_tie` and makes no runtime-selection claim. The Novel shadow derives the provider configuration and then applies `min(configured max_tokens, words_to_tokens(target_words))` exactly as the current continuation path does. Thus retrieval beat, Memory inputs, instruction/tail, and final prompt budget are all reproducible from the request and owned snapshot when the production semantics are defined.

PR #27 did not define the clock instant used by Chat Memory recency. This implementation clarification closes only that diagnostic input: when Memory candidates exist, an offset-aware `evaluation_time` is required before the diagnostic can claim runtime equivalence. The shadow applies the existing production Memory relevance/recency/kind formula at that explicit instant through the same ranking function. If the field is absent, it returns deterministic `unsupported_legacy_semantics` with `memory_evaluation_time_required`; it never falls back to the server wall clock. Normal `MemoryEngine._rank()` still supplies `datetime.now(UTC)` and production Chat selection is unchanged. When no Memory candidate exists, no evaluation time is needed because recency cannot affect the result.

The service derives the effective `context_window`, final `max_tokens`, and tokenizer/provider safety ratio from owned local model configuration and the registry capability lookup, without decrypting credentials. Explicit numeric overrides are allowed only as a complete validated effective trio, replace the computed effective values, and are labelled `diagnostic_override`. Local adapter capability lookup is allowed; invoking `chat()`/`stream_chat()`, decrypting or exposing a secret, or making a network call is forbidden.

The endpoint derives `user_id` from authentication, loads the owned Chat or Chapter and reachable anchors itself, and returns both coverage and runtime sections by default. Supplying both anchor kinds, neither anchor, an invalid Chat mode/message combination, a foreign/deleted anchor, a partial override trio, or invalid budget values is rejected. It exposes no write/autofix action and has no P1-8 frontend. A test-only helper without this application caller is insufficient evidence for real stored data. Character-only coverage may remain an internal pure-function fixture; it is not a substitute for a concrete Chat runtime API anchor.

### 9.1 Typed response boundary

The response contains:

- `situation`: anchor kind/id, effective numeric budgets, task/policy versions, whether an override was used, and the explicit Memory evaluation time when supplied;
- `coverage.records`: source identity/order, structural projection, `coverage_state`, exact/ineligible candidate ids and statuses, payload-difference fields, runtime visibility, and diagnostic codes;
- `runtime.records`: source key or Entry-only id, per-stage selected/excluded booleans, occurrence/order positions, exclusion code, `runtime_state`, and relevant trace ids;
- `entry_only`: owned live-canon ids and structural identity not matched by a legacy payload;
- detailed counts derived from, but never replacing, the records.

The API must not serialize ORM objects or return `user_id`, provider credentials, unbounded provenance/data blobs, SQL/debug internals, or unrelated Entries. For a mismatch it may return only the owner-visible compared title/content fields (or their digest plus a bounded preview) needed to diagnose the difference. Full internal retrieval and PromptBlock traces stay typed and are reduced to the ids, policies, scores, stages, and exclusion reasons required for cutover evidence.

## 10. Determinism and safety

- stable ordering: source kind, aggregate id, source field, source order, source id;
- stable Entry candidate ordering: current retrieval order, then Entry id;
- no server-current timestamps in the report body; an explicitly supplied Memory evaluation time may be echoed as required diagnostic context;
- no hidden wall clock in diagnostic Memory ranking; a Memory-bearing Chat request without explicit evaluation time is unsupported rather than guessed;
- no production-invented regenerate tie-break; timestamp ties are deterministic unsupported evidence;
- no random ids;
- no persistence or autofix action;
- no provider or network call;
- no feature-flag mutation and no dependency on the current flag value for whether both shadow paths run;
- no production/root database mutation in tests;
- isolated temporary databases only;
- owner, soft-delete, provenance, and retrieval traces preserved.

## 11. Acceptance criteria for the implementation PR

The separate implementation PR is complete when it proves:

- Character personality and voice projections;
- World description, era, arrays, Glossary, and Lore projections;
- Chapter-summary projection and chapter order;
- empty, duplicate, disabled, soft-deleted-anchor/orphaned, and non-canon cases;
- coverage precedence, independent runtime states, multi-code diagnostics, and Entry-only reporting;
- title-required/title-ignored mappings, legacy duplicate reuse for coverage, runtime multiplicity/order mismatch, and equal-priority Lore unsupported ordering;
- concrete Chat and Novel runtime comparison with separate exclusion traces;
- Chat `new_message`/`regenerate` memory and final-budget reproduction from `chat_id`; Novel `instruction`/`target_words`, prior/future-summary chronology evidence, and database-timestamp recency labelling;
- source-identity final-budget attribution under identical/overlapping aggregate text, not-applicable ordering isolation, explicit Memory evaluation-time determinism, regenerate timestamp-tie unsupported evidence, and selected/non-selected chronology codes;
- authenticated API tests for owned, foreign, deleted, and invalid anchor combinations;
- deterministic reruns and golden snapshots;
- zero SQL writes, zero migrations, zero provider calls;
- no change to current generation payloads with the Entry feature flag OFF or ON;
- all existing Entry lifecycle/retrieval/context/review/authoring/prompt/chat/novel/edit-diff/golden tests remain green.

## 12. Lore scanner cutover gate

`PromptEngine._make_lore_blocks()` may be disabled only in a later, separately approved PR after all of the following are true:

1. P1-8 implementation is merged and reports are available on representative user data.
2. Every effective Lore source has an approved Entry representation or an explicit retained-legacy exception.
3. Lorebook enable semantics are intentionally resolved and regression-tested.
4. keyword/scan-depth behavior is either reproduced, intentionally superseded, or proven unnecessary with golden/Bench evidence.
5. Chapter-summary always-on versus retrieved policy is resolved.
6. Chat and Novel runtime comparisons have no unexplained loss.
7. Entry retrieval/context is enabled through a separately reviewed rollout decision with rollback. The existing `entry_store_context` flag retains only that meaning.
8. The legacy scanner removal itself is a distinct PR and, if it needs a runtime control, uses a separate named control rather than reusing `entry_store_context`; no data or schema deletion is coupled to it.

## 13. Relationship to the Personal Author OS direction

P1-8 remains the shortest safe next step because the shared Generation Preparation must not inherit two unexplained canon authorities. Its projection/report types are diagnostic only and must not become a second Store or a generation-route-specific knowledge model.

The future direct-provider and Prompt Packet routes will reuse one provider-neutral preparation built from Store retrieval, Context Assembly, PromptEngine budgeting concepts, and repository prompt assets. Neither route will use this bridge as a permanent runtime source once authority is resolved. Taste, Voice, and Scene Brief remain separate concerns as defined in the product roadmap; none is projected from legacy canon by P1-8.

## 14. Rejected alternatives

- **Backfill while comparing:** makes the observer mutate the evidence and risks user data.
- **Byte-compare final prompts:** renderers and block kinds differ by design; byte equality would reject valid knowledge equivalence and hide selection reasons.
- **LLM semantic judge:** nondeterministic, paid, and unsuitable as the required cutover gate.
- **Treat every legacy field as one `note`:** loses governed type, subject, and retrieval behavior.
- **Fix legacy bugs inside the bridge:** changes the baseline being measured and mixes tasks.
- **Turn the feature flag on to gather evidence:** reverses the safe migration order in RFC-002.

## 15. Implementation PR boundary

The next PR after this design is reviewed should be named and scoped as P1-8 implementation only. It may add the pure projection/comparison module, typed report schema, owner-safe read seam, and golden/integration tests. It must not include Generation Preparation, Prompt Packet, Taste, Voice, Scene Brief, Analyst, Writer, provider, migration, backfill, flag, or UI work.
