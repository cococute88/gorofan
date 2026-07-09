# ADR-014: Minimal UI Philosophy

- **Status:** Accepted (revised v2 — adopts the reviews' 3-tab writing IA + five UI patterns; **partial disagreement** on demoting chat)
- **Date:** 2026-07-09 (v1) · revised 2026-07-09 (v2)
- **Deciders:** Architecture Review Board
- **Related:** ADR-001, ADR-004, ADR-011, ADR-015

## 1. Context

v1 locked a mobile-first, fixed-navigation, progressive-disclosure UX constitution, using `design.md`'s **five-tab** nav (홈/캐릭터/세계관/소설/채팅). Both Fable reviews propose a tighter, writing-centric information architecture and — more valuably — **five concrete UI patterns** that carry the entire complexity budget (`design-review` §10, `architecture-final-minimal.md` §1):

- Surface map = **three tabs: 쓰기 (Write) · 바이블 (Bible) · 서재 (Library: Collections + DNA cards)** + settings + the Review Card queue.
- Five patterns: **(1) generated defaults everywhere** (no empty forms — configuration becomes correction); **(2) Review Cards as the universal write-path**; **(3) one knob per engine, maximum**; **(4) examples are the editing surface** (edit the example dialogue/paragraph/portrait); **(5) provenance on tap**.

The Board adopts the five patterns wholeheartedly (they operationalize v1's progressive-disclosure principle). On the IA, the Board **partially disagrees**: the reviews are explicitly scoped to *novel-writing quality* and lean toward reducing chat to a "voice gym" (R22). But **character chat is half the product's identity** (로판AI); demoting it below the level of a first-class mode is not warranted by a review whose remit was the authoring pipeline.

## 2. Decision

**Adopt the reviews' five UI patterns and the writing-centric 쓰기/바이블/서재 tabs for the authoring experience. Keep chat as a first-class mode (not merely a voice gym), and lock all of it under the v1 discipline. Flag the chat-vs-writing IA reconciliation as Needs Validation.**

1. **Five UI patterns are binding** across all surfaces:
   1. **Generated defaults everywhere** — every field shows an already-good AI-generated value with an edit affordance; no empty forms. (This is *why* the DNA is auto-populated by the Analyst — ADR-007/008.)
   2. **Review Cards = universal write-path** (ADR-011) — one queue for Bible ingestion, world-fact creation, DNA conflicts.
   3. **One knob per engine, maximum** — reference influence = one slider; episode length = one number; everything else DNA-derived. "A second knob is a backend heuristic wearing a costume — send it back."
   4. **Examples are the editing surface** — users edit example dialogue / sample paragraph / character portrait; parameters live one disclosure level down (ADR-007).
   5. **Provenance on tap** — any AI-derived attribute shows its source excerpt (powered by ADR-003 provenance / ADR-008).
2. **Authoring IA = three tabs** — 쓰기 · 바이블 · 서재 + settings (API keys, forbidden list, toggles). Every authoring engine in the reviews lives behind these three (ADR-004/005/008 render here).
3. **Chat remains first-class**, not demoted. It keeps its own surface/mode and *also* serves as voice calibration: a long-press "이 말투야" bookmark writes a `character.exemplar` (R22, ADR-007). The Board **disagrees** with any reading of the reviews that removes chat as a peer capability.
4. **v1 discipline is retained and unchanged:** mobile-first from 360px, 3-tap rule, progressive disclosure, installable PWA, and **navigation invariance** — new features enter via slots/tabs/drawers/command palette/flags, never by growing the top-level nav (ADR-015).
5. **Needs Validation:** whether the unified top-level nav is exactly `{쓰기, 바이블, 서재, 채팅}` (four) or chat nests within the writing/character surfaces. The Board will not silently resolve a product-identity question that the reviews did not scope.

## 3. Alternatives Considered

- **A. Keep v1's five-tab 홈/캐릭터/세계관/소설/채팅** unchanged.
- **B. Adopt the reviews' three tabs literally and demote chat to a voice-gym feature only.**
- **C. Feature-rich dashboard / desktop-first / fully customizable UI** (v1's rejected alternatives).
- **D. Grow navigation organically.**

## 4. Why Rejected

- **A — Keep five tabs verbatim:** The reviews' consolidation (Write/Bible/Library) better matches the actual authoring workflow and the entry/DNA model, and the five UI patterns are a real advance. Superseded (but chat is preserved, unlike a pure adoption of the reviews).
- **B — Three tabs + demote chat:** Rejected in part. The five patterns and the three authoring tabs are adopted; the *demotion of chat* is not — chat is a founding half of the product and a genuine DNA-refinement asset (R22), not a subordinate tool. This is the Board's explicit partial disagreement with the reviews' novel-tunneled framing.
- **C — Dashboard/desktop/customizable:** Same reasons as v1 — contradict simplicity, mobile-first, and opinionated defaults. Rejected.
- **D — Organic nav growth:** The exact failure mode the constitution prevents; hard rule against it. Rejected.

## 5. Consequences

**Positive**
- The five patterns make a 10×-richer backend feel *simpler* than a tag-form product (the DNA Editor is a card + a few dials + editable examples).
- "Generated defaults + provenance on tap" delivers trust without configuration — the antidote to Heart-Fiction form fatigue.
- A single Review Card queue and a single editor component (rendering entries by `type`) minimize UI surface (ADR-003/011).
- Keeping chat first-class protects the product's dual identity.

**Negative**
- Advanced features are less discoverable behind disclosure (accepted trade).
- The chat-vs-authoring IA is left partly open (Needs Validation) rather than force-resolved.
- "One knob per engine" requires discipline to resist a second knob.

**Future risks**
- If real usage shows chat is central, the top-level nav may need chat as a peer tab — a conscious amendment, not drift.
- Over-hiding could make key features invisible; disclosure levels need occasional review against usage.

## 6. Future Revisit Conditions

- Resolve the chat IA (peer tab vs. nested) once real usage shows how much chat is used relative to authoring.
- Revisit the three-tab lock only if a genuinely new primary activity emerges (explicit amendment, per v1).
- Reassess disclosure levels if Bench/usage shows key advanced features are undiscoverable.
