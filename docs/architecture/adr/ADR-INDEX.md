# Architecture Decision Records — Index

**Project:** AI Native Creative Workspace (`ai-creative-workspace`) — "나만의 로판AI + 하트픽션"
**Status of this set:** Accepted (v1)
**Date:** 2026-07-09
**Author:** Architecture Review Board / Chief Software Architect

This directory holds the project's **architectural constitution**. Every future RFC and implementation MUST conform to these ADRs. Where an ADR marks a point **"Needs Validation,"** an RFC must not assume the unvalidated option is decided.

---

## Provenance and Honesty Statement (read first)

The task brief instructed the Board to review three documents: the **Project Plan**, an **"AI Author OS Design Review (R1–R26)"**, and a **"Final Architecture Review (Minimal Architecture)."**

**Only the Project Plan exists in this repository.** The R1–R26 review and the Final Architecture Review documents are **not present** anywhere in the repo (verified across the working tree and git history). The concrete artifacts that do exist are:

- `AI_캐릭터챗_소설앱_프로젝트_계획서.md` — the Project Plan.
- `.kiro/specs/ai-creative-workspace/design.md` — a 4,948-line full technical design (Phases 1–16).
- `.kiro/specs/ai-creative-workspace/requirements.md` — EARS requirements derived from the design.
- `.kiro/specs/ai-creative-workspace/tasks.md` — implementation task breakdown.

Consequently:

1. These ADRs are grounded in the **Project Plan + `design.md` + `requirements.md`** and the **decision principles** in the task brief — not in the missing review documents.
2. Several mandated ADR topics use **"AI Author OS" vocabulary** (Store/Analyst/Writer, Entry-first, Character DNA, Reference Analysis, Learning System, Review Card, Bench) that has **no counterpart in `design.md`.** For each, the Board reconstructed the *intent* of the concept, evaluated it against the existing design and the decision principles, and recorded an honest decision — **including outright rejection or scoping-down** where the concept added complexity a personal-use product cannot justify.
3. Per the brief's instruction to prize **architectural honesty over completeness**, genuinely uncertain decisions are labeled **"Needs Validation"** rather than dressed up as settled.

If the R1–R26 and Final Architecture Review documents surface later, this set should be re-reconciled against them; nothing here assumes their contents.

---

## How these ADRs relate

- The **existing `design.md`** is a strong, detailed, somewhat "kitchen-sink" design. The Board **adopts its genuinely load-bearing decisions** (layered monolith, Prompt Engine, Provider Adapter, SQLite-swap, minimal UI, non-destructive expansion) and **challenges/scopes-down its more expansive or under-specified areas** (prompt storage, auto-updating canon, relationship/graph ambition), plus the net-new "AI Author OS" proposals.
- The unifying thesis: **build the simplest architecture that can survive for years as a single-maintainer, personal, zero-cost tool** — invest effort in AI/creative quality (Prompt Engine, Story Bible, character/novel quality), keep everything else boring, and let the model *read* freely but *write to canon only through human review.*

---

## Decision Summary

| ADR | Title | Decision (one line) | Notable rejection | Flags |
|-----|-------|---------------------|-------------------|-------|
| [001](ADR-001-overall-architecture-philosophy.md) | Overall Architecture Philosophy | Single-process **layered modular monolith**; personal/local-first; simplicity is the tie-breaker. | Microservices, event-bus, agent-framework-backbone, serverless. | Accepted |
| [002](ADR-002-store-analyst-writer-architecture.md) | Store / Analyst / Writer Architecture | Adopt as **logical roles** over the existing engines: model reads freely, writes canon only via review. | Separate services; a **God-Object "Store"** facade. | Accepted |
| [003](ADR-003-entry-first-data-model.md) | Entry-first Data Model | **Typed aggregates as backbone; entry-first only for the knowledge/Bible tier.** | Full **EAV / God-Table**; document-per-world. | Accepted (scoped) |
| [004](ADR-004-living-story-bible.md) | Living Story Bible | Unifying **read model** over World/Lore/Glossary/Memory/Entries; **human-gated** canon writes. | Fully-automatic self-mutating canon. | Accepted; auto-accept **Needs Validation** |
| [005](ADR-005-writer-pipeline.md) | Writer Pipeline | **Single-pass, streaming, deterministic** pipeline; Service persists, background summary. | Multi-agent draft/critique **by default**; non-streaming. | Accepted; multi-pass **Needs Validation** |
| [006](ADR-006-relationship-system.md) | Relationship System | Relationships as **typed Entries**; visualization is a deferred, feature-flagged projection. | Dedicated graph subsystem/graph DB in MVP. | Accepted |
| [007](ADR-007-character-dna-philosophy.md) | Character DNA Philosophy | **Prose + examples + tags**; consistency via injection, not a trait model. | OCEAN/stat-block/genome schemas; learned embeddings. | Accepted |
| [008](ADR-008-reference-analysis-philosophy.md) | Reference Analysis Philosophy | **On-demand style distillation into reusable Entries**; no corpus ingestion. | Standing reference-RAG; fine-tuning; raw passages inline. | Accepted; ref-RAG **Needs Validation** |
| [009](ADR-009-prompt-architecture-philosophy.md) | Prompt Architecture Philosophy | **Block-based, budgeted, provider-neutral** Prompt Engine is the mandatory single path. | Ad-hoc strings; frameworks; per-provider builders; send-everything. | Accepted (core) |
| [010](ADR-010-learning-system-philosophy.md) | Learning System Philosophy | "Learning" = **human-curated** growth of Bible/examples/prompts; **no ML training.** | Fine-tuning; implicit personalization; auto-applied preference vectors. | Accepted; automated learning **Needs Validation** |
| [011](ADR-011-review-card-ux.md) | Review Card UX | **The** human-in-the-loop gate for all AI-proposed canon changes; non-blocking, batchable, mobile-first. | Auto-apply+undo; blocking modals; per-feature ad-hoc UX. | Accepted |
| [012](ADR-012-bench-evaluation-system.md) | Bench Evaluation System | **Lightweight, offline, dev-facing** A/B bench; no in-product eval runtime. | Continuous in-product scoring; auto quality gates; full eval platform. | Accepted; **whether to build it** Needs Validation |
| [013](ADR-013-prompt-files-vs-database.md) | Prompt Files vs Database | **Hybrid:** base templates as **versioned files**, user overrides in DB, files as fallback. | `design.md`'s **DB-only** templates (un-diffable core logic). | Accepted (revises design) |
| [014](ADR-014-minimal-ui-philosophy.md) | Minimal UI Philosophy | Lock mobile-first, **fixed top-level nav**, 3-tap rule, progressive disclosure. | Feature-rich dashboard; desktop-first; organic nav growth. | Accepted |
| [015](ADR-015-future-expansion-principles.md) | Future Expansion Principles | Non-destructive, flag-gated, **define the seam / defer the second impl.** | Speculative up-front implementations; plugin marketplace now. | Accepted |
| [016](ADR-016-provider-adapter-vendor-neutrality.md) | Provider Adapter & Vendor Neutrality | Thin **neutral `LLMProvider`** seam; runtime swap via config; offline via Ollama. | Direct SDK calls; single hard-coded provider; gateway lock-in. | Accepted |
| [017](ADR-017-persistence-and-db-swap-strategy.md) | Persistence & DB Swap Strategy | **SQLite-first, ORM-only, Postgres-ready**; hybrid `user_id` scoping; soft-delete; encryption. | Postgres-from-day-one; NoSQL; raw SQL; uniform-`user_id`. | Accepted |
| [018](ADR-018-memory-and-retrieval-strategy.md) | Memory & Retrieval Strategy | **Keyword-first retrieval + background summarization**; one shared `Retriever` seam. | RAG-from-day-one; no summarization; blocking summarization; parallel retrievers. | Accepted; embedding-RAG **Needs Validation** |
| [019](ADR-019-modular-authentication.md) | Modular Authentication | **Env-toggled** auth module; local no-login default; secure-by-requirement when exposed. | Always-on auth; custom passwords; auth SaaS. | Accepted |

---

## Cross-cutting principles (the constitution in brief)

1. **Simplicity is the tie-breaker.** Equal-quality options → fewer moving parts wins (ADR-001).
2. **The model reads freely; it writes to canon only through human review.** (ADR-002, ADR-004, ADR-011.)
3. **Typed aggregates for structure; entries for knowledge; never a God Object or God Table.** (ADR-002, ADR-003.)
4. **One deterministic, budgeted, provider-neutral prompt path.** (ADR-009.)
5. **Core prompts are product logic → versioned files.** (ADR-013.)
6. **The daily UI never grows; capability enters through disclosure and seams.** (ADR-014, ADR-015.)
7. **Local-first, zero-cost, no vendor lock-in — always preserved.** (ADR-001, ADR-016, ADR-017.)
8. **Define seams at known-volatile boundaries; defer speculative implementations.** (ADR-015.)
9. **"Learning" and "evaluation" stay lightweight, transparent, and human-owned — no opaque ML.** (ADR-010, ADR-012.)

---

## Open items explicitly marked "Needs Validation"

These MUST NOT be treated as decided by any RFC until validated (typically via a Bench, ADR-012):

- **Auto-accept of AI canon proposals** (bounded, high-precision kinds) — ADR-004, ADR-011.
- **Multi-pass / agentic Writer pipeline** as an opt-in mode — ADR-005.
- **Reference-analysis RAG** over user-owned corpora — ADR-008.
- **Automated learning** (any form that changes runtime behavior) — ADR-010.
- **Whether to build the Bench at all**, and when — ADR-012.
- **Embedding/RAG memory retriever** upgrade — ADR-018.

---

## Conventions

- One decision per file, format: Context → Decision → Alternatives Considered → Why Rejected → Consequences (positive / negative / future risks) → Future Revisit Conditions.
- Filenames: `ADR-NNN-kebab-title.md`. Numbers are permanent; superseding is done by a new ADR that references the old.
- These ADRs decide *what and why*, never *how*: no schemas, no APIs, no prompt text, no code. Those belong to RFCs, which must conform to this set.

> Next step (not part of this deliverable): RFCs may now be written **against** these ADRs. Do not begin RFC writing here.
