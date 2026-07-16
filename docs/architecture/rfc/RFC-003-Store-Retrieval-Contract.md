# RFC-003: Store-wide Retrieval Contract

- **Status:** Draft
- **Date:** 2026-07-11
- **Author:** Chief Software Architect
- **Project:** AI Native Creative Workspace (`ai-creative-workspace` / "gorofan")
- **Conforms to:** RFC-001, RFC-002; ADR-002, ADR-003, ADR-004, ADR-007, ADR-008, ADR-009, ADR-012, ADR-014, ADR-015, ADR-017, ADR-018
- **Supersedes:** the retrieval-contract portion of the former RFC-008 Retrieval & Context Assembly draft
- **RFC layer:** Phase 1 implementation contract; implementation-neutral

> **Precedence.** The accepted ADRs govern. RFC-001 and RFC-002 govern this RFC. The older `.kiro` PromptEngine and MemoryEngine design is a reusable implementation pattern, not the current Store-wide source of truth where it conflicts with newer ADRs.
>
> **Contract, not implementation.** This document fixes the observable behavior of Store-wide retrieval. It does not implement a retriever, repository, query, vector index, PromptBlock, or prompt assembler.

---

## 1. Summary

`retrieve()` is the Store's single read-only capability for selecting the smallest useful set of Entries for a task within an explicit context budget. It serves novel writing, Story Bible continuity, Character Chat shared knowledge, and future consumers through one seam.

Phase 1 retrieval is deterministic and keyword-first. It filters by ownership, scope, type, subject, and status; ranks by type weighting, textual relevance, recency, explicit priority, and appropriate confidence; then selects whole Entries within budget. Embeddings and a vector database are forbidden until the Bench demonstrates repeatable keyword misses, at which point semantic scoring is added behind this same seam.

## 2. Motivation

The Entry Store can grow without bound while a model context cannot. Sending the whole Store is impossible for long works, dilutes relevant facts, wastes tokens, and delegates arbitrary truncation to a provider. Separate retrievers for lore, chat memory, Story Bible, and references would recreate the parallel-engine debt ADR-018 rejects.

The next implementation therefore needs one minimum contract before query code exists: which contexts may be searched, how ownership is isolated, what ranking factors mean, how ties and budgets behave, and where retrieval stops and Context Assembly begins.

## 3. Non-goals

This RFC does not define or implement:

- a programming-language signature, HTTP API, repository method, SQL query, or ORM shape;
- exact numeric weights, tokenizers, database indexes, caches, or performance thresholds;
- embedding models, vector columns, vector extensions, or a second RAG pipeline;
- prompt bodies, final message ordering, provider rendering, or model calls;
- generation, extraction, summarization, review decisions, or canon mutation;
- chat-private Memory ranking beyond its boundary with Store retrieval;
- automatic type creation or user-tunable ranking knobs.

## 4. Purpose and non-responsibilities of `retrieve()`

### 4.1 Purpose

Given an authorized owner, a declared situation, filters, and a knowledge-token budget, `retrieve()` returns an ordered, budget-fitting set of eligible Entries plus enough metadata to explain and reproduce the selection.

It answers one question:

> What canonical knowledge from this owner's reachable Store scopes is most useful for this task right now, and fits in the allotted knowledge budget?

### 4.2 What `retrieve()` must not do

`retrieve()` must not:

- create, edit, promote, reject, supersede, or delete Entries;
- infer new facts, summarize content on demand, or call an LLM;
- decide whether a proposal becomes canon;
- assemble final prompts or provider-specific `messages[]`;
- query chat-private memories as though they were Entries;
- scan legacy LoreEntry triggers as a parallel retrieval path once Store retrieval is authoritative;
- silently broaden owner or scope when results are sparse;
- add embeddings or an external index without the Bench gate in §14.

## 5. Retrieval input contract

The contract is conceptual. Implementations may use a request object, typed parameters, or an internal protocol, but must preserve these inputs.

| Input | Required | Contract |
|---|---|---|
| owner | yes | authenticated/implicit `user_id`; never inferred from Entry data returned by an unscoped query |
| scope | yes | one or more authorized scope selectors and their anchors; includes `user`, `collection`, `work`, `character`, `world`, and the explicit `chat-private` boundary |
| cast | no | stable Character identifiers currently on stage or participating |
| location | no | stable World/location subject or bounded textual location cue |
| beat | no | current scene/chat intent, instruction, or query text used for keyword relevance |
| budget | yes | positive maximum token estimate allocated to retrieved Entry content and required retrieval metadata |
| entry types | no | allow-list from RFC-002's governed type vocabulary; omission means caller-default policy, not unrestricted guesswork |
| subject filters | no | typed subject constraints such as character, pair, location, chapter, or story thread |
| status filters | no | explicit allowed statuses; default is exactly `canon` |
| task kind | recommended | writer stage, chat turn, continuity check, review view, or other governed consumer; selects a documented type-weight profile |
| as-of position | no | chapter/scene/time boundary when future knowledge must not leak backward |
| limit | no | optional safety cap subordinate to the token budget |

### 5.1 Scope reachability

A caller does not gain access to all scopes owned by a user merely by supplying `user_id`. The request must declare the scope graph that is relevant to the task.

Examples:

- a work scene may reach that `work`, its linked `character` and `world` scopes, explicitly attached `collection` scopes, and relevant `user` preferences;
- a collection analysis view may reach that collection but not an unrelated work's canon;
- a character chat may reach the character, linked world, an explicitly selected work, and user preferences, while conversation-private Memory remains a separate input to Context Assembly;
- `chat-private` in the input is a boundary marker. Phase 1 Store retrieval returns no Entry from that scope because RFC-002 forbids persisting chat-private Entry rows.

Scope expansion must be explicit and deterministic. It may not depend on keyword hits.

### 5.2 Status defaults

Generation and checks default to `status = canon` only. Review tooling may explicitly request `captured`, `proposed`, `rejected`, or `superseded`, but those results must remain clearly labelled and must not be mixed into trusted prompt context by default.

## 6. Retrieval output contract

The result must contain:

- an ordered list of selected Entries, preserving stable Entry identity, type, scope, subject, status, content, provenance reference, confidence, explicit priority, and token estimate as applicable;
- the total estimated tokens selected and the requested budget;
- a deterministic score or score breakdown sufficient for debug/Bench comparison;
- the retrieval policy/version or equivalent configuration identity used to rank;
- exclusion/trace metadata in debug or Bench mode, at least for filtered status/scope, duplicate suppression, and budget rejection;
- a truncation indicator that is false for every selected Entry in Phase 1, because retrieval selects whole Entries.

The output is not a prompt, not `messages[]`, and not model-ready by itself. Callers must not depend on incidental database row order.

## 7. Filtering contract

Filtering occurs before ranking. Ineligible records must never receive a score and then "lose"; they must be absent from the candidate set.

### 7.1 Ownership filtering

- Every candidate query is scoped by the authorized owner at its root.
- Scope anchors and subjects must belong to or be visible to that same owner.
- Missing or unauthorized anchors produce an empty/not-authorized result according to the calling boundary; retrieval never falls back to another user's data.
- Cache keys and traces must include owner identity without exposing it across users.

### 7.2 Scope filtering

- Only explicitly reachable scope anchors are eligible.
- Work canon does not bleed into another work.
- Collection guidance is included only when the collection is attached or requested.
- Character/world Entries are included only for linked or requested subjects.
- User-level preferences may apply across works but still require explicit policy inclusion.
- `as-of position`, when supplied, excludes Entries that became true later in story order.

### 7.3 Type and subject filtering

Type allow-lists and subject filters are hard constraints. `cast`, `location`, and relationship-pair filters must use stable identifiers when available. Textual aliases may contribute to relevance but may not substitute for ownership-safe identity matching.

### 7.4 Status and supersession filtering

Default generation retrieval includes active `canon` only. It excludes captured, proposed, rejected, superseded, soft-deleted, and invalid Entries. A canonical Entry with a canonical replacement is excluded through its `superseded` status; retrieval must not guess current truth by timestamp alone.

### 7.5 Aggregate anchor liveness

Entry history is retained when a Character, World, Work, Chapter, Collection, or other aggregate anchor is soft-deleted or becomes orphaned. Default retrieval must nevertheless exclude a candidate when its scope anchor or any required subject anchor is soft-deleted, missing, or no longer owner-visible.

This is a pre-ranking eligibility filter, not a negative ranking signal. Retrieval must not silently re-anchor the Entry or guess a surviving aggregate. Explicit audit, administration, or recovery modes may opt into such Entries through a separately named option and must keep them visibly distinct from default generation context.

## 8. Candidate normalization and duplicate handling

Before scoring, the implementation must:

- normalize keyword text consistently for Korean/CJK and Latin text, including Unicode normalization and documented case handling;
- preserve exact original content for output;
- collapse the same Entry reached through multiple scope paths to one candidate;
- use supersession state rather than fuzzy similarity to remove replaced canon;
- avoid semantic deduplication that could erase genuinely conflicting canonical assertions;
- keep provenance distinct when separate Entries legitimately share similar content.

Exact tokenization and morphological analysis are implementation choices. Phase 1 must not require an external search service.

## 9. Ranking contract

Ranking is a deterministic blend of governed factors. Exact numeric weights are deliberately not frozen here; they must be versioned and Bench-tuned.

### 9.1 Type weighting

Each task kind uses a documented type-weight profile. Examples:

- scene drafting emphasizes on-cast `character.*`, location `world.*`, current `relationship.state`, relevant `story.fact`/`story.knowledge`, due `story.promise`, and appropriately-grained `story.summary`;
- continuity checking emphasizes `story.fact`, `story.knowledge`, `story.promise`, and relationship state;
- surface style emphasizes `style.preference` and `user.preference` after correctness-bearing context is protected;
- chat emphasizes the active character's identity/voice/exemplars and shared world/relationship canon.

Type weight is a ranking signal, not permission to bypass filters.

### 9.2 Keyword matching and relevance

Phase 1 relevance is keyword-first. It may combine normalized overlap across:

- the `beat`/query text;
- cast names and stable subject aliases;
- location names and world terms;
- Entry content and bounded searchable metadata;
- explicit story-thread or promise identifiers.

Exact-match identity and subject relevance must outrank incidental prose overlap. Empty `beat` input yields a neutral textual-relevance contribution rather than excluding all candidates.

### 9.3 Recency

Recency represents how recently knowledge was established or updated in the relevant chronology, not merely database write time. Work-scoped facts should prefer story position (`created_at_chapter` or equivalent) when available; user/collection guidance may use update/capture time.

Recency is type-sensitive. An enduring character identity or world rule must not decay out of relevance merely because it is old. For evolving state and summaries, newer current canon generally outranks older material.

### 9.4 Priority

Entry priority is an explicit bounded importance hint. It is distinct from type weighting, textual relevance, and final PromptBlock priority. It may raise an Entry within its eligible set but must not override ownership, scope, status, or as-of filtering.

### 9.5 Confidence

Confidence may break or influence ranking among otherwise comparable AI-derived Entries. It must not demote explicit user-authored canon below lower-authority inferred content. Missing confidence, and any explicitly designated neutral confidence value, contributes exactly zero confidence bonus and zero confidence penalty; it is not treated as the minimum value. Confidence cannot replace ownership, scope, subject, anchor-liveness, status, or supersession filters, and it never determines whether an Entry is canon.

### 9.6 Exemplar precedence

For tasks that generate or validate a character's voice, `character.exemplar` outranks descriptive `character.voice`, which in turn outranks broader behavior/identity guidance, subject to relevance and budget. This is a task-specific precedence, not a universal rule: continuity checks need not prioritize exemplars over facts.

### 9.7 Score composition

An implementation may use an additive or multiplicative normalized composition if it preserves the meanings above, exposes a reproducible breakdown, and is Bench-validated. The ADR phrase "type-weight × relevance × recency" is conceptual; a zero keyword score must not erase mandatory identity/current-state context when the task profile requires it.

## 10. Deterministic behavior

For a fixed Entry snapshot, request, tokenizer/version, and ranking-policy version, retrieval must return the same ordered result.

Determinism requires:

1. stable normalization;
2. fixed factor calculation and policy version;
3. stable descending score ordering;
4. explicit tie-breakers, in this order unless a later RFC amends it: higher explicit priority, higher applicable confidence, newer relevant chronology, then stable Entry identifier;
5. deterministic duplicate elimination and budget selection;
6. no provider call, randomness, ambient locale, or wall-clock dependence beyond an explicit request/as-of time.

Tests and the Bench may freeze `now` or use story chronology so recency is reproducible.

## 11. Context budget handling

### 11.1 Budget meaning

The retrieval budget is the caller-allocated budget for the **knowledge slice**, not the model's entire context window. Context Assembly separately reserves system instructions, user input, recent history, output tokens, and tokenizer safety margin.

The caller must supply a positive budget already derived from the final context plan. Retrieval must not infer a larger budget from model capability.

### 11.2 Selection rule

After ranking, Phase 1 selects whole Entries in deterministic order while the cumulative token estimate remains within budget.

- Retrieval does not cut an Entry mid-sentence.
- If the next Entry does not fit, the selector may skip it and consider later smaller Entries; it must not stop prematurely if useful candidates can still fit.
- Selected estimated tokens must never exceed budget.
- A single oversize Entry is excluded with a trace reason. Content trimming, if allowed at all, belongs to PromptBlock assembly and must be visible there.
- A count limit is a secondary guard; token budget is authoritative.

### 11.3 Coverage under pressure

A pure global top-score fill can starve a required context family. Task profiles may therefore reserve bounded quotas or minimum slots for load-bearing families such as on-cast identity, current relationship state, continuity facts, or due promises. Such coverage rules must be explicit, deterministic, traceable, and Bench-tested.

Multi-level `story.summary` Entries provide graceful compression: when detailed history cannot fit, the profile may prefer an appropriate coarser canonical summary. Retrieval does not generate that summary on demand.

## 12. Context Assembly and PromptBlock conversion

Retrieval selects knowledge; Context Assembly builds the final prompt. They must remain separate.

The adapter from a selected Entry to a PromptBlock (or equivalent substrate block) must:

- preserve Entry identity and provenance in trace metadata;
- map Entry content without inventing new facts;
- derive block kind/role and initial assembly priority from governed type/task policy;
- carry an estimated/actual token count and truncatability policy;
- keep selected order stable within the applicable context layer;
- make inclusion, trimming, and dropping auditable.

Retrieval priority and PromptBlock drop priority are related but not identical: retrieval decides which knowledge enters the candidate context; Context Assembly decides how all prompt material fits after system/user/history blocks are included. Context Assembly remains the final authority on the whole-prompt invariant and provider-neutral `messages[]`.

Token accounting has three explicit responsibility boundaries:

1. `retrieve()` estimates Entry `content` only and selects whole Entries within the knowledge budget.
2. the Entry-to-PromptBlock bridge re-estimates the complete rendered block text, including its compact label, and excludes only whole blocks when its assembly budget is exceeded;
3. the final PromptEngine/BudgetManager applies the model-context allocation and provider/tokenizer safety margin across every prompt source.

Retrieval exclusions (including orphan, retrieval-budget, and limit rejection) remain in the retrieval trace. Rendered-block budget exclusions are recorded separately as Context Assembly exclusions, so a consumer can identify which stage rejected an Entry without re-running retrieval.

## 13. Relationships with existing subsystems

### 13.1 MemoryEngine

The existing chat MemoryEngine provides the reusable pattern: keyword candidate search, a blend of relevance/recency/priority, and selection within a budget. Store-wide retrieval should reuse that reasoning and, where code quality permits, small pure utilities.

It must not reuse the chat-specific data boundary as the Store boundary. MemoryEngine retrieves `Memory` for one chat session and manages rolling summaries; Store retrieval retrieves Entries across explicitly reachable Store scopes and never summarizes. The two results meet only in Context Assembly as separate blocks.

### 13.2 Story Bible

The Story Bible is the work-scoped canonical Entry view, not a separate retriever. Store retrieval selects relevant Bible facts, knowledge state, promises, relationships, and summaries through the same function used for DNA and preferences. Proposed Bible updates are excluded from generation until reviewed.

### 13.3 Character Chat

Character Chat uses Store retrieval for shared character/world/work/relationship canon and uses MemoryEngine for private conversational memory. The caller must provide an explicit work when work canon is desired; chat must not guess among works. A bookmarked private line crosses into the Store only as a proposed Entry through the review gate.

### 13.4 Writer and Analyst

Writer stages declare their situation and task profile, then consume retrieval output through Context Assembly. They do not implement their own ranking. The Analyst may use Store retrieval to obtain supporting canon, but extraction remains text-to-proposals and cannot turn retrieval into a canon write path.

## 14. Embedding adoption gate

Phase 1 is keyword/type-weight/relevance/recency/priority retrieval with no embedding model and no vector database.

Embeddings may be added only when all conditions hold:

1. Bench fixtures contain representative keyword-miss cases, including Korean paraphrase/synonym cases;
2. the current keyword policy is tuned and still fails recall in a repeatable way;
3. an embedding-assisted candidate or relevance signal materially improves downstream quality or retrieval recall without unacceptable latency/cost;
4. the path remains local/cheap enough to preserve the project's operating constraints;
5. the implementation sits behind this same `retrieve()` seam and falls back deterministically to keyword retrieval;
6. any schema/index change is additive and covered by a separate ADR/RFC/migration.

Embeddings augment candidate generation or relevance scoring. They do not create a second Store, a reference-only RAG, or a chat-only vector path.

## 15. Testing strategy

### 15.1 Unit and contract tests

The implementation PR must test:

- owner isolation and cross-owner anchor/subject rejection;
- scope reachability for user/collection/work/character/world and the chat-private no-Entry boundary;
- default canon-only behavior and explicit review-history status queries;
- type/subject filters and as-of exclusion;
- keyword normalization and relevance monotonicity;
- type, recency, priority, confidence, and exemplar precedence in appropriate task profiles;
- deterministic tie-breaking and duplicate elimination;
- superseded/deleted Entry exclusion and soft-deleted/missing scope or subject anchor exclusion;
- whole-Entry budget fitting, oversize skipping, and total tokens never exceeding budget;
- Entry-to-PromptBlock trace preservation without prompt execution.

### 15.2 Property tests

Useful invariants include:

- no returned Entry belongs to another owner or an unreachable scope;
- default results contain only active canon;
- default results contain no Entry with a soft-deleted, missing, or owner-invisible scope/subject anchor;
- selected token estimate is always `<= budget`;
- the same fixed inputs always produce the same ordered IDs;
- adding an ineligible Entry cannot change results;
- increasing a candidate's relevance/priority within fixed filters cannot lower it below an otherwise identical candidate;
- superseding canon removes the old Entry and admits the replacement only after approval.

### 15.3 Integration and Bench tests

Use frozen Entry snapshots for a work scene, continuity check, and character chat. Verify selected IDs, score trace, PromptBlock conversion, and downstream context budget accounting. Bench cases should specifically measure fact recall, premature-knowledge prevention, due-promise recall, voice exemplar coverage, and Korean keyword misses.

Every ranking-policy change and any embedding proposal is Bench-gated.

## 16. Open questions and intentional deferrals

1. Exact normalized ranking weights and whether composition is additive or multiplicative remain Bench-tuned implementation choices.
2. Korean tokenization may begin with Unicode-normalized substring/token overlap; whether a morphological analyzer earns its cost is deferred.
3. Coverage quotas versus pure global ranking require Bench evidence; the contract permits explicit task profiles but does not choose values.
4. The authoritative token estimator and safety margin remain Prompt/Provider substrate decisions.
5. Cache shape and invalidation are deferred; caches must include owner, request, Entry snapshot/version, tokenizer, and policy identity.
6. How `as-of position` maps across chapter, scene, and chat time needs the persistence/Story Bible implementation contract.
7. Whether contradictory canonical Entries receive conflict-aware ranking is deferred; retrieval must not silently merge them.
8. The migration point at which the legacy LoreScanner is disabled must be coordinated with compatibility tests; two authoritative retrieval paths must not remain indefinitely.

## 17. Acceptance criteria for the implementation PR

The later Store retrieval implementation conforms only if it demonstrates:

- one owner-safe retrieval seam over the Entry Store;
- the full input/output contract, including scope/cast/location/beat/budget/type/subject/status;
- deterministic keyword-first ranking with traceable factors and exemplar precedence;
- whole-Entry budget selection and Context Assembly separation;
- Story Bible and Character Chat shared-knowledge use without folding chat-private Memory into Entries;
- no embedding/vector infrastructure before a Bench-proven miss;
- no second lore/reference/chat retrieval subsystem.

---

*End of RFC-003.*
