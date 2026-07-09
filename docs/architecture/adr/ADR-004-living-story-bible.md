# ADR-004: Living Story Bible

- **Status:** Accepted (with automatic canon mutation deferred — **Needs Validation**)
- **Date:** 2026-07-09
- **Deciders:** Architecture Review Board
- **Related:** ADR-002, ADR-003, ADR-006, ADR-010, ADR-011

## 1. Context

The product's differentiator is the **creative flywheel** (`design.md` §3.5): settings created in chat flow into the novel, and the novel's developments flow back into character memory and lore. The "Living Story Bible" is the name for the always-current, canonical body of knowledge that both chat and novel read from and (potentially) write to: **World + Lorebook/LoreEntry + Glossary + Memory + extracted facts/events/relationships**.

"Living" implies two things:
1. It is the **single read model** for all generation context (the Analyst reads it).
2. It **stays current** as the story progresses — new facts, relationships, and events accrue.

The architectural tension is entirely in #2: *who updates the canon, and how much of that is automatic?* An LLM that autonomously extracts "facts" and writes them into the source of truth will, over a long project, pollute the canon with hallucinations, duplicates, and contradictions — and because the same canon feeds future generation, errors compound. This is the single biggest long-term-quality risk in the whole product.

## 2. Decision

**Adopt the Living Story Bible as the unifying read model over World + Lore + Glossary + Memory + typed knowledge Entries (ADR-003), with a strict human-gated write path.**

1. **The Bible is a read model, not a new store.** It is a *view/assembly* over existing aggregates and the Entry tier (ADR-003), owned by the Store (ADR-002). It introduces no parallel database.
2. **Reads are free and automatic.** The Analyst (Prompt + Memory Engines) queries the Bible every turn: keyword-triggered lore injection, memory ranking, glossary, relevant facts — within the token budget (ADR-009).
3. **Writes to canon are human-gated by default.** AI-proposed additions/changes (extracted facts, inferred relationships, new glossary terms, chapter-derived events) enter the Bible **only** as *proposals* surfaced through the Review Card UX (ADR-011). The user accepts, edits, or rejects. Accepted proposals become canon Entries with provenance `user-approved`.
4. **Provenance is mandatory** (ADR-003): every Entry records whether it is user-authored, AI-proposed (pending), or AI-derived-and-approved. Generation context may be configured to include only approved canon, or approved + pending with a marker — but pending proposals never silently become authoritative.
5. **Automatic (unattended) canon mutation is explicitly deferred and marked _Needs Validation_.** The architecture *allows* a future "auto-accept high-confidence extractions" mode, but it is **not** part of the accepted design until validated against real long-project quality data.

## 3. Alternatives Considered

- **A. Fully automatic living bible** — the AI continuously extracts and writes facts/relationships/events into canon after every chat turn and chapter, no human gate.
- **B. Static bible** — the bible is only ever hand-authored; no AI extraction at all; the "flywheel" is manual copy-paste.
- **C. Separate canonical store + derived index** — a second database/graph that mirrors and enriches the canon (e.g. a knowledge graph) kept in sync.
- **D. Bible-as-one-document** — a single editable world document (see ADR-003 alt C).

## 4. Why Rejected

- **A — Fully automatic:** The compounding-hallucination risk described above. In a long novel (the explicit goal is *장편* / long-form), a small per-turn error rate integrates into a corrupted canon that then degrades every future generation. Unattended write-back to the source of truth is the highest-regret decision available; rejected for MVP and gated behind validation thereafter.
- **B — Static/manual:** Throws away the product's core differentiator (the flywheel). Manual copy-paste is exactly the "data scattered across tools" problem the product exists to solve. Rejected.
- **C — Separate enriched store (knowledge graph):** Real value someday, but it is a second source of truth to keep in sync, a second thing to back up, and a large complexity increase for a single user. It also front-runs ADR-006 (Relationship System), which deliberately stays lightweight. Rejected now; a *read-only projection* remains possible later without changing the canonical store.
- **D — One document:** Same reasons as ADR-003 alt C (conflicts, poor incremental review, awkward keyword injection).

## 5. Consequences

**Positive**
- Delivers the flywheel *safely*: the canon grows richer over time without silently rotting.
- One read model unifies chat and novel context assembly (less code, consistent behavior).
- Provenance + review gate means canon quality is auditable and reversible — essential for a multi-year project.

**Negative**
- The human gate adds friction: the user must periodically triage proposals. For a very active project this could become a chore (mitigated by batching and good Review Card UX — ADR-011).
- "Read-only view over aggregates + entries" assembly has a runtime cost per turn; caching (ADR-009 Prompt Cache) is relied upon to keep it cheap.

**Future risks**
- If proposal volume outpaces the user's willingness to triage, pending proposals pile up and the "living" promise weakens. This is the trigger to *validate* a bounded auto-accept mode — not to abandon the gate wholesale.
- Extraction quality is provider-dependent; a weak/local model may produce noisy proposals, raising triage burden.

## 6. Future Revisit Conditions

- **Validate auto-accept:** once real long-project data exists, measure AI-proposal precision. If precision on a well-defined subset (e.g. glossary terms, named-entity facts) is high enough that auto-accept doesn't degrade canon, revisit rule #5 to allow a *scoped, reversible* auto-accept with an audit log.
- If a genuine need for graph queries over relationships/events emerges (visualization, consistency checking), revisit alt C as a **derived, disposable projection** — never as a second source of truth.
- If per-turn Bible assembly becomes a latency problem beyond what caching solves, revisit the read-model materialization strategy.
