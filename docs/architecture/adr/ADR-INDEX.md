# Architecture Decision Records — Index

**Project:** AI Native Creative Workspace (`ai-creative-workspace` / "gorofan") — "나만의 로판AI + 하트픽션"
**Status of this set:** Accepted — **v2** (re-evaluated against the two Fable architecture reviews)
**Date:** 2026-07-09
**Author:** Architecture Review Board / Chief Software Architect

This directory is the project's **architectural constitution**. Every future RFC and implementation MUST conform to these ADRs. Points marked **"Needs Validation"** must not be treated as decided.

---

## Provenance (v2)

The two architecture reviews that v1 could not find now exist and are treated as **primary inputs**:

- `docs/design-review-ai-author-os.md` — the **R1–R26** review: a comprehensive *map of the creative-quality space* (reference intelligence, Story Bible ledgers, scene/episode units, drafting loop, learning loop).
- `docs/architecture-final-minimal.md` — the **Final Minimal Architecture**: a blank-page redesign that *deliberately overrules* parts of R1–R26, collapsing everything into **Store / Analyst / Writer + Bench**, one prose-first **Entry** model, and creative logic living in **prompt files + entry types**.

Both are treated as the work of a senior peer architect — **engaged with, not rubber-stamped.** Where the Board agrees, partially agrees, or disagrees is stated explicitly per ADR and summarized below. The prior source of truth (`.kiro/specs/.../design.md`) is retained as the **substrate** design; where the Fable reviews' later, deliberate redesign conflicts with it (data model, prompt storage, generation unit, feed-forward pipeline), **the reviews win**, with migration paths recorded (ADR-017).

---

## Decision Summary (v2)

| ADR | Title | Decision (one line) | v2 status |
|-----|-------|---------------------|-----------|
| [001](ADR-001-overall-architecture-philosophy.md) | Overall Architecture Philosophy | Layered monolith = **substrate + Store/Analyst/Writer + Bench**; governing rule: *code written once is code, behavior tuned weekly is a prompt file*. | **Changed** |
| [002](ADR-002-store-analyst-writer-architecture.md) | Store / Analyst / Writer (+ Bench) | Three logical services + dev Bench; redefined per the reviews; God-Object concern reconciled (single Entry *table* ≠ God *class*). | **Changed** |
| [003](ADR-003-entry-first-data-model.md) | Entry-first Data Model | **One prose-first `Entry` model** for all knowledge/DNA/ledgers; Character/World become thin containers. | **Changed (reversed)** |
| [004](ADR-004-living-story-bible.md) | Living Story Bible & Continuity Loop | Bible = work-scoped entries (fact/**knowledge-matrix**/promise/relationship/summary/tone); human-gated ingestion + contradiction gate. | **Changed (enriched; core validated)** |
| [005](ADR-005-writer-pipeline.md) | Writer Pipeline | **Loop runner + declarative stages**; draft→validate→revise with **exactly two ground-truth checks**; optimistic streaming. | **Changed (reversed from single-pass)** |
| [006](ADR-006-relationship-system.md) | Relationship System | Relationships = `relationship` entries + a planning stage + a check; graph deferred. | **Validated (aligned)** |
| [007](ADR-007-character-dna-philosophy.md) | Character DNA Philosophy | Prose + **exemplars-first**; five layers as prompt-org, not schema; axes & back-prop dropped. | **Changed (enriched; core validated)** |
| [008](ADR-008-reference-analysis-philosophy.md) | Reference Analysis & the Analyst | **Central pillar**: one extractor, three inputs; facet prompt files; provenance; keyword-first. | **Changed (reversed)** |
| [009](ADR-009-prompt-architecture-philosophy.md) | Prompt Architecture Philosophy | Block/budget/provider-neutral engine = substrate; now fed by `retrieve()` + driven by stages. | **Validated (aligned)** |
| [010](ADR-010-learning-system-philosophy.md) | Learning System Philosophy | No ML training; **capture edit diffs from day one**; distill later via an Analyst facet → `preference` entries. | **Changed (added capture; core validated)** |
| [011](ADR-011-review-card-ux.md) | Review Card UX | Universal human-gated write-path; a Review Card **is** an entry with `status=proposed`. | **Validated (converged)** |
| [012](ADR-012-bench-evaluation-system.md) | Bench Evaluation System | **Necessary** dev harness (was "maybe never"); reuses Writer checks; built step 4. | **Changed (upgraded)** |
| [013](ADR-013-prompt-files-vs-database.md) | Prompt Files vs Database | Prompt **bodies files-only**; DB-override tier dropped; users customize **inputs**, not bodies. | **Changed (hardened)** |
| [014](ADR-014-minimal-ui-philosophy.md) | Minimal UI Philosophy | Five UI patterns + 쓰기/바이블/서재 tabs; **chat kept first-class** (partial disagreement). | **Changed** |
| [015](ADR-015-future-expansion-principles.md) | Future Expansion Principles | Evolve via **prompts + entry `type`s**, not services + migrations; no per-library table ever. | **Changed (sharpened)** |
| [016](ADR-016-provider-adapter-vendor-neutrality.md) | Provider Adapter & Vendor Neutrality | Neutral `LLMProvider` seam; runtime swap; offline via Ollama. | **Unchanged (substrate)** |
| [017](ADR-017-persistence-and-db-swap-strategy.md) | Persistence & DB Swap Strategy | SQLite→Postgres swap etc. unchanged; schema Entry-centric + named debt migrations. | **Changed (schema note)** |
| [018](ADR-018-memory-and-retrieval-strategy.md) | Memory & Retrieval Strategy | **One `retrieve()` over the Store**; keyword-first, embeddings Bench-gated; multi-level summaries. | **Changed (unified; core validated)** |
| [019](ADR-019-modular-authentication.md) | Modular Authentication | Env-toggled auth; local no-login default; secure-by-requirement when exposed. | **Unchanged (substrate)** |
| [020](ADR-020-scene-unit-and-serialization.md) | Scene Unit & Serialization (회차) | **Scene = atomic unit**, episode = delivery unit; serialization = one stage + checks, not an engine. | **New** |

---

## v2 Change Report

### ADRs that CHANGED
- **ADR-001** — reframed around substrate + Store/Analyst/Writer + Bench and the "code-once vs prompt-weekly" governing rule.
- **ADR-002** — Store/Analyst/Writer redefined concretely (+ Bench); the God-Object objection reconciled and the single Entry model accepted.
- **ADR-003** — **reversed**: adopts one prose-first Entry model (v1 had rejected it as EAV); Character/World demoted to thin containers.
- **ADR-004** — enriched with the ledgers (fact, **knowledge matrix**, promise, relationship, multi-level summary, tone contract) and the continuity loop + contradiction gate; the human-gated-write core was validated.
- **ADR-005** — **reversed**: single-pass → a bounded draft→validate→revise loop with exactly two ground-truth checks; stages-as-data.
- **ADR-007** — enriched: exemplars-first, five layers as prompt-organization; adopted the reviews' self-correction dropping axes-as-schema and back-propagation.
- **ADR-008** — **reversed**: reference analysis promoted from peripheral feature to the central Analyst pillar (one extractor, three inputs); R2/R3 machinery deleted.
- **ADR-010** — added the urgent decision to **capture edit diffs from day one**; framed learning as a transparent Analyst facet (no ML training — core validated).
- **ADR-012** — **upgraded** the Bench from "optional, maybe never" to "necessary, built early."
- **ADR-013** — **hardened** to files-only prompt bodies; dropped v1's DB-override tier.
- **ADR-014** — adopted five UI patterns + 쓰기/바이블/서재 IA; **kept chat first-class** against the reviews' novel-tunneled demotion.
- **ADR-015** — sharpened to "evolve via prompts + entry types; no per-library tables."
- **ADR-017** — strategy unchanged; schema note added (Entry-centric + named two-year debt migrations).
- **ADR-018** — unified into one `retrieve()` over the whole Store; multi-level summaries; deleted the lorebook keyword-scanner as a second retrieval system.
- **ADR-009** — light: still substrate, now fed by `retrieve()` and driven by declarative stages.

### ADRs that were REMOVED
- **None.** Every v1 topic remained a valid decision. Several decisions were *reversed or hardened in place* (003, 005, 008, 012, 013) rather than deleted — the topic stays; the answer changed. This is recorded honestly rather than manufacturing deletions.

### ADRs that were ADDED
- **ADR-020 — Scene Unit & Serialization (회차).** Both reviews make the atomic generation unit the *scene* and the delivery unit the *episode*; serialization craft is a stage + checks, not an engine. Distinct and load-bearing → its own ADR.

### Decisions that remained UNCHANGED (validated)
- **ADR-016** (Provider Adapter) and **ADR-019** (Auth) — explicitly named substrate, kept verbatim.
- **ADR-011** (Review Cards), **ADR-006** (relationships-as-entries), **ADR-018 core** (keyword-first retrieval + background summarization), **ADR-009 core** (block/budget/neutral prompt engine), **ADR-004 core** (human-gated canon writes), **ADR-007 core** (prose over rigid schema), **ADR-010 core** (no ML training) — the Board's v1 positions that the reviews independently corroborated. Notably, v1 had **already** proposed Store/Analyst/Writer, Review Cards, prose-first character DNA, keyword-first retrieval, and human-gated canon — several of the reviews' central ideas — before the reviews were available.

### The single biggest architectural change
**From "engines + a feed-forward pipeline + a rich typed schema" to "three verbs (Store/Analyst/Writer) + a Bench, where all creative knowledge collapses into ONE prose-first Entry model and all creative *behavior* lives in versioned prompt files and declarative pipeline stages — and the pipeline is a set of closed LOOPS, not a line."**

In one sentence: **engines → three verbs + data + prompts; feed-forward → loops; chapter → scene; static config bible → living ledger.** The load-bearing shift is the governing rule that *the product evolves by commits to `prompts/` and new entry `type` strings, not by new services and migrations* — which in turn makes the **Bench** necessary (constantly-changing prompt files must be regression-measured) and makes the **one Entry model** viable (new libraries are `type` strings, not tables).

---

## Where the Board AGREES / PARTIALLY AGREES / DISAGREES with the two reviews

The reviews are strong and mostly right. Explicit positions:

**Agree (adopted with conviction):**
- **Store/Analyst/Writer + Bench** collapse (ADR-002); **one prose-first Entry model** for knowledge (ADR-003) — the Board *reversed its own v1 caution* here after concluding the God-Object objection targets a class, not a discriminated prose table.
- **Prompts in files, not DB** (ADR-013) — went further than v1's hybrid, to files-only; this also fixes a drift risk v1 itself flagged.
- **Scene as the generation unit + episode serialization as a stage** (ADR-020).
- **Living Bible with ledgers + human-gated ingestion + contradiction gate** (ADR-004); **Review Cards = proposed entries** (ADR-011).
- **Keyword-first retrieval, embeddings Bench-gated, one `retrieve()`** (ADR-018); **relationships/foreshadowing as entries + stages, not engines** (ADR-006).
- **Capture edit diffs day one; no ML training** (ADR-010).
- **Delete R2 reconciliation, R3 baseline-delta storage, R16 back-propagation, axes-as-schema** (ADR-007/008) — agreeing with `architecture-final-minimal.md`'s own self-corrections.

**Partially agree (adopted with a reservation):**
- **The drafting loop / critics (R12):** agree single-pass has a real ceiling and adopt a validate→revise loop — but hold the line at **exactly two ground-truth checks at launch**, per-scene, streamed (the *minimal* reading, matching `architecture-final-minimal.md` over R1–R26's fuller ensemble). More critics are Bench-gated (ADR-005).
- **The Bench:** agree it is **necessary — because** the architecture puts behavior in constantly-changing prompt files (a consequence, not a free-standing good); keep it strictly dev-only/zero-UI (ADR-012).
- **The one Entry model:** adopt it, but keep two guardrails the reviews underweight: a governed closed `type` vocabulary (no `misc`) and the explicit **promote-a-type-to-a-table** valve for when deterministic checks (knowledge matrix, timeline) strain prose-first `data` JSON (ADR-003 §6). The reviews themselves flag prose-first as the riskiest assumption; the Board keeps the escape hatch first-class.

**Disagree (declined or held):**
- **Demoting chat to a "voice gym" (R22 framing):** the Board **disagrees**. Character chat is half the product's identity (로판AI), not a subordinate calibration tool. The Board adopts the voice-gym *bookmark* as a bonus but keeps chat **first-class**, and refuses to silently resolve the chat-vs-authoring top-level IA — it is marked **Needs Validation** (ADR-014). The reviews' remit was novel-writing quality; that remit does not license removing chat as a peer capability.
- **Fine-tuning / preference-model "moat" (R25 read maximally):** the Board holds v1's line — no opaque ML; "learning" is transparent, injected `preference` entries (ADR-010). (The Final Minimal review agrees; the disagreement is only with the maximal reading of R25.)

---

## Open items marked "Needs Validation"

- **Bounded auto-accept** of high-precision AI canon proposals — ADR-004, ADR-011.
- **Per-scene generation cost** on very long works (does the draft→validate→revise loop stay affordable for a personal budget?) — ADR-005, ADR-020.
- **Chat's place in the top-level IA** (peer tab vs. nested) — ADR-014.
- **Embeddings/RAG** upgrade — ADR-008, ADR-018 (Bench-gated).
- **A third+ Writer critic** — ADR-005 (Bench-gated).
- **Prose-first `data` JSON durability** for knowledge-matrix/timeline math — ADR-003 §6.

---

## Conventions

- One decision per file: Context → Decision → Alternatives Considered → Why Rejected → Consequences (positive / negative / future risks) → Future Revisit Conditions.
- Filenames `ADR-NNN-kebab-title.md`; numbers are permanent. A reversed decision is recorded *in place* with a v2 status note (no renumbering).
- ADRs decide *what and why*, never *how*: no schemas, APIs, prompt text, or code — those belong to RFCs, which must conform to this set.

> Next step (not part of this deliverable): RFCs may now be written **against** these ADRs. Do not begin RFC writing here.
