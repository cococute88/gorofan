# Entry context integration (P1-6 implementation note)

- **Status:** Implemented
- **Scope:** `EntryService.retrieve()` → `assemble_entry_context()` → real Chat/Novel prompt assembly
- **Governed by:** ADR-003, ADR-009, ADR-013, ADR-018; RFC-002, RFC-003 §11–§13, RFC-009
- **Not an ADR.** This records decisions the implementation had to make inside the
  space the ADR/RFC set already fixed. Where it appears to conflict with an
  ADR/RFC, those govern and this document is in error.

## 1. What changed

Before P1-6, `EntryService.retrieve()` and `assemble_entry_context()` had no
production caller — the Entry Store was built but disconnected, and generation
consumed only the legacy Character/World/Lore path. P1-6 connects the two,
additively and behind an OFF-by-default flag.

The single production call site is
[`app/services/entry_generation_context.py`](../../backend/app/services/entry_generation_context.py).
Chat and Novel hand it the anchors they can prove; it returns assembled
`PromptBlock`s plus a prompt-trace section. Neither service builds Entry prompt
text, and neither re-implements ranking or budgeting.

## 2. Feature flag

`FEATURES["entry_store_context"]`, read through `Settings.entry_store_context_enabled`.
Default **OFF**.

The flag is checked before the retrieval request is even constructed, so with it
off the generation path issues **zero** Entry queries and the assembled prompt is
unchanged by the presence or absence of canon in the Store.

`Settings.feature_enabled(name)` is a deliberately minimal typed read boundary
over the pre-existing `FEATURES` map — not a flag framework.

## 3. Entry PromptBlock contract

`entry` is a first-class `BlockKind`. Entry context is **never** relabelled as
`memory`, and never concatenated into the legacy `lore` text.

| Property | Value | Reason |
|---|---|---|
| `kind` | `entry` | ADR-018/RFC-003 §13.1: Store canon and chat-private Memory meet only as separate blocks. |
| `id` | `entry:<entry_id>` | Entry identity stays traceable through final assembly. |
| `role` | `system` | Shared canon is instruction-layer context, not a conversation turn. |
| `truncatable` | `False` | A partially rendered Entry is a fabricated fact. The BudgetManager drops the whole block instead. |
| `DEFAULT_PRIORITY` | `65` | See below. |
| `LAYER_ORDER` | between `lore` and `memory` | Grouped with the knowledge layers; inserting one element leaves every existing kind's relative order untouched. |

### Why priority 65

The ADR/RFC set fixes no numeric priority, so the value was chosen against the
existing `DEFAULT_PRIORITY` contract with the smallest possible change:

- **Above `memory` (60) and `lore` (50).** Entry canon is human-gated shared
  knowledge (ADR-003, RFC-002 review gate). It should outlive chat-private
  rolling memory and the legacy keyword scan under budget pressure.
- **Below `world` (70), `chapter` (75), `persona` (80), `character` (90).** P1-6
  is additive. The legacy identity/continuity blocks remain the authoritative
  context source until the separately approved P1-8 cutover, so Entry must not
  displace them.
- **Far below the protected `user`/`instruction` (1000) and `system` blocks**, which
  `BudgetManager.fit()` reserves before anything optional is considered.
- **No existing priority or layer position was changed.**

Starvation is prevented from the other direction too: Entry cannot unboundedly
displace `memory`, because total Entry volume is capped by the retrieval
knowledge-slice budget (§4), not by this priority.

## 4. Budget

Three responsibility boundaries, exactly as RFC-003 §12 requires:

1. `retrieve()` estimates Entry `content` and selects whole Entries within the
   knowledge-slice budget.
2. `assemble_entry_context()` re-estimates the **rendered** block (heading
   included) and excludes only whole blocks.
3. `PromptEngine`/`BudgetManager` applies the model-context allocation across all
   prompt sources and guarantees Property 7.

The knowledge slice is `max(256, context_window * 0.15)`
(`ENTRY_CONTEXT_BUDGET_RATIO`), with a secondary `limit=20` safety cap. The ratio
is held well below the chat memory hint (`0.4`) precisely because the legacy path
is still authoritative during coexistence. The same value is used for the
retrieval budget and the rendered-block assembly budget, which is what makes the
two-stage exclusion visible: an Entry that fits `content` but not `content +
heading` is recorded as an *assembly* exclusion, not a retrieval one.

## 5. Retrieval situations

Both are deterministic — same inputs produce the same request.

| | Chat | Novel |
|---|---|---|
| `task_kind` | `chat` | `scene` |
| scopes | `user`, `character`, that character's `world` | `user`, `work`, `world`, each linked `character` |
| `cast` | active character id | sorted linked character ids |
| `beat` | user message | instruction + last 1200 chars of the chapter |
| `location` | not set | not set |

**Chat never declares a `work` scope.** A `ChatSession` records a character and an
optional persona but no work, and RFC-003 §13.3 forbids guessing among works.
Work canon reaches chat only when a future change gives chat an explicit work
selection.

`location` is deliberately left unset. The ranker matches `location` against
`scope_id`/`subject_id`, and it is also folded into the keyword term set — passing
an opaque id there would dilute every candidate's keyword score without adding a
real signal. Scope filtering already provides the world constraint.

Status handling is inherited, never widened: no `status_filters`,
`include_rejected=False`, `include_superseded=False`. Canon only; orphaned
anchors are excluded by `retrieve()` itself.

## 6. Trace

`AssembledPrompt.trace["entry_context"]` carries the section. Retrieval and
Context Assembly stay separately attributable:

- `retrieval_exclusions.orphaned_entry_ids` / `.retrieval_budget_rejected_entry_ids`
  / `.limit_rejected_entry_ids` — the Store refused the candidate.
- `assembly_exclusions[]` — an already-selected Entry did not survive
  rendered-block budgeting; each carries `stage: "context_assembly"`.

Three states are distinguishable: flag off
(`{"feature_enabled": false, "retrieval_invoked": false}`), retrieved-but-nothing-
eligible (`no_eligible_entries: true`), and canon injected. Memory and lore keep
their own per-block trace entries and are never merged into this section.

With the flag OFF the provider-visible payload (`messages`, `system`,
`token_count`) is byte-identical to pre-P1-6 behaviour; the only difference is the
diagnostic `entry_context` marker inside `trace`.

## 7. Error policy

**Entry retrieval and assembly failures propagate; they are not swallowed.**

Entry retrieval sits in the same pre-stream context-building stage as
`MemoryEngine.build_memory_context()` and the legacy lore load, both of which
already abort the turn on failure. Three reasons to match them:

1. Consistency with the existing T1 contract.
2. Silently degrading to canon-less output produces continuity-broken prose that
   *looks* successful — the failure mode the review gate and trace contract exist
   to prevent.
3. The flag is OFF by default, so only an operator who opted in is exposed, and
   they get a loud, diagnosable failure.

Because the failure happens before streaming starts, nothing is streamed and no
chapter append or assistant message is persisted.

## 8. Explicitly unchanged

- Legacy `PromptEngine._make_lore_blocks()` keyword scanner — preserved, still
  running, no authority transfer (RFC-003 §16.8 permits coexistence until an
  approved migration).
- Legacy Character/World/Lore/Chapter context — unchanged, still authoritative.
- chat-private `Memory` — not converted, not unified, not stored as Entry.
- Repository prompt assets remain the only architecture prompt-body source; DB
  `PromptTemplate` is untouched.
- Alembic head stays `0002_entry_store`. **No migration.**
- No frontend change.

## 9. Enabling it

```jsonc
// .env  →  FEATURES='{"entry_store_context": true}'
```

Turning the flag on is a runtime decision, not a code change. Leave it off until
the Bench (P6-1) can measure the retrieval policy against golden scenes.
