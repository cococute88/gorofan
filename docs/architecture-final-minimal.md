# Final Architecture Review — The Minimal AI Author OS

**Premise:** blank-page redesign, 2026, everything learned. Not more features — the *simplest* architecture that can still become the best AI Author OS. This document deliberately overrules parts of the previous review (`design-review-ai-author-os.md`, R1–R26) where those recommendations added structure that doesn't pay rent.

---

## 0. Answer key

| Question | Answer |
|---|---|
| **Which engines should be merged?** | All of them, into three: **Store** (Story Bible + all six DNA/libraries + all ledgers = one Entry model), **Analyst** (Reference Intelligence + chapter fact-ingestion + preference distillation = one extraction service), **Writer** (Planning + Novel + Serialization + Style layer + critics = one loop runner executing declarative stages). |
| **Which engines should be deleted?** | As *named components*: Story Bible Engine, Plot Library, Dialogue Library, Emotion Library, Style Profile, Serialization Engine (my R11), Relationship Planner (my R9), Foreshadow Scheduler (my R10), Reader-Sim (my R26), Reconciliation Engine (my R2), genre-baseline machinery (my R3). The *capabilities* survive as entry types and prompt stages; the abstractions die. |
| **Which abstractions are unnecessary?** | "Engine" as the organizing noun. Per-library tables and per-library editors. Keyword-triggered lorebooks. DB-stored prompt templates. Structured knowledge graphs/ontologies. DNA "axes with intensity" as a first-class schema. |
| **Which data models become debt in two years?** | Free-text `Character.personality`/`speech_style` columns; `World.races/nations/taboos` string arrays; `Lorebook`/`LoreEntry` keyword triggering; single `Chapter.summary`; any per-library table; DB `prompt_templates`. All named with migrations in §3.4. |
| **Which parts are over-engineered?** | In R1–R26: edit-to-attribute back-propagation (R16), four-critic ensemble at launch (R12), baseline-delta DNA storage (R3), reconciliation (R2). In the old plan: keyword lorebook scanning, prompt-template DB. In temptation-space: knowledge graphs, embedding infrastructure before keyword retrieval fails, per-attribute sliders. |
| **Which missing engine matters most after shipping?** | **The Bench** — an evaluation harness (golden scenes + the critic checks run as metrics). Without it every prompt tweak is vibes and quality regresses invisibly. Second: edit-diff *capture* (not learning — capture), because diffs you never stored can never be recovered. |
| **Blank-page architecture?** | Kernel + data + prompts: three services on the existing substrate; all creative intelligence lives in versioned prompt files and typed entries, so the product evolves for years without new services or schema migrations. §1. |

---

## 1. The architecture

```
┌─────────────────────────────────────────────────────────────┐
│ SUBSTRATE (already built, keep as-is)                        │
│  provider adapters · PromptEngine (blocks/budget) · auth ·  │
│  chat engine · TipTap chapters · jobs                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  STORE      one Entry model + one retrieve(query, budget)   │
│             function. IS the Story Bible, IS all six        │
│             libraries, IS all ledgers.                       │
│                                                              │
│  ANALYST    text in → entries out. Same service for:        │
│             reference analysis (scope=collection),           │
│             chapter ingestion (scope=work),                  │
│             preference distillation (input=edit diffs).      │
│             A facet = one prompt file.                       │
│                                                              │
│  WRITER     one loop: retrieve → assemble → generate →      │
│             validate → persist. A pipeline = a declarative   │
│             stage list. Planning, drafting, critics,         │
│             episode assembly, style pass = stages, not       │
│             engines.                                         │
│                                                              │
│  BENCH      dev-only: golden scenes + metric'd critic        │
│             checks; A/B any prompt or stage change.          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
   UI: 쓰기 · 바이블 · 서재  + Review Cards (= entries with
   status=proposed). Unchanged from previous review.
```

Three runtime services, one dev harness, zero new UI. Every quality mechanism from R1–R26 that survives lives inside these as **data** (entry types) or **prompts** (facet/stage files) — the two cheapest things in software to change.

The governing rule: **code that must be written once (loop runner, entry store, retrieval, diff capture) is code; everything that will be tuned weekly (what to extract, how to plan, how to critique, how to style) is a prompt file in the repo.** Two years of product evolution should be commits to `prompts/`, not migrations and new modules.

---

## 2. Store — one Entry model kills seven schemas

The previous review implicitly proposed parallel stores: Character DNA (five layers), World DNA, Style Profile, Plot/Dialogue/Emotion libraries, fact ledger, knowledge matrix, promise ledger, relationship state. Built literally, that is ~10 tables, ~10 editors, ~10 retrieval paths — the classic two-year debt bomb. They are all the same thing:

```
Entry
  id, user_id
  scope        collection:<id> | work:<id>        -- where this is true
  type         character.core | character.voice | character.exemplar |
               world.rule | world.naming | world.place |
               style.prose | emotion.repertoire | plot.trope |
               fact | knowledge | promise | relationship | summary |
               preference | note
  subject      character id / pair / location / null
  content      TEXT — prompt-ready prose. The primary field.
  data         JSON — only when a check needs structure
               (promise: due window; knowledge: who+what;
                relationship: stage; summary: level)
  provenance   reference excerpt | chapter # | diff batch
  confidence   float
  status       proposed | canon | rejected      (Review Card = proposed entry)
  superseded_by, created_at_chapter
```

**The design principle that keeps this simple: prose-first.** The only heavy consumer of entries is prompt assembly, and models read prose better than schemas. `content` is written *to be injected*; `data` exists only where a deterministic check reads it (promise due-dates, knowledge-matrix lookups, relationship stage). Resist every urge to normalize character attributes into columns, build an ontology, or add a graph database — that is the single most attractive over-engineering trap in this product category, and it produces worse prompts than well-written paragraphs with provenance.

Consequences:

- **Six libraries → six `type` prefixes.** "Dialogue Library" = `character.exemplar` entries indexed by scene-type in `data`. "Emotion Library" = `emotion.repertoire` entries. No new tables ever for a new library — a new `type` string.
- **All ledgers → work-scoped entries.** Fact ledger = `fact` + `created_at_chapter`. Knowledge matrix = `knowledge`. Promise ledger = `promise` with due window in `data`. Contradiction gate and promise-due checks read these.
- **One editor.** The DNA Editor, the Bible browser, the Review Card queue are the *same component* rendering entries by type (card view for `character.*`, list for `fact`, timeline chip for `promise`). One editor to maintain instead of six.
- **One retrieval function.** `retrieve(scope, cast, location, beat, budget) -> entries` — rank by type-weight × relevance × recency, cut to token budget. This is the existing `MemoryEngine._rank/_select_within_budget` pattern (`engines/memory/engine.py`) generalized; it is ~100 lines, not an engine. Start with keyword ranking; add embeddings only when keyword retrieval demonstrably misses (measured on the Bench), not before.

**Self-correction on R15/R16:** the five-layer DNA taxonomy survives as *prompt organization for the Analyst* (what to look for) and *rendering order for the card*, not as schema. And drop R16's back-propagation (user edits example dialogue → engine infers attribute changes) from v1: when a user fixes an example line, just store the corrected line as a canonical `character.exemplar` with provenance `user`. Exemplars outrank descriptions in prompt assembly anyway, so the effect is ~equivalent at a fraction of the machinery. Back-prop can come later as an Analyst facet if it ever proves necessary.

---

## 3. Writer — one loop, stages as data

Planning Engine, Novel Engine, Serialization Engine, Style layer, and the critic ensemble share one runtime shape: *retrieve entries → assemble prompt → call model → validate → persist*. So there is exactly one loop runner, and pipelines are declarative:

```yaml
# pipelines/write_episode.yaml   (illustrative — format is yours)
stages:
  - plan_scenes:      retrieve [arc, promise(due), relationship, open-threads]
                      emit scene cards (goal/conflict/outcome/value-shift/hook)
  - draft_scene(×N):  retrieve [character.*(cast), world.*(location),
                      emotion.repertoire(beat), exemplar(scene-type), fact, knowledge]
                      voice-in (dialogue voice drafted here, per R18)
  - check:            continuity(fact+knowledge) · voice(attribution test, R13)
  - revise_scene:     only scenes with check findings; notes as instructions
  - assemble_episode: target length, in-hook, exit-hook present
  - surface_style:    style.prose entries; DIALOGUE FROZEN (R18)
  - qa:               llm-ism screen · user forbidden list · repetition counter
  - ingest:           Analyst(work scope): new facts/knowledge/promises → proposed
                      diff-capture armed for user's subsequent edits
```

What this dissolves:

- **R11 Serialization Engine — deleted as an engine.** Episode shaping is `assemble_episode` (one stage) plus hook/length checks in `qa`. I over-named a stage into an engine; the *craft knowledge* (절단신공, 사이다 cadence) lives in the stage prompt and the extracted signals, not in code.
- **R9 Relationship Planner, R10 Foreshadow Scheduler — deleted as components.** They are three things each: an entry type (`relationship`, `promise`), two lines in the `plan_scenes` retrieval list, and one check. The previous review made them sound like modules; they are rows and prompt clauses.
- **R12 critic ensemble — halved.** Launch with two checks that have ground truth (continuity vs. entries, voice vs. exemplars). Pacing and cliché become cheap `qa` assertions, not model-critics. Add a third model-critic only when the Bench shows a recurring failure the existing two can't see. Every critic is latency and cost; earn each one.
- **Prompts live in the repo, not the database.** The old plan's `prompt_templates` table: delete the idea. DB-stored prompts rot invisibly, can't be diffed or reviewed, and fork per-user into an unsupportable matrix. Prompt files + git + the Bench = versioned, reviewable, regression-tested creativity. (User-visible customization stays where you already put it: forbidden list, tone contract text box — *inputs to* prompts, never prompt bodies.)

Streaming UX stands as designed: stream the draft optimistically; deliver "polish" (revise + style + qa) as the finished state.

---

## 4. Analyst — one extractor, three inputs

The previous review had three separate learning mechanisms: Reference Intelligence (R1), Bible auto-ingestion (R4), and edit-diff preference learning (R25). They are the same operation — *text in, entries out* — differing only in input and scope:

| Input | Scope | Facets | Output |
|---|---|---|---|
| Uploaded reference | `collection` | §2 signal catalog (prev. review) | `character.*`, `world.*`, `style.*`, `emotion.*`, `plot.*` — status `canon`, provenanced |
| Accepted chapter | `work` | facts, knowledge, promises, relationship, summary | ledger entries — status `proposed` (Review Cards) |
| Accumulated edit diffs | `work`→`user` | style deltas, per-character voice fixes | `preference` entries injected into future prompts |

One service, one job queue, facet = prompt file. The signal catalog (previous review §2) is unchanged and remains the Analyst's spec — it was never an architecture, it was always a prompt library, and now it's explicitly that.

**Self-correction on R25:** ship *capture*, not learning. One column pair (draft text vs. accepted text) per chapter, from day one — this is the data you can never retroactively collect. The "learning" is a monthly Analyst facet run over diffs producing `preference` entries. No online-learning machinery, no per-edit classification pipeline. Delete that ambition from v1 scope.

**Self-corrections on R2/R3:** delete both. Reconciliation across disagreeing references → frequency-weighted merge with provenance is enough; if two references genuinely conflict, both entries exist and retrieval prefers higher confidence. Genre-baseline deltas → store absolutes; computing "what's distinctive" is a future Analyst pass, not a storage format. Designing storage around a speculative future analysis was my own premature cleverness.

---

## 5. Two-year debt list (current repo, name-by-name)

1. **`Character.personality` / `speech_style` free-text columns** (`models/character.py`) — will fight the entry store within months. Migration: on first analysis, convert to `character.core`/`character.voice` entries; columns become a *rendered view* (or are dropped). Do this before building any UI against them.
2. **`World.races/nations/taboos` string arrays** — real worlds outgrow string lists (a race needs description, provenance, relations). Migration: `world.*` entries; keep `World` as a thin container (name, description, tone).
3. **`Lorebook`/`LoreEntry` keyword-trigger system** (`scan_depth`, keyword scanning) — SillyTavern-inherited; superseded entirely by entry retrieval. Migration: lore entries → `world.*`/`note` entries; delete the trigger machinery. Two retrieval systems is one too many.
4. **`Chapter.summary` single text** — serialization needs summaries at multiple granularities (scene / chapter / arc / story-so-far). Migration: `summary` entries with `data.level`; the column stays as a cache of level=chapter.
5. **Chat `Memory` table** — fine for chat; do *not* extend it toward novel context. When chat and novel need shared knowledge (R22 voice-gym bookmarks), the bookmark writes an Entry; `Memory` stays chat-private.
6. **Anything per-library** — if a table named `dialogue_library` or `character_dna_attributes` ever appears in a migration, this document has failed.

---

## 6. R1–R26 disposition table

| Fate | Recommendations |
|---|---|
| **Survive as code** (the only real components) | R5 retrieval (→ Store function) · R12 *halved* (→ 2 checks in Writer) · R13 attribution test · R4 ingestion (→ Analyst) · R25 *capture only* · R6 contradiction gate (→ check) |
| **Survive as data** (entry types) | R15 DNA layers · R10 promises · R9 relationship state · R20 repetition (counter + qa) · R21 world rules/naming · R22 chat bookmarks · R23 emotion repertoire · R24 trope cards · R7 tone contract |
| **Survive as prompts** (facet/stage files) | R1 facet catalog · R8 scene-card cascade · R11 episode assembly · R14 exemplar injection · R18 voice-in/surface-late · R19 LLM-ism screen |
| **Deferred until Bench proves need** | R16 back-propagation · R17 conflict solver (start: last-write-wins by precedence, no card) · embeddings · 3rd+ critic |
| **Deleted** | R2 reconciliation · R3 baseline-deltas · R26 reader-sim |

Nothing of quality-consequence was lost: every surviving mechanism from the four loops (analysis, drafting, continuity, learning-capture) is present. What was lost is *nouns* — and each deleted noun is a service you don't operate, an editor you don't maintain, and a migration you don't write.

---

## 7. The Bench — the missing engine that matters most after shipping

Everything above makes creative behavior live in prompt files — which means creative behavior will change *constantly*. Without measurement, week-6-you will "improve" a prompt and silently break voice consistency, and you will not find out until a user does. The previous review missed this entirely because it reviewed the product; this is the meta-engine that protects the product:

- **Golden set:** 20–30 fixed scenarios (scene card + frozen entry snapshot) spanning scene types: confession, banter, action, reveal, quiet interiority.
- **Metrics = the checks you already built:** contradiction count, voice-attribution accuracy, hook presence, length adherence, LLM-ism hits, repetition score — plus a pairwise "old vs. new, which is better?" model judgment per golden scene.
- **Usage:** every prompt/stage/retrieval change runs the bench; a one-page diff report. It reuses Writer's checks — the marginal build cost is a runner script and fixtures.

This is dev-only, zero UI, and it is the difference between a system that *compounds* in quality and one that oscillates.

---

## 8. Build order (thin vertical slices, each shippable)

1. **Entry store + retrieval** (generalize the MemoryEngine pattern) + migrate character/world/lore fields → entries.
2. **Writer loop runner** with the smallest pipeline: `plan_scenes → draft_scene → assemble_episode` — no checks yet. Novels get better immediately from scene cards + retrieval alone.
3. **Analyst, reference path** — the top 5 facets (voice, prose style, emotion repertoire, chapter endings, naming). DNA cards appear in 서재.
4. **Checks:** continuity + voice attribution + qa (llm-isms, forbidden list). **Diff capture** (one column pair). **Bench v0** (10 scenes).
5. **Analyst, ingestion path** — facts/knowledge/promises as Review Cards. The Bible is now alive.
6. Then, and only then, ask the Bench what to build next.

Steps 1–4 are the whole quality core. Everything after is iteration on prompts and entry types — which is exactly where a two-person-or-smaller team wants its iteration surface to be.

---

## 9. Final assumptions challenged (including this document's)

1. **"Engines" was the wrong frame from the start** — mine as much as yours. The product has three verbs (store, extract, write) and one honesty mechanism (bench). Everything else is data and prose.
2. **The previous review optimized for completeness; completeness is a liability at implementation time.** R1–R26 remains valid as a *map of the quality space*; this document is the *route* — and the route deliberately visits only what compounds.
3. **The riskiest remaining assumption is prose-first entries.** If deterministic checks someday need heavily structured state (complex timeline math, large knowledge graphs), `data` JSON may strain. Accepted consciously: that day is far away, the failure mode is visible (checks start needing parsing gymnastics), and the migration path (promote one `type` to a table) is cheap *because* everything routes through one store.
4. **The second-riskiest: two critics may be too few.** The Bench exists precisely to convert that from an argument into a measurement.
