# RFC-011: Human Review & Review Card

- **Status:** Draft
- **Date:** 2026-07-10
- **Author:** Chief Software Architect
- **Project:** AI Native Creative Workspace (`ai-creative-workspace` / "gorofan") — "나만의 로판AI + 하트픽션"
- **Conforms to:** RFC-001, RFC-002, RFC-008, RFC-004, RFC-005, RFC-006, RFC-007, RFC-003, RFC-009, RFC-010; ADR-011, ADR-002, ADR-004, ADR-003, ADR-008, ADR-010, ADR-014
- **Supersedes:** nothing
- **RFC layer:** Component — the human-in-the-loop write-path reference the Story Bible, Analyst, Writer, and UI RFCs build on

> **Reading order.** RFC-001 is the system-level reference; RFC-002 the Entry Store; RFC-008 the Analyst; RFC-004 the Writer; RFC-005 the Story Bible; RFC-006 the Relationship model; RFC-007 Character DNA; RFC-003 Store-wide Retrieval; RFC-009 the Prompt System; RFC-010 the Bench. Read them first. This RFC defines the **Human Review System** — how AI proposals become trusted canonical knowledge — and the **Review Card**, the primary interaction model between the AI and the human. It explains *why Human Review exists*, *why the Review Card exists*, and *what they own and do not own*. It does **not** define UI implementation — layout, components, animations, or interaction detail are named and deferred.
>
> **Source of truth.** The RFC documents take precedence over this one, in order (RFC-001, then RFC-002…RFC-010); behind them the ADR set (`docs/architecture/adr/`) is authoritative, and the two reviews (`docs/design-review-ai-author-os.md`, `docs/architecture-final-minimal.md`) supply rationale only. Where anything here appears to conflict with an RFC or an ADR, **those win** and this document is in error.
>
> **This RFC is implementation-neutral.** It defines the *review gate* and the *interaction pattern*, not the screen. Whenever an implementation detail is needed, it writes **"Defined in the corresponding RFC"** (naming the topic) and stops. It defines no UI.

---

## 1. Purpose

Everything the system knows is knowledge it *acts on* — retrieved into drafts, checked against, spoken from. If the AI could write that knowledge directly, a single hallucinated fact would silently corrupt the very canon that feeds every future generation (RFC-005 §5; ADR-004 §4-A). The **Human Review System** is the discipline that prevents this: it is the single gate through which an AI *proposal* becomes *trusted canonical knowledge*, and it makes a human — the final judge of quality — the one who confers that trust (RFC-001 §2.6, §2.7).

The **Review Card** is the primary interaction model that makes the gate usable. Every AI-proposed change to canon — a new fact, a promise, a relationship movement, a piece of world or character knowledge — is *the same kind of thing* (an Entry with `status=proposed`) and is reviewed the *same way*: presented with what is proposed and where it came from, accepted, edited-then-accepted, or rejected (ADR-011 §2). One pattern governs the product's riskiest operation.

This RFC explains:

- **why Human Review exists** — why the AI never directly writes canon, and why human approval is fundamental;
- **why the Review Card exists** — why every AI proposal uses one interaction model instead of many editors;
- **what they own** — approval, editing, rejection, the conferral of trust, and the creation of canon;
- **what they explicitly do NOT own** — extraction, generation, prompt execution, retrieval, and storage.

It does **not** define the review screen, its components, or its interactions (§13).

---

## 2. Why Human Review Exists

### 2.1 Why the AI never directly writes canon

Canon is the source of truth that feeds all downstream generation — retrieved into every relevant draft and chat turn, and used as the ground truth the Writer's checks test against (RFC-005 §5; RFC-003). That gives a canon error a uniquely destructive property: it does not cause one bad output, it **compounds**. A wrong fact written to canon is silently retrieved into future drafts, which are built on it, which are accepted, which deepen the error — the compounding-hallucination failure a long serialization cannot survive (ADR-004 §4-A; RFC-005 §5). Unattended write-back to the source of truth is therefore *the highest-regret operation in the entire system* (RFC-005 §5). The AI never writes canon directly because the cost of a single silent mistake is not local — it is the slow rot of the foundation everything else stands on.

This is why "auto-apply with undo" is explicitly rejected: undo-after-the-fact places the burden of *catching* an error on the user *after* canon is already polluted and already contaminating generation. By the time the user notices, downstream outputs are corrupted. The gate must be **before** canon, not a cleanup after it (ADR-011 §4-A).

### 2.2 Why human approval is fundamental

Human approval is not a courtesy or a convenience feature; it is the **one-way discipline that governs the whole architecture**: the model *reads canon freely but writes to canon only through review* (RFC-001 §2.6, §8.7; ADR-002 §2). Every producer in the system obeys it — the Analyst emits proposals, never canon (RFC-008 §4); the Writer emits proposals, never silent canon writes (RFC-004 §4); the Story Bible never self-mutates (RFC-005 §5). Human Review is the single place that discipline is exercised. It is fundamental for three reasons:

- **The human is the final judge of quality.** The product's whole stance is that the system proposes and the human disposes; there are no automated gates over the user's own creative truth (RFC-001 §2.7). Review is where that authority lives.
- **It is the *only* write path into canon.** The gate is architectural, not optional chrome — bypassing it is forbidden, and a feature that quietly wrote canon without review would silently break the architecture's core safety rule (ADR-011 §2, §6; ADR-002 §2).
- **It makes canon trustworthy over years.** Because every canonical fact was seen and approved by a human, and the disposition is recorded, canon stays trustworthy across a multi-year project rather than accumulating unvetted machine assertions (ADR-011 §5; RFC-002).

---

## 3. Proposal is Cheap, Canon is Expensive

This is one of the core principles of the AI Author OS, stated here as a dedicated commitment: **proposals must be easy and abundant to generate; canonical knowledge must require deliberate human approval.** The asymmetry is the point, and it is what makes the whole knowledge flywheel both *safe* and *productive*.

### 3.1 Why proposals are cheap

A proposal changes *nothing* the system acts on. A proposed Entry is not ground truth: it is not retrieved as canon, the Writer's checks do not trust it, and it influences no generation until a human approves it (RFC-002; RFC-005 §6). Because proposing is consequence-free until approval, the system can afford to propose **generously** — the Analyst can extract every candidate fact from an accepted chapter, the Writer can surface every newly-observed promise, without any risk that a wrong guess corrupts anything (RFC-008 §3; RFC-004 §4). Proposals are cheap precisely because they are *inert*: abundant, low-stakes, reversible-by-default because they were never real. Generating them liberally is a feature, not a hazard.

### 3.2 Why canon is expensive

Canon is the opposite: it is the knowledge every future generation is built on, so admitting something to canon has *compounding* consequences (§2.1; RFC-005 §5). "Expensive" here does not mean effortful to click — it means **deliberate**: canon must be earned by a conscious human judgment, never conferred automatically, because the cost of a wrong canon entry is paid repeatedly and silently downstream (ADR-004 §4-A). The deliberateness *is* the safeguard. Making canon cheap to create — auto-applying proposals — would collapse the asymmetry and reintroduce exactly the compounding corruption the gate exists to prevent (ADR-011 §4-A).

### 3.3 Why the asymmetry matters

The two halves depend on each other. Because proposing is cheap, the AI can feed the flywheel abundantly; because canonizing is deliberate, that abundance never pollutes the source of truth. Get the asymmetry wrong in either direction and the product breaks: make proposing expensive (block the flow to adjudicate every one) and the user disables the flywheel (§4.2, §12); make canonizing cheap (auto-accept) and canon rots (§2.1). The architecture's answer is to keep them firmly apart — **generate freely, approve deliberately** — which is exactly what the Review Card operationalizes (§4, §7). This principle is why a proposal is a low-friction, non-blocking Card the user triages at leisure, while crossing into canon is a distinct, explicit, recorded act (ADR-011 §2).

The principle in one line: **propose abundantly because proposals are inert; canonize deliberately because canon compounds.**

---

## 4. Why the Review Card Exists

### 4.1 Why every AI proposal uses one interaction model

Many decisions across the architecture depend on the same primitive — *AI proposes, human disposes* — and they could each have invented their own approval affordance: one for Bible ingestion, one for world-fact creation, one for DNA conflicts, one for relationship movement (ADR-011 §1). The Review Card exists so they don't. **Every** AI-proposed change to canon is the same kind of thing — an Entry with `status=proposed` (RFC-002; ADR-011 §2) — so it is reviewed through **one** pattern: one queue, one shape, one set of actions, rendered by the one editor that already renders the Bible and DNA (ADR-011 §2; ADR-014 §2). One interaction model instead of many editors, for concrete reasons:

- **Per-feature approval affordances guarantee inconsistency and gaps.** If each feature invents its own approval, behavior diverges, code duplicates, and — worst — some feature quietly writes canon without review, silently breaking the architecture's core rule (ADR-011 §4-D). A single pattern is both simpler and safer.
- **One learnable interaction governs the riskiest operation.** Because canon mutation is the highest-stakes action, it should be governed by one consistent, learnable gesture the user masters once and trusts everywhere (ADR-011 §5). Uniformity is a safety property here, not just tidiness.
- **It is the universal write-path by design.** The reviews independently named the identical primitive as the pattern that *replaces forms everywhere* — the single write-path for Bible ingestion, world-fact creation, and DNA conflicts alike (ADR-011 §v2-note; ADR-014 §1). The Review Card is that write-path made concrete.

### 4.2 Why the pattern's shape is what it is

The Review Card's defining properties are UX-level architectural decisions (not a visual spec) that follow directly from the cheap-proposal/expensive-canon principle and the constraint that the product is mobile-first and must never block the creative flow (ADR-011 §1–§2):

- **Non-blocking and batchable** — cards surface asynchronously in a queue the user triages when they choose, *never* interrupting the active chat or writing stream (ADR-011 §2). Modal/blocking approval is rejected: interrupting a mobile writing session to adjudicate a fact is hostile and trains reflexive dismissal, defeating the gate (ADR-011 §4-B).
- **Editable before accept** — the user can correct a proposal in place; accepting an edited card writes the *edited* version as canon (ADR-011 §3).
- **Reversible and auditable** — accept and reject are recorded and undoable, so a wrongly-accepted fact can be removed (ADR-011 §4).
- **Progressive disclosure** — the review surface lives inside existing screens, never adding a top-level navigation item (ADR-011 §5; ADR-014 §4). *The surfacing and layout are Defined in the corresponding RFC (the UI & Information Architecture RFC).*

---

## 5. Human Review Responsibilities

Human Review's ownership is **the gate: the sole authority that turns a proposal into canon.** This section defines *responsibilities* — high-level, **no UI, no algorithms** (those are Defined in the corresponding RFC).

- **Approval.** Accepting a proposal, transitioning it from `proposed` to `canon` — the single act that admits knowledge to the source of truth (ADR-011 §2; RFC-002). This is the gate's core function.
- **Editing.** Correcting a proposal before accepting it — accepting an edited proposal writes the *corrected* version as canon, carrying provenance that a human approved it (ADR-011 §3). The human is not limited to yes/no; they refine before conferring trust.
- **Rejection.** Declining a proposal, transitioning it to `rejected` — retained for provenance and audit, not silently discarded (ADR-011 §2, §4; RFC-002). Rejection is a first-class, recorded outcome.
- **Trust.** Conferring trust on knowledge. Provenance and confidence *inform* the decision — the "why does the AI think this?" is visible — but the human is the authority that decides what the system will treat as true (ADR-011 §2; RFC-002; ADR-014 §1 pattern 5). Trust is granted by a person, not computed.
- **Canon creation.** Owning the `proposed → canon` transition as the **one and only** path that creates canonical knowledge (RFC-001 §2.6; ADR-011 §6). No other route writes canon; this responsibility is exclusive and exhaustive.

Across all of these, Human Review owns the **decision and its disposition**, recorded and reversible (ADR-011 §4). It decides *what becomes true*; it does not extract, generate, retrieve, or persist (§6).

---

## 6. What Human Review Does NOT Own

Human Review's non-ownership is as binding as its ownership; ambiguity here re-creates sprawl or, worse, a second write-path (RFC-001 §4). Human Review owns the *decision*, not the machinery around it.

- **Knowledge extraction.** Human Review does not turn text into knowledge or generate proposals. Producing candidate knowledge is the **Analyst's** job (and the Writer's ingestion step) (RFC-008 §3; RFC-004 §4). Review *disposes* of proposals; it does not *create* them.
- **Narrative generation.** Human Review does not write prose. Generating draft fiction is the **Writer's** job (RFC-004 §3). Review governs knowledge-canon, not creative output — and notably does **not** gate the user's own writing (§12; RFC-001 §2.7).
- **Prompt execution.** Human Review does not compose or run prompts. Composition is the **Prompt System's** job (RFC-009 §3). Review is a human decision point, not a generation step.
- **Retrieval.** Human Review does not select knowledge for prompts. Retrieval is the **Store's** one capability (RFC-002; RFC-003). Review determines *what is eligible* to be retrieved (by making it canon); it does not perform retrieval.
- **Storage.** Human Review does not own persistence. All knowledge — proposed, canon, or rejected — is persisted by the **Store** (RFC-002). Review changes an Entry's *status*; the Store owns the model, the persistence, and the record. Review is the *decision*; the Store is the *ledger*.

The discipline: **Human Review decides what becomes canon and records the disposition; it never extracts, generates, composes, retrieves, or persists — and it never gates the user's own creative output.**

---

## 7. Review Card Philosophy

The Review Card is the **universal interaction pattern** for canon mutation, and its philosophy is *one pattern, not many editors* (ADR-011 §2; ADR-014 §1).

- **One pattern because every proposal is one kind of thing.** A proposed fact, a proposed promise, a proposed relationship movement, a proposed piece of DNA — all are Entries with `status=proposed`, so all are reviewed identically: what is proposed, its provenance and confidence, and accept / edit-then-accept / reject (ADR-011 §2; RFC-002). The uniformity is not cosmetic; it follows directly from the one-Entry-model decision (RFC-002). Because knowledge is one representation, its review is one pattern.
- **One queue, one editor.** All proposals flow into one review queue rendered by the *same* component that renders the Bible and DNA — one component to build and maintain instead of one per proposal kind (ADR-011 §2; ADR-014 §5). This is the direct UI payoff of the unified knowledge model: less surface, uniform behavior, no gaps.
- **The pattern embodies the cheap/expensive asymmetry.** Its non-blocking, batchable, low-friction shape keeps *proposing* cheap and unobtrusive, while making *accepting* a distinct, deliberate, recorded act — the interaction is the principle of §3 made tangible (ADR-011 §2; §3 here).
- **The pattern is a UX-level architecture, not a screen.** Its properties — uniform shape, three actions, non-blocking, editable, reversible, progressive-disclosure — are architectural decisions; the visual layout, components, and interactions that realize them are not defined here (ADR-011 §2). *The UI is Defined in the corresponding RFC (the UI & Information Architecture RFC).*

The philosophy in one line: **one Card, one queue, one editor for every AI proposal — because one knowledge model deserves one review pattern.**

---

## 8. Relationship with Story Bible

Human Review is the gate through which the **Living Story Bible** stays living without rotting (RFC-005 §5, §7).

- **Review is the Bible's only write path.** The Bible never self-mutates; every increment to its canon — a new fact, a paid promise, a relationship movement — passes through Human Review (RFC-005 §5; ADR-004 §3). Human Review is precisely the mechanism RFC-005 names as the guard that keeps a *living* Bible from becoming a *corrupted* one (RFC-005 §7).
- **The continuity loop closes on the gate.** When an accepted chapter yields new knowledge, it enters as proposals, the human reviews them, and approved knowledge joins canon — immediately available to the next draft (RFC-005 §7; ADR-004 §3). Human Review is the human-gated step in the loop that lets the Bible grow richer per chapter *safely* (RFC-005 §7).
- **Review confers the Bible's trustworthiness.** Because every canonical Bible entry was approved and its provenance recorded, the Bible is trustworthy over a long project rather than an accumulation of unvetted assertions (RFC-005 §2.2; ADR-011 §5). **This RFC does not redefine the Bible — RFC-005 does.**

---

## 9. Relationship with Analyst

The **Analyst** is the primary source of proposals; Human Review is where they are disposed (RFC-008 §3–§4).

- **The Analyst proposes; Review disposes.** The Analyst's one operation is *text → proposed Entries* — it emits proposals and never writes canon (RFC-008 §4). Human Review is the counterpart that decides which of those proposals become canon (§5; ADR-011 §2). Together they are the two halves of the cheap-proposal/expensive-canon asymmetry: the Analyst makes proposing abundant, Review makes canonizing deliberate (§3).
- **Provenance and confidence flow from the Analyst into the decision.** The Analyst tags each proposal with where it came from and how strongly it is believed; Review surfaces these so the human decides with the evidence in view (RFC-008 §6; ADR-011 §2; ADR-014 §1 pattern 5). The Analyst supplies the *why*; the human supplies the *whether*.
- **Extraction quality shapes the queue, not the gate.** Better Analyst facets mean higher-signal proposals and a lighter triage burden — but the gate itself is unchanged by extraction quality (§12; ADR-011 §5). **This RFC does not redefine the Analyst — RFC-008 does.**

The one-line boundary: **the Analyst generates proposals abundantly; Human Review admits them to canon deliberately.**

---

## 10. Relationship with Writer

The **Writer** both consumes canon and, like the Analyst, proposes back to it through the gate (RFC-004 §4, §6).

- **The Writer proposes; it never writes canon silently.** The Writer reads canon freely to draft, but any knowledge its output reveals — a new fact, a planted promise — is emitted as a *proposal* into the same review queue, never an inline canon write (RFC-004 §4; ADR-005 §7). The Writer is bound by the same gate as everyone else.
- **Review governs the Writer's contributions, not its output.** Human Review gates what the Writer proposes *into canon*; it does **not** gate the prose the Writer produces for the user (RFC-004 §3; RFC-001 §2.7). The distinction is sharp: canon knowledge is human-gated; the user's creative output is not (§6, §12). The Writer's drafts are the user's to judge; only the *knowledge extracted from* accepted drafts is reviewed.
- **The gate protects the ground truth the Writer relies on.** Because the Writer checks its drafts against canon, keeping canon clean through review directly protects the quality of every future draft the Writer produces (RFC-004 §7; RFC-005 §5). **This RFC does not redefine the Writer — RFC-004 does.**

The one-line boundary: **the Writer proposes newly-observed knowledge through the gate; its prose flows to the user ungated — knowledge is reviewed, creative output is not.**

---

## 11. Evolution Strategy

Human Review and the Review Card are designed to absorb every future proposal kind without architectural change (RFC-001 §7).

- **A new proposal kind is a new Entry `type`, absorbed by the one queue.** When a new kind of knowledge becomes proposable, it is a new `type` in the governed vocabulary (owned by RFC-002) that flows into the *same* review queue, rendered by the *same* editor, disposed by the *same* three actions — no new approval affordance, no new review path (RFC-002; ADR-011 §2; ADR-014 §5). The gate scales by absorbing types, not by growing surfaces.
- **The pattern stays uniform as the product grows.** Because every proposal is an Entry with `status=proposed`, the Review Card never forks per feature; new capabilities inherit review for free (ADR-011 §2, §v2-note). This is the direct evolutionary payoff of the one-knowledge-model, one-pattern design.
- **Per-kind *policy* may evolve, gated by evidence.** The concrete, evidence-triggered evolution is **bounded auto-accept for narrow, high-precision proposal kinds** — accept-by-default with easy revert, *only* for kinds real usage proves highly precise, and *only* to relieve triage fatigue (§12; ADR-011 §6; ADR-004 §6). This is a per-kind policy on top of the gate, never a removal of it, and it is validated on evidence — never adopted speculatively (RFC-001 §7.4). *Any such policy is Defined in the corresponding RFCs (coordinating the Living Story Bible and Learning Capture RFCs).*
- **Advanced review surfaces are additive, never the default.** If power users want bulk operations, an optional advanced bulk-review view may be added *in addition to* — never replacing — the card default (ADR-011 §6). The low-friction single-Card path stays the default. *Such surfaces are Defined in the corresponding RFC.*

---

## 12. Architectural Risks

The human-gated-canon design is a strong bet; honesty requires naming its failure modes and the guard on each.

### 12.1 Can users become overwhelmed? Can too many Review Cards reduce usability?

**Yes — queue fatigue is the real failure mode**, and it is the same risk stated two ways (ADR-011 §5-Negative, §5-Future-risks). The gate introduces a triage responsibility; if proposals are frequent and low-value, the queue becomes noise, and — critically — *if the user stops triaging, pending knowledge stagnates and the flywheel stalls* (ADR-011 §5-Future-risks). A clumsy or noisy review experience could sink the entire flywheel the product depends on (ADR-011 §5-Future-risks).

The guards:

- **Non-blocking and batchable by design.** The queue never interrupts the creative flow; the user triages when they choose, so review never competes with writing (ADR-011 §2). This keeps proposing cheap and unobtrusive (§3).
- **Surface only high-signal proposals, and allow muting.** The mitigation is to tune extraction so the queue carries high-value proposals, and to let the user mute low-signal kinds (ADR-011 §5-Negative). Queue quality is an Analyst-tuning and Bench-measured concern (RFC-008 §9; RFC-010).
- **Bounded auto-accept is the evidence-gated relief valve.** Persistent fatigue is the concrete trigger to validate accept-by-default-with-revert for narrow, high-precision kinds — reducing the queue without removing the gate (§11; ADR-011 §6; ADR-004 §6).

### 12.2 When should the AI auto-suggest — and when should approval be automatic?

**The AI should auto-*suggest* abundantly; approval should almost never be automatic.** Auto-suggestion is *proposing*, which is cheap and safe — the system should generate proposals generously (§3.1; RFC-008 §3). Automatic *approval* is the dangerous case, and the default answer is **never**: canon is expensive and must be deliberate (§3.2). The single sanctioned exception is **bounded auto-accept**, and only under strict conditions (ADR-011 §6; ADR-004 §6):

- the proposal kind must be **demonstrably high-precision**, proven on real long-project data — not assumed (ADR-004 §6);
- auto-accept must be **scoped, reversible, and audited** — accept-by-default with easy revert, for that kind only (ADR-004 §6; ADR-011 §6);
- it is adopted **only on evidence**, as a validated relief for measured triage fatigue — never speculatively (RFC-001 §7.4; ADR-011 §6).

Until that bar is met for a specific kind, every proposal is reviewed. Auto-suggest freely; auto-approve almost never.

### 12.3 What should never bypass review?

**No AI-proposed change to canon may ever reach the source of truth by any path other than review** (RFC-001 §2.6, §8.2; ADR-011 §6; ADR-002 §2). This is the architecture's hardest rule, and the honest list of what it forbids:

- **No silent canon writes from the Analyst or the Writer** — both emit proposals only (RFC-008 §4; RFC-004 §4).
- **No self-mutating Bible** — the Bible never writes its own canon (RFC-005 §5).
- **No per-feature back door** — a feature inventing its own approval affordance that quietly writes canon is forbidden; that gap is exactly why the one-pattern gate exists (ADR-011 §4-D, §6).
- **No auto-apply-then-undo** — the gate is *before* canon, never a cleanup after (ADR-011 §4-A; §2.1 here).

The one thing that *does* legitimately bypass the knowledge-review gate is **the user's own creative output** — the user is the final judge of their prose and is never gated by review (RFC-001 §2.7; §6, §10 here). Knowledge into canon is always gated; the user's own writing never is. Bounded auto-accept (§12.2) is not a bypass — it is a human-configured, reversible, audited *policy on the gate*, not a route around it.

---

## 13. Out of Scope

This RFC deliberately defines **none** of the following. Each is named so no later reader mistakes this document for defining it:

- **UI layout** — the review screen, the queue's placement, the card's visual arrangement. *Defined in the corresponding RFC (the UI & Information Architecture RFC).*
- **Components** — the editor component, the card component, the queue/badge surface. *Defined in the corresponding RFC.*
- **Frontend implementation** — rendering, state, mobile/PWA specifics. *Defined in the corresponding RFC.*
- **Animations & interaction details** — gestures, transitions, the exact accept/edit/reject affordances. *Defined in the corresponding RFC.*
- **Algorithms** — proposal ranking or ordering in the queue, muting logic, any auto-accept precision computation. *Defined in the corresponding RFCs.*
- **The Entry model and status mechanism, extraction, generation, and retrieval** — owned by RFC-002, RFC-008, RFC-004, and RFC-003 respectively; referenced here, not redefined. Physical persistence remains a later implementation contract.

Wherever this document needed such a detail, it wrote **"Defined in the corresponding RFC"** (naming the topic) and stopped, by rule.

---

## 14. Dependencies

RFC-011 depends on **RFC-001**, **RFC-002**, **RFC-008**, **RFC-004**, and **RFC-005** and must conform to them (and to the other completed RFCs); where they conflict, they govern (RFC-001 §10; and the dependency notes of the prior RFCs). The following areas of the system **depend on Human Review & the Review Card** — they route their proposals through it, or render it, and none may override the review-before-canon, one-queue-one-pattern, propose-cheaply/canonize-deliberately boundaries established above:

| Depends on Human Review & the Review Card | Depends on it for |
|---|---|
| **The Living Story Bible & Continuity Loop RFC** | The single human-gated write path that keeps the living Bible current without rotting. |
| **The Analyst-facet RFC** | Disposing of the proposals the Analyst emits from references, accepted chapters, and edits. |
| **The Writer Pipeline & Scene/Episode RFC** | Disposing of the newly-observed knowledge the Writer's ingestion step proposes. |
| **The Relationship System RFC** | Approving proposed relationship movement into canon. |
| **The Character / World DNA Organization RFC** | Approving proposed identity knowledge, including corrected exemplars, into canon. |
| **The Learning Capture & Distillation RFC** | Reviewing distilled preference proposals; coordinating any bounded auto-accept policy. |
| **The UI & Information Architecture RFC** | Rendering the one review queue and editor within existing screens (the Review Card is a UX pattern realized there). |
| **The Bench RFC** | Measuring extraction/proposal precision that governs whether a kind qualifies for bounded auto-accept. |

> The forward references above are named by title rather than by number, because the review-before-canon gate, the one-queue-one-pattern write-path, and the propose-cheaply/canonize-deliberately asymmetry are what those RFCs build on regardless of final numbering. Their **dependence on the single human-gated write path, the Review-Card-as-proposed-Entry primitive, and the no-silent-canon rule is fixed**; where a successor and this RFC appear to conflict on those, this RFC — and behind it RFC-001 through RFC-005 and the ADR set — governs.

---

## Appendix A — Traceability

| RFC-011 Section | Primary sources |
|---|---|
| §1 Purpose | RFC-001 §2.6, §2.7; RFC-005 §5; ADR-011 §2; ADR-004 §4-A |
| §2 Why Human Review Exists | RFC-001 §2.6, §2.7, §8.2, §8.7; RFC-005 §5; ADR-002 §2; ADR-004 §4-A; ADR-011 §4-A, §5–§6; RFC-008 §4; RFC-004 §4 |
| §3 Proposal is Cheap, Canon is Expensive | RFC-002; RFC-005 §5–§6; RFC-008 §3; RFC-004 §4; ADR-004 §4-A; ADR-011 §2, §4-A |
| §4 Why the Review Card Exists | ADR-011 §1–§5, §v2-note; ADR-014 §1–§2, §4; RFC-002 |
| §5 Human Review Responsibilities | ADR-011 §2–§4, §6; RFC-002; RFC-001 §2.6; ADR-014 §1 |
| §6 What Human Review Does NOT Own | RFC-001 §4, §2.7; RFC-002; RFC-008 §3; RFC-004 §3; RFC-003; RFC-009 §3 |
| §7 Review Card Philosophy | ADR-011 §2; ADR-014 §1, §5; RFC-002; §3 here |
| §8 Relationship with Story Bible | RFC-005 §2.2, §5, §7; ADR-004 §3; ADR-011 §5 |
| §9 Relationship with Analyst | RFC-008 §3–§4, §6, §9; ADR-011 §2; ADR-014 §1 |
| §10 Relationship with Writer | RFC-004 §3–§4, §6–§7; ADR-005 §7; RFC-001 §2.7; RFC-005 §5 |
| §11 Evolution Strategy | RFC-001 §7, §7.4; RFC-002; ADR-011 §2, §6, §v2-note; ADR-004 §6; ADR-014 §5 |
| §12 Architectural Risks | ADR-011 §4-A, §4-D, §5–§6; ADR-004 §6; RFC-001 §2.6, §2.7, §8.2; RFC-008 §4; RFC-004 §4; RFC-005 §5 |
| §13 Out of Scope | RFC-001 §9 (RFC boundary conventions) |
| §14 Dependencies | RFC-001 §10; RFC-005 §13 |

*End of RFC-011.*
