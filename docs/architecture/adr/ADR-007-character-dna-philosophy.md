# ADR-007: Character DNA Philosophy

- **Status:** Accepted — *prose-based character definition adopted; rigid trait schemas rejected*
- **Date:** 2026-07-09
- **Deciders:** Architecture Review Board
- **Related:** ADR-003, ADR-009, ADR-004

## 1. Context

The `Character` is the product's unifying entity — the same record is both a chat partner and a novel cast member (`design.md` §3.1). "Character DNA" asks: **how do we represent a character's identity so the AI keeps them consistent** across hundreds of chat turns and dozens of chapters?

The design space runs from:
- **Prose** — free-text `personality`, `speech_style`, `greeting`, plus a few `tags` (the existing `design.md` model), to
- **Structured trait schemas** — Big-Five/OCEAN sliders, stat blocks, formal trait ontologies, mood/relationship state machines, or a "character genome" of weighted attributes.

The seductive idea is that more structure = more consistency. In practice, LLMs consume and honor **well-written prose descriptions and concrete examples** far more faithfully than numeric sliders, which must be re-verbalized into prose before they influence generation anyway. Over-structuring also multiplies UI complexity (forms, sliders, editors) — directly against mobile-first minimalism.

## 2. Decision

**Adopt prose-and-example-based Character DNA. The "DNA" of a character is authored natural-language text plus a small set of tags — not a formal trait model.**

1. **Core DNA fields are prose:** identity/personality, speech style/voice, greeting, and background — authored by the user as expressive text that is injected largely verbatim by the Prompt Engine (ADR-009). Plus lightweight `tags` for filtering/discovery.
2. **Consistency comes from injection + examples, not from a model.** Character voice is held stable by (a) always injecting the character block at high priority (near-protected from truncation, `design.md` §9.8), and (b) optionally attaching a few **example utterances** (few-shot) that demonstrate voice — themselves just text.
3. **No numeric personality schema, no stat blocks, no mood state machine** in the canonical model. If a user wants such structure, they express it in the prose ("cold on the surface, fiercely loyal underneath").
4. **Character-specific canon (facts, relationships, memories) lives in the Bible as Entries** (ADR-003/004), not crammed into the Character record. The Character record stays the stable "who they are"; evolving facts are Entries.
5. **Extensibility is via optional structured fields added non-destructively** (ADR-015) *only if validated* — never a speculative trait ontology up front.

## 3. Alternatives Considered

- **A. Formal trait model** — OCEAN/Big-Five sliders, alignment grids, weighted attribute genome, mood/affinity state machines as canonical character data.
- **B. Card-format import compatibility as the canonical model** — adopt an external character-card spec (e.g. SillyTavern-style fields) verbatim as the internal schema.
- **C. Minimal single-field** — one free-text "description" blob, no separation of personality vs speech vs greeting.
- **D. Learned character embeddings** — derive a vector "DNA" from past dialogue and condition generation on it.

## 4. Why Rejected

- **A — Formal trait model:** Numeric traits don't improve LLM fidelity commensurate with their cost; they must be translated back into prose to matter, so the prose is the real payload. They add substantial UI (sliders, editors) against mobile-first minimalism, and they encode a psychological theory the product has no reason to commit to. State machines for mood/affinity add runtime complexity and failure modes. **Rejected as complexity without proportional quality.**
- **B — External card spec as canonical schema:** Coupling the internal model to a third-party card format is a subtle lock-in and imports fields we may not want. *Import/export compatibility* with such formats is worthwhile as an adapter at the edges (future), but it should not dictate the core schema. Rejected as canonical; acceptable as an I/O adapter later.
- **C — Single blob:** Under-structured: separating personality, speech style, and greeting has real value (greeting seeds the first message per AC-CHAT-5; speech style can be emphasized in prompting). Collapsing them loses useful injection control. Rejected as too coarse.
- **D — Learned embeddings:** Opaque, hard to edit ("tweak the vector"?), provider/model-dependent, and a large ML apparatus for a single-user app. Directly conflicts with the human-editable, transparent ethos. Rejected (and see ADR-010 on learning systems).

## 5. Consequences

**Positive**
- Maximum expressiveness with minimum machinery: users write who the character is, the model honors it.
- Trivial editing on mobile (text fields, not slider arrays).
- Character record stays stable and small; evolving canon is cleanly separated into Bible Entries.
- No commitment to any psychological ontology; portable across models.

**Negative**
- Consistency quality depends on the user's writing skill and on prompt injection discipline; a vaguely-written character yields a vague AI.
- No automatic enforcement of trait consistency (nothing "checks" the AI stayed in character) — mitigated only by injection priority and optional examples, and by user regeneration.
- Free-text is harder to analyze programmatically (e.g. for a future consistency checker) than structured fields.

**Future risks**
- A future "character consistency checker" (a listed extension) would have to work over prose + generated text rather than structured traits; this is an LLM-judgment task, not a rule check.
- If users demand structured attributes, resisting scope creep into a full trait system will require re-deciding here.

## 6. Future Revisit Conditions

- If a Bench (ADR-012) demonstrates that a *small, specific* structured field (e.g. an explicit "speech quirks" list, or example-utterance count) measurably improves consistency, add it as an optional non-destructive field — not a full ontology.
- If character-card import/export becomes a real need, add an edge adapter mapping external formats to the prose model, keeping the canonical schema unchanged.
- Reconsider learned/derived character conditioning only if (a) local, cheap, editable-by-humans methods exist, and (b) they clearly beat prose+examples in a Bench.
