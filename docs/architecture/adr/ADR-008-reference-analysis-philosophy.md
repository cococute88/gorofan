# ADR-008: Reference Analysis & the Analyst (One Extractor, Three Inputs)

- **Status:** Accepted (revised v2 — **substantially reversed**: reference analysis is now a central pillar, not a peripheral feature)
- **Date:** 2026-07-09 (v1) · revised 2026-07-09 (v2)
- **Deciders:** Architecture Review Board
- **Related:** ADR-002, ADR-003, ADR-004, ADR-009, ADR-010, ADR-018

## 1. Context

v1 treated reference analysis as a *peripheral* "write in this style" feature — on-demand style distillation into a reusable entry — and **rejected** any standing reference pipeline. That judgment was made on a thinner understanding of the product. Both Fable reviews make clear that **reference-derived DNA is the product's core creative input**: *"reference-derived DNA instead of hand-filled forms"* is named the architecture's leading strength (`design-review` §0). The Analyst's reference path (facet-pass extraction, R1) feeds *everything* downstream — Character DNA, World DNA, Style Profile, Emotion/Plot/Dialogue libraries, exemplars.

Crucially, `architecture-final-minimal.md` §4 shows the three "learning" mechanisms the reviews describe — Reference Intelligence (R1), Bible auto-ingestion (R4), and edit-diff distillation (R25) — are **the same operation**: *text in → entries out*, differing only by input and scope. That collapses to **one Analyst service**. And it stays simple: extraction is **facet prompt files**, retrieval is **keyword-first**, with embeddings deferred until the Bench proves keyword misses.

So the Board reverses v1: reference analysis is central. But two v1 guardrails are *kept and shared by the reviews*: **provenance is non-negotiable**, and **no premature embedding/vector infrastructure**.

## 2. Decision

**Adopt the Analyst as one extractor with three inputs. Reference analysis is a first-class, standing capability that produces provenanced Store entries via facet prompt files. Keep keyword retrieval; defer embeddings; keep copyright discipline.**

1. **One Analyst service — text in → entries out** (`architecture-final-minimal.md` §4):

   | Input | Scope | Facets | Output entries |
   |-------|-------|--------|----------------|
   | Uploaded reference | `collection` | the §2 signal catalog | `character.*`, `world.*`, `style.*`, `emotion.*`, `plot.*` — status `canon`, provenanced |
   | Accepted chapter | `work` | facts, knowledge, promises, relationship, summary | ledger entries — status `proposed` (Review Cards, ADR-004/011) |
   | Accumulated edit diffs | `work`→`user` | style deltas, per-character voice fixes | `preference` entries injected into future prompts (ADR-010) |

2. **A facet = one prompt file** (ADR-013). The §2 signal catalog (voice, prose style, emotion repertoire, chapter-ending taxonomy, naming morphology, contradiction pairs, 사이다/고구마 rhythm, etc.) is *"a prompt library, now explicitly that"* — not an architecture.
3. **Provenance + confidence are mandatory** on every extracted entry (`design-review` §2, R1): source excerpt + confidence power the "why does the AI think this?" popover (ADR-014) and let low-confidence attributes be hidden rather than shown as noise.
4. **Exemplar retrieval at generation time (R14):** for each scene, the Writer's retrieve step pulls scene-type-matched reference excerpts (`character.exemplar`, scene-typed via `data`) and injects them as *"imitate the manner, never the content."* Description + exemplar together beat either alone.
5. **Keyword retrieval first; embeddings deferred** (shared with ADR-018): add embeddings only when keyword retrieval demonstrably misses, measured on the Bench — one shared `Retriever` seam, never a parallel reference-RAG.
6. **Copyright/provenance discipline retained:** the Store holds *distilled, provenanced guidance* the user uploaded/owns, and the QA gate screens for verbatim leakage from exemplars into output (`design-review` R14 guardrail). No echoing of reference text into output.
7. **Cross-reference handling stays minimal:** MVP = frequency-weighted merge with provenance; genuine conflicts keep both entries and retrieval prefers higher confidence. **R2 reconciliation engine and R3 genre-baseline-delta storage are deleted** (`architecture-final-minimal.md` §4 self-correction) — store absolutes; "what's distinctive" is a *future Analyst facet*, not a storage format.
8. **Still rejected:** fine-tuning on references (opaque, provider-locking, non-portable — ADR-010); a bespoke second retrieval system; storing/echoing third-party corpora verbatim.

## 3. Alternatives Considered

- **A. v1's peripheral on-demand style distillation only** (no standing reference pipeline).
- **B. Reference RAG / vector store from day one.**
- **C. Fine-tuning on reference corpora.**
- **D. Full R2 reconciliation + R3 baseline-delta storage.**

## 4. Why Rejected

- **A — Peripheral only:** Under-valued the product. Reference-derived DNA is the leading strength both reviews identify; treating it as a side feature would gut the value proposition. Reversed.
- **B — Vector RAG day one:** Premature infrastructure and non-zero cost; keyword + priority retrieval over provenanced entries performs well at personal scale, and embeddings should be Bench-gated (ADR-018). Rejected now; kept as a deferred shared seam.
- **C — Fine-tuning:** Opaque, provider-locking, non-portable, expensive — against every founding principle (ADR-010). Rejected.
- **D — R2/R3 machinery:** `architecture-final-minimal.md` retracts both as premature cleverness (designing storage around a speculative future analysis). Rejected — absolutes + provenance suffice; distinctiveness is a later facet.

## 5. Consequences

**Positive**
- The product's core input (reference → DNA) is first-class, yet implemented as *prompt files + entries* — the cheap evolution surface (ADR-001/015).
- One Analyst service covers reference analysis, chapter ingestion, and preference distillation — no three parallel learning systems.
- Provenance makes DNA trustworthy and enables the trust-without-configuration UI (ADR-014); exemplar retrieval directly lifts prose quality.
- No vector infrastructure, minimal copyright exposure.

**Negative**
- Facet extraction quality is model-dependent; a weak/local analyzer yields vaguer DNA (and noisier proposals for the ledger path).
- Keyword retrieval has a semantic-recall ceiling (shared with ADR-018).
- Reference upload + analysis is a real pipeline (segment → classify → facet extract → aggregate → dedupe) to build, though it is prompt-and-job code, not new services.

**Future risks**
- Users wanting "train on my favorite novels" will pull toward corpus ingestion/fine-tuning; this ADR is the guardrail (provenanced distillation, not corpus echo).
- If reference retrieval is later validated, it must reuse the shared `Retriever` seam, not spawn a second RAG.

## 6. Future Revisit Conditions

- Adopt embeddings for reference/exemplar retrieval only when the Bench shows keyword recall limits quality *and* a local/cheap embedding path preserves Zero-Cost — via the shared seam (ADR-018).
- Add a genre-baseline-delta *facet* (not storage format) if "what's distinctive about this author" becomes a real need (revisiting the deleted R3 as analysis, not schema).
- Revisit reconciliation only if frequency-weighted merge + provenance proves insufficient for multi-reference collections.
