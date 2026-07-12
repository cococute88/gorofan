# RFC-002: Entry Model Contract

- **Status:** Draft
- **Date:** 2026-07-11
- **Author:** Chief Software Architect
- **Project:** AI Native Creative Workspace (`ai-creative-workspace` / "gorofan")
- **Conforms to:** RFC-001; ADR-002, ADR-003, ADR-004, ADR-006, ADR-007, ADR-008, ADR-010, ADR-011, ADR-014, ADR-015, ADR-017, ADR-018
- **Supersedes:** the conceptual-only Entry Store draft at this path
- **RFC layer:** Phase 1 implementation contract; implementation-neutral

> **Precedence.** The accepted ADRs govern. RFC-001 governs this RFC. The older `.kiro` specification is useful implementation history, but where it conflicts with the accepted ADRs, the ADRs win.
>
> **Contract, not implementation.** This document fixes the minimum semantics a later additive Entry Store implementation must preserve. It does not add a model, migration, API, repository, retrieval function, or UI.

---

## 1. Summary

An **Entry** is the single prose-first, typed, owned, scoped, provenanced, and reviewable unit of persisted creative knowledge. The Store consists of Entries and the one Store-wide retrieval capability defined in RFC-003.

This contract fixes:

- what is and is not an Entry;
- the minimum scope, subject, type, status, provenance, ownership, and supersession semantics;
- how Entries represent Character DNA, World DNA, Story Bible facts, and relationships;
- how Entry remains separate from chat-private `Memory`;
- the minimum candidate persistence shape and an additive migration path after the frozen Alembic `0001` baseline.

It deliberately leaves physical schema choices and API shapes to the implementation PR.

## 2. Motivation

The accepted architecture replaced parallel character, world, lore, style, relationship, and story-ledger stores with one discriminated knowledge model. Implementing that model without a prior contract would make the next migration guess at load-bearing semantics: whether a fact is true for a user or a work, how a relationship pair is identified, which statuses retrieval may trust, how corrections preserve history, and whether chat memory leaks into the Story Bible.

Those choices are expensive to reverse after rows exist. RFC-002 therefore freezes the smallest useful contract before DDL or repository code is written.

## 3. Non-goals

This RFC does not define or implement:

- SQLAlchemy models, columns, constraints, indexes, or Alembic code;
- request/response DTOs, routers, services, repositories, or review UI;
- a retrieval algorithm or concrete ranking weights (RFC-003);
- Analyst extraction, Writer behavior, Review Card rendering, or Bench fixtures;
- JSON schemas beyond the minimum semantic obligations below;
- a graph database, ontology, per-library table, or generic EAV system;
- migration or deletion of legacy data in this documentation change.

## 4. Core concept

### 4.1 What an Entry means

An Entry is **one independently reviewable assertion or piece of prompt-ready guidance** that is true within a declared scope. Its primary payload is prose written to be consumed by a model. Narrow structured data may accompany that prose only when a deterministic check needs it.

An Entry must be meaningful when read with its type, scope, subject, provenance, and status. It should not require reconstructing an object from an unbounded attribute bag.

### 4.2 What is not an Entry

The following remain typed aggregates or operational records and are not Entries:

- `User`, `Collection`, `Work`, `Chapter`, `ChatSession`, `Message`, `ModelConfig`, and other records with independent lifecycle invariants;
- transient scene plans, in-flight prompt context, model responses, and other operation-local working state;
- chat-private `Memory` summaries and recent-message state;
- prompt bodies, which remain versioned repository files;
- secrets, credentials, jobs, audit events, and review UI state.

An Entry is also not a per-attribute row, arbitrary user-defined schema, raw reference corpus, or replacement for aggregate identity.

### 4.3 Aggregate and Entry relationship

Aggregates establish identity, lifecycle, and ownership. Entries describe creative knowledge about or within them.

- `Character` and `World` remain thin containers. Their durable identity fields remain on the aggregate; their evolving creative detail becomes Entries.
- `Work` and `Collection` remain scope anchors, not Entries.
- `Chapter` remains the canonical authored document; summaries and extracted assertions about it may be Entries.
- Deleting or unlinking an aggregate must not silently reassign its Entries to another owner or scope.
- Soft-deleting an aggregate does not delete its Entries. Entry history and provenance remain available for audit, recovery, and an aggregate restore.
- Default Store retrieval must exclude an Entry when either its scope anchor or any required subject anchor is soft-deleted, missing, or otherwise orphaned. It must not infer a replacement anchor.
- Explicit audit, administration, or recovery tooling may opt into orphaned/soft-deleted-anchor Entries, but must label them as non-default history. The later `retrieve()` implementation owns this filter; this persistence-hardening change does not implement Store-wide retrieval.

## 5. Scope, subject, and ownership

### 5.1 Entry scope

`scope` answers **where this Entry is applicable or true**. Phase 1 must be able to express the following closed scope kinds:

| Scope kind | Meaning | Typical use |
|---|---|---|
| `user` | Portable knowledge owned by one user | author preferences and global notes |
| `collection` | Reusable knowledge derived from a curated reference collection | style guidance and reference-derived DNA |
| `work` | Canon or guidance belonging to one novel | Story Bible and story ledgers |
| `character` | Knowledge anchored to one Character container | identity, behavior, voice, exemplars |
| `world` | Knowledge anchored to one World container | rules, facts, terms, places |
| `chat-private` | Conversation-private memory boundary | reserved for interoperability with chat `Memory`; not an Entry persistence target in Phase 1 |

The scope representation must include a kind and, except for the implicit current `user`, an anchor identifier where applicable. It must reject impossible or cross-owner combinations.

`chat-private` is intentionally representable in retrieval and context contracts so callers cannot accidentally widen it. ADR-003 and ADR-018 still govern: Phase 1 chat-private memories remain in the existing `Memory` aggregate and **must not be stored as Entries**. A later ADR/RFC is required before that boundary changes.

### 5.2 Subject

`subject` answers **who or what the Entry is about** inside its scope. It is optional only when the type is genuinely scope-wide.

The contract requires a typed subject reference, not an ambiguous free-text identifier. Supported subject shapes must cover:

- one character;
- one world or location;
- one work, chapter, scene, or story thread;
- an unordered or role-labelled character pair for a relationship;
- no subject for scope-wide style, preference, summary, or note Entries.

The physical representation may use columns or bounded JSON. It must preserve subject kind and stable identifiers and must validate referenced ownership.

### 5.3 Ownership

Every Entry belongs to exactly one `user_id`, consistent with ADR-017. Ownership filtering is mandatory on every read and write.

All referenced scope anchors, subjects, provenance sources, and supersession targets must be visible to the same owner. Linking an Entry across users is invalid even if the referenced UUID exists. Ownership is immutable; moving knowledge between users is copy-with-new-provenance, not mutation.

## 6. Governed Entry type vocabulary

The Phase 1 vocabulary is closed. Values are architectural identifiers, not user input. There is no `misc` type. `note` is the explicit low-structure escape hatch and must still carry scope and provenance.

| Type | Meaning | Minimum subject expectation |
|---|---|---|
| `character.identity` | enduring core identity, values, contradiction pair | character |
| `character.behavior` | recurring behavior and decision patterns | character |
| `character.voice` | speech rules, never-says guidance, verbal manner | character |
| `character.exemplar` | concrete, approved example of voice or behavior | character |
| `world.fact` | setting rule, place fact, institution, constraint | world/location or scope-wide world |
| `world.term` | naming convention, glossary term, morphology | world or term subject |
| `story.fact` | established work-specific truth | work/chapter/scene subject as needed |
| `story.knowledge` | who knows what and since when | character plus work context |
| `story.promise` | planted setup, open thread, due window, payoff state | story thread/work |
| `story.summary` | scene/chapter/arc/story-so-far compression | summarized aggregate |
| `relationship.state` | current relationship stage and last justified transition | character pair |
| `style.preference` | prose/style guidance derived from references or work | collection/work/user |
| `user.preference` | transparent author preference distilled from edits or supplied directly | usually scope-wide |
| `note` | intentionally unstructured annotation that fits no stronger Phase 1 type | optional |

This vocabulary chooses namespaced forms for clarity while preserving ADR intent. Earlier architecture prose used shorthand such as `character.core`, `world.rule`, `fact`, `knowledge`, `promise`, `relationship`, `summary`, and `preference`; those are conceptual predecessors, not additional runtime aliases. The implementation PR must choose one canonical stored spelling and must not silently accept both.

Adding a type requires an RFC or ADR update, its validation rules, retrieval treatment, and a demonstrated use case. A new type does not justify a new table by itself.

## 7. Entry status and lifecycle

### 7.1 Status vocabulary

Phase 1 must support:

| Status | Meaning | Retrieval default |
|---|---|---|
| `captured` | persisted candidate awaiting proposal construction or explicit user disposition | excluded |
| `proposed` | complete candidate awaiting human review; mechanically a Review Card | excluded unless explicitly requested by review tooling |
| `canon` | human-authorized knowledge trusted by generation and checks | included |
| `rejected` | proposal explicitly declined | excluded |
| `superseded` | formerly canonical knowledge replaced by newer canon | excluded from current retrieval |

`captured` is the chosen Phase 1 name for the draft/capture state. It exists to preserve raw candidate intent without pretending it is review-ready. Producers may emit `proposed` directly when the candidate already satisfies validation.

### 7.2 Allowed transitions

The minimum state machine is:

```text
captured -> proposed
captured -> rejected
proposed -> canon
proposed -> rejected
canon -> superseded     (only when an approved replacement becomes canon)
```

Additional rules:

- Analyst and Writer extraction outputs create `proposed` Entries, as required by ADR-002 and RFC-008; they must not directly create `captured` or `canon` Entries. `captured` is limited to explicit user drafts, import staging, and lossless pre-analysis capture that is not yet an Analyst output.
- Explicit user-authored knowledge may become `canon` as part of the same intentional user action; the user action is the human gate.
- Curated reference import may use a documented batch approval, but the Analyst itself still never decides canon.
- Editing a proposed Entry before acceptance may update that proposal with audit metadata. Correcting existing canon creates a replacement proposal; it does not rewrite history in place.
- `rejected` and `superseded` are terminal for current truth. Undo creates an auditable new transition or replacement; it must not erase history.
- `relationship.state` and `story.summary` are Phase 1 single-current-value types. A direct `proposed -> canon` transition must fail when active canon already has the same owner, scope, type, and subject identity; the caller must use the atomic supersession path instead.
- Other Entry types retain their existing multiple-canon policy until their contracts explicitly classify them as single-current-value.

### 7.3 Review Card relationship

A Review Card is a presentation of an Entry with `status=proposed`, not a second model. Accept maps to `canon`; edit-then-accept records the reviewed content and human action; reject maps to `rejected`. Review UX may batch actions but must preserve per-Entry provenance and disposition.

## 8. Provenance and supersession

### 8.1 Provenance

Provenance is mandatory. It must answer, without inspecting application logs:

- what kind of source produced the Entry (`user`, `reference`, `chapter`, `chat-bookmark`, `edit-diff`, `import`, or bounded future value);
- which stable source record or external locator it came from, when one exists;
- where in that source the assertion came from (chapter/scene/message/range or equivalent locator);
- which actor or process captured it and when;
- whether the content was human-authored, AI-extracted, or human-edited after extraction.

The persistence shape may be normalized or bounded JSON. It must be portable across SQLite and PostgreSQL and must not require storing an entire copyrighted source excerpt. Provenance may point to a source and retain only the minimal excerpt needed for review.

### 8.2 Supersession

Supersession preserves history while identifying current truth.

- A replacement must have the same owner and a compatible scope/type/subject identity.
- The old canonical Entry becomes `superseded` only after the replacement becomes `canon`.
- The relationship must be acyclic and traceable in one direction at minimum (`superseded_by` or an equivalent version link).
- Current retrieval excludes superseded Entries by default; audit/history views may include them.
- Rejecting a proposed replacement leaves the old canon unchanged.
- Hard deletion must not be used as ordinary correction semantics.

### 8.3 Confidence

Confidence records how strongly an extracted assertion is supported; it is not a substitute for human authority or Entry status.

- AI-extracted Entries must use a documented finite scale and identify the producer that assigned the value.
- Explicit user-authored canon is authoritative because of the human action, not because it receives an artificially high model confidence.
- Missing confidence, and any future explicitly designated neutral confidence value, contributes neither a ranking bonus nor a ranking penalty. It is not equivalent to low confidence.
- Confidence may influence retrieval among otherwise comparable eligible Entries, but it cannot bypass ownership, scope, status, supersession, or Review Card rules.
- Confidence never decides whether an Entry is canon. Conflicting canon may coexist where a type permits it until a human supersedes one; confidence alone does not rewrite canon.

## 9. Domain representation contracts

### 9.1 Character DNA

Character DNA is a view over `character.*` Entries anchored to a Character aggregate. Identity, behavior, voice, and exemplars are separate types so retrieval can target them. The five-layer DNA concept remains an Analyst/card organization scheme, not columns, numeric axes, or tables.

Exemplars are first-class prompt-ready prose with provenance. A user-corrected line is stored as a new canonical `character.exemplar`; Phase 1 does not back-propagate that edit into inferred personality attributes.

### 9.2 World DNA

World DNA is a view over `world.fact` and `world.term` Entries anchored to a World or location. It replaces growth of free-text arrays and keyword-trigger LoreEntry behavior as the future canonical knowledge path. It does not remove legacy containers in this RFC.

### 9.3 Relationships

A relationship is `relationship.state` with a stable character-pair subject. Pair identity must be canonicalized so `(A, B)` and `(B, A)` cannot become accidental duplicates unless roles are semantically directional and explicitly represented. Prose describes chemistry and power balance; bounded structured data may hold the current stage and last transition for deterministic checks.

### 9.4 Story Bible

The Story Bible is the `work`-scoped canonical view of relevant `story.*`, `relationship.state`, world, character, and note Entries. It is not a table or service of its own. Chapter ingestion adds proposals; human review creates canon; supersession evolves truth without destroying history.

### 9.5 Chat-private Memory separation

Chat `Memory` remains conversation-private operational state. It may be ranked and budgeted by the existing MemoryEngine, but it does not become Story Bible canon and is not widened into the Entry Store.

Shared knowledge crosses the boundary only through an explicit action: for example, bookmarking a chat line proposes a `character.exemplar` with chat-message provenance. The original private conversation remains private; only the reviewed Entry joins shared retrieval.

## 10. Promote-to-Table escape valve

A type may be promoted to a dedicated structured model only when all of the following are true:

1. a deterministic consumer repeatedly performs complex parsing or graph/timeline reconstruction from Entry prose or bounded `data`;
2. the strain is demonstrated by production evidence or Bench fixtures, not anticipated;
3. a dedicated model materially improves integrity, queryability, or correctness;
4. Entry remains the compatibility/retrieval boundary during migration, or a replacement contract is approved;
5. an ADR records the new source of truth, migration, rollback, and ownership rules.

Likely pressure points are knowledge-state, promises, and timeline arithmetic. Their possibility is not permission to promote them in Phase 1.

## 11. Minimum persistence field candidates

The additive implementation RFC/PR should evaluate at least the following logical fields. Names and physical layout are not fixed here.

| Candidate | Contractual purpose |
|---|---|
| `id` | stable Entry identity |
| `user_id` | mandatory immutable owner |
| `scope_kind`, `scope_id` | applicability boundary and anchor |
| `type` | governed discriminator |
| `subject` | bounded typed subject reference(s) |
| `content` | non-empty prompt-ready prose |
| `data` | optional bounded structured facts used by deterministic consumers |
| `status` | lifecycle state |
| `provenance` | mandatory source and capture metadata |
| `confidence` | normalized confidence governed by §8.3; required for AI extraction and explicitly neutral or not-applicable for direct user authorship |
| `priority` | explicit bounded author/system importance hint, distinct from retrieval score |
| `superseded_by` | optional replacement link |
| `created_at`, `updated_at` | audit timestamps |
| `created_at_chapter` | optional story-order origin for work-scoped facts |
| `deleted_at` | optional soft-delete marker if existing persistence conventions require it |

Validation must not allow `data` to become an unbounded user-defined schema or a substitute for `content`.

## 12. Migration and compatibility strategy

### 12.1 Additive migration after frozen `0001`

The first Entry Store migration must be a new forward-only revision after the frozen Alembic `0001` baseline. It must not edit, replace, or regenerate `0001`.

The safe sequence is:

1. add the Entry structure and constraints additively;
2. ship typed writes behind a narrow service/repository boundary;
3. backfill or dual-read legacy Character, World, Lore, and Chapter summary data in bounded steps;
4. compare legacy and Entry projections with tests/Bench fixtures;
5. switch reads only after equivalence is demonstrated;
6. defer dropping legacy columns/tables and the keyword lore scanner to a separate, explicitly approved migration.

No migration is created or executed by this RFC PR.

### 12.2 Legacy compatibility

- `Character.personality` and `speech_style` remain legacy sources until converted to `character.identity`/`character.voice` Entries or rendered from them.
- `World` arrays, `Lorebook`/`LoreEntry`, and glossary data remain readable until converted to `world.fact`/`world.term`/`note` Entries.
- `Chapter.summary` may remain a cache until multi-level `story.summary` is authoritative.
- Chat `Memory` is not backfilled into Entries.
- Legacy APIs and UI must not be changed in the additive Entry Store PR unless separately scoped.
- Compatibility aliases for old conceptual type names must not become silently persisted duplicate vocabulary.

## 13. Validation contract

An Entry is valid only if:

- owner, scope, and subject references are present where required and share ownership;
- type and status are members of their governed vocabularies;
- `content` is non-empty after normalization;
- provenance satisfies the minimum source contract;
- type-specific scope/subject combinations are allowed;
- `confidence` and `priority`, when present, are within defined finite bounds;
- a supersession link is same-owner, compatible, non-self-referential, and acyclic;
- `canon -> superseded` is paired with an approved replacement;
- `chat-private` is not persisted as an Entry in Phase 1;
- rejected, superseded, deleted, or non-canon Entries cannot enter default generation retrieval.

Validation belongs at the application boundary and should be reinforced by portable database constraints where practical. SQLite/PostgreSQL portability takes precedence over dialect-specific cleverness.

## 14. Open questions and intentional deferrals

1. Whether `subject` is implemented as bounded JSON, join rows, or explicit nullable columns remains an implementation RFC decision.
2. Whether `confidence` is mandatory for user-authored canon, and its exact non-neutral scale, remains open; missing confidence is nevertheless ranking-neutral under §8.3.
3. Exact structured shapes for `story.knowledge`, `story.promise`, `relationship.state`, and summary levels are deferred to their consumer contracts.
4. Hard-delete and restore UX for thin aggregates remains a persistence RFC decision; default retrieval exclusion and Entry history retention are fixed by §4.3.
5. Direct curated-reference batch approval must be reconciled with the universal Review Card UX without weakening the human gate.
6. Classification of additional single-current-value types is deferred; Phase 1 fixes `relationship.state` and `story.summary` as single-current-value under §7.2.
7. The concrete migration revision identifier after `0001`, indexes, and uniqueness constraints are intentionally not fixed here.

## 15. Acceptance criteria for the implementation PR

The later Entry Store implementation conforms only if it demonstrates:

- the closed scope/type/status vocabularies and ownership checks;
- proposal/canon/rejected/superseded behavior and auditable replacement;
- chat-private Memory separation;
- additive migration lineage after immutable `0001`;
- no per-library table and no `misc` type;
- compatibility coverage for legacy Character/World/Lore/Chapter summary reads;
- Store-wide retrieval can consume the model through RFC-003 without type-specific repositories.

---

*End of RFC-002.*
