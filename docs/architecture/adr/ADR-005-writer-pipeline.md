# ADR-005: Writer Pipeline

- **Status:** Accepted (single-pass streaming; multi-agent draft/critique loops rejected for now — **Needs Validation** as future option)
- **Date:** 2026-07-09
- **Deciders:** Architecture Review Board
- **Related:** ADR-002, ADR-004, ADR-009, ADR-011, ADR-016

## 1. Context

The "Writer" role (ADR-002) produces prose in two modes: **chat replies** (Chat Engine) and **novel chapter continuation** (Novel Engine, `design.md` §11). Both follow the same skeleton: gather context from the Bible → assemble a budgeted prompt → stream generation from a provider → persist the result → (background) summarize for future context.

The open question is the *shape* of generation. AI-writing tools increasingly reach for multi-step agentic pipelines: outline → draft → self-critique → revise → continuity-check → finalize, sometimes with multiple model calls or multiple agents per paragraph. These can improve quality but multiply **latency, cost, and complexity** — each of which is expensive for a personal, zero-cost-infrastructure, mobile-first product where the user is watching a stream and paying per token.

## 2. Decision

**Adopt a single deterministic, single-pass, streaming Writer pipeline as the default for both chat and novel:**

`build_context (Analyst) → assemble prompt (Prompt Engine) → stream generate (Adapter) → persist (Service, transactional) → summarize (background)`

Binding rules:
1. **Single primary generation call per user action.** One "continue" or one chat "send" = one streamed completion. No hidden fan-out of extra model calls in the interactive path.
2. **Streaming is first-class.** Output is streamed via SSE (Property 9); partial output is preserved on disconnect (`status="partial"`). The user sees tokens immediately (NFR-1: system overhead < 200ms).
3. **Persistence is transactional and post-stream.** The Service (not the Engine) commits results after the stream completes, using optimistic concurrency (`version`, 409 on conflict) so autosave and continuation cannot clobber each other (`design.md` §11.6). Engines never commit.
4. **Summarization is background and non-blocking** (BR-6): the follow-on chapter/chat summary is produced off the interactive path and must never delay or fail the user's generation.
5. **Canon write-back only via review.** Anything the Writer "notices" (new facts, events) is a *proposal* routed to the Review Card (ADR-011), never an inline canon write (ADR-002 rule #2).
6. **Multi-pass/agentic generation is an opt-in future capability, not the default.** The pipeline's seams (a distinct "generate" step behind the Adapter) leave room to insert a critique/revise stage later, but it is **Needs Validation** and feature-flagged, never on by default.

## 3. Alternatives Considered

- **A. Multi-agent / multi-pass by default** — outline→draft→critique→revise→continuity-check as the standard chapter pipeline.
- **B. Non-streaming batch generation** — generate the whole chapter, then display.
- **C. Engine-owned persistence** — let the Novel/Chat Engine write to the DB directly for simplicity.
- **D. Two divergent pipelines** — completely separate chat vs novel generation flows with no shared skeleton.

## 4. Why Rejected

- **A — Multi-agent by default:** 3–6× the token cost and latency for every generation, plus non-deterministic control flow that is hard to test and debug. For a single user paying their own API bill and watching a mobile stream, this is a poor default. Quality gains are real but uneven and provider-dependent; they belong behind a validated, opt-in flag — not in the base pipeline. **Rejected as default; retained as future seam.**
- **B — Non-streaming batch:** Kills perceived responsiveness (long silent waits on mobile), loses partial-output preservation on disconnect (Property 9), and worsens the felt cost of a bad generation (you pay the whole latency before seeing it's wrong). Rejected.
- **C — Engine-owned persistence:** Violates the layering rule (ADR-001) and the Store/Analyst/Writer contract (ADR-002): engines are stateless transformers; commits and transaction boundaries belong to the Service. Engine-owned writes would scatter transaction logic and break optimistic-concurrency guarantees. Rejected.
- **D — Divergent pipelines:** Doubles the surface area, guarantees drift between chat and novel behavior, and duplicates the risky post-stream persistence logic. The shared skeleton with mode-specific context assembly is strictly simpler. Rejected.

## 5. Consequences

**Positive**
- Predictable cost and latency: one call per action, streamed. Aligns with Zero-Cost and mobile-first.
- Deterministic, testable pipeline (the LLM is the only non-determinism; everything around it is pure/ordered).
- Clean separation: Analyst assembles, Writer streams, Service persists — each independently testable.
- Partial-output preservation and optimistic concurrency protect user work.

**Negative**
- Out-of-the-box prose quality is bounded by single-pass generation + prompt quality; no automatic self-revision. Users wanting higher polish must iterate manually (regenerate, edit) until/unless the multi-pass flag is validated.
- Long chapters near the context limit rely entirely on good summarization + budget truncation; a poor summary degrades the next continuation.

**Future risks**
- If single-pass quality proves insufficient for long-form coherence, pressure to enable multi-pass will grow; this must be validated (cost vs quality) rather than switched on reflexively.
- Background summarization failures, if silently swallowed, could quietly starve future context; needs observability (a summary can be retried/forced — AC-MEM-6).

## 6. Future Revisit Conditions

- **Validate multi-pass:** run a Bench (ADR-012) comparing single-pass vs draft/critique/revise on representative chapters, measuring quality delta against token-cost delta. Adopt an opt-in flag only if the trade is clearly favorable for the maintainer's own use.
- If a specific weakness (dialogue consistency, continuity) is isolated, consider a *targeted* second pass for that facet only, rather than a full agentic loop.
- If providers add cheap "thinking"/reasoning modes that improve first-pass quality at low marginal cost, revisit whether they belong in the default pipeline.
