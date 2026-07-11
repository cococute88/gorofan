# RFC-004: Writer

- **Status:** Draft
- **Date:** 2026-07-10
- **Author:** Chief Software Architect
- **Project:** AI Native Creative Workspace (`ai-creative-workspace` / "gorofan") — "나만의 로판AI + 하트픽션"
- **Conforms to:** RFC-001, RFC-002, RFC-008; ADR-002, ADR-005, ADR-020, ADR-004, ADR-009, ADR-011, ADR-012, ADR-013
- **Supersedes:** nothing
- **RFC layer:** Component — the orchestration reference the pipeline, validation, retrieval-consumer, and review RFCs build on

> **Reading order.** RFC-001 is the system-level reference, RFC-002 defines the Entry Store, and RFC-008 defines the Analyst; read all three first. This RFC opens the **Writer** — the third of RFC-001's three verbs (RFC-001 §3.3) — and defines *why the Writer exists*, *what it owns and does not own*, and *how narrative generation fits the overall architecture*. It does **not** define prompts, stages, generation algorithms, validation rules, retrieval, or streaming — each is named and deferred.
>
> **Source of truth.** RFC-001, RFC-002, and RFC-008 take precedence over this document; behind them the ADR set (`docs/architecture/adr/`) is authoritative, and the two reviews (`docs/design-review-ai-author-os.md`, `docs/architecture-final-minimal.md`) supply rationale only. Where anything here appears to conflict with RFC-001/002/003 or an ADR, **those win** and this document is in error.
>
> **This RFC is implementation-neutral.** It is the conceptual charter of the Writer. Whenever an implementation detail is needed, this document writes **"Defined in the corresponding RFC"** (naming the topic) and stops. It defines no stages.

---

## 1. Purpose

This RFC defines the **Writer** — the system's one mechanism for transforming **knowledge into narrative**.

RFC-001 establishes three verbs — **Store, Analyst, Writer** (RFC-001 §2.3, §3). RFC-002 defined where knowledge lives (the Entry Store); RFC-008 defined how knowledge enters (the Analyst). This RFC defines the verb that *uses* that knowledge to produce the product's reason for existing: **Korean web-novel-class prose** — 로판 and Heart-Fiction-grade long-form fiction (RFC-001 §1.1).

The Writer is the **orchestration layer** of the AI Author OS. It does not merely "call a model to continue the chapter"; it **owns the complete writing lifecycle** — assembling the right knowledge into context, generating a draft, validating that draft against ground truth, revising where it fails, composing scenes into a deliverable episode, and handing the result to persistence. It is the one place where the system's knowledge, its craft, and its quality loops come together into narrative.

This RFC explains:

- **why the Writer exists** — why the writing lifecycle is centralized into a single orchestration layer;
- **what it owns** — the orchestration of context, generation, validation, revision, and persistence hand-off;
- **what it explicitly does NOT own** — knowledge storage, extraction, human review, and the craft *content* that lives in prompts;
- **how narrative generation fits the architecture** — as a consumer of the Store, a producer of proposals like everyone else, and a runner of closed quality loops.

It does **not** define the pipeline's stages, the validation rules, the retrieval mechanics, or any prompt (§11).

---

## 2. Why the Writer Exists

### 2.1 Why writing is centralized into a single orchestration layer

Producing a chapter is not one action; it is a **sequence of dependent actions** — decide what knowledge is relevant, assemble it into a prompt, generate prose, check that prose against the facts and the character's established voice, fix what failed, shape the result into an episode, and persist it. Every one of those steps depends on the ones before it, and every one must obey the same architectural rules (read the Store, never write canon silently, keep craft in prompts).

Centralizing that sequence into **one orchestration layer** is what keeps those dependencies and rules in one governable place. The naive alternative — a "continue writing" call scattered across chat and novel features — is exactly the design both reviews reject: it produces single-pass prose with a hard quality ceiling and no place for the quality loops to live (ADR-005 §1; ADR-020 §1). The Writer exists so that the *whole* lifecycle, not a single generation call, is the unit the architecture reasons about.

This is a direct application of RFC-001's governing rule: **the loop runner is written once; the craft it runs is a versioned prompt** (RFC-001 §2.4). The Writer is that "written once" runner — the orchestration — and the planning, drafting, checking, and styling *content* are prompts, not code inside it (§3, §4; ADR-005 §2).

### 2.2 Why planning, drafting, validation, and revision belong to ONE Writer

The naive design grows a separate engine per phase: a Planning Engine, a Novel Engine, a Serialization Engine, a Style layer, a critic ensemble. Both project reviews establish that these share **one runtime shape** — *retrieve → assemble → generate → validate → revise → persist* — and must collapse into one loop runner executing a declarative stage list (ADR-005 §2; ADR-002 §2; `architecture-final-minimal.md` §3).

Planning, drafting, validation, and revision belong to one Writer for four reasons:

- **They are one loop, not four engines.** Planning produces scene structure, drafting fills it, validation checks it, revision fixes it — each feeds the next around a single loop. Splitting them into engines would fracture one coherent lifecycle into services that must be re-integrated (ADR-005 §2; ADR-020 §1).
- **Separate engines are the debt bomb the architecture exists to prevent.** "An engine per phase" is precisely RFC-001's named failure mode (RFC-001 §1.2, §8.5). Each engine is a service to operate and a boundary to keep in sync; the reviews explicitly *delete* the Serialization Engine, the Relationship Planner, and the Foreshadow Scheduler as named components, keeping their capabilities as stages and checks (ADR-020 §2; `architecture-final-minimal.md` §3, §6).
- **Quality lives in the loop, and a loop needs one owner.** The single largest quality lever — draft → validate → revise against ground truth — only works if drafting and checking and revising sit inside one bounded loop that can iterate (§7; ADR-005 §1–§2). Distributed across engines, there is no loop to close.
- **New craft becomes a stage, not an engine.** With one Writer, a new planning heuristic, a new check, or a new style behavior is a **new stage backed by a prompt file** added to a declarative list — not a new service (RFC-001 §7.2; §9 here). This is the cheap evolution surface the whole architecture is organized around.

RFC-001 makes this a hard constraint: **a new capability is an entry `type`, a prompt stage, or a check — not a new named engine** (RFC-001 §8.5). "Writer" is one orchestration layer; the many phases of writing are stages, not engines. *The concrete stage list, the scene card, and the pipeline shape are Defined in the corresponding RFC (the Writer Pipeline & Scene/Episode RFC) — not here.*

---

## 3. Writer Responsibilities

The Writer's ownership is exclusive (RFC-001 §4.3). This section defines *responsibilities* — orchestration only, **high-level, no stages, no algorithms**.

- **Narrative orchestration.** The Writer owns the **complete writing lifecycle** end to end — sequencing planning, drafting, validation, revision, and episode composition into one bounded loop over the **scene** as the atomic unit and the **episode (회차)** as the delivery unit (RFC-001 §3.3; ADR-005 §2; ADR-020 §2). It is the orchestrator; the phases are stages it runs.
- **Context assembly orchestration.** The Writer *requests* the relevant slice of knowledge for each situation and assembles it into the material a generation call needs (RFC-001 §3.3; §6 here). It orchestrates assembly; it does **not** own the retrieval that selects the knowledge (that is the Store) nor the prompt-assembly substrate it uses. *Retrieval is Defined in the corresponding RFC; prompt assembly is Defined in the corresponding RFC.*
- **Generation orchestration.** The Writer owns *driving* the generation of draft prose — invoking the model through the shared substrate with the assembled context — scene by scene (ADR-005 §2). It orchestrates generation; it does **not** own the provider machinery it calls (that is substrate). *Provider adapters are Defined in the corresponding RFC.*
- **Validation orchestration.** The Writer owns running the draft through its checks against ground truth and deciding, from their findings, what must be revised (RFC-001 §3.3; ADR-005 §2–§3). It orchestrates validation; it does **not** own the *definition* of the checks — the rules and criteria live in prompts and cheap assertions, tuned weekly (§4; ADR-005 §3). *The validation rules are Defined in the corresponding RFC.*
- **Revision orchestration.** The Writer owns the bounded, **targeted** revision step — revising only what the checks flagged, with their findings as instructions — as part of closing the loop (ADR-005 §4). It orchestrates revision; the *revision craft* is prompt content.
- **Persistence orchestration.** The Writer owns *handing the finished result to persistence* and *emitting proposals* from what it produced. Two disciplines are intrinsic and non-negotiable: transactional persistence itself stays in the service layer, post-loop (§4; ADR-005 §6), and any newly-observed knowledge is emitted as a **proposal through review**, never written to canon inline (§4, §6; ADR-005 §7). It orchestrates the hand-off; it does not own the transaction policy or the canon gate.

In one breath: the Writer **orchestrates** the lifecycle — assemble, generate, validate, revise, compose, hand off — while the *knowledge*, the *craft content*, the *retrieval*, the *checks-as-defined*, the *review gate*, and the *transaction policy* all live elsewhere and are consumed or invoked, not owned.

---

## 4. What the Writer Does NOT Own

The Writer's non-ownership is as binding as its ownership; ambiguity here re-creates the engine sprawl the architecture exists to prevent (RFC-001 §4). The Writer *reads the Store and emits proposals like everyone else* (RFC-001 §3.3).

- **Knowledge storage.** The Writer holds **no persisted knowledge of its own**. All creative knowledge lives in the Store; the Writer consumes it and never becomes a second home for it (RFC-002; RFC-001 §4.3). It reads the Store; it does not own the Store.
- **Knowledge extraction.** The Writer does not turn text into knowledge; that is the Analyst (RFC-008 §3). When accepted output yields new facts or promises, the Writer's ingestion step **invokes the Analyst** to extract them — it does not extract them itself (ADR-005 §7; RFC-008 §5).
- **Human review — the canon decision.** The Writer **never writes canon silently.** Anything it wants to add to the source of truth surfaces as a *proposed* Entry for human review, exactly like an Analyst proposal (RFC-001 §2.6, §8.2; RFC-002; ADR-005 §7). The Writer proposes; the human disposes. *The review interaction is Defined in the corresponding RFC.*
- **Reference analysis.** The Writer does not read uploaded references or distill preferences; those are Analyst input paths (RFC-008 §5). The Writer *consumes* the reference-derived knowledge (e.g. exemplars) that the Analyst produced and a human approved — it does not produce it.
- **Relationship management.** The Writer does not own the evolving state between characters as a subsystem. A relationship is knowledge in the Store, planned for in a stage, and checked — an Entry type plus prompt clauses, not a Writer-owned engine (RFC-001 §7.2; ADR-020 §2; `architecture-final-minimal.md` §3). *The relationship model is Defined in the corresponding RFC.*
- **Retrieval, and the craft content it runs.** The Writer does not own the **retrieval function** that selects knowledge (that is the Store's one capability — RFC-002), nor the **content** of its own craft: planning heuristics, critique criteria, serialization cadence, and style behavior all live in **prompt files and cheap assertions**, not in the runner's code (RFC-001 §4.3, §8.3; ADR-005 §1–§3; ADR-020 §4). The runner is written once; the craft is tuned weekly.
- **Transactional persistence policy and quality gating over the user.** The Writer does not own the transaction/concurrency policy — that stays in the service layer, post-loop (ADR-005 §6) — and it owns no authority to block the user's own output; measuring quality is the Bench, out-of-band (RFC-001 §2.7, §4.4). *Persistence policy is Defined in the corresponding RFC; the Bench is Defined in the corresponding RFC.*

The one-way discipline that governs the whole system applies to the Writer without exception: **it reads canon freely and writes canon only through review** (RFC-001 §2.6, §8.7; ADR-002 §2).

---

## 5. Writing Lifecycle

The Writer produces narrative along one high-level lifecycle. This section names the stages of that lifecycle **conceptually**; it defines **no stage list, no algorithms, no checks** (those are Defined in the corresponding RFC).

```
   context      ── the relevant slice of knowledge, assembled for a situation
      │             (retrieved from the Store — RFC-002; §6 here)
      ▼
   draft        ── prose generated scene by scene from that context
      │             (scene = the atomic unit — ADR-020)
      ▼
   validation   ── the draft checked against ground truth
      │             (facts, knowledge-state, established voice)
      ▼
   revision     ── only what validation flagged is revised, targeted
      │             (the closed loop that breaks the single-pass ceiling — §7)
      ▼
   episode      ── validated scenes composed into a deliverable 회차
      │             (episode = the delivery unit — ADR-020; §8 here)
      ▼
   persistence  ── the finished episode handed to the service layer;
                    newly-observed knowledge emitted as proposals for review
                    (transaction policy and canon gate owned elsewhere — §4)
```

- **Context.** The Writer requests, from the Store, the knowledge relevant to the situation being written, within a budget, and assembles it (§6; RFC-002). Nothing is written from a blank prompt; every draft stands on retrieved knowledge.
- **Draft.** The Writer generates prose **scene by scene** — the scene being the atomic, checkable dramatic unit (goal → conflict → outcome → value shift), not the whole chapter (ADR-020 §2). Drafting at chapter granularity is the root cause the reviews attach the single-pass ceiling to; the scene unit is what makes the loop possible (ADR-020 §1, §4-A).
- **Validation.** Each draft is checked against ground truth — the stored facts and knowledge-state, and the character's established voice — so quality becomes *measured*, not vibes (ADR-005 §3). The Writer orchestrates the checks; *their rules are Defined in the corresponding RFC.*
- **Revision.** Only scenes with findings are revised, with the findings as instructions — a **bounded, targeted** pass, not a global rewrite (ADR-005 §4). This is the loop that lifts prose above the single-pass ceiling (§7).
- **Episode.** Validated scenes are composed into a deliverable episode (회차) with the serialization craft a Korean web-novel serial requires — shaped as one stage plus cheap checks, never a Serialization Engine (ADR-020 §2–§3; §8 here).
- **Persistence.** The finished episode is handed to the service layer, and any newly-observed knowledge (new facts, promises) is emitted as **proposals** for human review (ADR-005 §6–§7). The Writer orchestrates the hand-off; the transaction policy and the canon gate are owned elsewhere (§4).

**One invariant holds across the whole lifecycle:** the Writer reads knowledge in and hands narrative and *proposals* out — it never mutates canon on its own path (RFC-001 §2.6). *Optimistic streaming of the draft, and the "polish ready" delivery of the validated result, are UX concerns Defined in the corresponding RFC — not defined here (ADR-005 §5).*

---

## 6. Context Philosophy

The Writer's relationship to knowledge is the sharpest boundary in this RFC: **the Writer consumes knowledge; it never owns it.**

- **The Store is the single source of knowledge; the Writer is a reader.** All creative knowledge — characters, world, style, facts, promises, relationships, summaries — lives in the Store as Entries (RFC-002). The Writer *retrieves* the relevant slice for each situation and assembles it into context; it holds no private knowledge and maintains no parallel store (RFC-002; RFC-001 §4.3). If the Writer began keeping its own knowledge, it would have absorbed the Store and broken the three-verb separation (RFC-001 §2.3).
- **Context is retrieval, not dumping.** The Writer does not pour the whole Bible into every prompt; past roughly chapter 50 the Bible exceeds any context window (RFC-002; ADR-018 §2). It asks the Store's one retrieval function for *what is relevant to this situation, within this budget*, and works with what comes back. **The Writer does not own that retrieval** — it consumes its result (RFC-002; §4 here). *Retrieval is Defined in the corresponding RFC.*
- **Consuming knowledge keeps the Writer stateless with respect to truth.** Because the Writer owns no knowledge, it is reproducible given its inputs: the same retrieved context and the same prompts yield the same drafting behavior. Truth lives in one place (the Store), and the Writer is a transformer over it — which is exactly what makes the Store/Writer boundary testable and the Writer disposable plumbing around durable knowledge (RFC-001 §2.8; ADR-002 §5).
- **What the Writer produces flows back only through the gate.** New knowledge the act of writing reveals (a fact the draft established, a promise it planted) does not get written back by the Writer; it is emitted as a **proposal** and re-enters the Store only through the Analyst-and-review path every other piece of knowledge takes (§4; ADR-005 §7; RFC-002). Consumption is free; contribution is gated.

The Writer is, in one line: **a consumer of the Store and a proposer to it — never an owner of it.**

---

## 7. Quality Philosophy

The Writer exists because quality **compounds in loops and hits a ceiling in a line** (RFC-001 §2.8). This section states that philosophy; it defines **no checks and no algorithms.**

- **Single-pass generation has a hard quality ceiling.** A model asked once to "continue the chapter" has a quality limit no prompt can lift (RFC-001 §1.2; ADR-005 §1). Both reviews identify this as the core failure of naive LLM writing tools, and the architecture's answer is not a better single prompt but a **loop** (`design-review` R12; `architecture-final-minimal.md` §3).
- **Quality comes from a closed loop: draft → validate → revise.** The draft is checked against **ground truth** — the stored facts and knowledge-state, the character's established voice — and only what fails is revised, with the findings as instructions (ADR-005 §2–§4). This is *the largest single quality lever after scene-level planning* (ADR-005 §1). The checks are **falsifiable** precisely because they check against ground truth, not against a vague "make it better" (ADR-005 §1). *The specific checks are Defined in the corresponding RFC.*
- **The loop is bounded and targeted, not maximal.** The architecture deliberately holds the launch loop to a small number of ground-truth checks and **targeted** revision — two focused passes beat five generic ones — because every check is latency and cost, and each must be earned (ADR-005 §2, §4; §10.3 here). More checks are Bench-gated, not default (ADR-005 §3). Quality-from-loops does not mean quality-from-more-loops.
- **The scene is what makes the loop possible.** A loop needs a unit small enough to draft coherently and check surgically; the chapter is too big for both. The **scene** — a dramatic unit that *turns* (changes a value) — is the atomic unit the loop operates on, and the reason evaluation is tractable at all (ADR-020 §1–§2; §8 here).
- **The loop is measured, or it drifts.** Because the craft driving the loop lives in constantly-changing prompt files, the loop's quality is only trustworthy if it is **Bench-measurable**: every prompt or stage change is A/B-tested out-of-band before it ships (RFC-001 §8.9; ADR-005 §5; ADR-012). The Writer's quality philosophy and the Bench are two halves of one commitment. *The Bench is Defined in the corresponding RFC.*

The net position: the Writer's value is not a clever prompt but a **disciplined closed loop over a checkable unit, measured against ground truth** — the one thing a feed-forward pipeline cannot do (RFC-001 §2.8).

---

## 8. Episode Philosophy

The Writer composes narrative at three conceptual scales. This section explains their relationship; it defines **no lengths, no hook taxonomy, no assembly algorithm** (those are Defined in the corresponding RFC).

```
   scene     ── the atomic unit: one dramatic beat that turns
      │           (goal → conflict → outcome → value shift)
      ▼
   episode   ── the delivery unit (회차): scenes composed with
      │           serialization craft — an in-hook, an exit-hook (절단신공),
      ▼           cadence, a target length
   novel     ── the emergent whole: episodes accumulated into a
                 coherent long-form work across hundreds of 회차
```

- **Scene — the atomic unit.** The scene is the unit the Writer plans, drafts, and checks (ADR-020 §2). It is a *dramatic* unit — it must change something (a value shift) — which is why it is both the natural craft unit and the checkable one. Scenes that do not turn are flagged before drafting, at the cheapest place to fix "boring" (ADR-020 §2). *The scene card's shape is Defined in the corresponding RFC.*
- **Episode — the delivery unit.** The episode (회차) is what the reader receives: scenes composed with the serialization craft a Korean web-novel serial requires — an in-hook, an exit-hook, cadence, a target length (ADR-020 §2–§3). Crucially, this composition is **one stage plus cheap checks, not a Serialization Engine** — the reviews explicitly retract the engine framing; the craft knowledge lives in the stage prompt and extracted signals, tunable weekly (ADR-020 §3–§4; `architecture-final-minimal.md` §3).
- **Novel — the emergent whole.** The novel is not a unit the Writer generates in one act; it **emerges** from episodes accumulated coherently over hundreds of 회차. Long-form coherence across that span is not held by the Writer but by the knowledge the Store carries (facts, knowledge-state, promises, multi-level summaries) and the continuity loop that feeds accepted episodes back as ground truth for the next draft (RFC-001 §5; RFC-002; §6 here). The Writer keeps each episode true to that accumulating knowledge; the *whole* stays coherent because knowledge, not the Writer, remembers.
- **User-facing simplicity is preserved.** This three-scale structure is **backend structure, not UI structure**: the author sees a synopsis and an episode list, with scene cards rendered as a few editable lines — one serialization knob (episode target length), not a cascade of controls (ADR-020 §5). *The UI is Defined in the corresponding RFC.*

The relationship in one line: **scenes are checked, episodes are delivered, and the novel emerges from episodes held coherent by the Store — not by the Writer.**

---

## 9. Evolution Strategy

The Writer is designed so that years of craft evolution arrive without architectural change — the same promise the whole system makes (RFC-001 §7).

- **New craft is a new stage or a new check.** A new planning heuristic, a new critique, a new style behavior, or a new serialization technique is a **new stage backed by a prompt file** (or a cheap assertion) added to the declarative list — not a new engine and not code in the runner (RFC-001 §7.2; ADR-005 §2; ADR-020 §4). The loop runner is written once; the stage list is the evolution surface.
- **Better craft is a better prompt, not new orchestration.** Because planning, critique, and style *content* live in prompt files, improving them is a commit to `prompts/`, measured on the Bench before it ships — not a change to the Writer's structure (RFC-001 §2.4, §7.2; ADR-005 §5; ADR-013). The orchestration stays still while the craft improves.
- **New knowledge the Writer can use is a new `type` and a retrieval clause.** When the Writer should draw on a new kind of knowledge, that is a new Entry `type` (owned by RFC-002) plus a line in a stage's retrieval request — never a new Writer-owned store (RFC-002; ADR-020 §2). The relationship system, promises, and foreshadowing entered the Writer exactly this way: an Entry type, a retrieval clause, and a check — not an engine (`architecture-final-minimal.md` §3).
- **More quality is earned, not assumed.** A new model-check is added **only** when the Bench shows the existing loop repeatedly misses a failure class — because every check is latency and cost (ADR-005 §3, §6; §10.3 here). The loop grows on evidence, not ambition.
- **Deferred capabilities wait for a real trigger.** Richer critique, finer granularity of checking, or folding checks into the draft call are **named but deferred** until a concrete or Bench-measured trigger fires — not built speculatively (ADR-005 §6; ADR-020 §6; RFC-001 §7.4). When such a capability arrives, it arrives as a stage or a check, reusing the one runner.

The evolution surface is, as everywhere in this architecture, **prompt files and typed data**; the Writer's core — the loop runner and its lifecycle — stays still (RFC-001 §7).

---

## 10. Architectural Risks

The one-Writer orchestration is a strong bet; honesty requires naming its failure modes and the guard on each.

### 10.1 Can the Writer become too large?

**Yes — this is the central risk.** As the orchestration layer that touches knowledge, generation, checks, and persistence, the Writer is where "just add it here" pressure concentrates. Left unguarded it accretes craft *code* — a planning branch here, a serialization special-case there, a fourth and fifth model-critic — until the "one loop runner" has become a monolith that every change edits (ADR-005 §5, "future risks"; ADR-002 §5).

The guards:

- **Craft lives in stages and prompts, not in the runner.** The runner is "written once"; planning, critique, serialization, and style are prompt-backed stages in a declarative list (§3, §9; RFC-001 §8.3; ADR-005 §2). The moment craft logic migrates into the runner's code, this guard has been breached — the reviews' whole point is that these are stages, not engines (ADR-020 §3).
- **The loop is held small by discipline.** Exactly a small number of ground-truth checks at launch; more are Bench-gated, not default (ADR-005 §3). "Earn each one" is the standing rule against loop bloat.
- **The Writer owns no knowledge and no transaction policy.** Storage stays in the Store, transaction policy in the service layer (§4; ADR-005 §6). Denying the Writer these keeps it an orchestrator, not a subsystem.

### 10.2 When should a capability leave the Writer?

The default is that new *craft* stays in the Writer as a stage — that is the whole design (§9). But some capabilities should **not** live in the Writer at all, and the signal is ownership, not size:

- **A capability leaves the Writer the moment it is really about knowledge, extraction, review, or transactions.** If a "Writer feature" turns out to persist knowledge, it belongs to the Store; if it turns text into knowledge, it belongs to the Analyst; if it decides canon, it belongs to human review; if it governs transactions, it belongs to the service layer (§4; RFC-001 §4). The relationship system, promises, and foreshadowing are the worked examples — each looked like a Writer engine and was correctly placed as an Entry type + a stage clause + a check, its *knowledge* in the Store, not in the Writer (`architecture-final-minimal.md` §3, §6; ADR-020 §2).
- **A capability that needs its own durable state has left orchestration.** The Writer is stateless with respect to truth (§6). Anything that must maintain standing state between runs is, by definition, no longer pure orchestration and must be re-placed — most likely as knowledge in the Store — rather than grown inside the Writer (ADR-002 §5–§6).
- **The trigger must be real, not anticipated.** Capabilities are placed by what they actually own once understood, not spun out speculatively; the default remains "a stage in the one Writer" until a capability demonstrably owns storage, extraction, review, or transactions (RFC-001 §7.4).

### 10.3 How should generation cost be controlled?

The Writer is the system's heaviest consumer of model calls — drafting plus per-scene checks plus conditional revision — and the founding constraint is **zero infrastructure cost beyond LLM usage** (RFC-001 §1.2, §2.1). Unbounded looping is a real cost risk, especially on long works (ADR-005 §5, "Needs Validation"; ADR-020 §5). The architecture controls this in ways this RFC states as principle (the mechanics are deferred):

- **A bounded loop, not an open one.** The loop is a small, fixed number of ground-truth checks plus **targeted** revision — only flagged scenes are revised, one pass (ADR-005 §2, §4). Cost is bounded by the exactly-few-checks discipline, not left to run until "good enough."
- **Cheap assertions before model-critics.** Pacing, cliché, hook presence, and repetition are cheap deterministic `qa` checks, not additional model calls; a new model-critic is added only when the Bench proves the cheaper checks cannot see a recurring failure (ADR-005 §3; ADR-020 §3). Spend model budget only where measurement justifies it.
- **Retrieval keeps context bounded.** Because the Writer consumes budgeted retrieval rather than dumping the Bible, per-scene context — and therefore per-call cost — stays bounded even as the work grows to hundreds of episodes (RFC-002; ADR-020 §6; §6 here).
- **Latency is hidden, not paid twice.** Optimistic streaming delivers the draft immediately and the validated result as "polish ready," so the loop's cost is amortized in perceived time rather than blocking the author (ADR-005 §5). *Streaming is Defined in the corresponding RFC.*
- **Cost/quality trade-offs are a Bench question.** Whether per-scene checking stays affordable on very long works is an explicitly flagged validation item, to be settled with Bench cost/quality data — not by guessing (ADR-005 §6; ADR-020 §6). *The Bench is Defined in the corresponding RFC.*

---

## 11. Out of Scope

This RFC deliberately defines **none** of the following. Each is named so no later reader mistakes this document for defining it:

- **Prompt contents** — the text of any planning, drafting, critique, serialization, or style prompt. *Defined in the corresponding RFC (the Prompt Architecture RFC).*
- **Stage definitions** — the concrete stage list, the scene card, the pipeline shape, the planning cascade. *Defined in the corresponding RFC (the Writer Pipeline & Scene/Episode RFC).*
- **Generation models** — which model generates or checks, provider selection, local-vs-hosted generation. *Defined in the corresponding RFC (the Provider Adapter RFC).*
- **Validation algorithms** — the continuity check, the voice-attribution check, the `qa` assertions, revision selection logic. *Defined in the corresponding RFC.*
- **Retrieval implementation** — ranking, budgeting, keyword-vs-embedding selection. *Owned by the Store; Defined in the corresponding RFC (the Retrieval RFC) — not here.*
- **Streaming** — optimistic streaming, "polish ready" delivery, partial-output preservation on disconnect. *Defined in the corresponding RFC.*
- **Scheduling & jobs** — how generation work is queued, batched, retried, or throttled. *Defined in the corresponding RFC.*
- **Persistence policy** — the transaction boundary, optimistic concurrency, versioning. *Owned by the service layer; Defined in the corresponding RFC (the Persistence RFC).*
- **The Entry model, the review UX, and the Bench** — owned by RFC-002, and by the Review Card and Bench RFCs respectively — not redefined here.

Wherever this document needed such a detail, it wrote **"Defined in the corresponding RFC"** (naming the topic) and stopped, by rule.

---

## 12. Dependencies

RFC-004 depends on **RFC-001**, **RFC-002**, and **RFC-008** and must conform to them; where they conflict, they govern (RFC-001 §10; RFC-002; RFC-008 §12). The following areas of the system **depend on the Writer** defined here — they detail its lifecycle, consume its output, or measure its loops, and none may override the one-orchestrator, reads-Store, proposals-not-canon, quality-in-loops boundaries established above:

| Depends on the Writer | Depends on it for |
|---|---|
| **The Writer Pipeline & Scene/Episode RFC** | The concrete stage list, the scene card, the planning cascade, and episode assembly — the detailed realization of this RFC's lifecycle. |
| **The Validation / Checks RFC** | The continuity and voice-attribution checks and the `qa` assertions the Writer's validation step orchestrates. |
| **The Living Story Bible & Continuity Loop RFC** | The Writer's ingestion step that feeds accepted episodes back as proposals, and the ground truth the loop validates against. |
| **The Retrieval RFC** | The budgeted retrieval the Writer consumes to assemble context (defined on the Store, driven by the Writer's requests). |
| **The Prompt Architecture RFC** | Assembling retrieved knowledge and stage prompts into the generation prompts the Writer drives. |
| **The Review Card RFC** | The proposals the Writer emits from newly-observed knowledge, entering the same human-gated queue as Analyst proposals. |
| **The Relationship System RFC** | Relationship-aware planning and checking, realized as an Entry type + a stage clause + a check consumed by the Writer. |
| **The Bench RFC** | Measuring the Writer's loops and A/B-testing every stage or prompt change out-of-band. |
| **The UI & Information Architecture RFC** | Surfacing the writing lifecycle — synopsis, episode list, streaming draft, "polish ready" — to the author. |

> The forward references above are named by topic rather than by number, because the Writer's orchestration boundary, its reads-Store/proposals-not-canon discipline, and its quality-in-loops principle are what those RFCs build on regardless of final numbering. Their **dependence on the one-orchestrator model, the consume-don't-own-knowledge rule, and the review-before-canon gate is fixed**; where a successor and this RFC appear to conflict on those, this RFC — and behind it RFC-001, RFC-002, RFC-008, and the ADR set — governs.

---

## Appendix A — Traceability

| RFC-004 Section | Primary sources |
|---|---|
| §1 Purpose | RFC-001 §1.1, §3.3; RFC-002; RFC-008 §1; ADR-005 §2 |
| §2 Why the Writer Exists / ONE Writer | RFC-001 §2.3, §2.4, §7.2, §8.5; ADR-002 §2; ADR-005 §1–§2; ADR-020 §1; `architecture-final-minimal.md` §3, §6 |
| §3 Responsibilities | RFC-001 §3.3, §4.3; ADR-005 §2–§6; ADR-020 §2 |
| §4 Does NOT Own | RFC-001 §2.6, §4.3, §8.2, §8.3, §8.7; RFC-002; RFC-008 §3, §5; ADR-005 §6–§7 |
| §5 Writing Lifecycle | RFC-001 §2.6, §5; ADR-005 §2–§7; ADR-020 §2 |
| §6 Context Philosophy | RFC-002; RFC-001 §2.3, §2.8, §4.3; ADR-018 §2; ADR-005 §7 |
| §7 Quality Philosophy | RFC-001 §1.2, §2.8, §2.9, §8.9; ADR-005 §1–§4; ADR-020 §1–§2; ADR-012 |
| §8 Episode Philosophy | ADR-020 §2–§5; RFC-001 §5; RFC-002; `architecture-final-minimal.md` §3 |
| §9 Evolution Strategy | RFC-001 §2.4, §7.2, §7.4; RFC-002; ADR-005 §2–§3, §6; ADR-020 §4, §6; ADR-013 |
| §10 Architectural Risks | ADR-005 §3, §5–§6; ADR-002 §5–§6; ADR-020 §5–§6; RFC-001 §1.2, §2.1, §4, §7.4; RFC-002 |
| §11 Out of Scope | RFC-001 §9 (RFC boundary conventions) |
| §12 Dependencies | RFC-001 §10; RFC-002; RFC-008 §12 |

*End of RFC-004.*
