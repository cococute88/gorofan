# RFC-010: Bench

- **Status:** Draft
- **Date:** 2026-07-10
- **Author:** Chief Software Architect
- **Project:** AI Native Creative Workspace (`ai-creative-workspace` / "gorofan") — "나만의 로판AI + 하트픽션"
- **Conforms to:** RFC-001, RFC-002, RFC-008, RFC-004, RFC-005, RFC-006, RFC-007, RFC-003, RFC-009; ADR-012, ADR-005, ADR-008, ADR-009, ADR-013, ADR-001
- **Supersedes:** nothing
- **RFC layer:** Component — the evaluation-harness reference the Prompt System, Writer, retrieval, and Analyst RFCs rely on to ship changes safely

> **Reading order.** RFC-001 is the system-level reference; RFC-002 the Entry Store; RFC-008 the Analyst; RFC-004 the Writer; RFC-005 the Story Bible; RFC-006 the Relationship model; RFC-007 Character DNA; RFC-003 Store-wide Retrieval; RFC-009 the Prompt System. Read them first. This RFC defines the **Bench** — the architectural quality-evaluation environment that measures changes in AI behavior *before those changes reach users*. It explains *why the Bench exists* and *what it owns and does not own*. It is a **development capability, not a runtime feature.** It does **not** define scoring methods, models, datasets, automation, or CI — each is named and deferred.
>
> **Source of truth.** The RFC documents take precedence over this one, in order (RFC-001, then RFC-002…RFC-009); behind them the ADR set (`docs/architecture/adr/`) is authoritative, and the two reviews (`docs/design-review-ai-author-os.md`, `docs/architecture-final-minimal.md`) supply rationale only. Where anything here appears to conflict with an RFC or an ADR, **those win** and this document is in error.
>
> **This RFC is implementation-neutral.** Whenever an implementation detail is needed, it writes **"Defined in the corresponding RFC"** (naming the topic) and stops. It defines no datasets and no scoring formulas.

---

## 1. Purpose

The architecture deliberately concentrates the product's creative behavior in **constantly-changing prompt files, stages, facets, and entry types** — because that is the cheapest, most-exercised surface to evolve (RFC-001 §2.4, §7; RFC-009 §2). That choice has a shadow: behavior that changes weekly can *regress* weekly, silently, and a single maintainer will not notice a broken voice or a lost hook until a reader does (`architecture-final-minimal.md` §7; ADR-012 §1). The **Bench** exists to close that gap. It is the environment that **measures a change in AI behavior before that change reaches users**, so quality *compounds* instead of oscillating.

The Bench is emphatically a **development capability, not a runtime feature**. It runs out-of-band, imports the real code paths so it measures what actually ships, and never touches a live generation, a user's output, or the running product (RFC-001 §3.4, §4.4; ADR-012 §2, §5). It is the meta-mechanism that makes the whole prompt-file-centric architecture *survivable* (ADR-012 §1). This RFC explains:

- **why the Bench exists** — why AI quality must be measurable, and why prompt changes must never rely on intuition;
- **what it owns** — the golden scenarios, the offline scoring runs, the comparison report, and repeatable measurement;
- **what it explicitly does NOT own** — runtime generation, knowledge storage, retrieval, prompt editing, and human review.

It does **not** define the metrics' formulas, the golden dataset, or the runner (§13).

---

## 2. Why the Bench Exists

### 2.1 Why AI quality must be measurable

For a product whose entire reason to exist is **novel quality**, "did that change help or hurt?" is the most important question the maintainer asks — and it is exactly the question a human cannot answer reliably by eye across a long, subtle, drifting body of creative output (ADR-012 §1). Voice consistency, continuity, hook presence, and cliché-avoidance degrade *gradually and invisibly*; by the time a regression is obvious in the reading, it has already shipped and compounded (`architecture-final-minimal.md` §7). AI quality must be **measurable** because it is the one axis the product competes on, and because the failure mode — silent, gradual regression — is precisely the kind humans are worst at catching unaided. The Bench turns an unanswerable feeling into a comparable measurement (ADR-012 §2, §5).

### 2.2 Why prompt changes must never rely on intuition

The architecture puts creative logic in prompt files *so it can be tuned constantly* (RFC-001 §2.4; ADR-013 §4). But constant tuning on **intuition** is how quality oscillates: week-6 you "improve" a prompt, it silently breaks something week-3 you fixed, and neither change was ever measured against the other (`architecture-final-minimal.md` §7; ADR-012 §1). This is not a hypothetical — it is the *designed-in* risk of prompt-file-centrism, and the Bench is its designed-in answer (ADR-012 §1). Every prompt, stage, facet, or retrieval change is therefore **Bench-gated**: A/B-compared against the current version before it ships, so the decision to merge rests on evidence, not vibes (ADR-012 §2; RFC-009 §10). The rule is absolute because the risk it guards is created by the architecture's own central bet. Without the Bench, prompt-file-centrism would be negligent; with it, that centrism is what lets quality compound (ADR-012 §1).

---

## 3. Bench Responsibilities

The Bench's ownership is **out-of-band, repeatable measurement of creative change**. This section defines *responsibilities* — high-level, **no scoring formulas, no datasets, no runner design** (those are Defined in the corresponding RFC).

- **Golden scenes.** The Bench owns a fixed, curated set of representative scenarios — each a frozen scene setup paired with a frozen knowledge snapshot — spanning the scene types the product must handle well (confession, banter, action, reveal, quiet interiority) (ADR-012 §2; §6 here). The golden set is the *stable ground* against which change is measured. *Its contents are Defined in the corresponding RFC; this RFC does not define the dataset.*
- **Regression evaluation.** The Bench owns running a change against the golden set and detecting whether it *regressed* any quality signal relative to the prior version — the core safety function that catches a silent break before it ships (ADR-012 §2, §5). *The metrics are the checks the Writer already runs, reused out-of-band (§8, §9); this RFC defines no scoring method.*
- **Prompt comparison.** The Bench owns the A/B comparison — old version vs. new — that answers "which is better?" per golden scene, and emits a concise diff report the maintainer acts on (ADR-012 §3–§4). Comparison, not an absolute grade, is the Bench's characteristic output.
- **Quality history.** The Bench owns a record of how the measured signals move over time, so quality trends — and the effect of each change — are visible rather than lost (ADR-012 §2; §7 here). This history is what lets the maintainer see compounding versus oscillation.
- **Repeatability.** The Bench owns that the *same* change measured against the *same* golden set yields the *same* comparison — the reproducibility without which no measurement is trustworthy (§5; RFC-003). Repeatability is a first-class responsibility, not an incidental property.

Across all of these, the Bench **imports the real code paths so it tests what ships, but runs strictly out-of-band** — it measures the product without being part of it (RFC-001 §4.4; ADR-012 §5).

---

## 4. What the Bench Does NOT Own

The Bench's non-ownership is as binding as its ownership, and unusually strict: the Bench touches only the *change process*, never the live data path (RFC-001 §4.4; ADR-012 §5). It is dev-only.

- **Runtime generation.** The Bench does not generate for users. Producing draft prose is the **Writer's** job on the live path; the Bench merely *invokes* the real generation code out-of-band, against frozen fixtures, to measure it (RFC-004 §3; ADR-012 §5). There is **no per-generation live scoring** — the Bench never rides along on a user's generation (ADR-012 §5).
- **Knowledge storage.** The Bench holds no persisted creative knowledge. All knowledge lives in the **Store** (RFC-002 §6.1). The Bench's frozen snapshots are *fixtures* — inert copies for repeatable measurement — not a knowledge store, and they never flow into canon (§6; ADR-012 §2).
- **Retrieval.** The Bench does not perform retrieval as a capability; it *exercises* the real retrieval path to measure it. Selecting knowledge is the Store's one function (RFC-002 §8; RFC-003). The Bench is a designated *arbiter* of retrieval changes, not an owner of retrieval (§10; ADR-018 §6).
- **Prompt editing.** The Bench does not author or edit prompts. Prompt bodies are versioned files owned by the **Prompt System** and edited by the maintainer (RFC-009 §3, §6). The Bench *measures* a prompt change; it never makes one (§8; ADR-012 §5).
- **Human review.** The Bench does not decide what becomes canon, and — critically — it does not gate the user's own output. The **review gate** governs knowledge (RFC-002 §3.4; RFC-005 §5), and the **user is the final judge** of their own creative work (RFC-001 §2.7). The Bench has **no authority to block or flag a user's generation** — automated gates over the user's output are explicitly rejected as paternalistic in a personal tool (ADR-012 §4-C, §5).
- **Any user-facing surface.** The Bench has **zero UI** and no in-product presence — no dashboards, no live scores, no runtime coupling (ADR-012 §5). It is invisible to the running product.

The discipline: **the Bench measures the change process out-of-band and reports; it never generates for users, stores knowledge, selects it, edits prompts, or gates output.**

---

## 5. Evaluation Philosophy

The Bench rests on one commitment: **identical inputs must always produce comparable outputs.** Measurement is only meaningful if the thing being measured is held still except for the change under test.

- **Comparison demands a fixed baseline.** The Bench answers "is the new version better than the old?" — a *comparative* question — and a comparison is only valid when everything except the change under test is identical: the same golden scenes, the same frozen knowledge snapshot, the same code paths (ADR-012 §2–§3). The golden set exists precisely to be that fixed baseline (§6).
- **Comparability depends on deterministic retrieval and context.** RFC-003 makes Entry selection reproducible for a frozen snapshot; ADR-009 makes final assembly reproducible for fixed blocks and inputs. If either varied run-to-run, every comparison would be confounded.
- **Repeatability over any single verdict.** Because a comparison must be reproducible to be trusted, the Bench prizes *repeatable* measurement over a one-off score (§3; ADR-012 §5). The same change, re-measured, must yield the same conclusion — otherwise the maintainer cannot rely on it to merge or revert.
- **Measurements are directional, and honestly so.** The Bench converts vibes into numbers, but the numbers are **directional, not authoritative**: a 20–30-scene set has limited coverage, and a model-based pairwise judgment is itself imperfect and provider-dependent (ADR-012 §5-Negative; §12 here). The philosophy is not "the Bench is the truth" but "the Bench makes change *comparable* enough to catch regressions and inform decisions" — a measurement to reason with, not an oracle to obey.

The philosophy in one line: **hold everything still but the change, measure comparably and repeatably, and treat the result as directional evidence — not gospel.**

---

## 6. Golden Dataset Philosophy

The golden scenes are the Bench's fixed ground. This section explains their *role* — it defines **no dataset, no scene contents, no counts as normative** (those are Defined in the corresponding RFC).

- **Golden scenes are the stable baseline change is measured against.** Each is a frozen scenario — a scene setup plus a frozen knowledge snapshot — chosen to be *representative* of the work the product must do well (ADR-012 §2). Freezing them is what makes a comparison across two prompt versions valid: the inputs do not move, so any output difference is attributable to the change (§5).
- **Coverage spans the scene types that matter.** The set deliberately covers the range of dramatic situations — confession, banter, action, reveal, quiet interiority — because a change can help one scene type and hurt another, and a narrow set would hide that (ADR-012 §2). Breadth of *type*, not volume, is the design goal.
- **The set is small and curated, on purpose.** A handful of well-chosen scenarios, not a vast corpus — because the Bench's value is cheap, directional regression-catching, not a full evaluation platform (ADR-012 §4-D). A large dataset would be a second product's worth of machinery, against the simplicity the whole architecture defends (ADR-001; ADR-012 §4-D).
- **Frozen fixtures are inert, never canon.** A golden snapshot is a copy held still for measurement; it is not part of the Store, never flows into a work's canon, and is not subject to the review gate (§4; RFC-002 §6.1). The golden set lives entirely in the development world.
- **A small fixed set has a known cost: over-fitting.** Because the set is small, prompts can be tuned to please the fixtures rather than to generalize (ADR-012 §5-Negative). This is the tension the next section confronts head-on: the golden set must *evolve* to stay honest, without destroying the comparability that makes it useful.

---

## 7. Benchmark Drift

This section confronts the Bench's sharpest internal tension, as a dedicated commitment: **the benchmarks themselves must evolve over time, yet historical comparability must be preserved.** These two needs pull in opposite directions, and the Bench must hold both.

### 7.1 Why benchmarks must evolve

A frozen golden set does not stay representative forever:

- **Over-fitting erodes honesty.** With a small fixed set, continued tuning eventually optimizes for the *fixtures* rather than for real quality — the scores keep improving while the actual product does not (ADR-012 §5-Negative, §6). A benchmark that is gamed, even unintentionally, has stopped measuring what matters.
- **New failure classes and scene types appear.** As the product grows, new kinds of scenes and new ways to fail emerge that the original set never covered; a benchmark blind to them cannot catch regressions in them (ADR-012 §6). The set must grow to keep pace with the product it guards.
- **The Bench is the designated arbiter of open questions, and those change.** The Bench is explicitly the tool that resolves deferred decisions — whether a third critic is worth its cost, whether embeddings beat keyword retrieval (ADR-012 §6; ADR-005 §6; ADR-018 §6). Serving that role over time requires the set to evolve to probe each new question.

### 7.2 Why historical comparability must be preserved

But naive evolution destroys the Bench's core value: **if the golden set changes, a new score can no longer be compared directly to an old one** — the baseline moved, so the trend line breaks and "is quality compounding?" becomes unanswerable. The whole point of the Bench is comparison over time (§5), and comparison requires a stable reference. Uncontrolled drift in the benchmark would silently invalidate every historical comparison it was built to enable.

### 7.3 Holding both — the discipline

The resolution is to treat the golden set the way the architecture treats prompts: as a **versioned asset that evolves deliberately, with change tracked so comparability is preserved across the change** (RFC-009 §6–§7). Stated as principles (the mechanics are deferred):

- **The set is versioned, and changes are deliberate, not silent.** Like prompt bodies, a change to the golden set is an explicit, recorded act — so it is always known *which* benchmark version a score belongs to (RFC-009 §7; ADR-012 §6). A score without a benchmark version is meaningless.
- **Comparison is valid only within a benchmark version.** An A/B result compares two product versions *against the same golden-set version*; it does not compare across golden-set versions (§5). Drift is contained by scoping every comparison to a fixed benchmark version.
- **A stable core preserves the trend; additions extend coverage.** Evolving the set favors *adding* new scenarios to cover new types and failure classes over silently swapping the existing ones, so a stable core keeps the long-run trend legible while the set still grows (ADR-012 §6). When a scenario must change, the break in comparability is acknowledged and re-baselined, not hidden.
- **Refresh is periodic and intentional.** The set is refreshed on a deliberate cadence to fight over-fitting, treated as a maintenance act with its own record — never an ad-hoc edit mid-measurement that would confound the run in flight (ADR-012 §5-Negative, §6).

*The versioning scheme, refresh cadence, and re-baselining procedure are Defined in the corresponding RFC.*

The commitment in one line: **the benchmark evolves like a versioned asset — growing to stay honest, versioned so that every historical comparison remains valid within its own baseline.**

---

## 8. Relationship with Prompt System

The Bench is the **measurement half** of the Prompt System's change workflow; the two are inseparable (RFC-009 §10).

- **Every prompt change is Bench-gated.** The Prompt System makes prompt bodies changeable, versioned, and diffable; the Bench makes every change *measurable* before it merges (RFC-009 §7, §10; ADR-012 §2). Neither is safe alone: versioning without measurement lets regressions ship with a clean diff; measurement without versioning has nothing to compare (RFC-009 §10).
- **The maintainer's loop closes on the Bench.** Editing a prompt is *edit the file → Bench-compare against the current version → commit if it wins* (ADR-013 §4; RFC-009 §7). The Bench is the gate in that loop — the step that converts "I think this is better" into "this measured better on the golden set" (ADR-012 §2).
- **The Bench measures prompts; it never edits them.** The Bench owns the comparison; the Prompt System owns the bodies (§4; RFC-009 §3). The Bench reports which version won; the maintainer, not the Bench, makes the commit. **This RFC does not redefine the Prompt System — RFC-009 does.**

The one-line boundary: **the Prompt System makes prompts versioned and changeable; the Bench makes every change measured — one workflow, two owners.**

---

## 9. Relationship with Writer

The Bench **reuses the Writer's checks as its metrics** and **exercises the Writer's real code paths** — which is exactly what makes it cheap and faithful (ADR-012 §2–§3, §5).

- **The metrics are the checks the Writer already runs.** The Bench does not invent a separate evaluation apparatus; it repurposes the Writer's ground-truth checks — continuity against facts, voice-attribution against exemplars, and the cheap `qa` assertions — as out-of-band metrics, adding a comparative "which is better?" judgment per scene (ADR-012 §3; RFC-004 §7; ADR-005 §3). This is why the Bench's marginal build cost is *a runner plus fixtures*, not a new system (ADR-012 §1, §5).
- **The Bench tests what ships.** Because it imports the real Writer paths and runs them against frozen fixtures, its results reflect the actual product, not a stand-in (RFC-001 §4.4; ADR-012 §5). A change measured green on the Bench is a change to the code that will run for users.
- **The Bench resolves the Writer's open quality questions.** The deliberately-small launch loop (a bounded set of checks, more deferred) leaves questions — is a third critic worth its cost? — that the Bench is the designated tool to answer with evidence rather than argument (ADR-005 §6; ADR-012 §6). It converts "two critics may be too few" from a debate into a measurement (ADR-012 §6). **This RFC does not redefine the Writer — RFC-004 does.**

The one-line boundary: **the Writer defines and runs the checks live; the Bench reuses those same checks out-of-band to measure change — no separate metric apparatus.**

---

## 10. Relationship with Retrieval

The Bench is the **designated arbiter** of retrieval and context-assembly changes (ADR-018 §6; RFC-003).

- **Retrieval changes are Bench-gated.** Retuning ranking weights, or adopting embeddings over keyword retrieval, ships **only** when the Bench shows it helps — the Bench is the explicit trigger for both (RFC-003; ADR-018 §6). Retrieval quality, being silent when it fails, must be settled by measurement, not intuition (RFC-003).
- **Retrieval quality is measured through its downstream effect.** The Bench does not grade retrieval in isolation; it measures whether the *output* improved when retrieval changed — the same built-in checks pass more often when the right knowledge was retrieved (RFC-003; ADR-012 §3). Retrieval is evaluated by what it enables the Writer to produce.
- **This depends on frozen snapshots and deterministic selection.** A retrieval change can be attributed only because golden fixtures freeze the knowledge, RFC-003 fixes deterministic selection, and ADR-009 fixes deterministic assembly. **This RFC exercises those contracts; it does not redefine them.**

The one-line boundary: **the Bench is where every retrieval and assembly change earns its way in — measured on frozen scenes, judged by output quality.**

---

## 11. Evolution Strategy

The Bench is designed to grow with the product it guards, without becoming a second product itself (ADR-012 §4-D, §6).

- **The golden set grows and refreshes.** New scene types and new failure classes are added as they appear, and the set is periodically refreshed to fight over-fitting — evolved as a versioned asset so historical comparability survives (§7; ADR-012 §6). This is the Bench's primary evolution surface.
- **New metrics are added sparingly, reusing what exists.** As new checks appear in the Writer, they become available as Bench metrics for free — the Bench grows by *reuse*, not by building a parallel evaluation apparatus (ADR-012 §3, §5; §9 here). A metric earns its place by catching a failure the existing ones miss.
- **The Bench becomes the arbiter of more deferred decisions.** Its role as the tool that resolves "is this worth it?" questions extends naturally to each new deferred capability — a third critic, embeddings, a new stage — making the Bench the standing mechanism by which the architecture's deferred seams are opened on evidence (ADR-005 §6; ADR-018 §6; ADR-012 §6; RFC-001 §7.4).
- **It stays dev-only, cheap, and zero-UI — permanently.** The Bench does not evolve toward in-product scoring, dashboards, or automated gates; those are explicitly and permanently rejected (ADR-012 §4-B, §4-C, §5). Any minimal in-product surfacing would only ever be a feature-flagged maintainer playground, never default behavior (ADR-012 §6; ADR-014). Evolution adds coverage and arbitration power, never runtime coupling.

---

## 12. Architectural Risks

The Bench is a strong bet, and — being itself an imperfect measurement instrument — it demands unusual honesty about its own limits.

### 12.1 Can evaluation become too expensive?

**Yes.** Running the real code paths across the golden set, especially with a model-based pairwise judgment per scene, is model work — and a model judge *per scene* adds real token cost (ADR-012 §4-B, §5-Negative). Unbounded, evaluation could rival the cost of the generation it guards.

The guards:

- **A small, fixed set bounds the cost.** A curated 20–30-scene set — not a large corpus — keeps each Bench run cheap by design (ADR-012 §2, §4-D). Cost scales with a deliberately small set, not with the whole Store.
- **Reusing the Writer's checks means near-zero marginal build.** The Bench adds a runner and fixtures, not a new evaluation engine, so its cost is dominated by the model calls it chooses to make (ADR-012 §1, §5). Expensive model-judging is used where cheap deterministic checks cannot decide, not everywhere.
- **It runs out-of-band, not per generation.** Because the Bench never scores live generations, its cost is paid occasionally by the maintainer at change time — not multiplied across every user interaction (ADR-012 §4-B, §5). This is the decisive reason continuous in-product evaluation was rejected.

### 12.2 Can benchmarks become stale?

**Yes — staleness and over-fitting are the Bench's defining internal risk**, addressed as a dedicated concern in §7. A fixed set drifts out of representativeness as the product grows, and continued tuning can optimize for the fixtures rather than for quality (ADR-012 §5-Negative, §6).

The guards:

- **Deliberate, versioned evolution of the golden set.** The set grows and refreshes as a versioned asset, preserving comparability while staying honest (§7; ADR-012 §6). Staleness is fought by periodic, tracked refresh — not left to rot.
- **Breadth of scene type over volume.** Diverse fixtures reduce the chance that tuning to the set diverges from tuning for real quality (ADR-012 §5-Negative, §6).
- **Scores treated as directional.** Because the set is small and known to be gameable, its scores inform decisions but do not dictate them — the maintainer reads them as evidence, keeping the human in the loop (ADR-012 §5-Negative; §5 here).

### 12.3 How should benchmark quality evolve?

**By being measured against reality, and kept honest by design** — the Bench must not be trusted blindly:

- **The judge is imperfect, and treated as such.** Model-based pairwise scoring is itself imperfect and provider-dependent; it is directional, never authoritative (ADR-012 §5-Negative). Benchmark quality improves by favoring the *deterministic ground-truth checks* (continuity, voice-attribution) where they apply, and using the softer model judgment only where nothing harder exists (ADR-012 §3; §9 here).
- **Coverage improves as failures escape it.** When a regression reaches the reading that the Bench missed, that is the signal to extend the golden set — real escapes drive benchmark growth, so the set improves against actual failure rather than in the abstract (ADR-012 §6; §7 here).
- **The Bench stays a means, not an end.** The user remains the final judge (RFC-001 §2.7); the Bench's job is to catch regressions cheaply and inform tuning, and its quality is measured by how well it does *that* — not by chasing a perfect score (ADR-012 §4-C, §5). *Scoring methods are Defined in the corresponding RFC.*

---

## 13. Out of Scope

This RFC deliberately defines **none** of the following. Each is named so no later reader mistakes this document for defining it:

- **Scoring methods** — the metric formulas, the pairwise-judgment procedure, thresholds, aggregation. *Defined in the corresponding RFC.*
- **Models** — which model performs any model-based judgment, provider selection for the judge. *Defined in the corresponding RFC (the Provider Adapter RFC).*
- **Algorithms** — the runner logic, comparison computation, regression-detection procedure. *Defined in the corresponding RFC.*
- **Datasets** — the golden scenes' contents, counts as normative, snapshot format, refresh procedure, versioning scheme. *Defined in the corresponding RFC.*
- **Automation / CI** — how and when Bench runs are triggered, integration into any pipeline, reporting format. *Defined in the corresponding RFC.*
- **Implementation** — the runner, fixtures, storage of results, quality-history persistence. *Defined in the corresponding RFC.*
- **The Writer checks, retrieval, the Prompt System, and the Store** — owned by their respective RFCs; reused or exercised here, not redefined.

Wherever this document needed such a detail, it wrote **"Defined in the corresponding RFC"** (naming the topic) and stopped, by rule.

---

## 14. Dependencies

RFC-010 depends on **RFC-001**, **RFC-004**, **RFC-003**, and **RFC-009** and must conform to them (and to the other completed RFCs); where they conflict, they govern (RFC-001 §10; and the dependency notes of the prior RFCs). The Bench is a development capability that *guards* the rest of the system rather than being consumed at runtime; the following areas **depend on the Bench** as the gate that lets their changes ship safely, and none may override the dev-only, out-of-band, never-gates-user-output, measured-not-intuited boundaries established above:

| Depends on the Bench | Depends on it for |
|---|---|
| **The Prompt System RFC (RFC-009)** | Gating every prompt-body change with an A/B measurement before it merges. |
| **The Writer Pipeline & Scene/Episode RFC** | Deciding whether a new stage or an additional critic earns its cost; the Writer's checks double as Bench metrics. |
| **The Analyst-facet RFC** | Measuring whether a new or changed extraction facet improves quality before it ships. |
| **The Store-wide Retrieval RFC (RFC-003)** | Arbitrating ranking-weight changes and the keyword-vs-embedding decision on frozen scenes. |
| **The Living Story Bible & Continuity Loop RFC** | Measuring extraction precision and contradiction-catch quality that keep the living Bible trustworthy. |
| **The Relationship System RFC** | Measuring relationship-inference precision and regression-catch quality. |
| **The Character / World DNA Organization RFC** | Measuring character fidelity and voice-attribution quality; gating any structured DNA field. |
| **The Provider Adapter RFC** | Supplying the model used for any model-based comparative judgment, out-of-band. |

> The forward references above are named by title rather than by number, because the Bench's dev-only, out-of-band, measured-before-shipping discipline — and its refusal to gate the user's own output — are what those areas rely on regardless of final numbering. Their **dependence on Bench-gated change, reuse of the Writer's checks as metrics, and deterministic frozen-fixture comparison is fixed**; where a successor and this RFC appear to conflict on those, this RFC — and behind it RFC-001 through RFC-009 and the ADR set — governs.

---

## Appendix A — Traceability

| RFC-010 Section | Primary sources |
|---|---|
| §1 Purpose | RFC-001 §2.4, §3.4, §4.4, §7; RFC-009 §2; ADR-012 §1–§2, §5; `architecture-final-minimal.md` §7 |
| §2 Why the Bench Exists | ADR-012 §1–§2, §5; RFC-001 §2.4; ADR-013 §4; RFC-009 §10; `architecture-final-minimal.md` §7 |
| §3 Responsibilities | ADR-012 §2–§5; RFC-001 §4.4; RFC-003 |
| §4 Does NOT Own | RFC-001 §2.7, §4.4; RFC-002 §6.1, §8, §3.4; RFC-004 §3; RFC-005 §5; RFC-003; RFC-009 §3, §6; ADR-012 §4-B, §4-C, §5 |
| §5 Evaluation Philosophy | ADR-012 §2–§3, §5; RFC-003; RFC-009 §10 |
| §6 Golden Dataset Philosophy | ADR-012 §2, §4-D, §5-Negative; RFC-002 §6.1; ADR-001 |
| §7 Benchmark Drift | ADR-012 §5-Negative, §6; ADR-005 §6; ADR-018 §6; RFC-009 §6–§7; RFC-003 |
| §8 Relationship with Prompt System | RFC-009 §3, §7, §10; ADR-012 §2; ADR-013 §4 |
| §9 Relationship with Writer | ADR-012 §1, §3, §5–§6; RFC-004 §7; ADR-005 §3, §6; RFC-001 §4.4 |
| §10 Relationship with Retrieval | RFC-003–§12; ADR-018 §6; ADR-012 §3 |
| §11 Evolution Strategy | ADR-012 §3, §4-B–§4-D, §5–§6; ADR-005 §6; ADR-018 §6; RFC-001 §7.4; ADR-014 |
| §12 Architectural Risks | ADR-012 §2, §4-B, §5-Negative, §6; RFC-001 §2.7; ADR-013; §7 here |
| §13 Out of Scope | RFC-001 §9 (RFC boundary conventions) |
| §14 Dependencies | RFC-001 §10; RFC-009 §14 |

*End of RFC-010.*
