# ADR-018: Memory & Retrieval Strategy (One retrieve() over the Store)

- **Status:** Accepted (revised v2 — **strongly validated**; unified into one `retrieve()` over the Entry store, multi-level summaries)
- **Date:** 2026-07-09 (v1) · revised 2026-07-09 (v2)
- **Deciders:** Architecture Review Board
- **Related:** ADR-002, ADR-003, ADR-004, ADR-008, ADR-009

## 1. Context

v1 adopted keyword-first retrieval + background summarization, with embeddings deferred behind a `Retriever` seam. Both reviews validate this precisely and unify it:

> `design-review` R5: *"scene-relevant retrieval … your MemoryEngine's rank-and-budget design is already the correct pattern — generalize it from chat memories to Bible entries."*
> `architecture-final-minimal.md` §2: *"one `retrieve(scope, cast, location, beat, budget) → entries` … rank by type-weight × relevance × recency, cut to token budget … ~100 lines, not an engine. Start with keyword ranking; add embeddings only when keyword retrieval demonstrably misses (measured on the Bench), not before."*

So v1's decision is corroborated, and two refinements are added: (1) the retrieval function is **one function over the whole Store** (Bible, DNA, ledgers, exemplars — not just chat memory); (2) summaries become **multi-granularity** entries (scene/chapter/arc/story-so-far), replacing the single `Chapter.summary`.

## 2. Decision

**Adopt a single `retrieve(scope, cast, location, beat, budget) → entries` function over the Entry store as the Store's core capability. Keep keyword-first ranking; defer embeddings behind the same seam, Bench-gated. Summaries are multi-level entries. Background, non-blocking summarization is retained.**

1. **One retrieval function for everything** (ADR-003): ranks Store entries by *type-weight × relevance × recency*, cut to token budget — the existing MemoryEngine rank/budget pattern generalized (~100 lines, not an engine). It serves chat memory, Bible facts, DNA, exemplars (ADR-008), and ledgers (ADR-004) uniformly.
2. **Keyword-first ranking; embeddings deferred, Bench-gated:** add an `EmbeddingRetriever` behind the same single seam **only** when keyword retrieval demonstrably misses, *measured on the Bench* (ADR-012) — never a parallel RAG (shared with ADR-008).
3. **Retrieval, not dumping** (R5): scene-relevant selection (on-stage cast, locations, due `promise`s, `knowledge` state) puts the *right* facts in budget — critical past chapter ~50 when the Bible exceeds any context window.
4. **Summaries are multi-granularity `summary` entries** (`data.level` = scene/chapter/arc/story-so-far), replacing the single `Chapter.summary` (ADR-004/017). Serialization needs summaries at multiple levels; one text field silently drops what a level needed.
5. **Background, non-blocking summarization** retained (BR-6, NFR-1): compress on threshold, isolated/retriable, force-summarize available. `Memory.cover_up_to_message_id` monotonic + real (Property 5).
6. **Chat `Memory` stays chat-private** (ADR-017 debt item 5): do not extend it toward novel context; shared knowledge (e.g. R22 chat-bookmark → exemplar) flows through **Entries**, not by widening the chat Memory table.

## 3. Alternatives Considered

- **A. Embedding/RAG from day one** (vector DB, embed everything).
- **B. Separate retrieval systems** for chat memory vs. Bible vs. references (the v1-era risk / lorebook keyword scanner).
- **C. No summarization / single-level summary only.**
- **D. Blocking summarization** at the turn boundary.

## 4. Why Rejected

- **A — RAG day one:** Premature cost/complexity; keyword + priority over provenanced entries performs well at personal scale; embeddings should be Bench-gated. Rejected now; kept as a deferred shared seam.
- **B — Separate retrieval systems:** Both reviews insist on *one* retrieval path; the `design.md` lorebook **keyword-trigger scanner** is explicitly deleted as a second retrieval system ("two retrieval systems is one too many," `architecture-final-minimal.md` §5). Rejected.
- **C — No / single-level summaries:** Guarantees context overflow on long-form and drops granularity serialization needs. Rejected — multi-level `summary` entries.
- **D — Blocking summarization:** Violates non-blocking principle (BR-6/NFR-1). Rejected.

## 5. Consequences

**Positive**
- One ~100-line retrieval function serves the entire product; a single place to tune ranking and later add embeddings.
- Long-form continuity (fact/knowledge/promise retrieval + multi-level summaries) without vector-DB cost/complexity.
- Deleting the lorebook keyword scanner removes a whole retrieval subsystem (simplification).

**Negative**
- Keyword ranking has a semantic-recall ceiling (synonyms/paraphrase) that embeddings would raise.
- Summary quality bounds long-range coherence; poor summaries degrade the next scene/chapter.
- Multi-level summaries add some Analyst work (produce them) and Store entries.

**Future risks**
- As a Bible grows large, keyword recall may degrade enough to justify embeddings — the Bench is the trigger.
- Summary-of-summaries drift over very long projects; may need periodic re-summarization.

## 6. Future Revisit Conditions

- Adopt the `EmbeddingRetriever` (single seam) when the Bench shows keyword recall limits quality *and* a local/cheap embedding path preserves Zero-Cost.
- Retune ranking weights (type-weight × relevance × recency) if retrieval surfaces the wrong entries (a Bench task).
- Revisit summarization strategy (hierarchical/re-summarization) if long-project coherence degrades.
