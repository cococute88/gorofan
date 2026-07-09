# ADR-004: Living Story Bible & the Continuity Loop

- **Status:** Accepted (revised v2 — enriched with ledgers + continuity loop; human-gated writes **retained** and now **validated** by both reviews)
- **Date:** 2026-07-09 (v1) · revised 2026-07-09 (v2)
- **Deciders:** Architecture Review Board
- **Related:** ADR-002, ADR-003, ADR-005, ADR-008, ADR-011, ADR-018

## 1. Context

v1 adopted the Living Story Bible as a read model over World/Lore/Glossary/Memory with **human-gated** canon writes, and deferred fully-automatic canon mutation as "Needs Validation." Both Fable reviews strongly endorse the *living* framing and — importantly — **converge on the human gate**: `design-review-ai-author-os.md` R4 auto-*extracts* facts on chapter acceptance but routes them through a **Review Card queue** (status=proposed); `architecture-final-minimal.md` §4 confirms ingestion output is `proposed`. So the v1 decision was directionally right and is now corroborated by two senior reviews.

What v1 **missed** is the *richness and mechanism*. The reviews supply the Bible's real contents (multiple ledgers) and the **continuity loop** — the third of the four loops that separate "a generator" from "an Author OS": *every accepted chapter writes facts back into the Bible; retrieval feeds the right facts into the next draft; a contradiction gate catches violations.*

## 2. Decision

**Adopt the Living Story Bible as the work-scoped subset of the Store's Entry model (ADR-003), comprising typed ledgers, kept current through a human-gated continuity loop.**

1. **The Bible is Store entries at `scope=work`**, not a separate store. Its ledgers are entry `type`s (`architecture-final-minimal.md` §2/§4):
   - `fact` — canonical facts with `created_at_chapter` (contradiction checking needs timestamped facts).
   - `knowledge` ★ — the **knowledge matrix**: who knows which secret as of which chapter. *Kills the #1 LLM long-fiction failure: characters knowing things too early.*
   - `promise` ★ — the **promise ledger**: setups/foreshadowing with `data` = planted-chapter / due-window / status (open·paid·abandoned). Payoff discipline is what makes stories feel *authored*.
   - `relationship` — current stage per pair + last transition (ADR-006).
   - `summary` — multi-granularity (scene / chapter / arc / story-so-far) via `data.level` (replaces the single `Chapter.summary`, ADR-018).
   - plus `note`, timeline/state facts, and the **tone/theme contract** (R7): a standing 2–3 line guardrail injected at prompt top as the cheapest drift-anchor.
2. **Reads are free and automatic** via the single `retrieve()` (ADR-018): scene-relevant facts (on-stage cast, locations, due promises, knowledge state) enter the draft prompt within budget — *retrieval, not Bible-dumping* (R5).
3. **The continuity loop (R4) is adopted, human-gated:** on chapter acceptance the Analyst (ADR-008, `scope=work`) extracts new `fact`/`knowledge`/`promise`/`relationship`/`summary` entries as **status=proposed**. They surface as Review Cards (ADR-011) — a "Bible updated: 3 new facts" toast + a veto queue. Approved → `canon`. **No silent canon mutation.**
4. **The contradiction gate (R6) is adopted as a Writer check** (ADR-005), not a Bible feature: post-draft, the scene is checked against retrieved `fact` + `knowledge` entries; violations trigger an automatic **targeted revision**, not a user-facing error.
5. **v1's core safety decision stands:** the model reads canon freely but writes only through review (ADR-002/011). This is now *validated*, not merely asserted.

## 3. Alternatives Considered

- **A. Fully automatic living bible** — AI writes extracted facts straight to canon, no gate.
- **B. Static bible** — hand-authored only; no ingestion (v1 alt B).
- **C. Separate ledger subsystem / knowledge graph** kept in sync with prose canon.
- **D. Single `Chapter.summary`** as the only continuity memory (the current `design.md` state).

## 4. Why Rejected

- **A — Fully automatic:** The compounding-hallucination risk over a *장편* serialization; unattended write-back to the source of truth is the highest-regret option and would corrupt the very canon that feeds future drafts. Both reviews independently route ingestion through review. Rejected (auto-accept remains Needs Validation, §6).
- **B — Static bible:** Guarantees staleness → contradictions by chapter 40 (`design-review` §3). Kills the continuity loop and the product's differentiator. Rejected.
- **C — Graph subsystem:** A second source of truth to sync and back up; both reviews warn this produces worse prompts than provenanced prose (ADR-003 alt D). Rejected; a derived projection stays possible.
- **D — Single summary:** Serialization needs summaries at multiple granularities and timestamped facts; one text field silently drops what chapter 37 established. Rejected — migrate to multi-level `summary` entries (ADR-018).

## 5. Consequences

**Positive**
- Consistency at chapter 100 becomes *possible at all* — the knowledge matrix + fact ledger + contradiction gate are precisely the anti-contradiction machinery long fiction needs.
- The flywheel delivered *safely*: the Bible grows richer per chapter without rotting, because writes are reviewed.
- One store, one retrieval path unify chat and novel context; ledgers are `type`s, not tables (ADR-003).
- Promise ledger + tone contract are cheap to store, high-leverage for "feels authored."

**Negative**
- Review-queue triage is a recurring user cost; heavy projects could accumulate proposals (mitigation: batch, mute low-signal `type`s, good Review Card UX — ADR-011).
- Per-turn Bible retrieval has a cost; relies on the retrieval budget + caching (ADR-009/018).
- Knowledge-matrix / timeline checks are the parts most likely to strain prose-first `data` JSON (ADR-003 §6).

**Future risks**
- If proposal volume outpaces triage willingness, "living" weakens → the concrete trigger to *validate* bounded auto-accept for high-precision `type`s (e.g. named-entity `fact`s).
- Extraction quality is model-dependent; a weak/local model raises triage noise.

## 6. Future Revisit Conditions

- **Validate bounded auto-accept** once real long-project data shows high extraction precision on a specific `type` — then allow scoped, reversible, audited auto-accept for that `type` only (coordinate ADR-010/011).
- Promote `knowledge`/`promise`/timeline to structured tables if their checks strain (ADR-003 §6).
- If graph queries over relationships/threads become genuinely needed, add a *derived, disposable* projection — never a second source of truth.
