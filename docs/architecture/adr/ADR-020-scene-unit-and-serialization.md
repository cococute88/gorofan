# ADR-020: Scene as Generation Unit & Episode Serialization (회차)

- **Status:** Accepted (new in v2) — *introduced by both Fable reviews; the atomic generation unit is the scene, the delivery unit is the episode*
- **Date:** 2026-07-09
- **Deciders:** Architecture Review Board
- **Related:** ADR-002, ADR-004, ADR-005, ADR-008, ADR-012

## 1. Context

Neither v1 nor `design.md` fixed the *unit of generation* — `design.md`'s NovelEngine does single-pass "continue writing" at the **chapter** level with a flat character/world block. Both Fable reviews identify this as a core error:

> `design-review` §0/§13: *"the generation unit is wrong. Chapters are too big to draft coherently in one pass and too big to critique. The atomic unit must be the **scene** (goal, conflict, outcome, value shift), assembled into Korean-webnovel **episodes (회차)** with engineered hooks."*

And they add a whole missing craft — **serialization** — that no `design.md` engine owns: episode length norms (~4,500–5,500 chars, CJK), in-hooks, exit-hooks (절단신공), 사이다/고구마 cadence, recap weaving, and reveal scheduling (`design-review` R8/R11, §2.9). `architecture-final-minimal.md` §3 then *right-sizes* this: serialization is **not an engine** (it retracts its own R11 Serialization Engine) — episode shaping is a single Writer **stage** (`assemble_episode`) plus hook/length checks in `qa`; the craft knowledge lives in the **stage prompt** and the extracted signals, not in code.

This is a distinct, load-bearing decision (it reshapes planning, drafting, checks, and the Bench fixtures), so it earns its own ADR rather than being buried in ADR-005.

## 2. Decision

**Adopt the scene as the atomic unit of planning, drafting, and critique; the episode (회차) as the delivery unit. Serialization craft lives in prompt stages + extracted signals + cheap `qa` checks — not in a dedicated engine.**

1. **Scene = the atomic unit.** A scene card carries: POV / cast / location / **goal → conflict → outcome** (win / lose / win-but…), **value shift** (e.g. trust − → +), emotional beat, promise refs (plants or pays), and an exit hook (`design-review` §4). Planning produces scene cards (R8); drafting drafts per scene; critics check per scene (ADR-005). Scenes that don't *turn* (change a value) are flagged **before** drafting — the cheapest place to fix "boring."
2. **Planning cascade: Premise → Promise contract → Arc → Scene cards** (R8). Intermediate layers (promise contract) may be internal-only. Each layer is checkable (does the arc pay the premise's promises? does each scene turn?).
3. **Episode = the delivery unit.** An `assemble_episode` Writer **stage** composes scenes into a 회차 with a target length, an in-hook, and an exit-hook (절단신공); a `qa` stage asserts hook presence and length adherence. **No Serialization Engine** — this is one stage + two checks (`architecture-final-minimal.md` §3).
4. **Serialization craft is data + prompts, not code:** 사이다/고구마 cadence, recap technique, reveal scheduling come from the extracted serialization signals (Analyst §2.9 → Store entries) and the stage prompt — tunable weekly (ADR-001/013).
5. **User-facing simplicity preserved** (ADR-014): the user sees what Heart Fiction shows — a synopsis and an episode list; scene cards render as 2–3 editable bullet lines per episode. **One serialization knob:** episode target length (default from references). The cascade is backend structure, not UI structure.
6. **Bench fixtures are scene-shaped** (ADR-012): golden scenes (confession, banter, action, reveal, interiority) + frozen entry snapshots. The scene unit is what makes evaluation tractable.

## 3. Alternatives Considered

- **A. Chapter as the unit** (the `design.md` status quo: single-pass chapter continuation).
- **B. Paragraph/beat as the atomic unit.**
- **C. A dedicated Serialization Engine** (the reviews' own initial R11).
- **D. No explicit episode shaping** — generate prose and let the user chunk it.

## 4. Why Rejected

- **A — Chapter unit:** Too big to draft coherently in one pass and too big to critique surgically; it is the root cause the reviews attach the single-pass ceiling to (ADR-005). Rejected.
- **B — Paragraph/beat:** Too small to carry a goal/conflict/outcome/value-shift; over-fragments planning and multiplies model calls without a coherent dramatic unit. Rejected — the scene is the natural dramatic and checkable unit.
- **C — Serialization Engine:** Over-naming a stage into an engine (`architecture-final-minimal.md` §3 retracts R11); the craft is a stage prompt + checks + extracted signals. A separate engine is the debt bomb (ADR-002). Rejected.
- **D — No episode shaping:** Abdicates the Korean-market table-stakes craft (hooks, cadence, recap); "a novel cut into pieces" is not "a serial." Rejected.

## 5. Consequences

**Positive**
- The scene unit unlocks the drafting loop (per-scene draft→check→revise, ADR-005), scene-level planning quality checks ("did it turn?"), and tractable Bench fixtures — the three biggest quality levers.
- Episode hooks + cadence deliver serialization craft that competitors miss, as **one stage + two checks**, not an engine.
- Serialization knowledge stays in prompts/signals → tunable without code (ADR-001/015).
- User UI is unchanged (synopsis + episode list); richness is backend.

**Negative**
- Scene decomposition adds planning structure and more per-scene model calls (cost/latency — shared with ADR-005; **Needs Validation** that per-scene generation stays affordable on long works).
- CJK length targeting (chars, not words) is approximate; `target_words`/length is a *soft* target, actual end deferred to `finish_reason` (per `design.md` §11.6 CJK note).
- Scene-card planning quality depends on the planning prompt + extracted structure signals.

**Future risks**
- Over-rigid scene cards could make prose feel mechanical; the card is a scaffold, not a cage — drafting must retain freedom within it.
- Very long works accumulate many scenes/episodes; retrieval + summaries (ADR-018) must keep per-scene context bounded.

## 6. Future Revisit Conditions

- If per-scene generation proves too costly on long works, revisit granularity (scene vs. multi-scene batches vs. sampled critique) using Bench cost/quality data (ADR-005/012).
- Promote serialization/pacing signals to richer structure only if `qa` cadence checks strain prose-first `data` (ADR-003 §6).
- Revisit episode-length defaults and hook taxonomy per platform/market as the product's target audience clarifies.
