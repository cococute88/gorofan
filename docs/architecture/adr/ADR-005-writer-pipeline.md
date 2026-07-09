# ADR-005: Writer Pipeline (Loop Runner + Stages as Data)

- **Status:** Accepted (revised v2 — **reversed** from v1's single-pass default to a bounded draft→validate→revise loop)
- **Date:** 2026-07-09 (v1) · revised 2026-07-09 (v2)
- **Deciders:** Architecture Review Board
- **Related:** ADR-002, ADR-004, ADR-008, ADR-009, ADR-012, ADR-020

## 1. Context

v1 adopted a **single-pass, streaming** Writer and deferred multi-pass/critique loops as "Needs Validation," reasoning from cost/latency for a personal user. Both reviews challenge this head-on and the Board finds the challenge persuasive:

- `design-review-ai-author-os.md` R12: *"single-pass generation has a hard quality ceiling regardless of prompt quality,"* and the drafting loop (draft → specialized critics → targeted revision) is *"the largest single quality lever after scene-level planning."* The critics are cheap and **falsifiable** because they check against ground truth (fact/knowledge ledgers, Voice DNA, the scene card) — not vague "make it better."
- `architecture-final-minimal.md` §3 tempers R12: launch with **two** checks that have ground truth (continuity, voice-attribution), make pacing/cliché cheap `qa` assertions, and add a third model-critic **only** when the Bench proves a recurring blind spot. It reframes the whole Writer as *one loop runner* executing a **declarative stage list**, dissolving Planning/Novel/Serialization/Style/critic "engines" into stages.

For a product whose entire reason to exist is **novel quality**, keeping a known hard ceiling to save latency is the wrong trade — *especially* when latency can be hidden by streaming the draft optimistically and delivering "polish" as the finished state.

## 2. Decision

**Adopt a single Writer loop runner executing a bounded, declarative stage list. Replace single-pass generation with a draft → validate → targeted-revise loop, held to exactly two ground-truth checks at launch.**

1. **One loop runner, stages-as-data.** A pipeline is a declarative stage list (illustrative shape in `architecture-final-minimal.md` §3), not code branches. Planning, drafting, critics, episode assembly, and the style pass are **stages**, each backed by a prompt file (ADR-013). The runner is written once; the stages are tuned weekly (ADR-001 governing rule).
2. **The core loop:** `retrieve → assemble → generate → validate → revise → persist`, operating on the **scene** as the atomic unit (ADR-020).
3. **Exactly two model-checks at launch**, both with ground truth:
   - **Continuity check** — draft vs. retrieved `fact` + `knowledge` entries (the contradiction gate, ADR-004 R6).
   - **Voice-attribution check (R13)** — strip speaker tags, ask a checker to attribute each dialogue line via Voice DNA exemplars; mis-attributed lines are the flat lines → revise those specifically. *Voice becomes measurable, not vibes.*
   Pacing and cliché are cheap **`qa` assertions** (hook present? did the scene turn? LLM-ism screen, repetition counter — ADR-020, ADR-013), not model-critics. **A third model-critic is added only when the Bench (ADR-012) shows the two can't see a recurring failure.** Every critic is latency and cost — *earn each one.*
4. **Targeted revision, not global rewrite:** only scenes with check findings are revised, with the critic notes as instructions — one pass. Two focused passes beat five generic ones.
5. **Optimistic streaming hides the loop's latency:** stream the draft to the user immediately; deliver the validated/revised/styled result as the "polish ready" finished state (per both reviews). Partial output is preserved on disconnect (Property 9).
6. **Persistence stays in the Service, transactional, post-loop**, with optimistic concurrency (`version`, 409) — engines never commit (unchanged from v1; upheld by the substrate).
7. **Canon write-back only via review:** the `ingest` stage runs the Analyst (`scope=work`) to emit *proposed* entries (ADR-004/008/011), never inline canon writes.

**Where the Board holds the line (partial disagreement with R12-maximalism):** the launch loop is **two ground-truth checks, per-scene, streamed** — not a four-critic ensemble. This is `architecture-final-minimal.md`'s tempered position, and the Board adopts it over R1–R26's fuller ensemble precisely on simplicity/cost grounds. More critics are Bench-gated, not default.

## 3. Alternatives Considered

- **A. v1 single-pass streaming** (no validate/revise).
- **B. Full R12 four-critic ensemble at launch** (continuity + voice + pacing + cliché as model-critics).
- **C. Per-episode (chapter) critique** instead of per-scene.
- **D. Hard-coded pipeline** (Planning/Novel/Serialization/Style as separate coded engines).

## 4. Why Rejected

- **A — Single-pass:** Both reviews identify a hard quality ceiling; for a quality-first product this is the wrong default. The latency argument that motivated v1 is answered by optimistic streaming + "polish ready." Reversed.
- **B — Four model-critics at launch:** Over-built (`architecture-final-minimal.md` §3): 2× more model calls (cost/latency) for critics that lack the clean ground truth continuity/voice have. Pacing/cliché are better as cheap assertions. Rejected as launch scope; available Bench-gated.
- **C — Per-episode critique:** Chapters/episodes are too big to critique coherently and too coarse to revise surgically; the scene is the checkable unit (ADR-020). Rejected.
- **D — Coded engines:** Recreates the engine sprawl (ADR-001/002). Stages-as-data + prompt files is the evolution surface. Rejected.

## 5. Consequences

**Positive**
- Breaks the single-pass ceiling with the two highest-ground-truth checks — the largest quality lever after scene planning.
- Voice quality becomes *measured* (attribution test), directly serving the dialogue-quality story.
- Stages-as-data + prompt files mean the pipeline evolves by commits to `prompts/`, not code (ADR-001/015), and is Bench-testable (ADR-012).
- Latency is hidden by optimistic streaming; cost is bounded by exactly-two-checks discipline.

**Negative**
- Real added cost/latency vs. single-pass (2 checks + conditional revise per scene) — the price of breaking the ceiling; must be watched on long works for a personal budget (**Needs Validation** that per-scene checks don't blow token cost on very long novels).
- A loop runner + declarative stage contract is infrastructure to design once and keep clean.
- Voice-attribution check quality depends on having good Voice DNA exemplars (ADR-007).

**Future risks**
- Stage/prompt tuning can regress silently — the reason the Bench is now necessary (ADR-012).
- Revision passes can over-sanitize prose (flatten voice); the style pass must freeze dialogue (ADR-020/R18) and repetition/LLM-ism screens must exempt signature phrases.

## 6. Future Revisit Conditions

- **Add a third+ critic** only when the Bench shows the two-check loop repeatedly misses a failure class.
- If per-scene checking proves too costly on long works, revisit granularity (per-scene vs. per-beat vs. sampled) using Bench cost/quality data.
- If providers ship cheap high-quality reasoning modes, revisit whether some checks fold into the draft call.
