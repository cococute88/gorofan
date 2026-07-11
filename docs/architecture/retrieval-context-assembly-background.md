# Retrieval & Context Assembly — Historical Background

- **Status:** Historical / Superseded
- **Formerly:** RFC-008 Retrieval & Context Assembly
- **Preserved:** 2026-07-11 during PR #7 self-review
- **Authoritative contracts:** [RFC-003 Store-wide Retrieval](rfc/RFC-003-Store-Retrieval-Contract.md) and [RFC-009 Prompt System](rfc/RFC-009-Prompt-System.md)

> This file preserves the pre-renumbering RFC-008 draft so PR #7 does not delete an existing architecture document wholesale. It is rationale and historical background, not a numbered RFC and not an implementation contract. Its original numeric cross-references describe the pre-PR series and are intentionally non-authoritative; use the current document map in [Architecture Guide](README.md).

---


## 1. Purpose

Every generation the product performs — a novel scene or a chat turn — depends on putting the *right* knowledge in front of the model, in a form the model can use, within a budget it can accept. Two distinct responsibilities make that possible:

- **Retrieval** selects, from the whole Store, the **minimum necessary** knowledge for the task at hand — the on-stage characters, the relevant world rules, the due promises, the current relationship state, the facts that matter now — and nothing else (RFC-002 §8; ADR-018 §2).
- **Context Assembly** takes that selected knowledge (together with the non-knowledge material a call needs — the system instruction, the user's input, recent history) and assembles it into a single, budget-fitting, provider-neutral, deterministic **LLM-ready context** (ADR-009 §2).

Neither is a new subsystem invented here. Retrieval is the Store's one `retrieve()` capability (RFC-002 §6.1, §8; ADR-018 §2); Context Assembly is the substrate's block/budget Prompt Engine, kept as-is and reused (ADR-009; `architecture-final-minimal.md` §1). This RFC's job is to define them as *distinct architectural responsibilities*, lock their boundary, and explain why keeping them separate matters. It explains:

- **why Retrieval exists** — why the model must never consume the whole Store, and why selective retrieval is essential;
- **why Context Assembly exists** — why selecting knowledge and assembling context are separate concerns;
- **what each owns and does not own**;
- **how each relates to the Store, the Writer, and character chat**.

It does **not** define ranking formulas, keyword-vs-embedding strategy, the block model, budgeting math, or caching (§13).

---

## 2. Why Retrieval Exists

### 2.1 Why the model must never consume the entire Store

A finished long-form work accumulates thousands of Entries — facts, promises, relationship history, DNA, world rules, summaries — and by roughly chapter 50 the Store far exceeds any model's context window (RFC-002 §8; ADR-004 §2; ADR-018 §2). Handing the model everything is therefore not merely wasteful; it is **impossible** past a certain size, and **harmful** long before that:

- **It does not fit.** Beyond the context window, "send everything" means *something* gets dropped — and if the model or the provider chooses what to drop, it often drops exactly the wrong thing: the system instruction, the user's message, the one fact the scene turns on (ADR-009 §4-D). Uncontrolled truncation is silent corruption of the prompt.
- **It drowns the signal.** Even where everything fits, burying the five facts that matter under five hundred that do not degrades generation — the model writes worse from a noisy prompt than from a focused one (RFC-002 §8; ADR-018 §2).
- **It wastes cost.** Every irrelevant token is paid for, on a product whose founding constraint is zero infrastructure cost beyond LLM usage (RFC-001 §2.1; ADR-018 §4-A).

### 2.2 Why selective retrieval is essential

The answer is **retrieval, not dumping**: select the knowledge *relevant to this situation*, within a *budget*, and leave the rest in the Store (RFC-002 §8; ADR-018 §2–§3). This is the single most important thing that makes long-form coherence affordable at all: the Store can grow without bound while every prompt stays focused and within budget (ADR-004 §2). Selective retrieval is what lets a hundred-chapter novel draw on its entire accumulated canon *one relevant slice at a time* — the difference between a system that remembers its whole story and one that either overflows or forgets (RFC-002 §8; ADR-018 §2). Retrieval exists to answer exactly one question for the rest of the system: *given this situation and this budget, what knowledge is relevant right now?* (RFC-002 §3.1, §8).

---

## 3. Why Context Assembly Exists

Retrieval selects *which knowledge*; Context Assembly decides *how the whole prompt is built*. These are genuinely different concerns, and the architecture keeps them as **separate responsibilities** for concrete reasons:

- **They answer different questions.** Retrieval answers *what knowledge is relevant?* — a question about the Store, ranked by relevance to a situation. Context Assembly answers *how is a prompt constructed?* — a question about ordering, priority, budget-fitting, variable resolution, and provider-neutral formatting across **all** the material a call needs, not just retrieved knowledge (ADR-018 §2; ADR-009 §2). A prompt contains more than retrieved Entries: the system instruction, the user's input, recent conversation or chapter context. Assembly owns the *whole*; retrieval supplies *one part* of it.
- **They have different owners.** Retrieval is the **Store's** capability (RFC-002 §6.1). Context Assembly is the **substrate's** Prompt Engine — provider-neutral, budget-aware, deterministic — the single mandatory path through which every prompt is built (ADR-009 §2; `architecture-final-minimal.md` §1). Collapsing them would put prompt-construction machinery inside the Store or knowledge-selection inside the substrate, blurring two clean boundaries.
- **They evolve independently.** Retrieval may one day gain embeddings (Bench-gated) without changing a line of assembly; assembly may gain a new provider's rendering without changing a line of retrieval (ADR-018 §6; ADR-009 §4-C, §6). Separation is what lets each improve on its own schedule.
- **Assembly enforces the guarantee retrieval cannot.** Retrieval budgets the *knowledge slice*; Context Assembly enforces the **final, whole-prompt token-budget invariant** across every block, with protected blocks (the user message, the system instruction) that are *never* dropped and priority-based truncation for the rest (ADR-009 §2–§3). That guarantee is a property of the *assembled prompt*, not of knowledge selection — so it must live in the assembler.

**What Context Assembly does NOT own** (its non-ownership, stated here to complete the boundary): it does not *select* knowledge (that is Retrieval), it does not *generate* or *extract* knowledge, it does not *decide which blocks a step needs* (that is the declarative Writer stage or the chat flow that drives it — ADR-009 §v2-note), and it does not *call the model or render provider quirks* (that is the provider adapter — ADR-016). Assembly is the deterministic, budgeted, provider-neutral assembler and nothing more (ADR-009 §2, §4).

The one-line separation: **Retrieval chooses the knowledge; Context Assembly builds the prompt — and no feature hand-assembles a prompt outside the Engine** (ADR-009 §2).

---

## 4. Retrieval Responsibilities

Retrieval's ownership is **selecting the minimum necessary knowledge** for a task. This section defines *responsibilities* — high-level, **no ranking formulas, no algorithms** (those are Defined in the corresponding RFC). Retrieval is the Store's single `retrieve()` capability generalized over the whole Entry space (RFC-002 §8; ADR-018 §2).

- **Selecting relevant Entries.** The core responsibility: given a situation, return the Entries that matter to it — the on-stage cast's DNA, the location's world rules, the due promises, the current relationship state, the pertinent facts and knowledge-state (RFC-002 §8; ADR-004 §2; ADR-018 §3). One function selects across *all* knowledge kinds uniformly — DNA, Bible ledgers, exemplars, relationships, summaries — not a separate retriever per type (ADR-018 §1).
- **Context budgeting.** Selecting the *most relevant knowledge that fits* a token budget, and stopping — budgeting is a first-class constraint on retrieval, not an afterthought (RFC-002 §8; ADR-018 §2). Retrieval hands a budgeted knowledge slice onward; Context Assembly then enforces the final whole-prompt budget (§3).
- **Prioritization.** Ranking candidate knowledge so that, when the budget is scarce, the *right* Entries win — conceptually a blend of *what kind of knowledge it is*, *how relevant it is* to the situation, and *how recent* it is, with confidence and canon-status as guards (RFC-002 §8; ADR-018 §2). *The concrete weighting is a Bench-tuned matter Defined in the corresponding RFC.*
- **Scope selection.** Drawing from the correct region of the Store — a work's own canon (its Story Bible), the character identity a work draws on (DNA), the collection-level reference knowledge — so retrieval returns *this* work's truth and *this* cast's identity, not another's (RFC-002 §5; RFC-005 §8; RFC-007 §8). *Scope semantics are owned by the Store and Defined in the corresponding RFC.*

Across all of these, Retrieval is **read-only and non-mutating**: it reads canon freely and returns Entries without changing them (RFC-002 §7, §8). It selects; it does not produce, format, or execute.

---

## 5. What Retrieval Does NOT Own

Retrieval's non-ownership is as binding as its ownership; ambiguity here re-creates the sprawl the architecture exists to prevent (RFC-001 §4). Retrieval is **selection**, not work done on knowledge.

- **Knowledge generation.** Retrieval does not invent knowledge. It returns what is already in the Store; it never fabricates, infers, or summarizes on the fly. Generating narrative is the **Writer's** job (RFC-004 §3); the Store holds only what a producer put there and a human approved (RFC-002 §7).
- **Knowledge extraction.** Retrieval does not turn text into knowledge. Extraction is the **Analyst's** job (RFC-003 §3). Retrieval reads the results of extraction; it performs none.
- **Prompt execution.** Retrieval does not build or send prompts. Assembling the prompt is **Context Assembly**; calling the model and rendering provider specifics is the **provider adapter** (§3; ADR-009 §4; ADR-016). Retrieval's output is *selected knowledge*, not a message list.
- **Writing.** Retrieval does not draft, plan, or revise. It supplies the knowledge the **Writer** drafts from; it owns none of the writing lifecycle (RFC-004 §3).
- **Human review.** Retrieval does not decide what is canon. It reads canon (and may surface proposals where asked), but the **review gate** — not retrieval — governs what knowledge exists to be retrieved (RFC-002 §3.4; RFC-005 §5). Retrieval reflects the Store's truth; it does not adjudicate it.

The discipline: **Retrieval reads and ranks; it never creates, formats, or decides** (RFC-002 §7, §8).

---

## 6. Context Assembly Philosophy

Context Assembly is governed by one commitment: **assembled context must be deterministic, auditable, and reproducible** (ADR-009 §2, §7).

- **Deterministic.** Assembly is a pipeline of near-pure stages — collect the material as blocks, resolve variables, order by priority, fit to budget, finalize — each reproducible given its inputs (ADR-009 §2). The same inputs yield the same assembled context (§7). This is not an accident of implementation; it is a locked principle of the "prompt constitution" (ADR-009 §2).
- **Auditable.** Every assembly can account for itself: which blocks were included, which were trimmed, which were dropped, and the token math behind those decisions — a dev-only trace so quality regressions are *diagnosable* rather than mysterious (ADR-009 §2, §7). Context that cannot be inspected cannot be debugged.
- **Budget-guaranteed.** The token budget is an **invariant, not a hope**: assembled tokens never exceed the context window, guaranteed by priority-based truncation — and the protected blocks (the user's message, the system instruction) are *never* the ones dropped (ADR-009 §2-Property-7, §3). This is what makes the product robust across wildly different context windows, from large cloud models to small local ones (ADR-009 §5).
- **Provider-neutral.** Assembly emits a neutral message list; how a given provider renders system messages or other quirks is the **adapter's** job, never encoded into assembly (ADR-009 §4; ADR-016). This preserves vendor-neutrality at the most important code path (ADR-009 §5).
- **Single mandatory path.** No feature — not the Writer, not chat — hand-assembles a prompt with ad-hoc string concatenation outside the Engine (ADR-009 §2, §4-A). Scattered, unbudgeted, untestable string-building is precisely the failure mode Context Assembly exists to prevent, and it is what guarantees chat and novel behave consistently rather than drifting apart (ADR-009 §1, §4-A).

The philosophy in one line: **one deterministic, budgeted, provider-neutral, inspectable assembler builds every prompt — or quality becomes unreasoned-about and un-diagnosable.**

---

## 7. Deterministic Context

This section states, as a first-class commitment, why **the same inputs must produce the same assembled context** — and why that reproducibility is load-bearing, not a nicety. *Determinism here is a property of the assembly pipeline given its inputs (ADR-009 §2); it does not claim the downstream model call is deterministic, nor that retrieval ranking can never change — only that, for a fixed set of retrieved knowledge and fixed non-knowledge inputs, assembly produces one and the same context every time.*

- **Why it must hold.** Assembly is defined as a pipeline of near-pure stages precisely so that its output is a function of its inputs (ADR-009 §2). If assembling the same character, the same facts, and the same user input could yield different contexts run to run — different blocks kept, different truncation — then nothing downstream could be reasoned about, because the one thing under the system's control (what it showed the model) would itself be unstable.

Reproducibility matters for three concrete reasons:

- **Debugging.** When output degrades, the first question is *what did the model actually see?* Deterministic assembly plus the audit trace answers it exactly: the included, trimmed, and dropped blocks are recoverable and repeatable (ADR-009 §7). Without determinism, a regression could not be reproduced, and "the model saw the wrong context" could never be distinguished from "the model wrote badly from the right context." Determinism is what makes prompt bugs *findable*.
- **Bench evaluation.** The Bench A/B-tests prompt, stage, and retrieval changes against frozen scenarios — a scene card plus a frozen Entry snapshot (ADR-012; ADR-005 §5; ADR-018 §6). This only yields a *measurement* if assembly is deterministic: with a fixed snapshot, any change in the assembled context must be attributable to the change under test, not to assembly noise. Non-deterministic assembly would make every Bench comparison confounded — you could not tell whether a prompt edit helped or whether the context simply differed by chance. Deterministic context is the precondition that turns "did this change help?" from a vibe into a number (RFC-001 §2.9; ADR-012).
- **Novel quality.** Consistency across a long work depends on the same knowledge reliably reaching the model. A character's defining voice exemplars, the fact the scene turns on, the due promise — these must be *present when relevant*, not randomly present. Deterministic, budget-guaranteed assembly ensures the important blocks are included by priority rather than dropped by chance, and that protected blocks are never sacrificed (ADR-009 §3). The rejected alternative — "send everything and let the provider truncate" — is non-deterministic *and* silently drops whatever the provider chooses, often the wrong thing (ADR-009 §4-D). Determinism is therefore not just a debugging aid; it is directly a quality mechanism: the reader's coherence rests on the model reliably seeing what it needs.

The commitment in one line: **fixed inputs, one context — because debugging, measurement, and long-form quality all rest on the prompt being a reproducible function of what the system knew.**

---

## 8. Relationship with Store

Retrieval **is** the Store's outward-facing capability; Context Assembly **reads from** what retrieval returns. Neither replaces the Store (RFC-002 §6, §8).

- **Retrieval is the Store's one capability, not a separate engine.** The single `retrieve()` function is owned by the Store and generalizes over the whole Entry space — DNA, Bible ledgers, relationships, exemplars, summaries — uniformly (RFC-002 §6.1, §8; ADR-018 §1–§2). There is no second retrieval system, no parallel lorebook scanner, no competing index; one path serves chat and novel alike (ADR-018 §2, §4-B). This RFC details that capability as its own responsibility but does **not** redefine the Store — RFC-002 does.
- **Retrieval reflects the Store's commitments.** Because it returns Entries, retrieval inherits their provenance, confidence, and canon status — it can prefer higher-confidence knowledge and can distinguish canon from proposal (RFC-002 §3.3, §3.4; RFC-005 §6). Retrieval selects over exactly the knowledge model RFC-002 defines; it adds no representation of its own.
- **The Store's growth is retrieval's growth, for free.** A new Entry `type` — a new library, a new ledger, a new identity facet — becomes retrievable automatically, with no new retrieval machinery, because retrieval already ranks over the whole typed space (RFC-002 §9.1; ADR-018 §1). This is a direct payoff of the one-model, one-retrieval design.
- **Context Assembly reads retrieved Entries; it does not reach into the Store.** Assembly consumes the *result* of retrieval (plus non-knowledge inputs) and never queries the Store directly or hand-selects knowledge — keeping selection wholly inside retrieval and construction wholly inside assembly (§3; ADR-009 §2, §v2-note).

---

## 9. Relationship with Writer

The Writer **drives** retrieval and assembly but **owns** neither (RFC-004 §4, §6).

- **The Writer requests; retrieval selects.** For each stage, the Writer's declarative retrieval request names *what kind* of knowledge the situation needs (on-stage cast, location, due promises, relationship state); retrieval selects and budgets it (RFC-004 §6; ADR-005 §2; ADR-018 §2). The Writer states the need; retrieval — the Store's capability — answers it. The Writer does not own the ranking (§5; RFC-004 §4).
- **The Writer drives assembly; the Engine builds.** Which blocks a given step needs is chosen by the declarative Writer stage; the Prompt Engine then deterministically assembles and budgets them (ADR-009 §v2-note; RFC-004 §3). The Writer orchestrates *context assembly*; it does not own the assembler (RFC-004 §4). This is exactly the boundary RFC-004 draws: the Writer orchestrates, while retrieval and prompt-assembly machinery live elsewhere (RFC-004 §4).
- **The Writer consumes the assembled context; it does not hold it.** The assembled context is working material for one generation — consumed and discarded, never persisted as knowledge (RFC-004 §6; RFC-005 §6). The Writer reads the Store through retrieval and builds prompts through the Engine, and owns the truth in neither. **This RFC does not redefine the Writer — RFC-004 does.**

The one-line boundary: **the Writer asks for knowledge and drives assembly; Retrieval selects and Context Assembly builds — the Writer owns the orchestration, not the machinery.**

---

## 10. Relationship with Character Chat

Character chat — one of the product's two core capabilities (RFC-001 §1.1) — uses the **same** retrieval and assembly architecture as novel writing. *This RFC does not define the chat architecture; it describes only how chat relates to retrieval and assembly.*

- **Chat retrieves through the same one function.** When the author converses with a character, chat needs the same kinds of knowledge a draft does — the character's DNA and voice exemplars, the relevant world rules, the current relationship state, the pertinent facts — and it selects them through the Store's single `retrieve()`, not a chat-specific retriever (RFC-002 §8; ADR-018 §1–§2). One retrieval path serves chat and novel; there is no second system (ADR-018 §2, §4-B).
- **Chat assembles through the same one Engine.** A chat prompt is built by the same deterministic, budgeted, provider-neutral Prompt Engine as a novel prompt — no hand-assembled chat strings, no divergent path (ADR-009 §2, §4-A). This is precisely what keeps a character *the same character* across chat and novel: both draw the same shared knowledge through the same selection and the same assembly, so they cannot silently drift apart (RFC-001 §1.1; RFC-007 §9).
- **Chat's private memory is not a second knowledge source.** Chat's own conversational memory stays chat-private and is *not* widened into a general retrieval store; shared knowledge (a bookmarked exemplar, an established beat) flows into the Store as Entries through the normal gate and is thereafter retrieved like any other knowledge (RFC-002 §5; ADR-018 §6; RFC-007 §9). Chat is a consumer of the one retrieval architecture, not an owner of a parallel one.

The one-line boundary: **chat and novel share one retrieval function and one assembler — which is exactly why the character stays consistent across both.**

---

## 11. Evolution Strategy

Retrieval and Context Assembly are designed to improve for years without architectural redesign (RFC-001 §7).

- **Retrieval improves by better ranking, not by a new store.** Retrieval quality is tuned by adjusting how relevance, recency, and knowledge-kind are weighted — a tuning surface, measured on the Bench, not a structural change (ADR-018 §2, §6). New knowledge kinds become retrievable automatically as new Entry `type`s (§8; RFC-002 §9.1). The retrieval *function* stays written-once; its *tuning* is the evolution surface.
- **Embeddings are a deferred, Bench-gated upgrade behind the same seam.** Semantic retrieval is added **only** when keyword ranking demonstrably misses, proven on the Bench, and then *behind the single shared retrieval seam* — never as a parallel RAG or a second retrieval system (RFC-002 §8; ADR-018 §2, §6). Until that trigger fires, keyword-first stands. This is the one sanctioned way retrieval's mechanism grows. *The embedding seam and its trigger are Defined in the corresponding RFC.*
- **Context Assembly grows by adding block kinds, not by new machinery.** The block/priority model is the natural insertion point for every future context source — reference-style Entries, relationship Entries, a new knowledge kind — with no new assembly machinery (ADR-009 §5). A new source is a new block with a priority, absorbed by the existing deterministic pipeline.
- **Provider evolution stays in the adapter, not the assembler.** New providers or provider features are handled by the adapter's rendering, keeping assembly provider-neutral; the neutral message contract is revisited only if a compelling feature genuinely cannot be expressed as neutral blocks (ADR-009 §4-C, §6; ADR-016). Assembly's core stays still while the provider landscape churns.
- **Tuning becomes measurable, not intuitive.** Because both retrieval ranking and assembly priority are quality levers that can silently hurt if mis-set, the sanctioned path is to make their tuning **Bench-measurable** rather than guessed (ADR-009 §6; ADR-018 §6; RFC-001 §2.9). Improvement is earned on evidence.

---

## 12. Architectural Risks

The retrieval-and-assembly design is a strong bet; honesty requires naming its failure modes and the guard on each.

### 12.1 Can retrieval become too expensive?

**Yes.** Retrieval runs on every generation — every scene, every chat turn — and over a large Store, unbounded ranking work could add real latency and, if it ever required embedding every query, real cost (ADR-004 §5-Negative; ADR-018 §5).

The guards:

- **Keyword-first keeps steady-state cost low.** The default retrieval is cheap keyword ranking with no standing embedding infrastructure; the expensive option is deferred until proven necessary (ADR-018 §2, §4-A). Cost is opt-in, on evidence.
- **Budgeting bounds the work and the result.** Retrieval selects to a budget and stops, so both the returned slice and the downstream prompt stay bounded regardless of Store size (RFC-002 §8; ADR-018 §2).
- **Caching is an optimization, never a correctness crutch.** Identical assemblies can be cached by content hash to avoid recomputation, but caching never changes what *should* be assembled (ADR-009 §8). *Caching is Defined in the corresponding RFC.*

### 12.2 Can context become too large?

**No, by invariant — and this is the guarantee's whole point.** The token budget is an invariant, not a hope: assembled tokens never exceed the context window, enforced by priority-based truncation, with protected blocks never dropped (ADR-009 §2-Property-7, §3). The honest residual risks are *quality under pressure*, not overflow:

- **Priority tuning is a subtle craft.** What gets dropped first when budget is tight is a real quality lever; wrong priorities silently hurt output (ADR-009 §5-Negative). The guard is Bench-measured priority tuning, not intuition (ADR-009 §6).
- **Token counting is approximate, especially for Korean/CJK.** The Engine uses approximate counts plus a safety margin, which can waste a little budget but preserves the never-overflow guarantee (ADR-009 §5-Negative). The invariant holds; the cost is a small efficiency loss.

### 12.3 Can ranking bias hide important knowledge?

**Yes — this is retrieval's most serious quality risk.** If the ranking systematically under-weights a kind of knowledge, a crucial fact, a due promise, or a defining exemplar can be *silently* left out of the prompt, and the model will write confidently without it. Keyword ranking additionally has a semantic-recall ceiling: it can miss knowledge phrased in synonyms or paraphrase (ADR-018 §5-Negative).

The guards:

- **Kind-aware ranking protects high-stakes knowledge.** Because ranking blends *knowledge-kind* with relevance and recency, load-bearing kinds (a due promise, a contradiction-relevant fact) can be weighted to survive budget pressure rather than being crowded out (RFC-002 §8; ADR-018 §2). *The weighting is Defined in the corresponding RFC.*
- **The Bench is the detector.** Systematic retrieval misses surface as recurring quality failures on the Bench — the sanctioned trigger both to retune weights and, if keyword recall is the culprit, to adopt embeddings behind the shared seam (ADR-018 §6; §11 here). Bias is caught by measurement, not left to chance.
- **The Writer's checks are a second net.** A retrieval miss that lets a contradiction through is still catchable by the Writer's continuity check against retrieved facts — imperfect, but a backstop (RFC-004 §7; ADR-004 §4). *The checks are Defined in the corresponding RFC.*

### 12.4 How should retrieval quality be evaluated?

**On the Bench, against frozen scenarios — never by intuition.** Because both retrieval ranking and assembly priority silently affect quality, they must be evaluated by measurement (ADR-012; ADR-018 §6; ADR-009 §6):

- **Frozen snapshots make evaluation possible.** The Bench's frozen Entry snapshots plus deterministic assembly (§7) let a retrieval or ranking change be A/B-tested with the result attributable to the change, not to noise (ADR-012; ADR-018 §6). This is the direct dependency of retrieval evaluation on deterministic context.
- **The metrics are the checks already built.** Contradiction count, voice-attribution accuracy, and the other Writer checks double as retrieval-quality signals — if the right knowledge was retrieved, these pass more often (ADR-012; ADR-005 §3). Retrieval quality is measured through its downstream effect on output.
- **Every ranking change is Bench-gated.** Retuning weights or adopting embeddings ships only after the Bench shows it helps (ADR-018 §6). *The Bench is Defined in the corresponding RFC.*

---

## 13. Out of Scope

This RFC deliberately defines **none** of the following. Each is named so no later reader mistakes this document for defining it:

- **Algorithms** — the retrieval selection procedure, the ranking computation, budgeting math, truncation order, variable resolution, deduplication. *Defined in the corresponding RFCs (the Retrieval and Prompt Architecture RFCs).*
- **Embeddings** — semantic retrieval, the embedding model, when and how it is adopted. *Deferred and Bench-gated; Defined in the corresponding RFC (the Retrieval RFC).*
- **Vector DB / storage** — any storage engine for retrieval; there is no second store. *Defined in the corresponding RFCs (the Retrieval and Persistence RFCs).*
- **Prompts** — prompt bodies, block contents, stage prompts, the tone/theme contract text. *Defined in the corresponding RFC (the Prompt Architecture RFC).*
- **Ranking implementation** — the concrete weighting of knowledge-kind × relevance × recency, confidence handling, scope resolution. *Defined in the corresponding RFC (the Retrieval RFC).*
- **Caching** — the assembly cache, content-hash keys, invalidation. *An optimization only; Defined in the corresponding RFC (the Prompt Architecture RFC).*
- **The block model and provider rendering** — the `PromptBlock` structure, the deterministic pipeline's stages, the neutral message contract, and provider-specific rendering. *Defined in the corresponding RFCs (the Prompt Architecture and Provider Adapter RFCs).*
- **The Entry model, the Store, the Writer, chat, and the Bench** — owned by their respective RFCs; consumed here, not redefined.

Wherever this document needed such a detail, it wrote **"Defined in the corresponding RFC"** (naming the topic) and stopped, by rule.

---

## 14. Dependencies

RFC-008 depends on **RFC-001**, **RFC-002**, **RFC-003**, **RFC-004**, **RFC-005**, **RFC-006**, and **RFC-007** and must conform to them; where they conflict, they govern (RFC-001 §10; and the dependency notes of the prior RFCs). The following areas of the system **depend on Retrieval & Context Assembly** defined here — they detail its mechanics, consume its output, or measure its quality, and none may override the retrieval-not-dumping, one-retrieval-function, deterministic-single-assembler boundaries established above:

| Depends on Retrieval & Context Assembly | Depends on it for |
|---|---|
| **The Retrieval RFC** | The concrete ranking (knowledge-kind × relevance × recency), scope resolution, budgeting, and the deferred embedding seam that realize §4. |
| **The Prompt Architecture RFC** | The block model, the deterministic assembly pipeline, priority truncation, the neutral message contract, and caching that realize §6–§7. |
| **The Writer Pipeline & Scene/Episode RFC** | Declarative per-stage retrieval requests and the block selection the Writer drives. |
| **The Character Chat RFC** | Consuming the same retrieval function and the same assembler so chat and novel stay consistent. |
| **The Living Story Bible & Continuity Loop RFC** | Retrieval of scene-relevant facts, knowledge-state, due promises, and multi-level summaries. |
| **The Relationship System RFC** | Retrieval of current relationship state (stage, last transition) into context. |
| **The Character / World DNA Organization RFC** | Retrieval and injection of identity with exemplars outranking descriptions. |
| **The Provider Adapter RFC** | Rendering the neutral assembled message list into provider-specific calls. |
| **The Bench RFC** | Evaluating retrieval and assembly quality against frozen scenarios, gating every ranking change. |

> The forward references above are named by title rather than by number, because the retrieval-not-dumping principle, the single-retrieval-function boundary, and the deterministic-single-assembler discipline are what those RFCs build on regardless of final numbering. Their **dependence on selective retrieval, the one shared retrieval path, and deterministic budgeted assembly is fixed**; where a successor and this RFC appear to conflict on those, this RFC — and behind it RFC-001 through RFC-007 and the ADR set — governs.

---

## Appendix A — Traceability

| RFC-008 Section | Primary sources |
|---|---|
| §1 Purpose | RFC-002 §6.1, §8; ADR-018 §2; ADR-009 §2; `architecture-final-minimal.md` §1 |
| §2 Why Retrieval Exists | RFC-002 §8; ADR-004 §2; ADR-018 §2–§3; ADR-009 §4-D; RFC-001 §2.1 |
| §3 Why Context Assembly Exists | ADR-009 §2, §4, §v2-note; ADR-018 §2; ADR-016; `architecture-final-minimal.md` §1 |
| §4 Retrieval Responsibilities | RFC-002 §8; ADR-018 §1–§3; ADR-004 §2; RFC-005 §8; RFC-007 §8 |
| §5 What Retrieval Does NOT Own | RFC-001 §4; RFC-002 §7, §8, §3.4; RFC-003 §3; RFC-004 §3; ADR-009 §4; ADR-016 |
| §6 Context Assembly Philosophy | ADR-009 §2–§5, §7 |
| §7 Deterministic Context | ADR-009 §2, §7, §4-D; ADR-012; ADR-005 §5; ADR-018 §6; RFC-001 §2.9 |
| §8 Relationship with Store | RFC-002 §6.1, §8, §3.3, §3.4, §9.1; ADR-018 §1–§2, §4-B; ADR-009 §v2-note |
| §9 Relationship with Writer | RFC-004 §3, §4, §6; ADR-005 §2; ADR-009 §v2-note; ADR-018 §2; RFC-005 §6 |
| §10 Relationship with Character Chat | RFC-001 §1.1; RFC-002 §5, §8; ADR-018 §1–§2, §6; ADR-009 §2, §4-A; RFC-007 §9 |
| §11 Evolution Strategy | RFC-001 §7, §2.9; RFC-002 §9.1; ADR-018 §2, §6; ADR-009 §4-C, §5, §6; ADR-016 |
| §12 Architectural Risks | ADR-018 §2, §5–§6; ADR-009 §3, §5–§8; ADR-004 §4–§5; RFC-002 §8; RFC-004 §7; ADR-012 |
| §13 Out of Scope | RFC-001 §9 (RFC boundary conventions) |
| §14 Dependencies | RFC-001 §10; RFC-002 §12 |

*End of RFC-008.*
