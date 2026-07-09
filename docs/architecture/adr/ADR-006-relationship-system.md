# ADR-006: Relationship System

- **Status:** Accepted (revised v2 — **validated** by both reviews; vocabulary aligned to entries + stages)
- **Date:** 2026-07-09 (v1) · revised 2026-07-09 (v2)
- **Deciders:** Architecture Review Board
- **Related:** ADR-003, ADR-004, ADR-005, ADR-020

## 1. Context

v1 decided relationships should be **typed entries**, not a dedicated graph subsystem, with visualization deferred behind a feature flag. Both reviews independently reach the same conclusion, in the same words: `architecture-final-minimal.md` §3 says the Relationship Planner (R9) and Foreshadow Scheduler (R10) are *"three things each: an entry type, two lines in the retrieval list, and one check … they are rows and prompt clauses,"* not modules. This is a strong external validation of the v1 decision. The only update needed is to align vocabulary to the now-adopted single Entry model (ADR-003) and the Writer stage model (ADR-005).

The reviews also **enrich** the relationship concept for romance (로판-critical): a **relationship-stage ladder** extracted from references (§2.8), monotonic-with-intent progression (not random oscillation), and a **relationship arc planner** that plans stage transitions across the arc *before* placing scenes (R9).

## 2. Decision

**Adopt relationships as `relationship` Store entries, planned as a Writer stage, checked as a `qa` assertion. No graph subsystem, no graph database.**

1. **Canonical form: `relationship` entries** (ADR-003), `subject` = the pair, `data` = current stage on the extracted stage ladder + last-transition event; prose `content` describes chemistry mechanics / power balance. Provenance + status apply (AI-inferred = proposed, ADR-011).
2. **Relationship-arc planning is a Writer stage, not an engine** (R9): the `plan_scenes` stage retrieves `relationship` + `promise` entries and places scenes to justify each planned stage transition. Romance progression is *monotonic-with-intent* — the anti-oscillation guarantee readers consume.
3. **A cheap `qa` check** flags relationship regressions (a scene moving a pair backward without an intended trigger), consistent with the two-model-check budget (ADR-005).
4. **Visualization stays a deferred, feature-flagged, read-only projection** computed on demand from `relationship` entries — inside existing screens (바이블/서재), never top-level nav (ADR-014). Full relationship graphs remain Future (both reviews concur; `design-review` R9 scopes MVP to the *primary couple*).
5. **No second storage engine.** Relationship queries at personal scale are ordinary Store retrieval.

## 3. Alternatives Considered

- **A. Dedicated relationship-graph subsystem** (typed-edge table, traversal API, interactive editor) in MVP.
- **B. Relationships buried in character free-text** (no structured entry).
- **C. Graph database** for relationships.
- **D. Per-scene relationship inference with no macro plan** (let the model decide progression per draft).

## 4. Why Rejected

- **A — Subsystem in MVP:** Both reviews reduce it to entry + retrieval-lines + check; a subsystem is over-naming (ADR-002). Rejected; visualization is a deferred projection.
- **B — Free-text only:** Can't be retrieved by stage, checked for regression, planned across an arc, or visualized without re-parsing prose. Rejected as too lossy — and contradicts the flywheel.
- **C — Graph DB:** Second storage engine; breaks Zero-Cost and the single-`DATABASE_URL` swap (ADR-017); unnecessary at personal cast sizes. Rejected.
- **D — No macro plan:** This is precisely the failure both reviews call out — LLMs oscillate relationships (cold/warm/cold) with no direction. The stage-ladder + arc plan is the fix (R9). Rejected.

## 5. Consequences

**Positive**
- Zero new subsystem/storage; relationships ride the Entry model, the retrieval function, and the Writer stages.
- Monotonic-with-intent romance progression — the core 로판 loop — is planned, retrievable, and checkable.
- Expensive visualization is opt-in and derived; the canonical model is untouched by it.

**Negative**
- Complex graph queries (clusters, shortest paths) are awkward on flat entries; a derived projection would be needed if they become core.
- Temporal evolution (stage across chapters) is expressible via `data` + `created_at_chapter` but not elegantly for deep timeline math (shares ADR-003's prose-first risk).

**Future risks**
- Large casts with intricate political webs may justify a derived graph projection for querying/visualization — still a disposable read model, never a second source of truth.

## 6. Future Revisit Conditions

- Build the visualization projection when the maintainer actually has enough relationships that a visual overview pays off.
- Extend from the primary couple to full relationship graphs only when a real work demands it (both reviews mark this Future).
- If stage-transition math strains `data` JSON, promote `relationship` to a structured table (ADR-003 §6).
