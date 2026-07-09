# ADR-012: Bench Evaluation System

- **Status:** Accepted (revised v2 — **upgraded** from "optional, maybe-never" to a **necessary** dev harness, built early)
- **Date:** 2026-07-09 (v1) · revised 2026-07-09 (v2)
- **Deciders:** Architecture Review Board
- **Related:** ADR-001, ADR-005, ADR-008, ADR-009, ADR-013

## 1. Context

v1 adopted a *lightweight, offline* Bench but was lukewarm — it flagged *whether to build it at all* as "Needs Validation," reasoning that a single user is already the judge. `architecture-final-minimal.md` §0/§7 makes the opposite case forcefully and, on reflection, correctly for **this** architecture:

> *"The missing engine that matters most after shipping is the Bench … everything above makes creative behavior live in prompt files — which means creative behavior will change constantly. Without measurement, week-6-you will 'improve' a prompt and silently break voice consistency, and you will not find out until a user does."*

The key is a **conditional the Board now grants**: v2's whole architecture deliberately moves creative logic *into constantly-changing prompt files and entry types* (ADR-001 governing rule, ADR-005 stages, ADR-008 facets). That choice *creates* the regression risk — so the Bench is not an optional nicety, it is the **safety mechanism that makes prompt-file-centrism survivable.** v1 was lukewarm because v1 put less in prompt files; v2's design makes the Bench necessary.

The reservation the Board *keeps*: the Bench stays strictly dev-only, zero-UI, and cheap — it reuses the Writer's checks as metrics, so its marginal build cost is a runner + fixtures.

## 2. Decision

**Adopt the Bench as a necessary, dev-only evaluation harness, built early (build-order step 4), reusing the Writer's checks as metrics. No in-product evaluation runtime.**

1. **Necessary, not optional.** Because creative behavior lives in prompt files/stages/entry types that change weekly, every such change is Bench-gated. This is the meta-engine that lets quality *compound* instead of oscillate.
2. **Golden set:** 20–30 fixed scenarios (scene card + a frozen entry snapshot) spanning scene types — confession, banter, action, reveal, quiet interiority (`architecture-final-minimal.md` §7).
3. **Metrics = the checks already built** (ADR-005/020): contradiction count, voice-attribution accuracy, hook presence, length adherence, LLM-ism hits, repetition score — **plus** a pairwise "old vs. new — which is better?" model judgment per golden scene.
4. **Usage:** every prompt/stage/retrieval change runs the Bench and emits a one-page diff report. Marginal cost = a runner script + fixtures (it reuses Writer checks).
5. **Dev-only, zero UI, zero runtime coupling.** It imports the real code paths (so it tests what ships) but runs out-of-band. **No** per-generation live scoring, **no** automated quality gates blocking the user's own output, **no** dashboards in the app.
6. **Build it in step 4** (with the first checks + diff capture), not speculatively before there is a pipeline to measure — but not deferred indefinitely either.

**Where the Board updates itself:** v1's "maybe never build it" is withdrawn. Given v2's prompt-file-centric architecture, *not* building the Bench would be negligent. The Board agrees with `architecture-final-minimal.md` that this is the single most important thing to add after the quality core.

## 3. Alternatives Considered

- **A. v1's "optional, maybe never."**
- **B. Continuous in-product evaluation** — score every live generation, dashboards.
- **C. Automated quality gates** — block/flag sub-threshold generations.
- **D. Full external eval platform** with large datasets/CI.

## 4. Why Rejected

- **A — Optional/maybe-never:** Withdrawn. It ignored that v2 deliberately concentrates volatile behavior in prompt files, which mandates regression measurement. Rejected.
- **B — Continuous in-product eval:** Doubles token cost (judge per generation), latency, and complexity, with an audience of one who already reads the output. Rejected.
- **C — Automated gates:** Blocking the user's *own* creative output on an imperfect automated judge is paternalistic in a personal tool — the user is the final judge. Rejected.
- **D — Full eval platform:** A second product's worth of machinery; violates simplicity (ADR-001). The 20–30-scene reuse-the-checks Bench captures the value cheaply. Rejected.

## 5. Consequences

**Positive**
- Turns constant prompt/stage tuning from vibes into measured A/B — the difference between compounding and oscillating quality.
- Near-free to build (reuses Writer checks); zero runtime cost/complexity for users.
- Tests the real code paths, so results reflect what ships.

**Negative**
- A 20–30-scene set has limited coverage; prompts can over-fit to fixtures (mitigate: diverse fixtures, treat scores as directional).
- LLM-as-judge pairwise scoring is itself imperfect and provider-dependent — directional, not authoritative.
- Maintainer effort with no user-visible feature (but now justified as necessary infrastructure).

**Future risks**
- Over-fitting to the golden set; refresh fixtures periodically.
- The "two critics may be too few" question (ADR-005) is *resolved by the Bench* — converting an argument into a measurement.

## 6. Future Revisit Conditions

- Grow/refresh the golden set as new scene types or failure classes appear.
- Use the Bench to decide ADR-005's third-critic and ADR-018's embeddings questions — it is the designated arbiter for both.
- Reconsider a minimal in-product surfacing only via the feature-flagged playground extension, never as default behavior (ADR-014).
