# ADR-007: Character DNA Philosophy

- **Status:** Accepted (revised v2 — prose-first **validated** by both reviews; enriched with layers-as-prompt-org + exemplars-first)
- **Date:** 2026-07-09 (v1) · revised 2026-07-09 (v2)
- **Deciders:** Architecture Review Board
- **Related:** ADR-003, ADR-005, ADR-008, ADR-011

## 1. Context

v1 adopted **prose + examples + tags** for character identity and rejected rigid trait schemas (OCEAN/stat-blocks/genomes/axes) and learned embeddings. The reviews both engage this directly and, notably, **converge toward the v1 position after a self-correction**:

- `design-review-ai-author-os.md` R15/R16 first proposes a **five-layer DNA** (Core / Behavioral / Voice / Relational / Arc) with *"tags become axes with intensity (냉정 0.8)"* and *edit→attribute back-propagation*.
- `architecture-final-minimal.md` §2 **self-corrects**: the five layers survive *"as prompt organization for the Analyst and rendering order for the card, **not** as schema"*; it **drops axes-with-intensity as first-class schema** and **drops R16 back-propagation** from v1 — *"when a user fixes an example line, just store the corrected line as a canonical `character.exemplar`… exemplars outrank descriptions in prompt assembly anyway."*

So the Board's v1 anti-rigid-schema instinct is corroborated. What the reviews add — and v1 under-specified — is the **structure of the prose** (which fields carry the most depth) and the primacy of **example dialogue (exemplars)**.

## 2. Decision

**Keep prose-and-example-first Character DNA. Store it as `character.*` Store entries auto-populated by the Analyst with provenance. Use the five layers as prompt/rendering organization, not schema. Make exemplars first-class and outranking.**

1. **DNA lives as entries** (ADR-003): `character.core`, `character.voice`, `character.exemplar` (+ later `character.behavioral|relational|arc`). Each has prose `content`, `provenance` (reference excerpt / chapter / user), `confidence`, `status`.
2. **The five layers are prompt organization + card rendering order, not tables/columns.** The Analyst knows to *look for* Core/Behavioral/Voice/Relational/Arc signals (`design-review` §2.2–2.8) and renders them in that order on the character card — but nothing is normalized into a rigid attribute schema.
3. **Highest-yield depth fields (adopt as prose):** the **contradiction pair** ("겉은 얼음, 아이 앞에서만 무장해제"), the **never-says list**, and **example dialogue** are the three fields that most raise perceived character depth. These are prose/exemplars, not sliders.
4. **Exemplars are first-class and outrank descriptions.** Models imitate examples better than descriptions (R14). A user correcting a line stores it as a canonical `character.exemplar` with provenance `user` (this replaces R16 back-propagation — same effect, far less machinery). The chat engine feeds this too: a bookmarked chat line becomes an exemplar (R22, ADR-014).
5. **Tags stay simple search keys**, not booleans-driving-generation and not axes-with-intensity. Custom tags are labels the Analyst may *expand into prose* on use — never a first-class numeric schema.
6. **Still rejected:** rigid trait ontologies, numeric personality axes as canonical schema, mood/affinity state machines, learned/opaque character embeddings (ADR-010). Precedence for conflicting inputs (R17) starts as **last-write-wins by declared precedence** (user desc > bible > tags > collection DNA > genre baseline), surfacing a conflict Review Card only when the Bench shows silent averaging hurts (deferred, per `architecture-final-minimal.md` §6).

**Explicit agreement with the reviews:** the Board agrees with `architecture-final-minimal.md`'s self-correction to drop axes-as-schema and back-propagation — these were the exact over-engineering v1 warned against, and their own senior reviewer reached the same conclusion.

## 3. Alternatives Considered

- **A. Five-layer DNA with axes-with-intensity as schema + edit→attribute back-propagation** (R15/R16 as originally written).
- **B. Rigid trait model** (OCEAN/stat blocks/state machines) — v1's alternative A.
- **C. Single free-text blob** — v1's alternative C.
- **D. Learned character embeddings** — v1's alternative D.

## 4. Why Rejected

- **A — Axes-as-schema + back-prop:** Over-built; the reviewer who proposed it retracted it. Axes must be re-verbalized into prose to matter; back-propagation is inference machinery when *just storing the corrected exemplar* achieves ~the same effect (exemplars outrank descriptions). Rejected as schema; the layers survive as prompt organization.
- **B — Rigid trait model:** Numeric traits don't improve LLM fidelity commensurate with UI cost; both reviews prefer prose/exemplars. Rejected.
- **C — Single blob:** Loses the useful separation (core vs. voice vs. exemplar) that drives targeted injection and the voice-attribution check (ADR-005). Rejected.
- **D — Learned embeddings:** Opaque, un-editable, provider-dependent — contra the transparent ethos (ADR-010). Rejected.

## 5. Consequences

**Positive**
- Maximum character depth with *less* UI than a tag form (the DNA Editor is a card + a few dials + editable example dialogue — ADR-014), backed by a 10× richer store that is still just prose entries.
- Exemplars-first gives the voice-attribution check (ADR-005) real ground truth and makes editing intuitive ("fix the line").
- Auto-population from references (Analyst, ADR-008) means no empty forms; provenance makes it trustworthy.

**Negative**
- Character quality depends on reference/extraction quality and on the user occasionally correcting exemplars.
- No DB-enforced trait consistency; consistency comes from injection priority + the voice-attribution check, not schema.
- Prose DNA is harder to query programmatically than columns (accepted; ADR-003).

**Future risks**
- If a specific structured field proves to measurably help (Bench-verified), it may be added as bounded `data` on a `character.*` type — never a full ontology.
- Conflict resolution starting as last-write-wins may occasionally pick wrong; the escalation (conflict Review Card) is Bench-gated.

## 6. Future Revisit Conditions

- Add a small structured `data` field to a `character.*` type only if the Bench shows it beats prose+exemplars.
- Re-enable an R16-style back-propagation facet only if storing corrected exemplars proves insufficient in practice.
- Add the conflict Review Card (R17) if silent precedence resolution is shown to hurt quality.
