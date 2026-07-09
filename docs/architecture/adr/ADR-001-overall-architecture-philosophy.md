# ADR-001: Overall Architecture Philosophy

- **Status:** Accepted
- **Date:** 2026-07-09
- **Deciders:** Architecture Review Board (Chief Software Architect)
- **Supersedes:** —
- **Related:** ADR-002, ADR-014, ADR-015, ADR-017

> **Source-of-truth note.** The task brief refers to an "AI Author OS Design Review (R1–R26)" and a "Final Architecture Review (Minimal Architecture)". **Neither document exists in this repository.** The concrete artifacts that do exist are `.kiro/specs/ai-creative-workspace/design.md` (the full technical design), `requirements.md`, and `AI_캐릭터챗_소설앱_프로젝트_계획서.md` (the project plan). Every ADR in this set is grounded in those artifacts plus the decision principles stated in the task brief. Where a mandated ADR topic uses "AI Author OS" vocabulary (Store/Analyst/Writer, Entry-first, Character DNA, Bench, etc.) that has no counterpart in the existing design, the ADR reconstructs the *intent* of the concept, evaluates it on its merits, and states the decision honestly — including rejection. See ADR-INDEX.md § "Provenance and Honesty Statement".

---

## 1. Context

This is a **personal-use, single-owner** AI creative workspace that unifies AI character chat and AI long-form novel writing over one shared character/world database ("나만의 로판AI + 하트픽션"). The defining constraints are not scale or team throughput; they are:

- One user, self-hosted, **zero infrastructure cost** beyond LLM API fees.
- **No vendor lock-in** — any OpenAI-compatible provider must be swappable at runtime.
- **Longevity** — the architecture must remain understandable and maintainable by a single maintainer for many years.
- **Mobile-first UX** with a deliberately minimal surface.

The existing `design.md` already commits to a layered dependency rule: `Router → Service → Engine → Adapter/Repository → Model`, with Engines (Prompt, Memory, Novel, Chat) as the domain core and a Provider Adapter for LLM neutrality. Before adopting any of the more ambitious "AI Author OS" proposals, the Board must first fix the *shape* of the system.

The temptation in an AI-native product is to reach for distributed services, agent swarms, message buses, vector databases, and ML feedback loops from day one. For a single-user app, each of those is a liability with no payer.

## 2. Decision

**Adopt a single-process, layered modular monolith as the permanent architecture for the foreseeable life of the product.**

Concretely:

1. **One backend process, one frontend app.** No microservices, no message broker, no separate worker cluster in the base architecture. Background work runs in-process (see ADR-015 for the swap seam).
2. **Strict unidirectional layering:** `Router → Service → Engine → Adapter/Repository → Model`. Reverse imports are forbidden. Engines depend only on Protocols (Adapter, read-only Repository), never on other Engines directly; shared logic (e.g. summarization) is a standalone component (per `design.md` CON-6).
3. **Personal-First / Local-First is the default and the tested path.** Multi-user, cloud, and collaboration are *latent* capabilities (every aggregate already carries `user_id`, auth is a toggle) but are **not built, not tested, and not assumed** until a concrete need exists.
4. **Simplicity is the tie-breaker.** When two designs are comparable in quality, the one with fewer moving parts, fewer abstractions, and fewer runtime dependencies wins. Abstractions are introduced only when a *second concrete implementation* is imminent, not speculatively.
5. **The domain is the asset; the plumbing is disposable.** Effort concentrates on the Prompt Engine, the Story Bible, and character/novel quality (ADR-004, ADR-007, ADR-009). Persistence, transport, and deployment are intentionally boring.

## 3. Alternatives Considered

- **A. Microservices / "AI Author OS" as separate deployable services** (a Store service, an Analyst service, a Writer service — see ADR-002).
- **B. Event-driven architecture** with a message bus and event-sourced domain.
- **C. Agent-framework-first** (LangChain/LangGraph-style orchestration as the backbone), where the app is a graph of autonomous agents.
- **D. Serverless / managed-cloud-first** to minimize ops.

## 4. Why Rejected

- **A — Microservices:** For one user on one machine, service boundaries add network hops, serialization, partial-failure handling, and deployment complexity with **zero scaling benefit**. The "Store/Analyst/Writer" separation is valuable as a *conceptual* decomposition, but realizing it as processes is pure cost. Rejected as topology; adopted as logical roles (ADR-002).
- **B — Event sourcing / bus:** Event sourcing is a powerful pattern for audit-heavy, multi-writer, high-throughput domains. Here there is a single writer and modest data volume. The append-only message model (INV-4) already gives the audit properties we actually need without the operational weight of a bus.
- **C — Agent-framework-first:** Making an agent framework the backbone couples the entire product to a fast-moving third-party abstraction (vendor lock-in of a different kind), obscures control flow, and makes deterministic testing hard. We keep orchestration as plain, explicit code and treat the LLM as a stateless function behind the Adapter.
- **D — Serverless/cloud-first:** Violates Zero-Cost and Local-First. Cold starts, per-request billing, and provider lock-in are unacceptable for a personal, offline-capable tool (Ollama path must work fully offline).

## 5. Consequences

**Positive**
- Trivial to run (`docker compose up`), reason about, and debug — one process, one stack trace.
- Lowest possible cost and operational burden; survives long idle periods and personal-project neglect.
- Layering keeps the codebase navigable years later; a new contributor can hold the whole system in their head.
- All the "scale" seams remain *available* (user_id, Protocol boundaries) without being *paid for* now.

**Negative**
- A monolith can rot into tangled modules if the layering rule is not enforced; discipline (and lightweight import-direction tests) is required.
- Some genuinely parallel workloads (e.g. batch reference analysis) are constrained by the single process until a JobQueue implementation is swapped in.
- The architecture is optimized for one user; a sudden pivot to true multi-tenant SaaS would require real work (though the seams soften it).

**Future risks**
- If the product ever becomes multi-user at scale, the in-process JobQueue and SQLite single-writer constraint become hard limits (mitigated by the documented swap paths — ADR-015, ADR-017).
- "Simplicity as tie-breaker" can be abused to justify under-abstraction; the counterweight is the explicit seam list in ADR-015.

## 6. Future Revisit Conditions

Reopen this ADR if **any** of the following becomes true:
- The product is deliberately repositioned from personal tool to hosted multi-user service.
- Sustained concurrent workloads (e.g. always-on background analysis, multi-user chat) saturate a single process.
- A background workload's latency or failure isolation materially degrades the interactive chat/writing path despite the in-process JobQueue.
- The maintainer count grows past ~3 and module ownership boundaries start causing merge friction that service boundaries would relieve.
