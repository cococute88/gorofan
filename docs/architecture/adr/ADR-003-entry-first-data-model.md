# ADR-003: Entry-first Data Model (One Prose-first Entry Model)

- **Status:** Accepted (revised v2 — **reversed** from v1's rejection of the single Entry model)
- **Date:** 2026-07-09 (v1) · revised 2026-07-09 (v2)
- **Deciders:** Architecture Review Board
- **Related:** ADR-002, ADR-004, ADR-007, ADR-017, ADR-018

## 1. Context

v1 adopted a **two-tier** model: typed aggregates (Character, World, …) as the backbone, with entries only for the knowledge tier, and it explicitly **rejected** a model-wide single Entry table as "EAV / God-Table." `architecture-final-minimal.md` §2 challenges exactly this and proposes **one Entry model** for all knowledge — Character DNA (five layers), World DNA, Style Profile, Plot/Dialogue/Emotion libraries, and all ledgers (fact / knowledge / promise / relationship / timeline / summary) — with `Character` and `World` demoted to **thin containers**.

The Board must decide whether v1's EAV alarm was correct. On re-examination it was **overstated**: the proposal is not classic EAV (one logical row shredded into attribute rows). It is a **discriminated single-table document model** — a well-understood, legitimate pattern — whose primary field is **prose** (`content`), with a `data` JSON escape hatch used *only* where a deterministic check needs structure. That is materially different from an attribute bag, and the alternative (≈10 tables/editors/retrieval paths) is the heavier debt.

## 2. Decision

**Adopt one prose-first `Entry` model as the Store's knowledge representation. Reverse v1's rejection of the single table. Keep true aggregates as typed tables; demote Character/World to thin containers.**

1. **One `Entry` type** carries all knowledge/DNA/ledger data. Its shape (conceptual — RFCs own the DDL): a `scope` (collection / work), a governed `type` discriminator, an optional `subject`, a **prose `content`** field written *to be injected into prompts*, an optional `data` JSON (only when a check needs structure), plus `provenance`, `confidence`, `status` (proposed / canon / rejected), `superseded_by`, and `created_at_chapter`.
2. **Prose-first is the governing principle.** The heavy consumer of entries is prompt assembly, and models read prose better than schemas. Normalize into `data` JSON *only* where a deterministic check reads it (promise due-dates, knowledge-matrix lookups, relationship stage, summary level). **Do not** build an ontology, a knowledge graph, per-attribute columns, or "axes-with-intensity" as first-class schema.
3. **`type` is a governed closed vocabulary** — e.g. `character.core|character.voice|character.exemplar`, `world.rule|world.naming|world.place`, `style.prose`, `emotion.repertoire`, `plot.trope`, `fact`, `knowledge`, `promise`, `relationship`, `summary`, `preference`, `note`. **A new library/ledger = a new `type` string, never a new table.** Adding a `type` is a deliberate decision (ADR/RFC), never user-supplied data. **No `type:"misc"` catch-all** (that would re-open EAV by the back door).
4. **True aggregates stay typed tables:** `User`, `Work`, `Chapter` (TipTap doc), `ChatSession`, `Message` (append-only, immutable — INV-4), `ModelConfig`, `Collection`. These have distinct lifecycles/invariants and are **not** entries. Chat `Memory` stays its own chat-private table (ADR-018) — it is not folded into Entry.
5. **Character and World become thin containers.** `Character` keeps identity/container fields; its personality/voice move into `character.*` entries. `World` keeps name/description/tone; races/nations/taboos/lore move into `world.*` entries. Legacy free-text columns become a *rendered view of entries* or are dropped (migrations in ADR-017 / `architecture-final-minimal.md` §5).
6. **Provenance + status are mandatory** and power Review Cards (status=proposed → ADR-011) and the "why does the AI think this?" popover (ADR-014).

> This ADR decides the *model and its guardrails*. It writes no columns, keys, or DDL — those belong to an RFC.

## 3. Alternatives Considered

- **A. v1's two-tier model** (typed aggregates + separate knowledge tier; no single Entry table).
- **B. Full literal R1–R26** — Character DNA (5 layered tables), World DNA table, Style Profile table, Plot/Dialogue/Emotion library tables, fact/knowledge/promise/relationship ledger tables.
- **C. Classic EAV** — one attribute-value store shredding every knowledge object into rows.
- **D. Knowledge graph / ontology** for facts, relationships, and world rules.

## 4. Why Rejected

- **A — v1 two-tier:** Its instinct (aggregates typed, knowledge unified) was right, but it stopped short and kept the knowledge tier as *multiple* typed tables while banning the single table. The single prose-first table is simpler (one editor, one retrieval path, new library = a string) and — crucially — **not** the EAV it feared. Superseded by the single Entry model.
- **B — Literal R1–R26 tables:** The explicit debt bomb (`architecture-final-minimal.md`): ~10 tables/editors/retrieval paths for what is one document model. Rejected.
- **C — Classic EAV:** Still rejected, and the Entry model is *not* this: the primary field is prose `content`, not shredded attributes; `type` is closed; `data` JSON is a narrow escape hatch. The genuine EAV harms (no type safety, self-join queries, integrity loss) do not apply to a discriminated prose-document table. Rejected.
- **D — Graph/ontology:** The single most attractive over-engineering trap in this category (both reviews flag it). It produces *worse* prompts than well-written provenanced paragraphs, and adds a second storage engine (breaking Zero-Cost and the single-`DATABASE_URL` swap). Rejected; a derived read-only projection remains possible later (ADR-006).

## 5. Consequences

**Positive**
- One table, one editor (rendered by `type`), one `retrieve()` — the Store is ~100 lines, not a subsystem (ADR-018).
- New DNA/library/ledger types cost a `type` string + a prompt facet, not a migration — the evolution surface the whole architecture wants (ADR-001, ADR-015).
- Prose-first yields better prompt material than schema; provenance/confidence make DNA trustworthy and Review-Card-gated.
- RAG upgrade later is a drop-in over one Entry space (ADR-018), not per-table retrofits.

**Negative**
- Weaker database-enforced integrity for structured facts (they live in `data` JSON); deterministic checks must parse JSON.
- Concentrated risk: a bug or a bad `type` proliferation affects one central table.
- The aggregate/Entry boundary still needs judgment (e.g., is a Chapter summary an Entry? — yes, `summary` type; is Message? — no, aggregate).

**Future risks**
- Prose-first is consciously the **riskiest** bet (both reviews and the Board agree). If `knowledge`/`promise`/`timeline` checks need heavy structure (timeline arithmetic, who-knows-what graphs), `data` JSON strains.
- `type` vocabulary creep; guarded by the no-`misc`, ADR-gated rule.

## 6. Future Revisit Conditions

- **Promote a `type` to a real table** when its deterministic checks start doing "parsing gymnastics" (the visible failure mode). This is cheap *precisely because* everything routes through one Store — the canonical pressure valve.
- Adopt embeddings on the Entry space only when keyword retrieval demonstrably misses, measured on the Bench (ADR-018).
- If a genuine user-defined-schema need appears, add a bounded `data` extension on a specific `type`, never a global attribute store.
