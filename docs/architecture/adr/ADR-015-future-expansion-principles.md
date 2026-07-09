# ADR-015: Future Expansion Principles

- **Status:** Accepted (revised v2 — sharpened by the reviews' governing rule: **evolve via prompts + entry types, not services + migrations**)
- **Date:** 2026-07-09 (v1) · revised 2026-07-09 (v2)
- **Deciders:** Architecture Review Board
- **Related:** ADR-001, ADR-003, ADR-013, ADR-014

## 1. Context

v1 adopted "non-destructive, flag-gated, define-the-seam / defer-the-second-impl" expansion. The reviews supply a sharper governing rule that the Board now treats as the *primary* expansion principle:

> `architecture-final-minimal.md` §1: *"Code that must be written once (loop runner, entry store, retrieval, diff capture) is code; everything that will be tuned weekly (what to extract, how to plan, how to critique, how to style) is a prompt file in the repo. Two years of product evolution should be commits to `prompts/`, not migrations and new modules."*

And the concrete corollary (§2/§5): **a new library/ledger is a new entry `type` string, never a new table**; *"if a table named `dialogue_library` or `character_dna_attributes` ever appears in a migration, this document has failed."* Embeddings are added *"only when keyword retrieval demonstrably misses, measured on the Bench, not before"* — exactly v1's defer-the-second-impl, now with an explicit measurement trigger.

## 2. Decision

**Adopt "evolve via prompts and entry types" as the primary expansion principle, with v1's non-destructive, flag-gated, seam-based rules as the supporting frame.**

1. **The evolution surface is `prompts/` + entry `type`s** (ADR-001 governing rule). New craft (a critic, a planning heuristic, a facet, a style pass) = a **prompt file / stage**. New knowledge kind (a library, a ledger) = a new **`type` string** (ADR-003) — *never* a new table or service.
2. **Non-destructive schema evolution** (unchanged): nullable columns / new tables via forward-only migrations; never break or repurpose existing structures. The single Entry model makes most "new data" need *no migration at all*.
3. **Feature flags default off; navigation invariance** (ADR-014): expansions enter via slots/tabs/drawers/command palette.
4. **Define the seam, defer the second implementation** (unchanged, now Bench-triggered where measurable). Sanctioned seams: `LLMProvider` (ADR-016), the single `Retriever` (ADR-018 — embeddings deferred, Bench-gated), `StorageBackend` (local→S3), `JobQueue` (in-process→distributed), `ImageProvider`, `AuthProvider` (ADR-019), Export/chapter-composition. **Not built until a concrete/Bench trigger:** the Celery/ARQ queue, S3, the embedding retriever, image generation, a third+ Writer critic (ADR-005).
5. **Promote-a-type-to-a-table is the sanctioned structural escape valve** (ADR-003 §6), used only when deterministic checks strain prose-first `data` JSON — the one place new tables are legitimately added later.
6. **Local-first stays invariant**; cloud/remote always optional.

## 3. Alternatives Considered

- **A. Build abstractions and their multiple implementations up front** (platform-from-day-one).
- **B. No seams — YAGNI-maximalist.**
- **C. Plugin framework / marketplace now** (the long-term vision made present).
- **D. Extend by adding tables/services per capability** (the `design.md`/R1–R26-literal instinct).

## 4. Why Rejected

- **A — Build impls up front:** Speculative complexity for hypothetical futures (Celery/S3/embeddings/image). The over-abstraction failure mode. Rejected — seams yes, unused impls no.
- **B — No seams:** Some boundaries *will* be crossed (providers, DB swap); a thin seam there is cheap insurance. Rejected as too rigid at *known-volatile* points, while its spirit (no speculative interfaces elsewhere) is adopted.
- **C — Plugin marketplace now:** Enormous machinery for a single-user product with no third-party developers; explicitly a long-term vision. Rejected until the product opens to external extensions.
- **D — Table/service per capability:** The debt bomb both reviews attack; the whole point of the Entry model + prompt files is to make this unnecessary. Rejected — *if a per-library table appears in a migration, the architecture has failed.*

## 5. Consequences

**Positive**
- Years of evolution become commits to `prompts/` and new `type` strings — the two cheapest change surfaces — with few/no migrations.
- Complexity paid just-in-time; the sanctioned-seam list prevents both rigidity and abstraction sprawl.
- The single Entry model + retrieval function means new knowledge kinds and new retrieval consumers cost almost nothing.

**Negative**
- Judgment needed to distinguish a known-volatile boundary worth a seam from speculative abstraction (the seam list is the guide).
- Forward-only migrations accrue some schema cruft over years (acceptable vs. ever breaking data).
- Prompt-file/`type` growth needs the Bench and declarative stage lists to stay legible.

**Future risks**
- The seam list itself could grow speculatively; adding one requires the "second impl foreseeable" test + an ADR/RFC note.
- `type` proliferation; guarded by the no-`misc`, ADR-gated rule (ADR-003).

## 6. Future Revisit Conditions

- Add a sanctioned seam only when a second implementation becomes concretely foreseeable; record it here.
- Build a deferred impl (Celery/S3/embeddings/image/3rd critic) when its concrete or Bench trigger fires.
- Reconsider a plugin/marketplace architecture only if the product deliberately opens to third-party extensions.
