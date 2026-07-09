# ADR-015: Future Expansion Principles

- **Status:** Accepted — *non-destructive, flag-gated, seam-based expansion adopted; speculative abstraction rejected*
- **Date:** 2026-07-09
- **Deciders:** Architecture Review Board
- **Related:** ADR-001, ADR-014, ADR-004, ADR-016, ADR-017

## 1. Context

A personal tool intended to live for years will grow: image generation, EPUB/PDF export, RAG retrieval, relationship visualization, story timeline, model/cost dashboards, eventual multi-user. `design.md` §7.15/§8.17/§16 already lay out an expansion philosophy: feature flags (default off), extension slots, non-destructive schema changes (nullable-only), Protocol seams (`Retriever`, `StorageBackend`, `JobQueue`, `LLMProvider`), and navigation invariance.

There are two opposing failure modes to steer between:
1. **Rigidity** — an architecture so concrete that every new capability requires invasive surgery.
2. **Speculative over-abstraction** — seams and plugin frameworks built for imagined futures that never arrive, paying complexity now for options never exercised (the classic YAGNI violation). `design.md` itself flirts with this by naming Celery/ARQ and S3 implementations that a single-user app may never need.

The Board must adopt expansion principles that keep the door open **without** paying to walk through doors nobody uses.

## 2. Decision

**Adopt disciplined, non-destructive, seam-based expansion — with a strict rule against speculative implementation.**

1. **Non-destructive schema evolution.** New capabilities add *nullable* columns or new tables and forward-only migrations; they never break or repurpose existing structures (FUT-2, `design.md` §16.2). Existing data and the local-first path keep working untouched.
2. **Feature flags, default off.** Every expansion ships behind a flag defaulting to off, so the MVP/base experience is unaffected until deliberately enabled (§7.15).
3. **Navigation invariance** (ADR-014): expansions enter via slots/tabs/drawers/command palette, never the top-level nav.
4. **Define the seam, defer the second implementation.** A Protocol/interface (a "seam") is introduced when a *second concrete implementation is genuinely foreseeable* — and even then, **only the first implementation is built.** The seam is cheap (an interface + the one impl behind it); the speculative second impl is not built until a real need exists.
   - Sanctioned seams (interface now, second impl later): `LLMProvider` (ADR-016), `Retriever` (memory/reference RAG — FUT-2), `StorageBackend` (local→S3), `JobQueue` (in-process→distributed), `ImageProvider`, `AuthProvider` (ADR-019), Export/chapter-composition seam.
   - **Not sanctioned now:** building the Celery/ARQ queue, the S3 backend, the embedding retriever, or the image adapter *implementations* before a concrete trigger. The seam holds the place; the implementation waits.
5. **Local-first stays the invariant.** Every expansion keeps the fully-local, zero-cost, offline path working; cloud/remote is always optional (§16.2).
6. **Core stays unchanged (0-core-change goal).** Adding a provider, retriever, storage, or auth method must be a registration/config act, not a change to Router/Service/Engine core (`design.md` §8.17).

## 3. Alternatives Considered

- **A. Build the abstractions and their multiple implementations up front** (the "platform from day one" approach).
- **B. No seams — YAGNI-maximalist** — write the simplest concrete code with zero interfaces; refactor only when a second need appears.
- **C. Plugin framework / marketplace architecture** now (the long-term "장기 비전" made present).

## 4. Why Rejected

- **A — Build implementations up front:** Pays real complexity for hypothetical futures. Celery, S3, embeddings, image generation — each is meaningful code, ops, and test surface that a single user may never touch. This is the over-abstraction failure mode. Rejected: define seams, don't build unused impls.
- **B — No seams at all:** Tempting for simplicity, but a few boundaries are *genuinely* certain to be crossed (LLM providers *will* be swapped — it's a founding requirement; SQLite→Postgres *is* planned). For those, retrofitting an interface across a concrete codebase later is costly and risky. A thin seam at the known-volatile boundaries is cheap insurance. Rejected as too rigid at the *known* volatile points — while its spirit (no speculative interfaces elsewhere) is adopted.
- **C — Plugin framework now:** Enormous complexity (extension API, sandboxing, versioning, discovery) for a single-user product with no third-party developers. It is explicitly a *long-term vision*, not a present need. Building it now is the ultimate speculative over-abstraction. Rejected until/unless the product genuinely opens to external extensions.

## 5. Consequences

**Positive**
- The product can grow for years without destructive rewrites; the local-first core is never disturbed by expansion.
- Complexity is paid *just-in-time*: seams are cheap, implementations arrive with their justification.
- Clear, short list of sanctioned seams prevents both rigidity and abstraction sprawl.

**Negative**
- Judgment is required to distinguish a "known-volatile boundary worth a seam" from speculative abstraction; the sanctioned-seam list is the guide but edge cases will arise.
- Nullable-only / forward-only migrations accumulate some schema cruft over years (unused nullable columns) — an acceptable trade for never breaking data.
- A seam with only one implementation can *look* like premature abstraction to a reviewer; the list here justifies each.

**Future risks**
- The sanctioned-seam list could itself grow speculatively; adding a seam should require the same "second impl foreseeable" test and, ideally, an ADR/RFC note.
- Forward-only migrations mean mistakes are corrected by new migrations, not rollbacks; discipline in migration authoring matters (ADR-017).

## 6. Future Revisit Conditions

- Add a new sanctioned seam only when a concrete second implementation becomes foreseeable; record it here.
- Build a deferred implementation (Celery, S3, embeddings, image, etc.) when its concrete trigger fires (documented per-seam in the relevant ADR/roadmap).
- Reconsider a plugin/marketplace architecture only if the product deliberately opens to third-party extensions (the long-term vision materializing) — a major, explicit re-decision.
