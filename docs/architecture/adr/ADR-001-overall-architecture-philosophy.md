# ADR-001: Overall Architecture Philosophy

- **Status:** Accepted (revised v2 — re-evaluated against the two Fable reviews)
- **Date:** 2026-07-09 (v1) · revised 2026-07-09 (v2)
- **Deciders:** Architecture Review Board (Chief Software Architect)
- **Related:** ADR-002, ADR-003, ADR-013, ADR-014, ADR-015

> **v2 provenance.** Two senior-architect reviews now exist in the repo and are treated as primary inputs: `docs/design-review-ai-author-os.md` (the R1–R26 "quality-space map") and `docs/architecture-final-minimal.md` (a blank-page redesign that deliberately overrules parts of R1–R26). The v1 statement that these documents did not exist was true at v1 time and is now void. This ADR set has been re-evaluated end-to-end; see ADR-INDEX.md § "v2 Change Report" for what changed, agree/partial-agree/disagree positions, and the single biggest architectural change.

---

## 1. Context

This is a **personal / very-small-team AI creative workspace** whose north star is Korean web-novel ("로판" / Heart-Fiction-class) **quality**, unifying AI character chat and AI long-form novel writing over one shared knowledge base. The founding constraints are unchanged: single owner, self-hosted, **zero infra cost** beyond LLM fees, **no vendor lock-in**, offline-capable (Ollama), mobile-first, and — above all — **maintainable by one person for years**.

The existing `design.md` describes a layered engine architecture (Prompt/Memory/Novel/Chat engines behind `Router → Service → Engine → Adapter/Repository → Model`). The two Fable reviews accept that **substrate** (provider adapters, the block/budget PromptEngine, chat engine, TipTap chapters, jobs, auth) but argue that the *creative* architecture on top of it should collapse from many "engines" into **three verbs plus one honesty mechanism**, and that most creative behavior should live in **data and prompt files**, not code and tables.

The Board finds this argument largely correct and adopts it, with specific reservations recorded in the topic ADRs.

## 2. Decision

**Adopt a single-process, layered modular monolith organized as: a reusable substrate, three creative services (Store / Analyst / Writer), and one dev-only evaluation harness (Bench).** The governing design rule is about *where behavior lives*, not just how layers depend.

1. **Topology (from `architecture-final-minimal.md` §1):**
   - **Substrate** — keep as built: provider adapters (ADR-016), block/budget PromptEngine (ADR-009), auth (ADR-019), chat engine, TipTap chapters, in-process jobs (ADR-015).
   - **Store** — one prose-first Entry model + one `retrieve()` function; it *is* the Story Bible, the DNA libraries, and the ledgers (ADR-002, ADR-003, ADR-004, ADR-018).
   - **Analyst** — one extractor: *text in → entries out* for reference analysis, chapter fact-ingestion, and edit-diff distillation (ADR-002, ADR-008, ADR-010).
   - **Writer** — one loop runner executing a *declarative stage list*: retrieve → assemble → generate → validate → revise → persist (ADR-002, ADR-005, ADR-020).
   - **Bench** — dev-only golden-scene eval harness reusing the Writer's checks as metrics (ADR-012).
2. **The governing rule (the single most important principle of this set):** *Code that is written once — the loop runner, the entry store, the retrieval function, diff capture — is code. Everything that will be tuned weekly — what to extract, how to plan, how to critique, how to style — is a **versioned prompt file** or a **typed entry**, not code, not a table, not a service.* Two years of product evolution should be commits to `prompts/` and new entry `type` strings, not migrations and new modules (ADR-013, ADR-015).
3. **Still a single-process monolith.** No microservices, no bus, no agent-framework backbone, no serverless. Store/Analyst/Writer are logical services in one process (ADR-002).
4. **Personal/Local-First remains the tested default.** Multi-user/cloud stay latent (user_id everywhere, auth toggle) — not built, not assumed (ADR-017, ADR-019).
5. **Simplicity is the tie-breaker, and "completeness is a liability at implementation time."** The R1–R26 map is valuable; the *route* deliberately visits only what compounds. Equal-quality options → fewer moving parts.
6. **Quality is the point; plumbing is disposable.** Effort concentrates on the reference→DNA→scene-draft→validate→living-bible **loops** (ADR-004, ADR-005, ADR-008), because — per both reviews — *quality lives in loops, not in a feed-forward pipeline.*

## 3. Alternatives Considered

- **A. Keep the many-engine, feed-forward design** (`design.md` as-is: Prompt/Memory/Novel/Chat + a Story Bible Engine + per-library engines).
- **B. Microservices / event bus / agent-framework backbone / serverless** (the v1 alternatives).
- **C. Realize R1–R26 literally** — build Story Bible Engine, Planning Engine, Serialization Engine, Relationship Planner, Foreshadow Scheduler, DNA libraries, etc. as named modules/tables.
- **D. Prompt-orchestration-framework-first** (LangChain/LangGraph as the loop runner).

## 4. Why Rejected

- **A — Feed-forward many-engine design:** Both reviews land the same blow: a feed-forward `plan → bible → draft → style → output` line has a hard quality ceiling because *quality lives in loops* (analysis, drafting, continuity, learning). And "engine" as the organizing noun multiplies services/tables/editors that are really the same three verbs. Rejected as the creative architecture (its *substrate* is kept).
- **B — Distributed/framework backbone:** Unchanged from v1 — pure cost for one user, and framework-backbone reintroduces lock-in and non-determinism. Rejected.
- **C — R1–R26 literally:** `architecture-final-minimal.md` convincingly shows these are ~10 tables, ~10 editors, ~10 retrieval paths that are all one Entry model, one extractor, and one loop with declarative stages. Building the nouns is the two-year debt bomb. Rejected in favor of "capabilities survive as entry types + prompt stages; the abstractions die."
- **D — Orchestration framework:** The loop runner is small first-party code (retrieve→assemble→generate→validate→persist); a framework buys nothing and costs control, testability, and lock-in. Rejected.

## 5. Consequences

**Positive**
- The product's evolution surface becomes the two cheapest things in software to change: **prompt files and entry types**. New "library" = a new `type` string; new craft = a new prompt stage.
- Three services + one harness is a smaller, more honest object graph than a dozen engines.
- Loops (not a line) mean quality can actually compound; the Bench keeps that compounding measurable (ADR-012).
- Substrate reuse means little is thrown away; the migration is data-model, not rewrite.

**Negative**
- Concentrating behavior in prompt files makes **prompt regressions** the dominant risk — silent quality loss on a prompt edit. This is exactly why the Bench moves from "optional" (v1) to "necessary" (v2, ADR-012).
- A single prose-first Entry model is a strong bet; if deterministic checks later need heavy structure (timeline math, knowledge graphs) the `data` JSON strains (consciously accepted; ADR-003 §6).
- The Writer loop (validate/revise) adds latency/cost versus single-pass — mitigated by optimistic streaming and a strictly bounded check set (ADR-005).

**Future risks**
- Prompt-file sprawl without discipline; mitigated by the Bench and by keeping stage lists declarative.
- The architecture is tuned for novel-writing quality; the **chat** half of the product must not be quietly demoted to a mere "voice gym" (a Board reservation against the reviews' novel-centric framing — ADR-014).

## 6. Future Revisit Conditions

- If the prose-first Entry bet strains (checks doing "parsing gymnastics"), promote specific `type`s to real tables (ADR-003 §6) — cheap *because* everything routes through one Store.
- If the product is repositioned to hosted multi-user scale, revisit the single-process assumption and the SQLite ceiling (ADR-017).
- If the Bench shows the two-check Writer loop is insufficient or excessive, retune the loop (ADR-005) rather than re-architecting.
- If chat becomes a primary usage mode in practice, revisit its place in the topology and IA (ADR-014).
