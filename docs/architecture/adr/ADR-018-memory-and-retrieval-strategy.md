# ADR-018: Memory & Retrieval Strategy

- **Status:** Accepted — *keyword-first retrieval with background summarization; embedding/RAG deferred behind a shared `Retriever` seam*
- **Date:** 2026-07-09
- **Deciders:** Architecture Review Board
- **Related:** ADR-002, ADR-004, ADR-008, ADR-009, ADR-015

## 1. Context

Long-form chat and novels exceed any context window, so the system needs **memory**: compress old dialogue into long-term summaries/facts, and retrieve the relevant pieces per turn within budget. `design.md` §10 specifies a Memory Engine that summarizes over a token threshold (background, non-blocking), stores `Memory` entries (`summary|fact|event`), and retrieves via a `Retriever` Protocol — **keyword matching for MVP**, with an embedding retriever as a schema-non-breaking future upgrade (FUT-2).

The tempting default in AI apps is "add a vector database and RAG everything." For a single user with modest data, an always-on embedding pipeline is cost and complexity that keyword retrieval largely obviates — while the *seam* for RAG is cheap to keep.

## 2. Decision

**Adopt keyword-first retrieval + background summarization now; keep a single `Retriever` seam for a future embedding upgrade. This retrieval path is shared by memory, lore, and (future) reference analysis.**

1. **Summarize on threshold, in the background** (BR-6, AC-MEM-1/4): when unsummarized tokens exceed a threshold, compress older messages into long-term `Memory`; never block the interactive turn; failures are isolated and retriable (force-summarize available, AC-MEM-6).
2. **Retrieve by keyword + rank by recency/relevance/priority** within the token budget (AC-MEM-2, `design.md` §10.8–10.9). The Analyst injects the selected memories via the Prompt Engine (ADR-009).
3. **`Memory.cover_up_to_message_id` is monotonic and references a real message** (Property 5 / INV-5) — no dangling or overlapping summaries.
4. **One retrieval abstraction for all knowledge.** Memory, lore Entries, and future reference/style Entries are retrieved through the *same* `Retriever` contract over the Bible (ADR-002/003/004). This avoids parallel retrieval systems.
5. **Embedding/RAG is deferred** (ADR-015): the `Retriever` seam and a nullable embedding column (FUT-2) reserve the upgrade; the `EmbeddingRetriever` implementation is **not built** until a concrete need and a local/cheap embedding path exist (Zero-Cost).
6. **Summarization model is configurable** (dedicated summary `ModelConfig`, falling back to the chat model — AC-MEM-5), so a cheaper/faster model can do compaction.

## 3. Alternatives Considered

- **A. Embedding/RAG from day one** (vector DB, embed everything, semantic retrieval).
- **B. No summarization — full history until it overflows**, then hard-truncate.
- **C. Separate retrieval systems** for memory vs lore vs references.
- **D. Synchronous (blocking) summarization** at the turn boundary.

## 4. Why Rejected

- **A — RAG from day one:** A vector store + embedding pipeline is non-trivial cost/complexity and often over-kill at personal scale, where keyword + priority retrieval over a curated Bible performs well. It also front-runs a decision better made with real data. The seam is kept; the system is not. Rejected as MVP default (revisit per FUT-2).
- **B — No summarization:** Guarantees context overflow on exactly the long-form use case the product targets; hard truncation then silently drops story-critical history. Rejected.
- **C — Separate retrieval systems:** Duplicates the most reusable machinery and guarantees drift; a single `Retriever` over the Bible is simpler and upgrades once. Rejected (ties to ADR-008's insistence on one RAG, if any).
- **D — Blocking summarization:** Violates the non-blocking principle (BR-6, NFR-1); users would feel periodic stalls. Rejected.

## 5. Consequences

**Positive**
- Long-form continuity with zero vector-DB cost/complexity; keyword+priority retrieval is transparent and debuggable.
- Non-blocking summarization keeps the interactive path fast.
- One retrieval contract serves memory, lore, and future references; RAG upgrade is a drop-in behind the seam.

**Negative**
- Keyword retrieval misses semantic matches (synonyms, paraphrase) that embeddings would catch — a real recall ceiling.
- Summary quality bounds long-range coherence; a poor summary degrades future generation (and, for novels, the next continuation).
- Background jobs add mild complexity (in-process queue, idempotency, retry).

**Future risks**
- As a project's Bible/history grows large, keyword recall may degrade enough to justify embeddings; the trigger for FUT-2 must be watched.
- Summarization drift (compounding lossy summaries of summaries) over very long projects; may need periodic re-summarization strategy.

## 6. Future Revisit Conditions

- **Validate/adopt `EmbeddingRetriever`** when keyword recall demonstrably limits quality *and* a local/cheap embedding path preserves Zero-Cost/offline. Implement via the shared `Retriever` seam only.
- Revisit summarization strategy (hierarchical summaries, re-summarization) if long-project coherence degrades.
- Reassess ranking weights (recency/relevance/priority) if retrieval consistently surfaces the wrong memories (a Bench task, ADR-012).
