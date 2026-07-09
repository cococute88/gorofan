# ADR-002: Store / Analyst / Writer (+ Bench) Architecture

- **Status:** Accepted (revised v2) — *now the primary structural decision, aligned with `architecture-final-minimal.md`*
- **Date:** 2026-07-09 (v1) · revised 2026-07-09 (v2)
- **Deciders:** Architecture Review Board
- **Related:** ADR-001, ADR-003, ADR-004, ADR-005, ADR-008, ADR-012

## 1. Context

v1 adopted Store/Analyst/Writer as loose *logical roles* over the existing engines, and — wary of a "God Store" — insisted the Store stay plural (per-aggregate repositories) and rejected a single Entry model. `architecture-final-minimal.md` sharpens the triad into three concrete services with precise definitions, adds a fourth **Bench**, and argues that the Store should in fact be **one Entry model + one retrieve function**. This forces the Board to re-adjudicate its own God-Object caution.

The reviews' core claim: the whole creative system has exactly **three verbs** — *store, extract, write* — and **one honesty mechanism** — *bench*. Everything else (Story Bible Engine, Planning Engine, Serialization Engine, Relationship Planner, Foreshadow Scheduler, six DNA/libraries) is a **noun** that dissolves into an entry `type`, a prompt stage, or a check.

## 2. Decision

**Adopt Store / Analyst / Writer as three real logical services in the monolith, plus a dev-only Bench. Redefine each per `architecture-final-minimal.md`, and reconcile the God-Object concern rather than using it to reject the single Entry model.**

| Service | Definition (authoritative) | Realized as | Detailed in |
|---------|---------------------------|-------------|-------------|
| **Store** | One prose-first **Entry** model + one `retrieve(scope, cast, location, beat, budget) → entries` function. It *is* the Story Bible, all six DNA/libraries, and all ledgers. | One Entry table (typed by `type`) + a ~100-line retrieval function generalizing the existing MemoryEngine rank/budget pattern. | ADR-003, ADR-004, ADR-018 |
| **Analyst** | One extractor: **text in → entries out.** Same service for reference analysis (`scope=collection`), chapter ingestion (`scope=work`), and edit-diff distillation (`input=diffs`). A facet = one prompt file. | One extraction service + job queue; facets are prompt files. | ADR-008, ADR-010 |
| **Writer** | One loop runner executing a **declarative stage list**: retrieve → assemble → generate → validate → revise → persist. Planning, drafting, critics, episode assembly, style pass are **stages, not engines**. | One loop runner + pipeline definitions (stages-as-data) + prompt files per stage. | ADR-005, ADR-020 |
| **Bench** | Dev-only harness: golden scenes + the Writer's checks run as metrics; A/B any prompt/stage/retrieval change. | Runner script + fixtures; reuses Writer checks. | ADR-012 |

**Reconciling the God-Object concern (the crux the Board owed an honest answer to):**
- v1 rejected a "God Store." The Board now distinguishes two things it had conflated: a **God-Object *class*** (one omniscient code object every feature imports and every change edits) vs. a **unified *data shape*** (one Entry table with a `type` discriminator + prose `content` + optional `data` JSON).
- The reviews propose the **latter**, not the former. A single discriminated Entry *table* accessed through one small `retrieve()` function is **not** a God facade class — the alternative (10 tables, 10 editors, 10 retrieval paths) is the true maintenance bomb. The Board therefore **accepts the single Entry model** (ADR-003) and **retains only the guardrail that matters**: there is no monolithic "Store" facade *class*; there is a data model + a retrieval function + typed access, and `type` is a governed closed vocabulary.
- The one-way discipline from v1 stands and is reinforced: **the model reads the Store freely; it writes to canon only through review** (proposed entries = Review Cards, ADR-011). Analyst emits proposed entries; the Writer never silently mutates canon.

## 3. Alternatives Considered

- **A. v1's loose roles over the existing engines** (Store = per-aggregate repos; Analyst = Memory+Prompt; Writer = Chat+Novel).
- **B. Keep the many named engines** (Story Bible / Planning / Serialization / Relationship / Foreshadow / DNA libraries) as first-class modules.
- **C. Three deployable services** (Store/Analyst/Writer as separate processes).
- **D. Adopt the triad but reject the single Entry model** (keep v1's "Store is plural, many typed tables").

## 4. Why Rejected

- **A — Loose roles / old mapping:** Superseded. The reviews give sharper, better definitions (Store = data+retrieval, Analyst = one extractor with three inputs, Writer = one loop over declarative stages) that eliminate the engine-per-capability sprawl. Rejected in favor of the concrete triad.
- **B — Many named engines:** This is the two-year debt bomb (`architecture-final-minimal.md` §2/§3/§6): each noun is a service you operate, an editor you maintain, a migration you write. Their *capabilities* survive as entry types + prompt stages + checks. Rejected as structure.
- **C — Separate processes:** Same microservice cost as ADR-001 with zero scaling benefit for one user; also blurs data ownership (Store owns all state; Analyst/Writer are stateless transformers). Rejected.
- **D — Triad without single Entry model:** This was v1's position. On re-examination, the God-Object objection targets a *class*, not a *table*; the many-typed-tables alternative is more complex and less flexible (a new library needs a migration instead of a `type` string). The Board reverses its v1 caution here. Rejected in favor of the single Entry model (ADR-003).

## 5. Consequences

**Positive**
- A tiny, memorable object graph: three verbs + one harness. New capability = new entry type / new prompt stage / new check — not a new service.
- The riskiest AI operation (writing to canon) is governed by one rule: *read freely, write only via review*.
- Store/Analyst/Writer are independently testable — Store is state, Analyst/Writer are stateless given inputs.

**Negative**
- The Writer loop-runner + declarative stages is a real (if small) piece of infrastructure to get right once; a sloppy stage contract would leak complexity back.
- "Store = one Entry model" concentrates schema risk in one table (mitigated by the promote-a-type-to-a-table valve, ADR-003 §6).
- The triad vocabulary coexists with substrate names (PromptEngine, chat engine); the mapping table above must stay authoritative.

**Future risks**
- The Analyst accreting stateful caches/indexes (embeddings later) could drift toward its own subsystem; keep it stateless-over-explicit-inputs (ADR-008).
- Pressure to let the Writer auto-commit canon "for convenience" recurs; forbidden (ADR-011).

## 6. Future Revisit Conditions

- If one Entry `type` needs heavy deterministic structure, promote it to a dedicated table (ADR-003 §6) — the triad is unaffected.
- If Analyst extraction becomes genuinely stateful (persistent embedding indexes), revisit whether it earns its own store, re-running the God-Object analysis.
- If profiling shows retrieve→assemble→validate is a latency bottleneck, cache inside the Store/Analyst boundary without collapsing the roles.
