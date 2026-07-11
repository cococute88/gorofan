# RFC-005: Story Bible

- **Status:** Draft
- **Date:** 2026-07-10
- **Author:** Chief Software Architect
- **Project:** AI Native Creative Workspace (`ai-creative-workspace` / "gorofan") — "나만의 로판AI + 하트픽션"
- **Conforms to:** RFC-001, RFC-002, RFC-008, RFC-004; ADR-004, ADR-002, ADR-003, ADR-008, ADR-011, ADR-018
- **Supersedes:** nothing
- **RFC layer:** Component — the canonical-knowledge reference the continuity, retrieval, review, and relationship RFCs build on

> **Reading order.** RFC-001 is the system-level reference; RFC-002 defines the Entry Store; RFC-008 defines the Analyst; RFC-004 defines the Writer. Read all four first. This RFC defines the **Story Bible** — the canonical knowledge source for a *single work* — and explains *why it exists*, *what it owns and does not own*, *how it relates to the Store and the Writer*, and *how it evolves across a novel*. It does **not** define Entry structures, retrieval, validation logic, prompts, or UI — each is named and deferred.
>
> **Source of truth.** The RFC documents take precedence over this one, in order (RFC-001, then RFC-002, RFC-008, RFC-004); behind them the ADR set (`docs/architecture/adr/`) is authoritative, and the two reviews (`docs/design-review-ai-author-os.md`, `docs/architecture-final-minimal.md`) supply rationale only. Where anything here appears to conflict with an RFC or an ADR, **those win** and this document is in error.
>
> **This RFC is implementation-neutral.** It is the conceptual charter of the Story Bible. Whenever an implementation detail is needed, this document writes **"Defined in the corresponding RFC"** (naming the topic) and stops. It defines no Entry structures.

---

## 1. Purpose

This RFC defines the **Story Bible** — the **canonical knowledge source for a single work**.

RFC-002 established the Store: one prose-first, provenanced, typed body of all creative knowledge, spanning collections and works (RFC-002 §1). The Story Bible is the **work-scoped canon within that Store**: everything the system holds as true *about one ongoing novel* — its facts, who knows what, the promises it has made, where its relationships stand, and how to remember what has happened. It is what makes a serialized 장편 (long-form work) stay coherent from chapter 3 to chapter 100.

The Story Bible is not a new store and not a separate subsystem. It is a **conceptual view over the Store** — the canonical Entries at work scope, kept current through the human-gated continuity loop (ADR-004 §2). This RFC explains:

- **why the Story Bible exists** — why long-form fiction needs a single canonical source of truth, and why that is more than a pile of notes;
- **what it owns** — the canonical, continuity-bearing knowledge of one work;
- **what it explicitly does NOT own** — extraction, generation, prompt execution, the review UI, reference analysis;
- **how it relates to the Store** — it *uses* the Entry Store; it does not replace it (RFC-002);
- **how it supports the Writer** — the Writer *consumes* it; it does not serve it (RFC-004);
- **how it evolves** — how the Bible grows, chapter by chapter, without architectural change.

It does **not** define the Entry model, the ledgers' structure, retrieval, or the contradiction check (§12).

---

## 2. Why the Story Bible Exists

### 2.1 Why long-form novels require a canonical source of truth

A single chapter can be written from a good prompt. A *hundred* chapters cannot. By chapter 40, a naive system produces the failure modes the whole architecture exists to prevent: characters know things they should not yet know, promises and foreshadowing go unpaid, and freshly-invented facts contradict earlier ones (RFC-001 §1.2). These are not prose-quality problems a better sentence fixes; they are **memory** problems. The model has no durable, checkable record of what is already true.

The Story Bible is that record. It exists so that long-form fiction has a **single canonical source of truth** the Writer can check every draft against and draw every relevant fact from (ADR-004 §1, §5). Without it, coherence at chapter 100 is not merely hard — it is *impossible at all*, because there is nothing to be coherent *with* (ADR-004 §5). With it, the continuity loop — accepted chapter → canon → retrieved into the next draft → checked — becomes the machinery that makes serialization survivable (RFC-001 §5; ADR-004 §1).

### 2.2 Why the Story Bible is not simply a collection of notes

A pile of notes is passive, unstructured, unprovenanced text a human occasionally re-reads. The Story Bible is something categorically different, in four ways:

- **It is canonical, not incidental.** Every piece of it is knowledge the system treats as *true* and will act on — checked against, retrieved into drafts, used to catch contradictions (ADR-004 §2–§4). Notes inform a human; canon governs the system.
- **It is typed and continuity-bearing, not freeform.** Its contents are organized as the kinds of knowledge long fiction depends on — established facts (timestamped to when they became true), who-knows-what state, the promise ledger, relationship state, and multi-granularity summaries (ADR-004 §2). A single free-text `Chapter.summary` silently drops what chapter 37 established; the Bible does not (ADR-004 §4-D; ADR-018 §4).
- **It is provenanced and reviewed, not asserted.** Every entry traces to its source and reached canon only through human approval (RFC-002 §3.2, §3.4; ADR-004 §3). This is what makes it *trustworthy* rather than merely present.
- **It is living, not static.** It grows with every accepted chapter through the continuity loop, without rotting into contradiction, because its growth is gated (§6, §7; ADR-004 §1). A static bible guarantees staleness by chapter 40; the Bible stays current *safely* (ADR-004 §4-B).

The Story Bible is, in one line, **the work's canonical, typed, provenanced, living memory** — not a notebook.

---

## 3. Story Bible Responsibilities

The Story Bible's ownership is the **canonical knowledge of one work**. This section defines *responsibilities* — high-level, no Entry structures, no algorithms. Each responsibility below is a *kind of canonical knowledge the Bible holds*, realized as Entry types in the Store (RFC-002 §5) — **not** as tables or ledgers this RFC defines (ADR-004 §2).

- **Canonical knowledge.** The Bible is the authoritative record of what is true about the work — the single body of fact the Writer draws on and checks against (ADR-004 §2, §5). It is the source of truth, not a copy of it.
- **Continuity.** The Bible carries the established facts of the ongoing story, timestamped to the point they became true, so later chapters stay consistent with earlier ones (ADR-004 §2). Continuity is the Bible's reason for existing.
- **Narrative memory.** The Bible holds compressed accounts of what has happened at multiple granularities (scene / chapter / arc / story-so-far), so long-range context fits a budget and nothing important is silently forgotten (ADR-004 §2; ADR-018 §4). *The multi-level summary design is Defined in the corresponding RFC.*
- **Relationship state.** The Bible records where each character pairing currently stands and how it last moved — the evolving state a romance-forward work turns on (ADR-004 §2; ADR-006). *The relationship model is Defined in the corresponding RFC (the Relationship System RFC).*
- **Open threads.** The Bible tracks what the story has left unresolved — the live questions a reader is waiting on — so the Writer can keep them in view and pay them off (ADR-004 §2).
- **Promise tracking.** The Bible holds the promise ledger — the setups and foreshadowing the story has planted, with a sense of when each comes due and whether it is still open, paid, or abandoned. Payoff discipline is what makes a story feel *authored* rather than generated (ADR-004 §2).
- **Timeline.** The Bible carries the ordering and timing of what has happened, to the extent continuity checks need it — the "when" that keeps events in a coherent sequence (ADR-004 §2). *Timeline is among the parts most likely to need structured support later (§11; ADR-003 §6).*

Across all of these, one responsibility is constant: the Bible holds this knowledge **canonically and provenanced**, and it changes only through review (§5). It is the *keeper* of the work's truth, not the producer or consumer of it.

---

## 4. What Story Bible Does NOT Own

The Story Bible's non-ownership is as binding as its ownership; ambiguity here re-creates the engine sprawl the architecture exists to prevent (RFC-001 §4). The Bible is **knowledge kept**, not work done.

- **Knowledge extraction.** The Bible does not turn text into knowledge. New facts, promises, and relationship movement are extracted by the **Analyst** on chapter acceptance (RFC-008 §3; ADR-004 §3). The Bible *receives* proposed knowledge; it does not produce it.
- **Narrative generation.** The Bible does not write prose. Generating draft fiction is the **Writer's** job (RFC-004 §3). The Bible supplies the truth the prose must respect; it does not author the prose.
- **Prompt execution.** The Bible does not assemble or run prompts, and it does not own the retrieval that selects its knowledge for a prompt — that single capability belongs to the **Store** (RFC-002 §6.1, §8). The Bible is *read from*; it does not do the reading. *Retrieval and prompt assembly are Defined in the corresponding RFCs.*
- **The contradiction check.** Catching a draft that violates canon is a **Writer check**, not a Bible feature (ADR-004 §4). The Bible provides the ground truth; the Writer runs the check against it. *Validation is Defined in the corresponding RFC.*
- **Human editing UI.** The Bible does not own the interface through which a human reviews proposals or browses canon. The Review Card queue and the Bible browser are UI surfaces defined elsewhere (ADR-011; ADR-014). The Bible owns the *knowledge and its status*, not the screen. *The review and browse UI are Defined in the corresponding RFCs.*
- **Reference analysis.** The Bible is *work*-scoped canon; the distillation of uploaded references into collection-scoped knowledge is an **Analyst** input path, not a Bible responsibility (RFC-008 §5; ADR-008 §2). The Bible holds what one novel has established, not what its source references teach.

The one-way discipline that governs the whole system governs the Bible too: **the model reads canon freely and writes canon only through review** (RFC-001 §2.6; ADR-002 §2; ADR-004 §5).

---

## 5. Canon Philosophy

The Story Bible's defining rule is *how knowledge becomes canonical*. Nothing enters the Bible's canon except through human approval.

```
   proposal   ── new knowledge is proposed (a Review Card), never asserted as canon
      │            (emitted by the Analyst on acceptance, or by the Writer's ingestion — §7)
      ▼
   review     ── a human accepts / edits / rejects the proposal
      │            (the single human-gated write path — RFC-001 §2.6)
      ▼
   canon      ── approved knowledge joins the Bible; now true, checkable, retrievable
```

- **The Bible never mutates itself.** No accepted chapter, no extraction, no Writer output writes canon on its own. Every change to the Bible's truth passes through a human accepting a proposal (ADR-004 §3, §5). This is not optional chrome; it is the **only** write path into the work's source of truth (RFC-001 §2.6, §8.2).
- **Why the gate is architectural.** The Bible is the very canon that feeds future drafts. Unattended write-back — letting the AI commit its own extracted facts straight to canon — is *the highest-regret option in the whole system*: a single hallucinated fact, written silently to the source of truth, corrupts every subsequent draft that retrieves it (ADR-004 §4-A). The compounding-hallucination risk over a long serialization is precisely why both reviews independently route ingestion through review (ADR-004 §1, §4-A). The gate exists because the cost of a wrong canon entry is not one bad chapter but a rotting foundation.
- **Reading is free; writing is gated.** The asymmetry is the point: the Writer and the checks read canon freely and automatically, but *contributing* to canon is always mediated by a human decision (RFC-001 §8.7; ADR-004 §2, §5). This is the same gate every producer in the system passes — the Analyst and the Writer both emit *proposed* knowledge, never canon (RFC-008 §4; RFC-004 §4).
- **Bounded auto-accept remains deferred, not adopted.** The architecture names a *possible future* where a specific high-precision knowledge type might be auto-accepted under scoped, reversible, audited conditions — but only after real long-project data proves the precision, and never as a default (ADR-004 §4-A, §6). Until that trigger fires, **no silent canon mutation** stands as an absolute. *The conditions for any bounded auto-accept are Defined in the corresponding RFCs.*

---

## 6. Canon vs Working Knowledge

The system holds knowledge in three distinct conditions. Only one of them **is** the Story Bible. Confusing them is how a source of truth quietly becomes untrustworthy, so this RFC states the distinction plainly. *The status mechanism itself is owned by RFC-002 (§3.4); this section explains what each condition means for the Bible.*

- **Temporary (working) knowledge — never part of the Bible.** This is the ephemeral knowledge that exists only *within* a single operation and is never persisted as canon: the context assembled for one draft, the internal scene scaffolding the Writer plans against, an unaccepted draft in flight. It is **working material**, not truth about the work. It lives and dies inside one writing act, and the Bible neither holds it nor is affected by it (RFC-004 §5, §6). Working knowledge that is never proposed simply vanishes when the operation ends — by design.
- **Proposed knowledge — a candidate for the Bible, not yet the Bible.** This is knowledge that has been *persisted* as an Entry but carries the status *proposed* — a Review Card awaiting human judgment (RFC-002 §3.4; ADR-004 §3). It is real and durable, but it is **not canon**: the Writer's checks do not treat it as ground truth, and it is not part of the work's source of truth until a human approves it. Proposed knowledge is the antechamber to the Bible — the queue of things the system *believes* but has not been *authorized to trust*.
- **Canonical knowledge — this is the Story Bible.** This is knowledge that has been reviewed and approved: Entries at status *canon* and work scope. It is what the Writer reads freely, checks against, and retrieves into drafts (§5, §8; ADR-004 §2). **The Story Bible is exactly this set** — the canonical, work-scoped knowledge, and nothing else.

The boundary that matters: **working knowledge may become proposed knowledge (by being extracted and persisted), and proposed knowledge may become canonical knowledge (by being approved) — but only canonical knowledge is the Bible.** The gate in §5 is the single door between "proposed" and "canonical," and there is no door at all from "temporary" directly to "canonical." *Rejected knowledge — proposals a human declined — is retained for provenance but is likewise not the Bible (RFC-002 §4).*

---

## 7. Living Bible Philosophy

The Story Bible is **living**: it grows with the work rather than being authored once at the start.

- **The Bible grows through the continuity loop.** Each time the author accepts a chapter as canonical story, that chapter becomes a source (RFC-008 §5): the Analyst extracts the new facts, knowledge-state, promises, relationship movement, and summaries it established, as *proposed* Entries (ADR-004 §3). The human reviews them; approved knowledge joins canon; and that freshly-approved knowledge is immediately available to retrieval for the next draft — which the Writer then checks against it (RFC-001 §5; ADR-004 §1). Accepted chapter → proposal → review → canon → retrieved into the next draft → checked: this closed loop is the Bible's life (RFC-001 §5.8).
- **Living, but never rotting.** The reason a living Bible does not degrade into contradiction is precisely the gate (§5): growth is continuous, but every increment is reviewed before it becomes truth (ADR-004 §1, §5). A static bible guarantees staleness; an *ungated* living bible guarantees corruption; the **gated** living bible is the only option that stays both current and coherent (ADR-004 §4-A, §4-B).
- **The flywheel that separates an Author OS from a generator.** The continuity loop is one of the four closed loops where quality compounds (RFC-001 §2.8, §5). It is what lets the Bible get *richer* per chapter — more facts, more paid promises, more relationship history — while staying trustworthy, which is the difference between a system that remembers its own story and a generator that forgets (ADR-004 §1, §5).
- **Evolution is knowledge changing, not schema changing.** As the story moves, knowledge is added, refined, and superseded — but this is movement *within* the Entry model (new and superseded Entries), not change to any structure (RFC-002 §4). The Bible evolves as fast as the novel does while the system underneath it stays still (§9). *Supersession mechanics are Defined in the corresponding RFC.*

---

## 8. Relationship to Entry Store

The single most important structural fact about the Story Bible: **the Bible uses the Entry Store; it does not replace it.**

- **The Bible is a view over the Store, not a separate store.** The Story Bible *is* the canonical, work-scoped subset of the one Entry model defined in RFC-002 — the same table, the same typed Entries, the same provenance and status, the same retrieval (RFC-002 §1, §5; ADR-004 §2). There is no "Bible store." Its ledgers are Entry `type`s, not new tables (RFC-002 §3.5, §9.1; ADR-004 §2). If a per-ledger Bible table ever appeared, the architecture would have failed (RFC-001 §7.1, §8.5).
- **"Bible" is a scope-and-status lens, not a new model.** What distinguishes the Bible from the rest of the Store is *which* Entries it names: those at **work scope** with status **canon** (§6; ADR-004 §2). Reference-derived knowledge (collection scope) and proposed knowledge (not yet canon) are in the same Store but are not the Bible. The Bible is a way of *looking at* the Store, defined by scope and status — not a second body of knowledge to keep in sync.
- **The Bible inherits all of the Entry model's commitments.** Because it *is* Store Entries, the Bible is automatically prose-first, provenanced, confidence-tagged, typed from the governed closed vocabulary, and superseded-rather-than-deleted (RFC-002 §3). This RFC adds no new representational rules; it applies RFC-002's model to one work's canon. **This RFC does not define the Entry — RFC-002 does** (§11).
- **One Store means one retrieval, one editor, one gate — shared, not duplicated.** Because the Bible is not a separate store, it needs no separate retrieval function, no separate editor, and no separate review path: it reuses the Store's single retrieval capability, the single typed editor, and the single review gate (RFC-002 §2.3, §6, §8). The Bible gets its living, checkable, retrievable behavior *for free* from the Store — which is the whole payoff of the one-model decision (ADR-004 §5).

The relationship in one line: **the Store is the machine; the Story Bible is what that machine holds for one work.**

---

## 9. Relationship to Writer

The Story Bible and the Writer meet through a strict one-way discipline: **the Writer consumes the Bible; the Bible does not serve or run the Writer.**

- **The Writer reads the Bible; it does not own it.** The Writer retrieves the relevant slice of the Bible for each situation and drafts against it, but it holds no knowledge of its own and maintains no parallel copy (RFC-004 §6; RFC-002 §6.1). The Bible is the truth; the Writer is a reader of it (RFC-004 §6).
- **Consumption is retrieval, not dumping.** The Writer does not receive the whole Bible; past roughly chapter 50 the Bible exceeds any context window (RFC-002 §8; ADR-004 §2). It consumes the *budgeted, situation-relevant* slice the Store's retrieval returns — the on-stage cast, the locations, the due promises, the current knowledge-state (ADR-004 §2). The Bible supplies truth; **the Store's retrieval selects it; the Writer consumes the result** (RFC-004 §6). *Retrieval is Defined in the corresponding RFC.*
- **The Writer checks against the Bible, and proposes back to it.** The Writer validates each draft against the Bible's facts and knowledge-state — the contradiction check reads canon as ground truth (ADR-004 §4; RFC-004 §7). And when an accepted draft reveals new knowledge, the Writer's ingestion step emits it as *proposals* into the same gate (§5, §7; RFC-004 §4). The Writer both **draws from** and **contributes to** the Bible — but contribution is always gated, never a silent write (RFC-004 §4).
- **The Bible is passive with respect to the Writer.** The Bible does not call the Writer, schedule generation, or push knowledge. It holds canon and answers retrieval; the Writer initiates every interaction (RFC-004 §3). This keeps the Bible a *source of truth*, not an orchestrator — orchestration is the Writer's exclusive job (RFC-004 §2). **This RFC does not define the Writer — RFC-004 does.**

The relationship in one line: **the Writer draws truth from the Bible and proposes new truth back through review — the Bible never reaches into the Writer.**

---

## 10. Evolution Strategy

The Story Bible is designed so that a novel can grow for hundreds of chapters without any architectural change — the same promise the whole system makes (RFC-001 §7).

- **A new kind of canonical knowledge is a new `type`, never a new ledger table.** When a work needs to track a new kind of truth (a new category of world fact, a new craft signal, a new thread dimension), that is a new Entry `type` string in RFC-002's governed vocabulary plus an Analyst facet that proposes it — absorbed automatically by the Store, retrieval, the editor, and the review queue (RFC-002 §9.1; RFC-008 §9). It is **never** a new Bible ledger, table, or subsystem (ADR-004 §2; RFC-001 §8.5).
- **The Bible grows in content, not in structure.** Day to day, the Bible grows the way §7 describes — new and superseded Entries flowing through the continuity loop — while the underlying model stays fixed (RFC-002 §4; ADR-004 §1). The evolution surface is *typed data and Analyst facets*, the two cheapest things in the system to change (RFC-001 §2.4, §7).
- **Richer continuity is a richer Analyst facet, not a Bible feature.** Sharper fact extraction, better promise tracking, or a new relationship dimension is a new or improved **Analyst facet** producing the same proposed-Entry shape into the same gate (RFC-008 §9; ADR-004 §2). The Bible does not gain code; the extraction that fills it gains a prompt.
- **Deferred structure waits for a real, visible trigger.** The parts of the Bible most likely to strain prose-first storage — the knowledge matrix, the promise ledger, the timeline, whose checks do arithmetic and graph-like lookups — are the named candidates for the *one sanctioned escape valve*: promoting a `type` to its own structured table **only** when its deterministic checks start doing "parsing gymnastics" (RFC-002 §9.4, §10.3; ADR-003 §6; ADR-004 §5–§6). This is cheap precisely because everything routes through one Store, and it is the only place the Bible's structure grows later. Speculative promotion is forbidden (RFC-002 §10.3). *The promotion path is Defined in the corresponding RFC.*

---

## 11. Architectural Risks

The living-canonical-Bible design is a strong bet; honesty requires naming its failure modes and the guard on each.

### 11.1 Can the Story Bible become too large?

**Yes.** A long novel accumulates thousands of facts, promises, and summaries; by late chapters the Bible far exceeds any context window and, unmanaged, would make every retrieval slower and every prompt noisier (ADR-004 §2, §5-Negative; ADR-020 §6). Size is not hypothetical — it is the guaranteed end state of a successful long work.

The guards:

- **Retrieval, not dumping.** The Bible is never loaded whole; the Store returns only the budgeted, situation-relevant slice, so per-draft context stays bounded no matter how large the Bible grows (RFC-002 §8; ADR-004 §2). Size stresses retrieval quality, not prompt size. *Retrieval is Defined in the corresponding RFC.*
- **Multi-level summaries compress the past.** Because narrative memory exists at multiple granularities (scene → chapter → arc → story-so-far), the far past can be carried at a coarseness the budget can afford rather than in full (ADR-004 §2; ADR-018 §4). *The summary levels are Defined in the corresponding RFC.*
- **Recall degradation is a Bench-gated trigger, not a redesign.** If a very large Bible degrades keyword recall, the sanctioned response is to adopt embeddings behind the single shared retrieval seam — only when the Bench proves the miss — never a second retrieval system (RFC-002 §8; ADR-018 §6).

### 11.2 Can canon become inconsistent?

**Yes — this is the failure the Bible exists to prevent, so it must be honest that the Bible can still suffer it.** Extraction is model-dependent, and a weak extractor or a careless approval can admit a fact that contradicts existing canon (ADR-004 §5-Negative, §5-Future-risks). The Bible reduces this risk sharply but does not make it impossible.

The guards:

- **The review gate is the primary defense.** Because every canon write passes through human review, the most dangerous inconsistencies — silently committed hallucinations — are structurally excluded (§5; ADR-004 §4-A). A human is the last check before a fact becomes truth.
- **The contradiction check catches violations at draft time.** The Writer validates each draft against retrieved facts and knowledge-state, so a draft that contradicts canon is caught and revised rather than shipped (ADR-004 §4; RFC-004 §7). This protects the *prose* from the canon's gaps. *The check is Defined in the corresponding RFC.*
- **Confidence and provenance let conflicts coexist and be adjudicated.** When two sources genuinely disagree, both Entries can exist with their provenance, and the more-confident one is preferred rather than one silently overwriting the other (RFC-002 §3.3; ADR-008 §7). Conflict is surfaced, not hidden.

### 11.3 How should obsolete canon be handled, and when should knowledge be retired?

Canon is not permanent truth; stories retcon, reveal, and move on. The architecture's answer is **supersession, not deletion**:

- **Obsolete knowledge is superseded, never destroyed.** When a newer fact replaces an older one, the older is marked superseded and *retained* — kept for provenance, audit, and the record of what the story once held to be true (RFC-002 §4). The Bible forgets nothing silently; it remembers what changed and why. *The supersession relationship is Defined in the corresponding RFC.*
- **Retirement is a status transition, not an erasure.** Knowledge is "retired" from active canon by being superseded or, where it was never approved, left as rejected — in both cases still present in the Store's history, out of the canon lens but not gone (§6; RFC-002 §4). Retrieval works over live canon; the archive stays available for provenance.
- **When to retire is a human, gated decision.** Because canon changes only through review (§5), retiring a fact — like establishing one — is a human judgment surfaced as a proposal, never an automatic purge (ADR-004 §5). The same gate that guards what enters canon guards what leaves it.
- **The open honesty:** promise abandonment and timeline retcons are exactly where the promise ledger and timeline are most likely to strain prose-first storage, and are therefore the leading candidates for the promote-a-type escape valve if their checks ever start doing parsing gymnastics (§10; RFC-002 §10.3; ADR-003 §6; ADR-004 §6).

---

## 12. Out of Scope

This RFC deliberately defines **none** of the following. Each is named so no later reader mistakes this document for defining it:

- **Entry schema** — the Entry's fields, the ledger `type` strings, the structured `data` facets (promise due windows, knowledge state, relationship stage, summary level), scope and status representation. *Owned by RFC-002; Defined in the corresponding RFC (the Persistence RFC).*
- **Prompt assembly** — how canon is composed into a generation prompt, block/budget assembly, the tone/theme contract's injection. *Defined in the corresponding RFC (the Prompt Architecture RFC).*
- **Retrieval** — ranking, budgeting, keyword-vs-embedding selection over the Bible. *Owned by the Store; Defined in the corresponding RFC (the Retrieval RFC).*
- **Algorithms** — extraction, deduplication, contradiction detection, timeline reasoning, summary generation. *Defined in the corresponding RFCs.*
- **UI** — the Review Card queue, the Bible browser, the "Bible updated" surfacing, editing and reversal. *Defined in the corresponding RFCs (the Review Card and UI RFCs).*
- **Generation** — how the Writer drafts against the Bible. *Owned by RFC-004; Defined in the corresponding RFC (the Writer Pipeline RFC).*
- **Validation** — the contradiction check and voice checks that read the Bible as ground truth. *Defined in the corresponding RFC.*
- **The continuity-loop mechanics, the relationship model, and the multi-level summary design** — the detailed realization of §3 and §7. *Defined in the corresponding RFCs (the Living Story Bible & Continuity Loop, Relationship System, and Retrieval RFCs).*

Wherever this document needed such a detail, it wrote **"Defined in the corresponding RFC"** (naming the topic) and stopped, by rule.

---

## 13. Dependencies

RFC-005 depends on **RFC-001**, **RFC-002**, **RFC-008**, and **RFC-004** and must conform to them; where they conflict, they govern (RFC-001 §10; RFC-002 §12; RFC-008 §12; RFC-004 §12). The following areas of the system **depend on the Story Bible** defined here — they detail its continuity, consume its canon, or govern its review, and none may override the canon-only-through-review, view-over-the-Store, consumed-not-serving boundaries established above:

| Depends on the Story Bible | Depends on it for |
|---|---|
| **The Living Story Bible & Continuity Loop RFC** | The detailed continuity-loop mechanics — extraction on acceptance, the ledgers' realization, the contradiction gate — that make §3 and §7 concrete. |
| **The Retrieval RFC** | Selecting the budgeted, situation-relevant slice of canon the Writer consumes; multi-level summary retrieval. |
| **The Writer Pipeline & Scene/Episode RFC** | Drafting against retrieved canon, checking drafts against it, and emitting ingestion proposals back through the gate. |
| **The Review Card RFC** | The human-gated approval of proposals into canon — the single write path the Bible depends on. |
| **The Relationship System RFC** | Relationship state as canonical, work-scoped knowledge planned for and checked. |
| **The Analyst-facet RFC** | The facets that extract new canonical knowledge from accepted chapters into proposals. |
| **The Persistence RFC** | The Entry model, scope/status, and the promote-a-type escape valve that the Bible's ledgers may one day use. |
| **The Bench RFC** | Measuring extraction precision and contradiction-catch quality that keep the living Bible trustworthy. |
| **The UI & Information Architecture RFC** | Surfacing canon (the Bible browser) and proposals (the Review queue) to the author. |

> The forward references above are named by title rather than by number, because the Story Bible's canon-only-through-review gate, its view-over-the-Store nature, and its consumed-by-the-Writer discipline are what those RFCs build on regardless of final numbering. Their **dependence on the human-gated canon, the one-Store model, and the living-but-not-rotting loop is fixed**; where a successor and this RFC appear to conflict on those, this RFC — and behind it RFC-001, RFC-002, RFC-008, RFC-004, and the ADR set — governs.

---

## Appendix A — Traceability

| RFC-005 Section | Primary sources |
|---|---|
| §1 Purpose | RFC-002 §1, §5; ADR-004 §2; RFC-001 §1.1 |
| §2 Why the Story Bible Exists | RFC-001 §1.2, §5; ADR-004 §1, §4–§5; ADR-018 §4 |
| §3 Responsibilities | ADR-004 §2; RFC-002 §5; ADR-018 §4; ADR-006 |
| §4 Does NOT Own | RFC-001 §2.6, §4; RFC-002 §6.1, §8; RFC-008 §3, §5; RFC-004 §3; ADR-004 §3–§4; ADR-008 §2; ADR-011; ADR-014 |
| §5 Canon Philosophy | RFC-001 §2.6, §8.2, §8.7; ADR-004 §3–§5; RFC-002 §3.4; RFC-008 §4; RFC-004 §4 |
| §6 Canon vs Working Knowledge | RFC-002 §3.4, §4; ADR-004 §2–§3; RFC-004 §5–§6 |
| §7 Living Bible Philosophy | RFC-001 §2.8, §5, §5.8; ADR-004 §1, §4–§5; RFC-008 §5; RFC-002 §4 |
| §8 Relationship to Entry Store | RFC-002 §1, §2.3, §3, §5, §6, §8, §9.1; ADR-004 §2; RFC-001 §7.1, §8.5 |
| §9 Relationship to Writer | RFC-004 §3, §4, §6, §7; RFC-002 §6.1, §8; ADR-004 §2, §4 |
| §10 Evolution Strategy | RFC-001 §2.4, §7, §8.5; RFC-002 §9.1, §9.4, §10.3; RFC-008 §9; ADR-003 §6; ADR-004 §2, §6 |
| §11 Architectural Risks | ADR-004 §2, §5–§6; RFC-002 §3.3, §4, §8, §10.3; ADR-008 §7; ADR-018 §4, §6; RFC-004 §7 |
| §12 Out of Scope | RFC-001 §9 (RFC boundary conventions) |
| §13 Dependencies | RFC-001 §10; RFC-002 §12; RFC-008 §12; RFC-004 §12 |

*End of RFC-005.*
