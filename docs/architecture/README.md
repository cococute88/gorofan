# AI Author OS — Architecture Guide

**Project:** AI Native Creative Workspace (`ai-creative-workspace` / "gorofan") — "나만의 로판AI + 하트픽션"
**Audience:** a developer joining the project who needs to understand the architecture in under 30 minutes.
**Status:** Architecture frozen and certified for implementation (see [Final Architecture Audit](#8-audit-summary--reconciliations)).

> **What this document is.** A map and an onboarding guide. The *authoritative* sources are the ADRs (the constitution) and the RFCs (the component architecture). Where this README summarizes them, the ADRs/RFCs win. This README also records the small reconciliations from the final architecture audit (§8) so you have one place to resolve the few cross-document ambiguities.

---

## 1. Architecture Philosophy

The system produces **Korean web-novel-class creative quality** — 로판 (romance-fantasy) and Heart-Fiction-grade long-form fiction, plus AI character chat — from a codebase **one person can own and maintain for years**. Two capabilities share **one body of creative knowledge**: AI character chat (로판AI) and AI long-form novel writing (하트픽션).

The whole architecture is a reaction to the ways naive LLM writing tools plateau:

- Single-pass "continue the chapter" has a hard quality ceiling → replace the *line* with **loops** (draft → validate → revise).
- Long fiction drifts into contradiction by chapter 40 → maintain a **living, human-reviewed knowledge base** and check drafts against it.
- "An engine per feature" is a maintenance debt bomb → collapse everything into **three verbs and one data model**.
- Creative behavior that changes weekly regresses silently → make every change **measurable** (the Bench).
- Vendor lock-in and cost → stay **provider-neutral, zero-infra-cost beyond LLM fees, offline-capable**.

The governing rule (the single most important sentence in the whole set):

> **Code that is written once — the loop runner, the entry store, the retrieval function, edit-diff capture — is code. Everything tuned weekly — what to extract, how to plan, how to critique, how to style — is a versioned prompt file or a typed entry.**

Two years of product evolution should be **commits to `prompts/` and new entry `type` strings**, not new services and migrations.

---

## 2. Core Principles

1. **Personal-first / local-first.** Single owner, self-hosted, offline-capable (Ollama), mobile-first, zero cost beyond LLM usage. Multi-user/cloud are latent seams, never assumed. (ADR-001, ADR-017, ADR-019)
2. **Simplicity over cleverness.** Equal-quality options → fewer moving parts. "Completeness is a liability at implementation time." (ADR-001)
3. **Three verbs + one honesty mechanism.** The creative system is **Store / Analyst / Writer**, plus **Bench**. Everything once called an "engine" becomes an entry *type*, a prompt *stage*, or a *check*. (ADR-002)
4. **Prompt-first evolution.** Behavior tuned weekly lives in versioned prompt files and typed entries, not code or tables. (ADR-001, ADR-013, ADR-015)
5. **Prose-first knowledge.** All creative knowledge is prompt-ready prose with provenance — not schemas, ontologies, or graphs. Structured `data` appears *only* where a deterministic check needs it. (ADR-003) This is the architecture's consciously riskiest bet, with a sanctioned escape valve (promote-a-type-to-a-table).
6. **Review before Canon.** No AI-*inferred* change reaches canon except through human review. The model reads canon freely, writes canon only through a gate. (ADR-002, ADR-004, ADR-011) — see the precise rule in §8.
7. **Human remains in control.** The user is the final judge of quality. The system proposes; the human disposes. No opaque ML; learning is transparent, curated, reversible. (ADR-010, ADR-011)
8. **Quality lives in loops, not in a line.** Effort concentrates on the closed loops (reference→knowledge, draft→validate→revise, accepted-chapter→living-bible, edit→capture) because quality compounds in loops. (ADR-001, ADR-004, ADR-005)

---

## 3. Reading Order (Project Plan → ADR → RFC)

There is no separate "Project Plan" file. The top-level intent lives in three documents; read them first, in this order:

1. **`docs/design-review-ai-author-os.md`** — the "R1–R26" review: a map of the creative-quality space (reference intelligence, Bible ledgers, scene/episode units, the drafting and learning loops).
2. **`docs/architecture-final-minimal.md`** — the blank-page redesign that *deliberately overrules* parts of R1–R26 and collapses everything into Store / Analyst / Writer + Bench, one prose-first Entry model, behavior in prompt files.
3. **`docs/architecture/adr/ADR-INDEX.md`** — the constitution's index, the v2 change report, and where the Board agrees / partially agrees / disagrees with the reviews.

Then read the **ADRs** (the constitution — *what and why*, never *how*): start with ADR-001 (philosophy), ADR-002 (the three verbs), ADR-003 (the Entry model). The rest are topic decisions.

Then read the **RFCs** (component architecture — still implementation-neutral) in numeric order **RFC-001 → RFC-012**. RFC-001 is the system-level reference every later RFC conforms to; read it fully. Each RFC states its own reading order in its header.

> **Precedence, top to bottom:** ADRs (win over everything) → RFC-001 → RFC-002…RFC-012 → this README. The two reviews supply *rationale*; where they conflict with a later, deliberate ADR decision, the ADR wins.

---

## 4. Architecture Overview

A single-process, layered **modular monolith**: a reusable **substrate** (provider adapters, the block/budget Prompt Engine, auth, the chat engine, TipTap chapters, in-process jobs) with the **creative architecture** on top. The creative architecture is three verbs + a dev harness; everything else in this list is a *kind of knowledge* or a *cross-cutting responsibility* that rides on them.

```
                 ┌───────────────── HUMAN (final judge) ─────────────────┐
                 │                 Review Cards (the gate)               │
                 └───────▲───────────────────────────────────┬──────────┘
                         │ proposals                          │ approves → canon
   references ─┐         │                                    ▼
   chapters   ─┼─► ANALYST ──proposed Entries──►      ┌───────────────┐
   edits      ─┘  (text → knowledge)                  │     STORE     │  one prose-first
                                                       │  (Entries)    │  Entry model +
   ┌── novel ──► WRITER ──drafts──► reader             │  = Story Bible│  one retrieve()
   │            (loop: retrieve→assemble→generate      │  + DNA        │
   │             →validate→revise→persist)             │  + Relationship│
   └── chat  ──► CHARACTER CHAT ──replies──► user      │  + ledgers    │
                (own generation path)                  └───────▲───────┘
                         │ both consume knowledge via         │
                         ▼                                     │
              RETRIEVAL (select) → CONTEXT ASSEMBLY / PROMPT SYSTEM (compose)
                         │
                    provider adapter → model

   BENCH ── dev-only, out-of-band ── measures every prompt/stage/retrieval change before it ships
```

**The eleven concepts, in one line each:**

- **Store** (RFC-002) — the one prose-first Entry model + the one `retrieve()`. It *is* the Story Bible, the DNA, the relationships, and all ledgers. Owns all persisted knowledge; owns *no* extraction, generation, or the promotion decision.
- **Store-wide Retrieval** (RFC-003) — the Store's one owner-safe, deterministic, keyword-first `retrieve()` contract: filters, ranks, and selects whole Entries within a knowledge budget, then hands them to Context Assembly.
- **Writer** (RFC-004) — one orchestration loop over declarative stages for the novel: retrieve → assemble → generate → validate → revise → persist, on the **scene** as the atomic unit and the **episode (회차)** as the delivery unit. Consumes the Store; emits proposals; owns no knowledge.
- **Story Bible** (RFC-005) — the work-scoped **canonical** subset of the Store: facts, knowledge-state, promises, relationships, summaries, timeline. A *view over the Store*, not a separate store. Living, but human-gated so it never rots.
- **Relationship** (RFC-006) — how characters relate, as `relationship` Entries: *shared narrative state* belonging to neither a character nor the Writer. Planned by a Writer stage, checked by a `qa` assertion. No graph subsystem.
- **Character DNA** (RFC-007) — the enduring **identity** of a character (`character.*` Entries): prose + exemplars-first, five layers as *organization not schema*. Identity, not personality labels, and not momentary emotional state.
- **Analyst** (RFC-008) — one extractor: *text in → proposed Entries out*, across references, accepted chapters, and edit diffs. Facets are prompt files. Never writes canon.
- **Prompt System** (RFC-009) — prompts as **versioned architectural assets**: prompt bodies live in files (never a DB), composed the one standardized way, evolved via the Bench.
- **Bench** (RFC-010) — the dev-only, out-of-band evaluation harness. Measures every prompt/stage/retrieval change on frozen golden scenes before it ships. Never gates the user's own output.
- **Human Review & Review Card** (RFC-011) — the single human-gated write path into canon. Every AI proposal is an Entry with `status=proposed`, reviewed via one uniform Card (Accept / Edit-then-accept / Reject).
- **Character Chat** (RFC-012) — a **first-class product capability** (로판AI), *not* a sub-feature of the novel. Has its own generation path, but shares the Store, DNA, Relationship, and Bible, and the same review gate.

**The two closed disciplines that make it work:** knowledge flows *in* only through review (Analyst/Writer/Chat propose → human approves → canon); prose flows *out* through loops (the Writer's draft→validate→revise). The Bench watches every change to the volatile prompt layer so quality compounds instead of oscillating.

---

## 5. Document Map — which document defines what

| Topic | Decision (what & why) | Component architecture (still no code) |
|---|---|---|
| Overall philosophy, the three verbs, governing rule | ADR-001, ADR-002 | RFC-001 |
| The Entry model / one knowledge representation | ADR-003 | RFC-002 |
| Store-wide retrieval contract | ADR-018, ADR-009 | RFC-003 |
| Writer loop, stages-as-data, scene/episode | ADR-005, ADR-020 | RFC-004 |
| Living Story Bible, ledgers, continuity loop | ADR-004 | RFC-005 |
| Relationships as entries + stage + check | ADR-006 | RFC-006 |
| Character DNA (prose + exemplars, five layers) | ADR-007 | RFC-007 |
| Extraction / reference analysis / learning capture | ADR-008, ADR-010 | RFC-008 |
| Prompts in files, composition, versioning | ADR-013, ADR-009 | RFC-009 |
| Bench evaluation harness | ADR-012 | RFC-010 |
| Review Card = proposed Entry; the gate | ADR-011, ADR-014 | RFC-011 |
| Character chat as a first-class capability | ADR-014, ADR-018 | RFC-012 |
| **Substrate — not yet given a dedicated RFC:** |||
| Provider adapters / vendor neutrality | ADR-016 | *(future Provider Adapter RFC)* |
| Persistence, SQLite→Postgres swap, scoping | ADR-017 | *(future Persistence RFC)* |
| Modular authentication | ADR-019 | *(future Auth RFC)* |
| Future-expansion principles / sanctioned seams | ADR-015 | *(cross-cutting)* |
| UI & information architecture, five UI patterns | ADR-014 | *(future UI RFC)* |

> **RFC numbering note.** RFC-003 defines Store-wide Retrieval and the pre-existing Analyst RFC moved without semantic deletion to RFC-008. RFC-001's dependency table and later RFC cross-references use this same current map. Unwritten topics do not reserve RFC numbers.
>
> **Historical background.** The former RFC-008 Retrieval & Context Assembly draft is preserved as [Retrieval & Context Assembly — Historical Background](retrieval-context-assembly-background.md). It is non-authoritative rationale; RFC-003 owns Store-wide selection and RFC-009/ADR-009 own prompt composition and final Context Assembly.

---

## 6. Implementation Guidance

**Read first, in order:** ADR-001 → ADR-002 → ADR-003 → RFC-001 → RFC-002. Those five give you the spine (the three verbs, the one Entry model, the governing rule). Then read the RFC for whatever you're building, plus its grounding ADR(s) from the map above.

**Build order (from ADR-001 / `architecture-final-minimal.md` §8):**
1. Entry store + `retrieve()`; migrate character/world/lore fields → Entries.
2. Writer loop runner with the smallest pipeline (plan → draft → assemble).
3. Analyst reference path (top facets) — DNA cards appear.
4. Checks (continuity + voice attribution + qa) + **edit-diff capture** + Bench v0.
5. Analyst ingestion path (facts/knowledge/promises as Review Cards) — the Bible goes live.
6. Then let the Bench tell you what to build next.

**What MUST NOT change without a new/updated ADR** (these are the constitution — changing them is an architecture decision, not an implementation choice):
- The three-verb structure (Store / Analyst / Writer) + Bench, single-process monolith. (ADR-001, ADR-002)
- The one prose-first Entry model; **no per-library table ever** (`dialogue_library`, `character_dna_attributes`, … appearing in a migration = architectural failure). (ADR-003, ADR-015)
- The governed, closed `type` vocabulary; **no `type:"misc"`**. (ADR-003)
- Review before Canon: no AI-*inferred* change reaches canon except through the review gate. (ADR-002, ADR-004, ADR-011)
- Prompt *bodies* live in versioned files, never a database; users customize *inputs*, not bodies. (ADR-013)
- One `retrieve()` over the Store; keyword-first; embeddings only Bench-gated behind the same seam. (ADR-018)
- The Bench is dev-only and never gates the user's own output. (ADR-012)
- Provider-neutrality (neutral `messages[]` + thin adapter); local-first default. (ADR-016, ADR-017, ADR-019)
- **Edit-diff capture from day one** — this is data you can *never* collect retroactively; capture it even though the "learning" that uses it is deferred. (ADR-010, RFC-008 §5)

**What MAY evolve through RFCs / normal work** (the cheap surfaces — this is where you should *want* to spend iteration):
- New knowledge kinds → a new entry `type` string (+ an Analyst facet). (RFC-002 §6, RFC-008 §9)
- New craft → a new Writer stage or Analyst facet, a new prompt file. (RFC-004 §9, RFC-009 §11)
- Better behavior → edit a prompt file, prove it on the Bench, commit. (RFC-009 §7, RFC-010)
- Retrieval tuning, and (when the Bench proves keyword recall misses) the embedding seam. (RFC-003 §9, §14)
- The deferred, evidence-gated items: bounded auto-accept for high-precision proposal kinds; a third+ Writer critic; the chat top-level IA. Open them only on a concrete or Bench-measured trigger — never speculatively. (ADR-INDEX "Needs Validation")

**The one sanctioned way to add a table later:** promote a specific `type` to its own structured table *only* when its deterministic checks start doing "parsing gymnastics" against prose-first `data` (the visible failure mode). Cheap precisely because everything routes through one Store. (ADR-003 §6, RFC-002 §10)

---

## 7. Glossary

Plain-English definitions of every major term. Where two terms are easy to confuse, the difference is called out.

- **Entry** — the single, uniform unit of creative knowledge. Prose-first (`content` written to be read into a prompt), typed (a `type` from a governed closed vocabulary), with provenance, confidence, and a status. *Everything* the system knows — a character's voice, a world rule, a fact, a promise, a relationship's stage — is an Entry. One model, one editor, one retrieval path. (RFC-002)
- **Store** — the one place Entries live, plus the one `retrieve()` function. It is not a facade class; it is a data model + a small retrieval function + typed access. (RFC-002)
- **`type`** — the governed discriminator that makes one Entry model behave as many kinds of knowledge (e.g. `character.voice`, `world.fact`, `story.promise`, `relationship.state`, `user.preference`). Adding one is a deliberate ADR/RFC decision — never user data, and never `misc`. (RFC-002 §6)
- **`scope`** — where an Entry applies: **user**, **collection**, **work**, **character**, or **world**. `chat-private` is an explicit boundary marker but remains backed by chat `Memory`, not persisted Entries, in Phase 1. (RFC-002 §5, RFC-005)
- **Canon** — knowledge the system treats as **true** and acts on: Entries with `status = canon`. AI-*inferred* knowledge becomes canon only through a human action; curated reference import may use explicit batch approval, but the Analyst never decides canon. (RFC-002 §7)
- **Proposal** — knowledge the system believes but is **not yet authorized to trust**: an Entry with `status = proposed`. It is inert — not retrieved as canon, not trusted by checks, influencing nothing — until a human approves it. Proposals are cheap (generate abundantly); canon is expensive (approve deliberately). (RFC-011 §3)
- **Working / temporary knowledge** — ephemeral knowledge that exists only inside one operation (the context assembled for a draft, an in-flight reply, a character's momentary emotion). Never persisted as canon. (RFC-005 §6)
- **Review Card** — the one interaction model for the gate: a proposed Entry presented with what it says, its provenance/confidence, and three actions — **Accept** (→ canon), **Edit-then-accept**, **Reject** (→ rejected). One queue, one editor, for every proposal kind. (RFC-011)
- **Human Review / the gate** — the single write path into canon. "AI proposes, human disposes." The gate is architectural, not optional chrome; bypassing it is forbidden. (RFC-011)
- **Analyst** — the one extractor: *text in → proposed Entries out*, for references, accepted chapters, and edit diffs. What it looks for is a **facet** (a prompt file), not code. (RFC-008)
- **Facet** — one unit of "what to extract," realized as a versioned prompt file the Analyst runs. New analytical depth = a new facet, not a new engine. (RFC-008 §8)
- **Writer** — the orchestration layer that turns knowledge into narrative for the novel, running the draft→validate→revise **loop**. Consumes the Store; owns no knowledge; emits proposals through the gate. (RFC-004)
- **Stage** — one step in the Writer's declarative pipeline (plan, draft, check, revise, assemble episode, style), each backed by a prompt file. New craft = a new stage. (RFC-004, ADR-005)
- **Scene / Episode (회차)** — the **scene** is the atomic unit the Writer plans, drafts, and checks (a dramatic beat that *turns*); the **episode** is the delivery unit readers receive; the **novel** emerges from episodes held coherent by the Store. (RFC-004 §8, ADR-020)
- **Story Bible** — the work-scoped **canon** subset of the Store: the living, human-gated memory of one novel (facts, knowledge-state, promises, relationships, summaries, timeline). A *view over the Store*, not a separate store. (RFC-005)
- **Continuity loop** — accepted chapter → Analyst proposes new knowledge → human reviews → canon → retrieved into the next draft → checked. The flywheel that keeps chapter 100 consistent with chapter 3. (RFC-005 §7, ADR-004)
- **Relationship (state)** — how two characters currently stand and how it last moved, as `relationship` Entries. **Shared narrative state**: it belongs to neither character's DNA nor the Writer — one pairing has one state, read by both novel and chat. (RFC-006)
- **Character DNA** — the **enduring identity** of a character (`character.*` Entries): voice (exemplars first), values, contradictions, motivations, growth anchors. Prose + examples, not personality dials. Contrast with **Current Emotional State** (how a character feels *right now* — transient working knowledge, never canonized) and with **Emotion (repertoire)** (a stored craft palette of emotional beats — an Entry category). (RFC-007)
- **Exemplar** — a concrete example line of a character's dialogue. Exemplars **outrank** abstract descriptions in shaping voice; a user-corrected or bookmarked line becomes a canonical exemplar (through review). (RFC-007 §7, ADR-007)
- **Identity vs State** — the architecture's spine for characters: **DNA** (identity, changes slowly, through review) ≠ **Relationship** (a pairing's shared trajectory) ≠ **Story Bible** (what has happened) ≠ **Current Emotional State** (momentary feeling, never canon). Keeping these in separate homes is what lets a character stay themselves while everything around them moves. (RFC-007 §6)
- **Retrieval** — selecting the *minimum necessary* eligible knowledge for a task, with owner/scope/status filters and deterministic type/relevance/recency/priority ranking, cut to a knowledge-token budget. "Retrieval, not dumping." (RFC-003, ADR-018)
- **Context Assembly** — the deterministic, budget-enforcing, provider-neutral **mechanism** that turns retrieved Entries plus non-knowledge inputs into an LLM-ready context. Retrieval selects; Context Assembly composes. (RFC-003 §12, ADR-009)
- **Prompt System** — prompts treated as **versioned architectural assets**: prompt *bodies* in files (never a DB), composed the one standardized way, evolved via the Bench. (Distinct from Context Assembly, which is the runtime mechanism; and from the substrate **Prompt Engine** of ADR-009, which both describe from different angles — see §8/W3.) (RFC-009)
- **PromptBlock** — the discrete unit context is collected as (a kind, a role, a priority, a truncatable flag) so composition can order and budget deterministically, never dropping the protected blocks (user message, system instruction). (ADR-009; concrete structure deferred to the future Prompt Architecture RFC.)
- **Bench** — the dev-only, out-of-band evaluation harness. Runs a change against a small fixed set of **golden scenes** (frozen scenario + frozen knowledge snapshot), reuses the Writer's checks as metrics plus a pairwise "which is better?" judgment, and reports. It **never** scores live generations or gates the user's output. Directional evidence, not an oracle. (RFC-010)
- **Golden scenes** — the fixed, curated, versioned scenarios the Bench measures against. They must evolve to stay honest (against over-fitting) while staying versioned so historical comparisons remain valid ("benchmark drift"). (RFC-010 §6–§7)
- **Character Chat** — a first-class product capability: interactive conversation with a character (로판AI). Its own generation path (the substrate chat engine, *not* the Writer's loop), but the same shared knowledge (DNA, Relationship, Bible, Store), the same retrieval/assembly substrate, and the same review gate. (RFC-012)
- **Substrate** — the machinery that is *not* creative logic: provider adapters, the block/budget Prompt Engine, auth, the chat engine, TipTap chapters, in-process jobs. Kept as-is; owns mechanism, never creative policy. (ADR-001 §2, ADR-009/016/019)
- **Provenance** — where an Entry came from (a reference, chapter, chat bookmark, edit batch, import, or user action). Mandatory; powers review and explanation. (RFC-002 §8.1)
- **Confidence** — how strongly an Entry is believed; a bounded ranking input whose treatment must respect human-authored authority. (RFC-002 §11, RFC-003 §9.5)
- **Supersession** — how canonical knowledge changes: an approved replacement becomes canon, the old Entry becomes *superseded*, and history is retained. (RFC-002 §8.2)
- **Promote-a-type-to-a-table** — the *one* sanctioned way a new table is added later: when a `type`'s deterministic checks strain prose-first `data`. Cheap because everything routes through one Store. (ADR-003 §6)
- **Sanctioned seam** — a named boundary whose second implementation is deferred until a concrete or Bench trigger fires (`LLMProvider`, the single `Retriever`/embeddings, `StorageBackend`, `JobQueue`, `AuthProvider`, …). Define the seam; defer the second impl. (ADR-015, ADR-016, ADR-018)

---

## 8. Audit Summary & Reconciliations

This section records the outcome of the final architecture audit performed before implementation. **No BLOCKER issues were found. The architecture is ready for implementation.** The reconciliations below keep the document map aligned with the Phase 1 contracts.

- **W1 — Status of reference-derived knowledge.** ADR-008 describes curated reference output as canon while the universal review rule forbids an Analyst decision to canonize. RFC-002 resolves this as an authority rule: AI-inferred output is captured/proposed; a deliberate user action may canonize directly or through explicit batch approval. The Analyst never decides canon.
- **W2 — RFC numbering alignment.** RFC-001, this guide, and the files on disk now share one current RFC-002~012 map. The pre-existing Analyst RFC is preserved as RFC-008, and the former Retrieval & Context Assembly draft is retained as non-authoritative historical background rather than deleted.
- **W3 — Retrieval ↔ Prompt System seam.** RFC-003 owns Entry selection and the Entry-to-PromptBlock handoff contract. RFC-009 and ADR-009 own prompt assets and final deterministic Context Assembly. Retrieval never emits provider messages; assembly never reaches into the Store to re-rank Entries.

**INFO (no action required):** implementation-level RFCs for the remaining substrate seams (Provider Adapter, Persistence, Auth, UI) and deferred internals (continuity-loop internals, Learning Capture, Bench runner, prompt contents) are intentionally not yet written. Retrieval mechanics now have the minimum Phase 1 contract in RFC-003. Evidence-gated items remain deferred: bounded auto-accept, per-scene cost, chat IA, embeddings, a third critic, and prose-first durability.

**Verdict:** the ownership graph is acyclic and one-way; the single human-gated canon write path is consistently enforced; terminology is consistent modulo the three documented naming/reference clarifications above. **The architecture is ready for implementation.**
