# ADR-002: Store / Analyst / Writer Architecture

- **Status:** Accepted (with explicit rejection of the process-level and God-Object interpretations)
- **Date:** 2026-07-09
- **Deciders:** Architecture Review Board
- **Related:** ADR-001, ADR-003, ADR-004, ADR-005, ADR-009

## 1. Context

The "AI Author OS" framing proposes organizing the system around three roles:

- **Store** — the single source of truth: persistence and retrieval of all canon (characters, world, lore, works, chapters, chat, memory).
- **Analyst** — the read/understand side: assembling context, ranking memory, scanning lore, analyzing references, and deriving guidance for generation.
- **Writer** — the generate side: producing prose (chat replies, chapter continuations) from assembled context.

The existing `design.md` does not use this vocabulary. It uses four Engines (Prompt, Memory, Novel, Chat), a Repository layer, and a Provider Adapter. The Board must decide whether Store/Analyst/Writer is a better organizing principle, and if so, at what altitude it lives.

Two failure modes must be confronted head-on (the task brief demands this honesty):
1. **The process trap** — treating the three roles as separate services (rejected in ADR-001).
2. **The God-Object trap** — collapsing "Store" into one omniscient object/module that every feature reaches into, and "Entry" into one universal table (see ADR-003). A God Store becomes the thing every future change must touch, which is the opposite of maintainability.

## 2. Decision

**Adopt Store / Analyst / Writer as a conceptual (logical) decomposition layered on top of the existing engine architecture — never as separate processes, and never as three monolithic objects.**

Mapping (authoritative):

| Role | What it *is* | Realized by (existing design) | Not allowed to be |
|------|--------------|-------------------------------|-------------------|
| **Store** | Owns persistence + retrieval of canon; enforces ownership scoping and invariants. | The **Repository layer** (one repository per aggregate root) + the Story Bible read model (ADR-004). | A single "Store" class; a generic key-value blob; a God Object. |
| **Analyst** | Turns raw canon into *generation-ready context*: memory ranking, lore scan, budget-aware assembly, optional reference/style guidance. | **Memory Engine** + **Prompt Engine** (+ optional reference-analysis helper, ADR-008). | A hidden dependency that writes to the Store; an autonomous agent. |
| **Writer** | Produces prose by streaming from a provider, given assembled context. | **Chat Engine** + **Novel Engine**, both calling the **Provider Adapter**. | A component that assembles its own prompts or mutates canon inline. |

Binding rules:
1. **Store is plural.** It is *not* one object. It is a family of per-aggregate repositories behind a read/write boundary. There is no `Store` God class. "Single source of truth" is a *data* guarantee (one canonical row per fact), not a *code* singleton.
2. **Data flows one way per turn:** Store → Analyst → Writer → (proposed) canon updates that re-enter the Store **only through an explicit, reviewed path** (Review Card, ADR-011). The Writer never silently writes to canon.
3. **Analyst never generates; Writer never assembles.** The Prompt Engine (Analyst) produces provider-neutral messages; the Adapter+Engines (Writer) consume them. This preserves determinism and testability (ADR-009).
4. **The three roles are documentation and dependency discipline, not new packages.** Existing folders (`repositories/`, `engines/prompt`, `engines/memory`, `engines/chat`, `engines/novel`, `adapters/`) stay. This ADR renames *concepts*, not files.

## 3. Alternatives Considered

- **A. Three services / three top-level packages** named Store, Analyst, Writer, each owning its own state.
- **B. A single unified `Store` facade** ("everything goes through the Store") as the one entry point to data.
- **C. Reject the triad entirely** and keep only the four-engine vocabulary from `design.md`.
- **D. Writer-owns-everything** (an agent that reads, thinks, and writes in one loop with tool access to the DB).

## 4. Why Rejected

- **A — Services/packages with own state:** Duplicates the microservice cost of ADR-001 at package granularity and invites data ownership ambiguity (who owns Memory — Store or Analyst?). The clean answer is: **the Store owns all state; Analyst and Writer are stateless transformers.** A three-package split blurs that.
- **B — Unified Store facade:** This is the God-Object trap. One facade over all aggregates becomes a 2000-line file that every feature imports and every change edits; it destroys the per-aggregate boundaries that make the domain legible, and it makes ownership scoping (Property 1) a single point of failure. Rejected explicitly.
- **C — Reject the triad:** The four-engine names describe *mechanism* but not the *responsibility boundary between reading canon, understanding it, and producing prose*. The triad adds a genuinely useful invariant — **generation must not mutate canon except through review** — that the raw engine list does not make obvious. So we keep both: engines as implementation, Store/Analyst/Writer as the responsibility contract.
- **D — Writer-owns-everything agent:** Non-deterministic, hard to test, and the fastest route to canon pollution (an LLM writing directly to the source of truth). Directly violates the human-in-the-loop principle (ADR-011).

## 5. Consequences

**Positive**
- A single, memorable rule governs the riskiest interaction in an AI-native app: *the model reads freely but writes only through review*.
- Store stays decomposed per aggregate → local changes stay local; no God Object.
- Analyst (Prompt+Memory) and Writer (Chat+Novel) are independently testable because they are stateless given inputs.

**Negative**
- The vocabulary overlaps with the engine names, which can confuse newcomers; the mapping table above must be kept authoritative.
- Requires discipline to keep the "no write-back except via review" rule; a lazy shortcut (Writer calling a repository `save`) would silently break it.

**Future risks**
- If reference analysis (ADR-008) or a learning loop (ADR-010) grows, the "Analyst" role could accrete responsibilities and drift toward its own God Object. Guard: Analyst remains a set of stateless functions over explicit inputs, not a stateful service.
- Pressure to let the Writer auto-commit canon "for convenience" will recur; it must be resisted or re-decided here.

## 6. Future Revisit Conditions

- If a concrete need arises for the Writer to persist *non-canon* artifacts directly (e.g. draft autosave) that don't threaten the source of truth, refine rule #2 rather than abandoning it.
- If the Analyst's reference/learning responsibilities become stateful (caches, indexes with lifecycles), revisit whether "Analyst" deserves to become a real subsystem with its own store — and if so, re-run the God-Object analysis.
- If profiling shows the Store→Analyst→Writer per-turn assembly is a latency bottleneck, revisit the boundary (e.g. caching in the Analyst) without collapsing the roles.
