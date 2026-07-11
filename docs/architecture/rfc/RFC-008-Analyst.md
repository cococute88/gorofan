# RFC-008: Analyst

- **Status:** Draft
- **Date:** 2026-07-10
- **Author:** Chief Software Architect
- **Project:** AI Native Creative Workspace (`ai-creative-workspace` / "gorofan") — "나만의 로판AI + 하트픽션"
- **Conforms to:** RFC-001, RFC-002; ADR-002, ADR-008, ADR-010, ADR-003, ADR-004, ADR-013, ADR-014, ADR-018
- **Supersedes:** nothing
- **RFC layer:** Component — the extraction reference the Store, Writer, Review, and learning-capture RFCs build on

> **Reading order.** RFC-001 is the system-level reference and RFC-002 defines the Entry Store; read both first. This RFC opens the **Analyst** — the second of RFC-001's three verbs (RFC-001 §3.2) — and defines *what the Analyst is*, *why it exists as one service*, *what it owns and does not own*, and *how knowledge enters the system*. It does **not** define prompts, extraction algorithms, models, scheduling, or any implementation — each of those is named and deferred.
>
> **Source of truth.** RFC-001 and RFC-002 take precedence over this document; behind them the ADR set (`docs/architecture/adr/`) is authoritative, and the two reviews (`docs/design-review-ai-author-os.md`, `docs/architecture-final-minimal.md`) supply rationale only. Where anything here appears to conflict with RFC-001, RFC-002, or an ADR, **those win** and this document is in error.
>
> **This RFC is implementation-neutral.** It is the conceptual charter of the Analyst. Whenever an implementation detail is needed, this document writes **"Defined in a later RFC"** (naming the topic) and stops.

---

## 1. Purpose

This RFC defines the **Analyst** — the system's one mechanism for turning **text into knowledge**.

RFC-001 establishes three verbs — **Store, Analyst, Writer** (RFC-001 §2.3, §3). RFC-002 defined the Store: where knowledge lives, as prose-first, provenanced, typed **Entries** (RFC-002 §1). This RFC defines the verb that *fills* the Store: the Analyst reads source text and proposes candidate knowledge, so that everything the Store holds originated in real material — an uploaded reference, an accepted chapter, or the author's own edits — rather than being invented.

The Analyst has exactly one shape: **text in → proposed knowledge out** (RFC-001 §3.2; ADR-002 §2; ADR-008 §2). This RFC explains:

- **what the Analyst is** — one stateless extractor, not a family of analysis engines;
- **why it exists** — why extraction is centralized into a single service;
- **what it owns** — turning text into candidate Entries, and the facet prompts that define what to look for;
- **what it explicitly does NOT own** — writing, retrieval, generation, storage, and the human decision that promotes a proposal to canon;
- **how knowledge enters the system** — the path from source text through extraction and review into canon.

It does **not** define the extraction prompts themselves or the algorithms that run them (§11).

---

## 2. Why the Analyst Exists

### 2.1 Why extraction is centralized

Every kind of knowledge in the system arrives the same way: some *text* is read, and *candidate knowledge* comes out of it. A reference novel is read for a character's voice; an accepted chapter is read for the new facts it established; a batch of author edits is read for the preferences they reveal. These look like three different features, but structurally they are **one operation** — *text in → entries out* — differing only in what text goes in and what scope the result is filed under (ADR-008 §1; `architecture-final-minimal.md` §4).

Centralizing that operation into a single Analyst is a direct application of RFC-001's governing rule: **the transformer is written once; what it looks for is a versioned prompt** (RFC-001 §2.4). The Analyst is the "written once" code; each *kind* of extraction is a prompt file — a **facet** (§8). Centralization is what lets years of new analytical capability arrive as prompt files rather than new services (RFC-001 §7.3).

### 2.2 Why ONE Analyst instead of multiple analysis engines

This is the load-bearing decision of this RFC, and it is deliberate. The naive design grows a separate engine per source of learning: a *Reference Intelligence* engine for uploads, a *Bible ingestion* engine for accepted chapters, an *edit-diff learning* engine for author edits (the R1 / R4 / R25 mechanisms of the design review). Both project reviews establish that **these three are the same operation** and must collapse into one service (ADR-008 §1–§2; ADR-002 §2; `architecture-final-minimal.md` §4).

There is one Analyst, not three engines, for four reasons:

- **They share one shape.** All three are *text in → proposed Entries out*. What differs is the **input** and the **scope** it is filed under — not the operation. Three engines would be three implementations of one verb (ADR-008 §1; ADR-002 §2).
- **Three engines are the debt bomb the architecture exists to prevent.** "An engine per feature" is precisely the failure mode RFC-001 names (RFC-001 §1.2). Each named engine is a service to operate, code to maintain, and a boundary to keep in sync. Three parallel learning systems is three times the maintenance for one operation (ADR-008 §5; `architecture-final-minimal.md` §4).
- **One extractor keeps the output uniform.** Because there is one Analyst, every piece of extracted knowledge is the same kind of thing — a proposed Entry with provenance and confidence (RFC-002 §3) — flowing into the same review queue and the same Store. Three engines would risk three subtly different output contracts, three provenance conventions, three review paths.
- **New analytical depth becomes a prompt, not an engine.** With one Analyst, a richer understanding of references or preferences is a **new facet** — a prompt file over the same extractor, producing the same shape of proposals (RFC-001 §7.3; §8, §9 here). With separate engines, new depth means new code in whichever engine, and the temptation to spawn a fourth.

RFC-001 states the principle as a hard constraint: **a new capability is an entry `type`, a prompt stage, or a facet — not a new named engine, module, or service** (RFC-001 §8.5). "Analyst" is one verb; the many things it can extract are prompts, not engines. *The one guardrail the Board attached to this — the Analyst must stay a **stateless transformer over explicit inputs** and must not accrete its own private indexes or caches — is a boundary condition, discussed in §4 and §10 (RFC-001 §4.2; ADR-002 §6; ADR-008 §5).*

---

## 3. Analyst Responsibilities

The Analyst's ownership is exclusive (RFC-001 §4.2). This section defines *responsibilities* only — no prompts, no algorithms.

### 3.1 What the Analyst owns

- **The single extraction operation** — *text → proposed Entries* — across every input it serves (RFC-001 §4.2; ADR-002 §2). This is the whole of what the Analyst does; everything below is a facet of it.
- **Reference analysis.** Reading uploaded reference material the author owns and distilling it into provenanced knowledge — the character, world, style, emotion, and craft knowledge that is the product's core creative input (ADR-008 §1–§2). *Reference-derived knowledge is central, not peripheral* (ADR-008 §1). *Which categories it produces is governed by RFC-002 §5.*
- **Story Bible ingestion.** Reading an accepted chapter and proposing the new facts, knowledge-state, promises, relationship movement, and summaries it established — the material that keeps long fiction coherent across hundreds of chapters (ADR-008 §2; RFC-001 §5). *The ledger internals these feed are Defined in the Living Story Bible RFC.*
- **Edit-diff analysis.** Reading the accumulated difference between what the system drafted and what the author accepted, and distilling the author's revealed preferences (ADR-010 §2). This is the "learning" the architecture permits — transparent, curated, revertible — and it is a *later distillation pass*, not an online learner (§10.3; ADR-010 §1–§2). *Capture-vs-distillation timing is Defined in the Learning Capture RFC.*
- **Knowledge extraction, uniformly.** In every path above, the operation is the same: identify candidate knowledge in text and emit it as proposed Entries, each tagged with **provenance and confidence** (RFC-002 §3.2, §3.3; ADR-008 §3). Provenance and confidence tagging of what it produces is the Analyst's responsibility (RFC-001 §4.2).
- **The facet prompts** that define *what to look for* in each path (RFC-001 §4.2; §8 here). The Analyst owns the catalog of facets as a governed prompt library — *their contents are Defined in the Analyst-facet and Prompt-Architecture RFCs.*

### 3.2 The three input paths, at a glance

The three responsibilities above are one operation over three inputs, differing only in input and the scope the output is filed under (ADR-008 §2; `architecture-final-minimal.md` §4). This RFC states the *shape* of that mapping conceptually; **it defines no scopes, columns, or facet contents** (those belong to RFC-002 and later RFCs):

| Input path | Filed under (scope) | Produces (see RFC-002 §5) | Enters as |
|---|---|---|---|
| **Reference analysis** — owned material the author uploaded | collection-level knowledge | Character, World, Style, Emotion, and craft knowledge | (path-dependent — see §7) |
| **Story Bible ingestion** — an accepted chapter | work-level knowledge | Fact, Knowledge, Promise, Relationship, Summary | (path-dependent — see §7) |
| **Edit-diff analysis** — draft-vs-accepted author edits | the author's distilled taste | Preference | (path-dependent — see §7) |

*Whether a given path's output enters as canon or as a proposal is a review-gate question, handled in §7. The concrete scope vocabulary is Defined in RFC-002 / the persistence RFC; the facet catalog is Defined in a later RFC.*

---

## 4. What the Analyst Does NOT Own

The Analyst's non-ownership is as binding as its ownership; ambiguity here re-creates engine sprawl (RFC-001 §4). The Analyst is a **stateless transformer over explicit inputs** and nothing more (RFC-001 §4.2; ADR-002 §2).

- **Writing / generation.** The Analyst never produces prose for the reader. Generating draft fiction is the Writer's job (RFC-001 §3.3, §4.3). The Analyst reads text and emits *knowledge*, never narrative output.
- **Retrieval.** The Analyst never selects knowledge for a prompt. Answering *"what knowledge is relevant right now?"* is the Store's single retrieval function (RFC-002 §6.1, §8; RFC-001 §3.1). The Analyst puts knowledge *in* (as proposals); it does not read it back out for assembly.
- **Prompt execution.** The Analyst does not own the prompt-assembly machinery or the model-calling substrate; those are shared substrate the services use (RFC-001 §3, §4.5). *Prompt assembly is Defined in the Prompt Architecture RFC.*
- **Storage.** The Analyst holds **no persistence of its own**. All persisted knowledge lives in the Store (RFC-002 §6.1). The Analyst is stateless: given the same input it produces the same proposals, and it keeps no private long-lived state, index, or cache between runs (RFC-001 §4.2; ADR-002 §6; ADR-008 §5). This is the one guardrail the Board explicitly attached to centralizing extraction (§2.2, §10.1).
- **Human review — the promotion decision.** The Analyst emits **proposed** knowledge; it never decides that a proposal becomes canon. That decision is human review, the single gated write path into canon (RFC-001 §2.6, §4.2; RFC-002 §3.4). The Analyst proposes; the human disposes. *The review interaction is Defined in the Review Card RFC.*
- **Quality judgment.** The Analyst does not score, critique, or A/B its own output; measuring the quality of extraction (and of the prompt changes that drive it) is the Bench's job, out-of-band (RFC-001 §3.4, §4.4). *Bench design is Defined in the Bench RFC.*

The one-way discipline that governs the whole system applies to the Analyst without exception: **it reads text and writes proposals; it never writes canon** (RFC-001 §2.6; ADR-002 §2).

---

## 5. Knowledge Sources

The Analyst is defined by the sameness of its operation *across different inputs*. This section describes those inputs **conceptually** — what each source is and what kind of understanding it carries. It defines **no ingestion mechanics, formats, or pipelines** (those are Defined in later RFCs).

- **References.** Material the author uploads and owns — favourite novels, style samples, character studies. This is the product's **core creative input**: reference-derived knowledge, not hand-filled forms, is the architecture's leading strength (ADR-008 §1). References describe *how good writing in this space reads* and *who these characters are*, and they are read once, on import, to seed the Store. **Copyright discipline is intrinsic:** the Store holds *distilled, provenanced guidance* from material the author owns — never verbatim third-party text echoed back into output (ADR-008 §2, §6). *Segmentation and copyright screening are Defined in later RFCs.*
- **Accepted chapters.** Once the author accepts a chapter as canonical story, its text becomes a source: the Analyst reads it for the new facts it established, what each character now knows, what promises it planted or paid, how relationships moved, and how to summarize it. This is the **continuity loop** — accepted output feeds the next draft's ground truth (RFC-001 §5, §5.8). This source is what keeps chapter 40 consistent with chapter 3.
- **User edits.** The difference between what the system drafted and what the author accepted is itself a source of knowledge — a signal of the author's taste. It must be **captured from day one**, because a diff never stored can never be recovered; the *distillation* of those diffs into Preference knowledge is a deferred, periodic pass (ADR-010 §2; `architecture-final-minimal.md` §4). The Analyst owns the distillation; *capture timing and the substrate that records diffs are Defined in the Learning Capture RFC.*
- **Character chat.** Conversation with a character is a latent source: a line the author bookmarks in chat as *"this is exactly how she talks"* is knowledge worth keeping. When such knowledge is captured, it flows through the **same Analyst-to-Entry path** — it becomes a proposed Entry like any other — never by widening the chat-private memory into a second knowledge store (RFC-002 §5; ADR-018 §2, §6). *The chat-bookmark capture surface is Defined in a later RFC.*
- **Future sources.** New sources will appear (for example, structured author input, or an external note). The architecture's promise is that a new source is a **new input to the one Analyst**, not a new engine: same operation, same proposed-Entry output, same review gate (§9; RFC-001 §7.3). A source that cannot be expressed as *text in → proposed Entries out* is the signal to reconsider — not to spawn a parallel analyzer (§10.2).

---

## 6. Analyst Outputs

The Analyst produces exactly one kind of output: **proposed knowledge, expressed as Entries** — as defined in RFC-002. This RFC **does not redefine the Entry**; it points to RFC-002 for the model and its commitments.

- **The output is Entries.** Every extraction result is a prose-first, typed Entry carrying provenance and confidence (RFC-002 §3). The Analyst never emits a bespoke output shape; there is one knowledge representation, and the Analyst produces it (RFC-002 §2.3).
- **The kinds of knowledge produced span the Entry categories.** Reference analysis yields Character, World, Style, and Emotion knowledge; chapter ingestion yields Fact, Knowledge, Promise, Relationship, and Summary knowledge; edit-diff analysis yields Preference knowledge (RFC-002 §5; ADR-008 §2; ADR-010 §2). **These categories and their governed `type` vocabulary are owned by RFC-002 — this RFC does not define them.**
- **Provenance and confidence are mandatory on every output.** The Analyst tags each proposed Entry with where it came from and how strongly it is believed (RFC-002 §3.2, §3.3; ADR-008 §3). This is what makes extracted knowledge *trustworthy rather than merely present*, powers the "why does the AI think this?" surface (ADR-014), and lets genuinely-conflicting extractions coexist and be adjudicated by confidence rather than silently overwritten (ADR-008 §7).
- **The output is a proposal, not a fact-in-canon.** By default the Analyst emits **proposed** Entries — Review Cards — never canon directly (RFC-002 §3.4; §7 here). The single exception path (reference-derived knowledge the author curated into a collection) is a review-gate matter handled in §7 and Defined in the Analyst-facet and Review RFCs.

The Analyst adds nothing to the knowledge model; it is a *producer* for the model RFC-002 already defines.

---

## 7. Analysis Lifecycle

Knowledge enters the system along one high-level path. This section names the stages only; **each stage's mechanics are Defined in the RFC noted.**

```
   input       ── source text: reference / accepted chapter / edit diff
      │
      ▼
   extraction  ── the Analyst reads text, proposes candidate knowledge
      │            (facet prompts define what to look for — §8)
      ▼
   proposal    ── candidate knowledge emitted as proposed Entries
      │            (RFC-002 §3.4 — a proposal is a Review Card)
      ▼
   review      ── a human accepts / edits / rejects        (Defined in the Review Card RFC)
      │
      ▼
   canon       ── approved knowledge joins the Store's source of truth
                   (RFC-002 §4 — immediately available to retrieval)
```

- **Input.** A source (§5) supplies text. The Analyst does not seek out its own inputs; inputs are handed to it — it is a transformer over explicit inputs (§4).
- **Extraction.** The Analyst applies the relevant facets (§8) to the text and identifies candidate knowledge. This is the Analyst's whole job. *The extraction prompts and how they run are Defined in later RFCs.*
- **Proposal.** Candidate knowledge is emitted as **proposed** Entries with provenance and confidence (§6). A proposed Entry is, by RFC-002, a Review Card (RFC-002 §3.4).
- **Review.** A human accepts, edits, or rejects each proposal. This is the single human-gated write path into canon (RFC-001 §2.6). *Defined in the Review Card RFC.*
- **Canon.** Approved knowledge becomes canonical in the Store and is immediately available to future retrieval and future drafts (RFC-002 §4).

**One nuance the lifecycle must state honestly:** not every path traverses the same gate identically. Story-derived ledger knowledge (facts, promises, relationship movement) always passes through *proposal → review* before canon, because it is model-inferred and must be checked. Reference-derived knowledge the author deliberately uploaded and curated may enter differently, since the human already exercised judgment by choosing and owning the source (ADR-008 §2; RFC-002 §4). **Either way the invariant holds: canon is only ever the result of human judgment, and the Analyst itself never writes canon** (RFC-001 §2.6). *Which path enters as canon vs. proposal is Defined in the Analyst-facet and Review RFCs, not here.*

---

## 8. Facet Philosophy

The Analyst is one extractor, but *what it looks for* varies enormously — a character's voice, a world's naming rule, a chapter's new facts, an author's sentence-length preference. Each distinct thing-to-look-for is a **facet**: an independent unit of analysis, realized as a prompt file (ADR-008 §2; RFC-001 §7.2–§7.3). This section explains *why* the Analyst is divided into facets; it **does not describe individual facets or define any prompt contents** (§11).

- **A facet is a prompt file, not a code path.** The single most important rule of the architecture is that what is tuned weekly lives in versioned prompt files, not in code (RFC-001 §2.4, §8.3). *What to extract* is exactly this kind of weekly-tuned behavior, so each facet is a prompt file the extractor runs — never a branch in the Analyst's code (ADR-008 §2; ADR-013). The signal catalog the reviews describe (voice, prose style, emotion repertoire, chapter-ending taxonomy, naming morphology, and so on) *"was never an architecture, it was always a prompt library, and now it's explicitly that"* (`architecture-final-minimal.md` §4).
- **Facets are independent.** Each facet looks for one thing and can be added, revised, or removed without touching the others or the extractor. Independence is what makes the Analyst's capability grow additively: a new facet is a new file, not a modification of existing behavior (§9). It also makes each facet **individually Bench-measurable** — a prompt change to one facet can be A/B-tested in isolation before it ships (RFC-001 §2.9, §8.9).
- **Facets keep the extractor small.** Because the *variety* of analysis lives in facet files, the extractor code stays one small, stable, "written once" thing (RFC-001 §2.4). The Analyst does not grow a method per kind of knowledge; it grows a prompt file per kind of knowledge, and the prompt files are the cheapest thing in the system to change.
- **The facet catalog is governed, like the `type` vocabulary.** Facets map to the Entry categories they produce (RFC-002 §5). Adding a facet is a deliberate act (a prompt-library addition), keeping the catalog coherent rather than sprawling — the analytical analogue of RFC-002's closed, governed `type` vocabulary (RFC-002 §3.5). *The facet catalog and its contents are Defined in the Analyst-facet RFC and the Prompt Architecture RFC.*

The net effect mirrors the whole architecture: the Analyst's *evolution surface is prompt files*, and its *core is written once* (RFC-001 §7).

---

## 9. Evolution Strategy

The Analyst is designed so that new analytical capability arrives without architectural change — the same promise the whole system makes (RFC-001 §7).

- **New analytical depth is a new facet.** A richer understanding of references, a new craft signal to extract, a sharper reading of the author's preferences — each is a **new facet prompt** over the same extractor, producing the same proposed-Entry shape into the same review queue (RFC-001 §7.3; ADR-008 §5; §8 here). No new pipeline, no new store, no new service.
- **A new knowledge kind pairs a facet with a `type`.** When the author wants the Analyst to extract a genuinely new *kind* of knowledge, that is a new Entry `type` string in RFC-002's governed vocabulary (owned by RFC-002) plus a facet that produces it. The Store, retrieval, the review queue, and the one editor absorb it automatically (RFC-002 §9.1; RFC-001 §7.1). It is **never** a new analysis engine and **never** a new table.
- **A new source is a new input, not a new analyzer.** A new source of text (§5, "Future sources") is wired as another input to the one Analyst, reusing the same operation and the same output contract (§2.2, §5). The extractor does not fork per source.
- **The extractor itself stays still.** The loop that reads text and emits proposals is "written once" code; years of evolution are commits to facet prompts and new `type` strings, not changes to the Analyst's structure (RFC-001 §2.4, §7). Minimizing change to the extractor is what keeps a single maintainer able to own it (RFC-001 §1.1).
- **Deferred capabilities wait for a real trigger.** Some richer analyses (embedding-assisted extraction/retrieval, a distinctiveness-versus-genre facet, edit-diff back-propagation) are **named but deferred** until a concrete or Bench-measured need appears — not built speculatively (ADR-008 §7, §6; ADR-010 §6; `architecture-final-minimal.md` §6). When such a capability arrives, it must reuse the shared retrieval seam rather than spawn a second analysis subsystem (§10; ADR-008 §5–§6).

---

## 10. Architectural Risks

The one-Analyst design is a strong bet; honesty requires naming its failure modes and the guards on each.

### 10.1 Can the Analyst become too large?

**Yes — this is the central risk.** Centralizing all extraction into one service invites that service to accrete: more facets, then facet-specific code, then private caches and indexes, until the "one small extractor" has quietly become a subsystem with its own state (ADR-002 §6, "future risks"; ADR-008 §5). The Board named this precisely: the Analyst *accreting stateful caches/indexes could drift toward its own subsystem.*

The guards:

- **The Analyst must stay a stateless transformer over explicit inputs.** It owns no persistence and keeps no private long-lived state between runs (§4; RFC-001 §4.2; ADR-002 §6). All state lives in the Store. A stateless transformer, however many facets it runs, stays small; a stateful one does not.
- **Variety lives in facets, not in the extractor.** New analytical capability is a prompt file, not code in the Analyst (§8, §9). The extractor's own surface stays "written once." The moment the Analyst grows large per-facet code branches is the moment this guard has been breached.
- **The mapping to substrate stays explicit.** The Analyst uses shared substrate (prompt assembly, model calls, jobs) but owns none of it (§4; RFC-001 §4.5). It does not absorb substrate responsibility to "simplify."

### 10.2 When should a capability become an independent service?

The default answer is **almost never** — the whole point of one Analyst is that new capability is a facet, not a service (§2.2, §9; RFC-001 §8.5). Spinning out a service is an exceptional act with a specific trigger, not a growth habit.

The honest trigger, adapted from the God-Object analysis the Board applied to the Store (ADR-002 §6; RFC-002 §10.3): **a capability earns its own service only when it becomes genuinely, persistently stateful in a way the stateless-transformer model cannot express** — for example, if extraction one day requires a standing, incrementally-maintained embedding index that must live and be updated between runs. At that point the capability has stopped being *text in → entries out* and the God-Object analysis must be re-run explicitly (ADR-002 §6). Two disciplines bound this:

- **The trigger must be real and visible, not anticipated.** Speculative extraction services are forbidden; the capability must *demonstrably* need standing state before it is extracted (ADR-008 §6; RFC-001 §7.4).
- **A spun-out capability must reuse shared seams, never spawn a parallel one.** If embedding-assisted analysis is ever validated, it uses the single shared retrieval seam — never a second, competing RAG or a parallel reference analyzer (ADR-008 §5–§6; ADR-018 §2).

### 10.3 How should analysis cost be controlled?

Extraction is model work, and model work is latency and money (ADR-008 §5, "facet extraction quality is model-dependent"). Unbounded analysis — re-running every facet over every input eagerly — is a real cost risk for a system whose founding constraint is **zero infrastructure cost beyond LLM usage** (RFC-001 §1.2, §2.1). The architecture controls this in ways this RFC states as principle (the mechanics are deferred):

- **Distill later, not continuously.** The most cost-sensitive path — edit-diff learning — is explicitly a **periodic distillation pass, not an online per-edit pipeline** (ADR-010 §2, §4; §5 here). Capture is cheap and immediate; the expensive analysis runs occasionally. This is the single most important cost discipline, and it is already an accepted decision.
- **Analysis is out-of-band and non-blocking.** Extraction runs as background work, not on the reader's critical path, so its cost is amortized rather than paid per interaction (ADR-008 §5; ADR-018 §5). *The background-job substrate is Defined in later RFCs.*
- **Earn each facet.** Because facets are individually Bench-measurable (§8), a facet that does not demonstrably improve quality is not run — cost is spent only where measurement justifies it (RFC-001 §2.9; ADR-008 §6). New model-dependent depth (a costlier facet, embeddings) is Bench-gated before it ships.
- **Prefer keyword-first, defer embeddings.** The architecture avoids standing embedding infrastructure until keyword retrieval demonstrably misses, measured on the Bench (ADR-008 §5; ADR-018 §2). This keeps the Analyst's steady-state cost low by default.

*Concrete cost budgets, batching, scheduling, and job policy are Defined in later RFCs (§11).*

---

## 11. Out of Scope

This RFC deliberately defines **none** of the following. Each is named so no later reader mistakes this document for defining it:

- **Prompt design** — the structure, blocks, and budgeting of any Analyst prompt. *Defined in the Prompt Architecture RFC.*
- **Extraction prompts** — the contents of any facet, the signal catalog's actual text, what each facet instructs the model to find. *Defined in the Analyst-facet RFC.*
- **Models** — which model performs extraction, provider selection, local-vs-hosted analysis. *Defined in the Provider Adapter RFC.*
- **Algorithms** — segmentation, classification, aggregation, deduplication, frequency-weighted merge, confidence computation, conflict handling. *Defined in later RFCs.*
- **Batch jobs & scheduling** — how extraction is queued, batched, retried, throttled, or scheduled; when the periodic distillation pass runs. *Defined in the persistence / jobs and Learning Capture RFCs.*
- **Implementation** — the extractor's code, its data contracts, storage of intermediate results, the diff-capture columns, ingestion pipelines. *Defined in later RFCs.*
- **The Entry model** — fields, `type` strings, scopes, provenance/confidence representation. *Owned by RFC-002 and the persistence RFC — not redefined here.*
- **Retrieval, review UX, and Bench mechanics** — the Store's retrieval function, the Review Card interaction, and the evaluation harness. *Defined in their respective RFCs.*

Wherever this document needed such a detail, it wrote **"Defined in a later RFC"** (naming the topic) and stopped, by rule.

---

## 12. Dependencies

RFC-008 depends on **RFC-001** and **RFC-002** and must conform to them; where they conflict, they govern (RFC-001 §10; RFC-002 §12). The following areas of the system **depend on the Analyst** defined here — they consume its proposals, its provenance, or its facet output, and none may override the one-extractor, proposals-not-canon, stateless-transformer boundaries established above:

| Depends on the Analyst | Depends on it for |
|---|---|
| **The Store (RFC-002)** | Receiving proposed Entries — the Analyst is the Store's principal producer; the Store holds what the Analyst proposes and a human approves (RFC-002 §7, §12). |
| **The Living Story Bible & Continuity Loop RFC** | Chapter-ingestion output — the fact / knowledge / promise / relationship / summary proposals that feed the ledgers and the continuity loop. |
| **The Writer Pipeline RFC** | The ingestion step that emits new facts/promises from accepted output back into the review gate; and, indirectly, the reference-derived exemplars the Writer retrieves. |
| **The Review Card RFC** | The stream of proposed Entries the human reviews — the Analyst is the primary source of Review Cards. |
| **The Learning Capture & Distillation RFC** | The edit-diff distillation pass that turns captured diffs into Preference Entries. |
| **The Character / World DNA Organization RFC** | Reference-derived character and world knowledge, organized for prompts. |
| **The Retrieval RFC** | Indirectly — retrieval ranks and returns exactly the provenanced, confidence-tagged Entries the Analyst produced. |
| **The Bench RFC** | Measuring extraction quality and A/B-testing facet prompt changes out-of-band. |

> The forward references above are named by topic rather than by number, because the Analyst's proposals, provenance discipline, and stateless-transformer boundary are what those RFCs build on regardless of final numbering. Their **dependence on the one-extractor model, the proposals-not-canon gate, and the facets-as-prompts principle is fixed**; where a successor and this RFC appear to conflict on those, this RFC — and behind it RFC-001, RFC-002, and the ADR set — governs.

---

## Appendix A — Traceability

| RFC-008 Section | Primary sources |
|---|---|
| §1 Purpose | RFC-001 §3.2; RFC-002 §1; ADR-002 §2; ADR-008 §2 |
| §2 Why the Analyst Exists / ONE Analyst | RFC-001 §2.3, §2.4, §7.3, §8.5; ADR-002 §2; ADR-008 §1–§2; `architecture-final-minimal.md` §4 |
| §3 Responsibilities | RFC-001 §4.2; ADR-002 §2; ADR-008 §2; ADR-010 §2; RFC-002 §3, §5 |
| §4 Does NOT Own | RFC-001 §2.6, §3.3, §4.2, §4.5; RFC-002 §3.4, §6.1, §8; ADR-002 §2, §6; ADR-008 §5 |
| §5 Knowledge Sources | ADR-008 §1–§2, §6; ADR-010 §2; ADR-018 §2, §6; RFC-001 §5; RFC-002 §5 |
| §6 Analyst Outputs | RFC-002 §2.3, §3, §5; ADR-008 §3, §7; ADR-010 §2; ADR-014 |
| §7 Analysis Lifecycle | RFC-001 §2.6, §5; RFC-002 §3.4, §4; ADR-008 §2 |
| §8 Facet Philosophy | RFC-001 §2.4, §2.9, §7.2–§7.3, §8.3, §8.9; ADR-008 §2; ADR-013; `architecture-final-minimal.md` §4 |
| §9 Evolution Strategy | RFC-001 §7; RFC-002 §9.1; ADR-008 §5–§6; ADR-010 §6 |
| §10 Architectural Risks | ADR-002 §6; ADR-008 §5–§6; ADR-010 §2, §4; ADR-018 §2; RFC-001 §1.2, §2.1, §2.9, §7.4; RFC-002 §10.3 |
| §11 Out of Scope | RFC-001 §9 (RFC boundary conventions) |
| §12 Dependencies | RFC-001 §10; RFC-002 §12 |

*End of RFC-008.*
