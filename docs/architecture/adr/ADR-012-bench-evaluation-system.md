# ADR-012: Bench Evaluation System

- **Status:** Accepted — *lightweight, offline, developer-facing Bench adopted; in-product continuous evaluation runtime rejected. Whether to build even the lightweight Bench is **Needs Validation***
- **Date:** 2026-07-09
- **Deciders:** Architecture Review Board
- **Related:** ADR-005, ADR-007, ADR-009, ADR-010, ADR-016

## 1. Context

Prompt tuning (ADR-009), the single-vs-multi-pass question (ADR-005), character-consistency choices (ADR-007), and provider/model selection (ADR-016) all raise the same need: **a way to tell whether a change actually improved output**, rather than relying on vibes. A "Bench" is an evaluation harness: a fixed set of scenarios run through the system, whose outputs are scored (by human, by rubric, or by an LLM-judge) and compared across prompts/models/pipeline variants.

The risk is over-building. A production-grade eval platform (continuous scoring of live generations, regression dashboards, automated gates) is heavy infrastructure — and for a **single user**, most of it has no audience. But *some* measurement discipline is what separates principled tuning from superstition.

This is the one ADR where the Board is least certain the artifact is worth building at all for a one-person product; that uncertainty is stated openly.

## 2. Decision

**Adopt a deliberately lightweight, offline, developer-facing Bench — a tuning instrument, not a product subsystem. Reject any in-product, always-on evaluation runtime.**

1. **Offline and opt-in.** The Bench is a development tool the *maintainer* runs, not a service that scores live user generations.
2. **Small curated scenario set.** A handful of representative fixtures (a chat exchange, a chapter continuation, a style-imitation task, a character-consistency probe) — not a large corpus. Fixtures are versioned as files (ADR-013 kinship: tuning artifacts belong in the repo).
3. **Comparison, not grading.** Its core job is *A/B comparison* — old prompt vs new, model X vs Y, single-pass vs multi-pass — surfaced side by side. Scoring may be manual (maintainer judgment) and/or an **LLM-as-judge** rubric; both are acceptable, neither is authoritative.
4. **No runtime coupling.** The Bench imports the same Prompt Engine / Adapter code paths as production (so it tests the real system) but runs out-of-band. It adds **no** always-on evaluation, no live scoring, no dashboards in the app.
5. **Feature-flagged if surfaced at all.** Any in-app entry point (e.g. a "prompt/model playground" — a listed future extension) is L3/advanced, behind a flag, and reuses the Bench fixtures. It never enters primary navigation (ADR-014).
6. **Existence is Needs Validation.** Build it only when a real tuning decision (e.g. ADR-005 multi-pass, ADR-009 priority tuning, provider selection) actually needs evidence. Do not build a Bench speculatively.

## 3. Alternatives Considered

- **A. Continuous in-product evaluation** — score every live generation, track quality metrics over time, show dashboards.
- **B. Automated quality gates** — block/flag generations that fall below an eval threshold.
- **C. No evaluation at all** — tune by intuition and manual spot-checks.
- **D. Full external eval platform** — adopt/build a comprehensive LLM-eval framework with datasets, metrics, and CI integration.

## 4. Why Rejected

- **A — Continuous in-product eval:** Doubles token cost (a judge call per generation), adds latency and complexity, and produces dashboards with an audience of one who is already reading the output. The value/cost ratio for a single user is poor. Rejected.
- **B — Automated gates:** Blocking or auto-rejecting the user's own generation based on an imperfect automated judge is user-hostile and paternalistic in a personal creative tool — the user *is* the judge. Rejected.
- **C — Nothing:** Leaves consequential decisions (multi-pass? which model? which prompt?) to guesswork, risking silent quality regressions precisely where the product's value lives. Some measurement is worth its modest cost. Rejected.
- **D — Full eval platform:** Enormous over-build for a personal app; a second product's worth of machinery. Directly violates simplicity-as-tie-breaker (ADR-001). Rejected.

## 5. Consequences

**Positive**
- Turns the highest-leverage tuning decisions (prompt, model, pipeline shape) from vibes into evidence, cheaply.
- Zero runtime cost/complexity for end users; nothing ships in the hot path.
- Reuses production code paths, so it tests what actually runs.

**Negative**
- A small fixture set has limited coverage; it can mislead if fixtures aren't representative (over-fitting prompts to the Bench).
- LLM-as-judge scoring is itself imperfect and provider-dependent; results are directional, not authoritative.
- It is maintainer effort that produces no user-visible feature — easy to skip, hence the explicit Needs-Validation stance.

**Future risks**
- Prompt/model tuning could over-fit to the Bench fixtures and generalize poorly; mitigated by keeping fixtures diverse and treating scores as directional.
- Scope creep toward option A/D is a constant temptation ("just log every generation's score"); this ADR is the guardrail.

## 6. Future Revisit Conditions

- **Decide to build it** when the first real evidence-needing decision arrives (ADR-005 multi-pass validation is the likely trigger). If no such decision materializes, the Bench may never be built — and that is an acceptable outcome for a personal tool.
- If the maintainer becomes a heavy multi-model user, revisit a slightly richer comparison surface (still offline, still opt-in).
- Reconsider (still cautiously) any in-product surfacing only via the feature-flagged playground extension, never as default behavior.
