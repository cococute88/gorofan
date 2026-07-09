# ADR-008: Reference Analysis Philosophy

- **Status:** Accepted — *on-demand, opt-in style extraction into reusable Entries adopted; standing reference-ingestion/corpus pipeline rejected (**Needs Validation** for any future form)*
- **Date:** 2026-07-09
- **Deciders:** Architecture Review Board
- **Related:** ADR-002, ADR-003, ADR-009, ADR-010, ADR-012

## 1. Context

"Reference Analysis" is the Analyst capability (ADR-002) of learning from **reference material** — exemplar novels, a favorite author's style, a genre's conventions, or the user's own prior work — to guide new generation ("write in this style"). It is not present in `design.md` at all; it is a net-new "AI Author OS" ambition.

The design space:
- **Heavyweight:** ingest a corpus of reference texts, chunk + embed them, build a standing retrieval index, and continuously condition generation on retrieved exemplars (a RAG-over-references subsystem).
- **Lightweight:** on demand, ask a model to distill a short **style guide** from a sample the user provides, store it as a reusable Entry, and inject it like any other Bible content.

For a personal, zero-cost, single-user product, corpus ingestion raises immediate concerns: storage and embedding cost, a second retrieval system, and — critically — **copyright/provenance** exposure if third-party texts are ingested wholesale and echoed into output.

## 2. Decision

**Adopt reference analysis as an on-demand, opt-in distillation into reusable `kind:"style"` Entries. Reject any standing reference-ingestion / corpus-embedding subsystem in the base architecture.**

1. **Style-as-Entry:** The user supplies a sample (a passage, a description of a target style). A one-shot analysis call distills it into a compact, human-readable **style Entry** (tone, pacing, diction, POV, sentence rhythm) stored in the Bible with provenance and injected via the ordinary Analyst path (ADR-009).
2. **No corpus ingestion, no reference embedding index** in the base build. There is no background pipeline that eats books.
3. **Human-in-the-loop:** the distilled style Entry is a Review Card proposal (ADR-011) — the user edits/accepts it. It is transparent text, not an opaque model artifact.
4. **Copyright discipline:** the system stores *distilled guidance* (a style description the user authored/approved), not verbatim third-party corpora, and never reproduces reference text into output. This keeps the personal tool clear of storing/echoing others' copyrighted work.
5. **RAG-over-references is a future, validated option only**, riding the same `Retriever` seam reserved for memory RAG (FUT-2) — never a bespoke second system.

## 3. Alternatives Considered

- **A. Standing reference corpus + RAG** — ingest many reference works, embed, retrieve exemplar passages per generation.
- **B. Fine-tuning on reference style** — train/adapt a model on reference texts.
- **C. No reference analysis at all** — rely solely on the character/style prose the user writes by hand.
- **D. Inline few-shot from raw references** — paste raw reference passages directly into every prompt as examples.

## 4. Why Rejected

- **A — Corpus + RAG subsystem:** A whole second retrieval system (ingestion, chunking, embeddings, vector store, sync) — heavy for one user, non-zero cost, and it front-runs the memory-RAG decision (FUT-2) with a parallel implementation. Plus corpus storage of third-party works raises copyright exposure. Rejected as base architecture; permitted later only through the *shared* Retriever seam after validation.
- **B — Fine-tuning:** Expensive, slow, provider-locking, non-portable, and opaque/uneditable — everything the product's transparent, provider-neutral ethos opposes (see ADR-010). Rejected.
- **C — Nothing:** Leaves a real, valuable capability (imitate a target style) entirely to manual prose. Given how cheaply a one-shot distillation delivers most of the value, doing nothing is under-ambitious. Rejected.
- **D — Raw passages inline every prompt:** Burns token budget on every generation, risks reproducing copyrighted text into output, and bloats prompts unpredictably. A distilled style Entry captures the essence far more cheaply. Rejected.

## 5. Consequences

**Positive**
- Delivers ~most of the "write in this style" value at near-zero standing cost and complexity.
- Style guidance is transparent, editable text (an Entry) — inspectable and reusable across works.
- No second retrieval system, no corpus storage, minimal copyright exposure.
- Rides existing seams (Entry model, Analyst injection, Review Card).

**Negative**
- A distilled style guide is lossier than retrieving actual exemplar passages; very fine stylistic mimicry may be weaker than a full RAG approach could achieve.
- Quality of distillation depends on the analyzing model; a weak/local model yields a vaguer style Entry.

**Future risks**
- Users may want to "train on my 10 favorite novels"; resisting the pull toward corpus ingestion (with its cost and copyright weight) will require pointing back to this ADR.
- If reference retrieval is later validated, it must reuse the memory Retriever seam rather than spawning a parallel system — otherwise the architecture accretes two RAGs.

## 6. Future Revisit Conditions

- **Validate reference RAG** only if: (a) style Entries prove insufficient for a real need, (b) a local/cheap embedding path exists (Zero-Cost preserved), and (c) copyright handling is clear (user-owned texts only, no echoing). Then implement via the shared `Retriever` seam.
- If distillation quality is the bottleneck, revisit prompt/model choice for the distillation step (a Bench task, ADR-012) before adding retrieval machinery.
- Reconsider fine-tuning only in the hypothetical future where cheap, local, portable adaptation exists — currently out of scope.
