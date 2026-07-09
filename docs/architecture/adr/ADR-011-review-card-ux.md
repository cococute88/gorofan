# ADR-011: Review Card UX

- **Status:** Accepted — *the canonical human-in-the-loop gate for all AI-proposed canon changes*
- **Date:** 2026-07-09
- **Deciders:** Architecture Review Board
- **Related:** ADR-002, ADR-004, ADR-008, ADR-010, ADR-014

## 1. Context

Multiple decisions in this set depend on a single UX primitive: **AI proposes, human disposes.** The Living Story Bible must not self-mutate (ADR-004); reference/style distillation is a proposal (ADR-008); learning happens by curating proposals into Entries (ADR-010); AI-inferred relationships are proposals (ADR-006). All of these need a *consistent, low-friction, mobile-first* way for the user to accept, edit, or reject an AI suggestion.

`design.md` gestures at this with "non-blocking banners" for the Lore Consistency Checker but never generalizes it. The Board elevates it to a first-class, reusable pattern: the **Review Card**.

The constraints are severe and specific: this must work **on a phone**, must **never block** the primary creative flow (BR-6/BR-7), and must impose **minimal cognitive load** — because if triaging proposals is annoying, the user disables the flywheel and the product loses its differentiator.

## 2. Decision

**Adopt the Review Card as the single, canonical UX pattern for every AI-proposed change to canon.** No AI-proposed mutation reaches the source of truth by any other path.

Principles (UX-level decisions, not visual spec):
1. **Uniform shape:** every proposal — a new fact, a relationship, a glossary term, a style Entry, a chapter-derived event — is presented as a Card with: what is proposed, where it came from (provenance/source), and three actions: **Accept / Edit-then-accept / Reject**.
2. **Non-blocking and batchable:** Cards surface *asynchronously* (a review queue / badge), never interrupting the active chat or writing stream. The user triages when they choose. Proposals accumulate as pending Entries (ADR-004) until reviewed.
3. **Editable before accept:** the user can correct a proposal in place; accepting an edited card writes the *edited* version as canon with provenance `user-approved`.
4. **Reversible:** accept/reject are auditable and undoable (proposals and their disposition are recorded); a wrongly-accepted fact can be removed.
5. **Progressive disclosure:** the review surface lives inside existing screens (e.g. a Bible/world review queue, a chapter's "suggestions" area) and behind the "more/advanced" affordances — it does **not** add a top-level navigation item (ADR-014).
6. **The gate is architectural, not optional chrome:** it is the *only* write path from Analyst/Writer proposals into the Store (ADR-002 rule #2). Bypassing it is forbidden.

## 3. Alternatives Considered

- **A. Auto-apply with undo** — AI writes proposals straight to canon; user can undo later.
- **B. Modal/blocking approval** — each proposal interrupts the flow with a required decision before continuing.
- **C. Bulk raw-diff editor** — dump all proposed changes as a text diff for wholesale accept/reject.
- **D. No dedicated pattern** — each feature invents its own approval affordance.

## 4. Why Rejected

- **A — Auto-apply + undo:** Places the burden of *catching* errors on the user after canon is already polluted and already influencing generation. Undo-after-the-fact doesn't prevent the compounding-hallucination problem (ADR-004); by the time the user notices, downstream generations were already contaminated. Rejected — the gate must be *before* canon.
- **B — Modal/blocking:** Directly violates "never block the creative flow" (BR-6). Interrupting a mobile writing session to adjudicate a fact is hostile and would train the user to reflexively dismiss, defeating the purpose. Rejected.
- **C — Bulk raw diff:** Poor on mobile, high cognitive load, and encourages careless bulk-accept (the opposite of a quality gate). Fine as an optional power-user view later, wrong as the default. Rejected as primary.
- **D — Per-feature ad-hoc:** Guarantees inconsistency, duplicated code, and gaps where some feature quietly writes canon without review — silently breaking ADR-002/004. A single pattern is both simpler and safer. Rejected.

## 5. Consequences

**Positive**
- One consistent, learnable interaction governs the product's riskiest operation (canon mutation).
- Non-blocking + batchable keeps the creative flow sacred while still enabling the flywheel.
- Provenance + reversibility make canon trustworthy over a multi-year project.
- Reused across every AI-proposal feature → less UI code, uniform behavior.

**Negative**
- Introduces a triage responsibility; if proposals are frequent and low-value, the queue becomes noise (mitigation: only surface high-signal proposals; tune extraction; allow "mute this kind").
- Slightly slower path from AI insight to usable canon than auto-apply.

**Future risks**
- Queue fatigue is the real failure mode: if users stop triaging, pending Entries stagnate. This is the concrete trigger to *validate* bounded auto-accept for narrow, high-precision proposal kinds (ADR-004 §6) — accept-by-default with easy revert for those kinds only.
- Designing a genuinely low-friction mobile review surface is non-trivial UX work; a clumsy implementation could sink the whole flywheel.

## 6. Future Revisit Conditions

- If triage fatigue is observed, revisit *per-kind* policies: keep the gate for low-precision kinds, allow validated auto-accept-with-revert for high-precision kinds (coordinate with ADR-004/ADR-010).
- If power users want bulk operations, add an optional advanced bulk-review view *in addition to* (not replacing) the card default.
- Revisit the surfacing model (queue vs inline vs digest) once real usage shows where users actually notice and act on cards.
