# ADR-006: Relationship System

- **Status:** Accepted — *lightweight, entry-based relationships adopted; dedicated relationship-graph subsystem rejected for MVP, deferred to feature-flagged extension*
- **Date:** 2026-07-09
- **Deciders:** Architecture Review Board
- **Related:** ADR-003, ADR-004, ADR-015

## 1. Context

Characters in a long-form story have relationships (ally, rival, sibling, love interest, betrayer-of, mentor-of). A "Relationship System" could range from:
- a lightweight set of relationship *notes* attached to characters, to
- a full **relationship graph** with typed edges, directionality, temporal evolution, and interactive visualization (관계도).

The existing `design.md` deliberately places the relationship graph in **Phase 2** as a feature-flagged extension (`relationshipGraph` slot, backed by `kind:"fact"` memory entries), not in the MVP. The project plan lists 관계도 under "향후 확장" (future expansion).

The Board must decide the *canonical data* decision now (so it doesn't have to be retrofitted destructively), while keeping the MVP minimal.

## 2. Decision

**Adopt relationships as typed knowledge Entries (ADR-003), not as a dedicated graph subsystem.**

1. **Canonical form: `kind:"relationship"` Entries** in the Living Story Bible (ADR-004). A relationship is an Entry with subject/object references (character ids), a relation label, directionality, optional strength/valence, and provenance — retrieved and injected like any other Bible entry.
2. **No graph database, no graph engine, no standing relationship service** in the base architecture. Relationships are queried through the ordinary Store/repository path.
3. **Relationship injection into generation** happens through the same Analyst path as lore/facts (keyword + relevance, budget-bounded) — no bespoke pipeline.
4. **Visualization (the 관계도) is a feature-flagged extension** (`relationshipGraph`), rendered as a *read-only projection* computed on demand from relationship Entries. It lives inside existing screens (world/work detail tabs), never in the top-level navigation (ADR-014).
5. **AI-inferred relationships are proposals**, gated through the Review Card (ADR-011), consistent with ADR-004.

## 3. Alternatives Considered

- **A. Dedicated relationship graph subsystem** now — typed edges table, graph traversal API, temporal edges, interactive editor — as a first-class MVP feature.
- **B. Embed relationships inside character free-text** (personality/notes prose) with no structured representation at all.
- **C. Adopt a graph database** (e.g. a Neo4j/SQLite-graph extension) for relationships.

## 4. Why Rejected

- **A — Dedicated subsystem in MVP:** Large build (edge schema, traversal, temporal modeling, an interactive graph UI) for a feature the project plan itself classifies as future. It adds a second retrieval mechanism, more UI surface, and more test surface, all for a single user who may have a handful of characters. Violates minimal-UI (ADR-014) and simplicity-as-tie-breaker (ADR-001). Rejected for MVP; retained as a *projection* extension.
- **B — Free-text only:** Cheapest, but relationships then can't be reliably injected (no keywords/priority), can't be visualized later without re-parsing prose, and can't be reviewed as discrete facts. It also contradicts the flywheel goal (relationships are exactly the kind of canon that should accrue). Rejected as too lossy.
- **C — Graph database:** Introduces a second storage engine, breaking Zero-Cost simplicity, the single-`DATABASE_URL` swap story (CON-3), and the SQLite→PostgreSQL migration path. Graph queries over a personal-scale character set are trivially served by ordinary relational queries. Rejected as disproportionate.

## 5. Consequences

**Positive**
- Zero new subsystem, zero new storage engine; relationships ride the existing Entry + Analyst machinery.
- The expensive part (visualization) is opt-in and derived, so it can be added — or not — without touching the canonical model.
- Relationships participate in the same review/provenance discipline as the rest of the Bible.

**Negative**
- Complex graph queries (shortest path, cluster detection) are awkward on a relational Entry model; if such queries ever become core, a projection/index is needed.
- Directionality and temporal evolution (how a relationship changes across chapters) are expressible as multiple Entries but not elegantly; heavy temporal modeling would strain this representation.

**Future risks**
- If relationships become numerous and central (large cast, intricate political plots), the flat Entry model may need a derived graph projection for both querying and visualization — planned as a disposable read model (ADR-004 alt C), never a second source of truth.

## 6. Future Revisit Conditions

- Enable/build the `relationshipGraph` extension when the maintainer actually has enough characters that a visual overview provides real value.
- If temporal relationship evolution (per-chapter state) becomes important, revisit whether relationship Entries need explicit time/versioning fields or a dedicated projection.
- If graph-shaped queries become common, revisit building a derived in-memory or relational graph projection — still not a graph DB unless scale demands it.
