# ADR-010: Learning System Philosophy (Capture Now, Distill Later)

- **Status:** Accepted (revised v2 — anti-ML-training **validated**; adds the critical new decision to **capture edit diffs from day one**)
- **Date:** 2026-07-09 (v1) · revised 2026-07-09 (v2)
- **Deciders:** Architecture Review Board
- **Related:** ADR-004, ADR-007, ADR-008, ADR-011, ADR-012

## 1. Context

v1 adopted "learning" as **human-curated accumulation** (richer Bible, example library, tuned prompts) and **rejected** ML training / fine-tuning / opaque preference vectors. The reviews both engage this and land close to v1 — with one important addition v1 missed:

- `design-review-ai-author-os.md` R25 calls edit-diff preference learning *"the moat … what makes it an Author OS rather than a generator."*
- `architecture-final-minimal.md` §4 **self-corrects R25**: *"ship capture, not learning."* Store draft-vs-accepted text **from day one** — *"this is the data you can never retroactively collect."* The "learning" is a periodic **Analyst facet** over diffs producing `preference` entries injected into future prompts. **No online-learning machinery, no per-edit classification pipeline.**

This is strong convergence with v1's transparency ethos — `preference` entries are exactly the "transparent, editable artifacts" v1 required — *plus* the point v1 got wrong by omission: **capture is urgent even though learning is deferred.**

## 2. Decision

**Keep "learning" as human-curated, transparent accumulation — no ML training. Add: capture edit diffs from day one; distill them later via an Analyst facet into transparent `preference` entries.**

1. **No fine-tuning, no reward models, no online learning, no opaque preference vectors** (unchanged from v1). Anything that shapes future output must be a **visible, editable, revertible** artifact.
2. **Capture edit diffs from day one** (the new, urgent decision): store draft text vs. accepted text per chapter (one column pair on the substrate). This is data that *cannot be recovered retroactively*, so it is captured immediately even though the learning that uses it is deferred.
3. **"Learning" = an Analyst facet, run periodically** (`scope=work`→`user`), that distills accumulated diffs into `preference` entries (e.g. sentence-length deltas, adverb-rate, per-character particle fixes). These are Store entries (ADR-003) with provenance `diff batch`, injected into future prompts by the Writer's retrieve step.
4. **The primary learning mechanisms remain transparent artifacts** (validated by both reviews): a richer Living Bible (ADR-004), canonical exemplars (ADR-007, including chat-bookmarked lines R22), and versioned prompt/tone-contract tuning (ADR-013).
5. **Scope discipline:** MVP-lite = capture + apply the 3 coarsest signals (sentence length, adverb rate, per-character particle fixes). A full edit taxonomy is Future. No per-edit real-time classification.
6. **Optional delight, not configuration:** a periodic "문체 리포트" is acceptable as read-only output; it never becomes a control surface.

**Explicit agreement:** the Board agrees with `architecture-final-minimal.md`'s "capture-not-learning" correction — it fixes a real v1 omission (urgency of capture) while *preserving* v1's core principle (no opaque ML; learning = transparent, injected `preference` entries).

## 3. Alternatives Considered

- **A. Fine-tuning / preference-model training** on user feedback (R25 read maximally).
- **B. Online per-edit classification pipeline** that updates behavior continuously.
- **C. Don't capture diffs** (v1's implicit stance — treat learning entirely as manual curation).
- **D. Auto-applied preference vectors** (opaque embeddings of edits steering generation).

## 4. Why Rejected

- **A — Training/fine-tuning:** Infrastructure + cost for one user; reintroduces provider lock-in; opaque/un-revertible; needs its own eval to avoid regressions. Against founding principles; both reviews avoid it. Rejected.
- **B — Online per-edit pipeline:** `architecture-final-minimal.md` explicitly deletes this from v1 scope; it is machinery where a monthly facet suffices. Rejected.
- **C — Don't capture:** The v1 omission. Diffs uncaptured are *permanently* lost; deferring learning is fine, deferring capture is not. Rejected (this is the substantive v2 change).
- **D — Opaque vectors:** Silent behavioral drift, un-editable — fails the transparency test (as v1 held). Rejected; the human-readable equivalent (`preference` entries) is adopted.

## 5. Consequences

**Positive**
- The product genuinely improves per-author over time with **zero** ML machinery — via transparent, editable `preference` entries and a growing Bible/exemplar library.
- Capturing diffs from day one preserves the option value of the "moat" without committing to any learning machinery now.
- Everything shaping output stays inspectable and revertible; no silent regressions from an opaque learner.

**Negative**
- Diff storage grows over time (draft+accepted per chapter); modest at personal scale but non-zero.
- "Learning" requires the periodic facet run + still benefits from user curation; it is not fully automatic.
- Coarse initial signals (3) may under-capture nuance until the taxonomy expands.

**Future risks**
- Captured diffs are user-writing data; retention stays **local and minimal** (personal tool).
- Pressure to "just fine-tune on my edits" as local training cheapens; this ADR must be re-decided, not drifted past.

## 6. Future Revisit Conditions

- Expand the diff taxonomy beyond the 3 coarse signals when the Bench (ADR-012) shows richer `preference` entries improve fidelity.
- Reconsider any automated adaptation only if it can be simultaneously local/cheap, portable, transparent, and revertible — else keep the facet model.
- Revisit retention/report design if diff volume or privacy considerations grow.
