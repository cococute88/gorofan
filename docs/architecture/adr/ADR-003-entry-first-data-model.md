# ADR-003: Entry-first Data Model

- **Status:** Accepted (scoped) — *Entry-first is adopted for the knowledge/Bible layer only; rejected as the model-wide organizing principle*
- **Date:** 2026-07-09
- **Deciders:** Architecture Review Board
- **Related:** ADR-002, ADR-004, ADR-006, ADR-007

## 1. Context

"Entry-first" proposes that the atomic unit of the system is an **Entry** — a small, typed, keyworded knowledge fragment (a lore fact, a glossary term, an event, a relationship note, a character trait, a memory) — and that the larger structures (world, character, story bible) are *compositions of entries*.

The existing `design.md` is **aggregate-first**: `Character` and `World` are the declared centers ("도메인의 중심은 Character와 World"), with `LoreEntry`, `GlossaryTerm`, and `Memory (kind: summary|fact|event)` as satellites. So the design already has an "entry-like" pattern in exactly the places where knowledge is polymorphic — but it does **not** dissolve typed aggregates into generic entries.

The Board must decide how far "entry-first" should go. Taken to its extreme, entry-first becomes an **Entity-Attribute-Value (EAV)** / universal-table model where one `entries` table holds everything. That is the God-Object trap of ADR-002 expressed in the schema (a "God Table"): it maximizes flexibility and destroys type safety, query clarity, and referential integrity simultaneously.

## 2. Decision

**Adopt a two-tier data model:**

1. **Typed aggregates are the backbone (aggregate-first).** `User`, `World`, `Character`, `Persona`, `Work`, `Chapter`, `ChatSession`, `Message`, `ModelConfig` remain **explicit, strongly-typed entities** with their own tables, columns, invariants, and repositories. These are *not* entries. They have distinct lifecycles, distinct UIs, and distinct invariants (INV-1..7).

2. **Entry-first applies to the knowledge/Bible layer only.** The polymorphic *knowledge fragments* that feed generation — lore, glossary, extracted facts, events, relationship notes, style notes — are modeled as **typed Entries** sharing a common shape: `{ kind, keywords[], content, priority, enabled, source, provenance }`. This is the unit the Living Story Bible (ADR-004) is composed of, and the unit the Analyst scans and injects (ADR-009).

The dividing line is a rule: **if a thing has its own screen, its own lifecycle, and its own invariants, it is an aggregate; if it exists only to be retrieved and injected as context, it is an Entry.**

Constraints on the Entry tier:
- Entries are **typed by `kind`**, not free-form EAV. `kind` is a closed vocabulary (e.g. `lore`, `glossary`, `fact`, `event`, `relationship`, `style`), extended only by deliberate migration — never by user data.
- Entries carry **provenance** (authored-by-user vs AI-proposed vs extracted-from-chapter) so the Bible can distinguish canon from suggestion (critical for ADR-004/ADR-011).
- Entries **do not replace** `Message` or `Chapter`. Chat history and chapter prose are first-class immutable/authored content, not entries. Entries may be *derived from* them (a summary, an extracted fact) but the derivation is explicit and reviewed.

> This ADR states the *decision and its boundaries*. It intentionally does **not** specify table columns, keys, or DDL — that belongs to an RFC.

## 3. Alternatives Considered

- **A. Full entry-first / EAV** — one universal `entries` table (or a handful) holds all knowledge *and* the aggregates dissolve into entries with `kind` discriminators.
- **B. Pure aggregate-first** — keep exactly the `design.md` model; treat lore/glossary/memory as unrelated satellite tables with no shared "Entry" concept.
- **C. Document-per-world** — store the whole Story Bible as one JSON document per world, edited wholesale.

## 4. Why Rejected

- **A — Full EAV / God Table:** Destroys type safety (every field becomes a string/JSON blob), makes constraints and referential integrity nearly impossible, turns every query into a self-join, and cripples the ORM's ability to isolate SQLite/PostgreSQL dialects (CON-2). It also recreates the God-Object problem at the storage layer: one table every feature must touch. The flexibility it buys is not needed — the set of aggregate types is small and stable. **Rejected as an anti-pattern for a long-lived personal app.**
- **B — Pure aggregate-first with no Entry concept:** This is *almost* the status quo, but it misses a real opportunity: lore, glossary, extracted facts, events, and relationships genuinely share a retrieval/injection contract (keyword match, priority, budget). Without a unifying Entry shape, the Analyst needs bespoke scan/inject logic per satellite type, and the "Living Story Bible" (ADR-004) has no coherent read model. Rejected as under-unified.
- **C — Document-per-world JSON:** Simple to start, but wholesale-edit documents fight the mobile, incremental, review-one-fact-at-a-time UX (ADR-011), make keyword-triggered partial injection awkward, and turn concurrent edits into whole-document conflicts. Rejected for the interaction model it forces.

## 5. Consequences

**Positive**
- Type safety and query clarity for the things that have real structure (aggregates); uniformity for the things that are genuinely uniform (knowledge fragments).
- The Analyst has **one** scan/rank/inject path over a shared Entry contract → less code, fewer bugs, easier RAG upgrade later (a Retriever over Entries — FUT-2).
- Provenance on entries makes the human-in-the-loop canon gate (ADR-011) implementable without bolt-ons.

**Negative**
- Two tiers means a judgment call at the boundary ("is a Character trait an aggregate field or an Entry?"). The rule in §2 resolves most cases but not all; some cases need a documented decision.
- Slightly more schema than pure aggregate-first (a typed Entry tier), though far less than EAV.

**Future risks**
- Scope creep of the Entry `kind` vocabulary could re-introduce EAV by the back door (a `kind:"misc"` catch-all). Guard: adding a `kind` requires an ADR/RFC and a migration, never runtime data.
- If character modeling later wants richer structure (ADR-007 currently keeps it prose-based), the aggregate/Entry boundary for character traits may need revisiting.

## 6. Future Revisit Conditions

- If a genuinely dynamic, user-defined schema requirement appears (e.g. users defining arbitrary custom fields per world), reconsider a *bounded* EAV escape hatch — scoped to a single `custom_fields` JSON column on an aggregate, never a global entities table.
- If RAG/embedding retrieval (FUT-2) is adopted, revisit whether the Entry tier needs an embedding column and whether `Message`/`Chapter` chunks should be projected into the Entry retrieval space.
- If the aggregate/Entry boundary produces repeated ambiguity in practice, promote §2's rule into a short decision-log appendix with worked examples.
