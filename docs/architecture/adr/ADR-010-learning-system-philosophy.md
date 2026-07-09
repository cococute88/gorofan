# ADR-010: Learning System Philosophy

- **Status:** Accepted — *explicit, human-curated "learning" adopted; automated ML/feedback-training subsystem rejected (**Needs Validation** for any bounded future form)*
- **Date:** 2026-07-09
- **Deciders:** Architecture Review Board
- **Related:** ADR-004, ADR-007, ADR-008, ADR-011, ADR-012

## 1. Context

A "Learning System" implies the product improves over time from user behavior — edits, regenerations, accepted/rejected suggestions, ratings. The ambitious interpretation is a machine-learning feedback loop: collect preference signals, train/fine-tune a model or a reward model, and condition future generation on it (RLHF-lite, preference learning, personalized fine-tunes).

This is not in `design.md`. For a **single-user, zero-cost, provider-neutral** product, an ML training loop is one of the highest-complexity, lowest-ROI things imaginable: it needs data pipelines, training infrastructure, model hosting, evaluation to avoid regressions, and it *reintroduces vendor lock-in* (fine-tunes are provider-specific and non-portable) — contradicting the product's founding principles.

Yet "learning" in a weaker, valuable sense is real: the system *should* get better at serving *this* user as their world, characters, and preferences accrue.

## 2. Decision

**Adopt "learning" as explicit, transparent, human-curated accumulation — not model training.** The system learns by *growing editable artifacts*, not by adjusting opaque weights.

Concretely, learning = the compounding of three transparent artifacts, all already in the architecture:
1. **A richer Living Story Bible** (ADR-004): every accepted fact/relationship/style Entry makes future generation more grounded. This is the primary learning mechanism.
2. **A growing example/few-shot library**: accepted outputs and user edits can be curated (via Review Cards, ADR-011) into reusable example Entries that demonstrate desired voice/style (ties to ADR-007/ADR-008).
3. **User-tuned prompts and settings** (ADR-013): the user (or the maintainer) adjusts prompt templates and model configs based on observed results — versioned and diffable.

Binding rules:
- **No fine-tuning, no reward models, no training pipeline** in the base architecture.
- **No silent behavioral adaptation.** Anything that changes future output is a visible, editable artifact (an Entry, an example, a prompt) the user can inspect and revert. Nothing learns behind the user's back.
- **Signals may be *recorded* (opt-in) but not *auto-applied*.** Capturing which outputs were kept/edited/regenerated is acceptable as data for the *maintainer* to tune prompts or feed a Bench (ADR-012); it must not auto-mutate behavior.
- **Automated learning is deferred and _Needs Validation_.** If ever revisited, it must preserve transparency, editability, portability, and Zero-Cost.

## 3. Alternatives Considered

- **A. Fine-tuning / preference-model training** on user feedback.
- **B. Implicit personalization** — silently reweight prompt content or sampling based on tracked behavior.
- **C. No learning of any kind** — the product is static; only manual edits change anything.
- **D. Vector "memory of preferences"** — embed user edits/ratings and retrieve them to steer generation automatically.

## 4. Why Rejected

- **A — Training/fine-tuning:** Massive infrastructure and cost for one user; reintroduces provider lock-in (non-portable fine-tunes); opaque and non-editable (can't "undo" what a fine-tune learned); needs its own eval harness to avoid silent regressions. Every one of these contradicts a founding principle. Rejected.
- **B — Implicit personalization:** Silent behavioral drift is user-hostile and undebuggable ("why did it start writing like this?"). It also makes reproducibility impossible. The product's ethos is transparency and control. Rejected.
- **C — Nothing:** Wastes the genuine, cheap wins (the Bible and example library *do* make things better with zero ML). Under-ambitious. Rejected.
- **D — Auto-applied preference vectors:** A lighter ML approach, but still opaque (a vector you can't read/edit), still an embedding subsystem (front-runs FUT-2), and still silently steering output. Fails the transparency test. Rejected as auto-applied; the *human-curated* version of the same idea (curate good examples into Entries) is what we adopt.

## 5. Consequences

**Positive**
- The product genuinely improves per-user over time with **zero** ML machinery, cost, or lock-in.
- Everything that shapes output stays transparent, editable, versionable, and reversible.
- No risk of silent quality regressions from an opaque learner.

**Negative**
- "Learning" requires user effort (curating Entries/examples, tuning prompts); it is not automatic.
- The ceiling is lower than a well-executed fine-tune could theoretically reach for a very heavy user.
- Preference signals, if recorded, sit unused by the runtime (only the maintainer/Bench uses them) — some may see that as under-leveraging data.

**Future risks**
- Pressure to "just fine-tune on my edits" will recur, especially as local training gets cheaper; this ADR must be re-decided rather than drifted past.
- Recorded signals could accumulate as privacy-relevant data; retention should stay local and minimal (personal tool).

## 6. Future Revisit Conditions

- **Validate automated learning** only if a method exists that is simultaneously: local/cheap (Zero-Cost), portable (no provider lock-in), transparent/editable, and reversible. Absent all four, keep the human-curated model.
- If recorded preference signals prove genuinely useful for maintainer-driven prompt tuning, formalize their (local, opt-in) capture and feed them into the Bench (ADR-012) — still not into runtime behavior.
- Revisit the example-library mechanism if curating examples becomes a bottleneck (e.g. semi-automatic candidate selection surfaced as Review Cards).
