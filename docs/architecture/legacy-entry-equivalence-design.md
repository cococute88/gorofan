# P1-8 Legacy Context ↔ Entry Equivalence Bridge

- **Status:** Proposed for architecture review
- **Scope:** P1-8 design only
- **Baseline:** `main` at `10683313321be4ee9d81d634943d55fa67f3f4cb`
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
- legacy Lore uses keyword matching plus `scan_depth`; Entry retrieval uses a different whole-Entry rank-and-budget policy. Equal stored text does not prove equal runtime inclusion.
- prior `Chapter.summary` values are always collected as structural `chapter` blocks, while `story.summary` Entries compete inside the Entry retrieval budget.
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
| `LoreEntry` | Chat/Novel service load + `PromptEngine._make_lore_blocks()` | enabled entry, keyword match, max scan depth, prompt-budget dependent |
| `Lorebook.enabled` | no production filter | currently ignored by generation loaders |
| prior `Chapter.summary` | `NovelService._build_story_context()` → `PromptEngine` | all non-empty prior summaries become `chapter` blocks |
| Entry canon | `entry_generation_context.py` | retrieved once and assembled when feature flag is ON; flag defaults OFF |

The bridge must report the unused fields and the ignored Lorebook flag as gaps. It must not "fix" them while measuring them.

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
- Taste, Voice, Scene Brief, Prompt Packet, result import, or edit-diff learning code;
- P1-9 review audit persistence;
- semantic equivalence inferred by an LLM.

## 5. Projection contract

### 5.1 Diagnostic value, not a persisted Entry

The implementation will use an immutable `LegacyEntryProjection` value. It is Entry-shaped enough to compare scope, subject, type, title, content, priority, and source metadata, but it is not an ORM `Entry` and must never be passed to `EntryService.create()`.

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
legacy_runtime_visibility
legacy_selection_metadata
```

`source_key` is stable within the legacy record identity. It is diagnostic identity, not a future Entry id and not persisted provenance.

### 5.2 Normalization

- trim leading/trailing whitespace;
- normalize line endings to `\n` for comparison only;
- preserve internal whitespace, punctuation, case, and Korean text;
- discard blank scalar values and blank list elements, recording their source keys as `blank_source` trace entries;
- preserve list order and chapter index order;
- do not apply Unicode compatibility folding to prose;
- do not perform paraphrase, embedding, fuzzy, or LLM comparison.

This deliberately makes the first bridge strict and explainable. A later Bench experiment may add a separately labelled semantic metric, but it cannot replace exact deterministic results.

### 5.3 Mapping table

| Legacy source | Diagnostic Entry projection | Granularity and content |
|---|---|---|
| `Character.personality` | character scope, character subject, `character.identity` | one projection per non-empty field; content preserved verbatim |
| `Character.speech_style` | character scope, character subject, `character.voice` | one projection per non-empty field; content preserved verbatim |
| `World.description` | world scope, world subject, `world.fact` | one projection; title labels description |
| `World.era` | world scope, world subject, `world.fact` | one projection; content retains the `시대:` semantic label |
| each `World.races[]` item | world scope, world subject, `world.fact` | one independently reviewable fact with `종족:` label |
| each `World.nations[]` item | world scope, world subject, `world.fact` | one independently reviewable fact with `국가:` label |
| each `World.taboos[]` item | world scope, world subject, `world.fact` | one independently reviewable fact with `금기:` label |
| `GlossaryTerm` | world scope, world subject, `world.term` | title is term; content is definition, with the term retained in normalized comparison text |
| `LoreEntry` | world scope, world subject, `world.fact` | one projection per entry; content preserved; keywords, priority, scan depth, entry/book enabled state remain selection metadata |
| `Chapter.summary` | work scope, chapter subject, `story.summary` | one projection per non-empty summary; ordered by chapter index |

Aggregate identity remains on aggregates: Character name, World name, Work title, and Chapter document are not converted into Entries. `Work.synopsis`, genre, and tags are not silently added to P1-8; their missing use belongs to the Prompt Packet Story Core design.

### 5.4 Why array items are separate

An array item such as one taboo or nation is an independently reviewable assertion, not an arbitrary per-attribute EAV row. Keeping items separate allows a missing or conflicting fact to be reported precisely and stays within RFC-002's prose-first, independently reviewable Entry rule. Empty and duplicate items remain traceable rather than silently merged.

## 6. Matching and result states

Matching uses the closed structural key first:

```text
owner + scope + subject + Entry type
```

Within that candidate set, exact normalized title/content is compared. Provenance is reported but is not required to match because existing human-authored Entries may legitimately describe the same fact without legacy source metadata.

Each legacy projection receives exactly one primary state:

| State | Meaning |
|---|---|
| `equivalent` | one eligible canon Entry has the exact normalized payload |
| `missing_entry` | no structurally compatible Entry exists |
| `content_mismatch` | compatible candidates exist but payload differs |
| `ambiguous_match` | multiple eligible exact matches exist |
| `ineligible_only` | only captured/proposed/rejected/superseded or orphaned matches exist |
| `legacy_not_runtime_visible` | legacy data is stored but has no current Chat/Novel consumer |
| `selection_mismatch` | both representations exist but only one side is selected for the concrete runtime situation |
| `unsupported_legacy_semantics` | payload exists but current Entry policy cannot represent equivalent selection behavior |

Entry-only canon is returned separately as `entry_only`; it is useful new knowledge and is not a failure. Counts must never collapse the detailed records.

## 7. Coverage and runtime comparison are different

### 7.1 Coverage comparison

Coverage asks: "Can the existing Entry corpus express every non-empty legacy knowledge item?"

It compares projections with owned Entries regardless of a particular prompt budget. It exposes missing or conflicting data and fields that legacy stores but current generation never reads.

### 7.2 Runtime comparison

Runtime comparison asks: "For this exact Chat or Novel request, did both paths select the same knowledge?"

It reuses, without modifying:

- the current legacy Lore matching rules;
- `EntryService.retrieve()`;
- `assemble_entry_context()`;
- the same declared owner, scopes, cast, beat, and budget used by P1-6.

It compares selected source keys and logical knowledge payloads, not byte-identical provider messages. The legacy and Entry renderers intentionally use different headings and block kinds.

The runtime report must keep these exclusion reasons distinct:

- legacy keyword miss;
- legacy disabled entry;
- ignored disabled Lorebook flag;
- Entry status or orphan exclusion;
- Entry low relevance / limit rejection;
- Entry retrieval budget rejection;
- Entry rendered-block budget rejection;
- final PromptEngine budget drop.

## 8. Known non-equivalences frozen by this design

P1-8 is expected to reveal at least these gaps on current main:

1. World arrays and Glossary are not consumed by current generation.
2. Lorebook-level disable is not honored by current generation loaders.
3. Lore keyword/scan-depth selection and Entry ranking are not equivalent policies.
4. Chapter summaries are structural, always-collected legacy blocks but budgeted retrieved Entries on the new path.
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

The production diagnostic caller is one authenticated, non-mutating `POST /api/v1/entries/equivalence:compare` endpoint. A request body avoids placing user prose in a query string. It accepts exactly one situation anchor:

- `character_id` for the current Chat context; or
- `chapter_id` for the current Novel continuation context.

Optional `beat`/`instruction` and `context_window` inputs let the service reproduce a concrete selection situation without resolving a provider. The endpoint derives `user_id` from authentication, loads the owned Character or Chapter and reachable World/Work/cast itself, and returns both coverage and runtime sections by default. Supplying both anchors, neither anchor, a foreign/deleted anchor, or an invalid budget is rejected. It exposes no write/autofix action and has no P1-8 frontend. A test-only helper without this application caller is insufficient evidence for real stored data.

## 10. Determinism and safety

- stable ordering: source kind, aggregate id, source field, source order, source id;
- stable Entry candidate ordering: current retrieval order, then Entry id;
- no current timestamps in the report body;
- no random ids;
- no persistence or autofix action;
- no provider or network call;
- no production/root database mutation in tests;
- isolated temporary databases only;
- owner, soft-delete, provenance, and retrieval traces preserved.

## 11. Acceptance criteria for the implementation PR

The separate implementation PR is complete when it proves:

- Character personality and voice projections;
- World description, era, arrays, Glossary, and Lore projections;
- Chapter-summary projection and chapter order;
- empty, duplicate, disabled, soft-deleted, and non-canon cases;
- coverage result states and Entry-only reporting;
- concrete Chat and Novel runtime comparison with separate exclusion traces;
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
7. Entry retrieval/context is enabled through a separately reviewed rollout decision with rollback.
8. The legacy scanner removal itself is a distinct PR; no data or schema deletion is coupled to it.

## 13. Relationship to the Personal Author OS direction

P1-8 remains the shortest safe next step because Prompt Packet compilation must not inherit two unexplained canon authorities. Its projection/report types are diagnostic only and must not become a second Store or a Prompt Packet-specific knowledge model.

The future Prompt Packet compiler will reuse Store retrieval, Context Assembly, PromptEngine budgeting concepts, and repository prompt assets. It will not use this bridge as a permanent runtime source once authority is resolved. Taste, Voice, and Scene Brief remain separate concerns as defined in the product roadmap; none is projected from legacy canon by P1-8.

## 14. Rejected alternatives

- **Backfill while comparing:** makes the observer mutate the evidence and risks user data.
- **Byte-compare final prompts:** renderers and block kinds differ by design; byte equality would reject valid knowledge equivalence and hide selection reasons.
- **LLM semantic judge:** nondeterministic, paid, and unsuitable as the required cutover gate.
- **Treat every legacy field as one `note`:** loses governed type, subject, and retrieval behavior.
- **Fix legacy bugs inside the bridge:** changes the baseline being measured and mixes tasks.
- **Turn the feature flag on to gather evidence:** reverses the safe migration order in RFC-002.

## 15. Implementation PR boundary

The next PR after this design is reviewed should be named and scoped as P1-8 implementation only. It may add the pure projection/comparison module, typed report schema, owner-safe read seam, and golden/integration tests. It must not include Prompt Packet, Taste, Voice, Scene Brief, Analyst, Writer, provider, migration, backfill, flag, or UI work.
