# RFC-002: Entry Store

- **Status:** Draft
- **Date:** 2026-07-10
- **Author:** Chief Software Architect
- **Project:** AI Native Creative Workspace (`ai-creative-workspace` / "gorofan") — "나만의 로판AI + 하트픽션"
- **Conforms to:** RFC-001; ADR-002, ADR-003, ADR-004, ADR-008, ADR-011, ADR-014, ADR-018
- **Supersedes:** nothing
- **RFC layer:** Component — the knowledge-model reference the Analyst, Writer, Review, and retrieval RFCs build on

> **Reading order.** RFC-001 is the system-level reference; read it first. This RFC opens the **Store** — the first of RFC-001's four responsibilities (RFC-001 §3.1) — and defines *what an Entry is*, *why the Entry model exists*, *how knowledge is represented and flows*, and *how every runtime component interacts with Entries*. It does **not** define the database, the fields, the indexes, the JSON, the retrieval algorithm, or prompt assembly — each of those is named and deferred to a later RFC.
>
> **Source of truth.** RFC-001 takes precedence over this document, and behind RFC-001 the ADR set (`docs/architecture/adr/`) is authoritative; the two reviews (`docs/design-review-ai-author-os.md`, `docs/architecture-final-minimal.md`) supply rationale only. Where anything here appears to conflict with RFC-001 or an ADR, **RFC-001 / the ADR wins** and this document is in error.
>
> **This RFC is not a database design.** It is the conceptual charter of the Store. Whenever an implementation detail is needed, this document writes **"Defined in RFC-00X"** and stops.

---

## 1. Purpose

This RFC defines the **Entry Store** — the architectural core of the AI Author OS.

RFC-001 establishes that the system is three verbs — **Store, Analyst, Writer** — plus one honesty mechanism, the **Bench** (RFC-001 §2.3, §3). Of those, the Store is the one that *persists*: the Analyst is a stateless transformer, the Writer is a loop runner, the Bench runs out-of-band. All of them are ephemeral in the sense that they hold no long-lived truth of their own. **The Store holds the truth.** It is the single body of creative knowledge that both AI character chat (로판AI) and AI long-form novel writing (하트픽션) draw on (RFC-001 §1.1).

The Store is built from exactly one representation: the **Entry**. This RFC explains:

- **what an Entry is** — the single, prose-first, provenanced, typed unit of creative knowledge;
- **why the Entry model exists** — why one discriminated model replaced a shelf of per-domain tables;
- **how knowledge is represented** — prose-first, with structure only where a deterministic check needs it;
- **how knowledge flows** — from extraction, through review, into canon, out through retrieval, and onward through revision to supersession;
- **how every runtime component interacts with Entries** — who may write, who may only read, and through which gate.

It is the conceptual foundation on which the retrieval RFC, the Living Story Bible RFC, the Analyst RFC, and the Review RFC all rest (see §12).

---

## 2. Why Entry Exists

### 2.1 The problem: an engine and a table per capability

The naive design of a creative-writing system grows one component per capability. A plot library, a dialogue library, an emotion library, a style profile, a character-DNA store, a world-DNA store, and then the ongoing-story ledgers — a fact ledger, a knowledge matrix, a promise ledger, a relationship state, a timeline, a summary store. Built literally, that is on the order of **ten tables, ten editors, and ten retrieval paths** (`architecture-final-minimal.md` §2). RFC-001 names this failure mode directly: *the maintenance debt of "an engine per feature"* is a debt bomb one person cannot carry (RFC-001 §1.2).

Every one of those stores is, on inspection, **the same shape**: a piece of creative knowledge, true within some scope, that exists to be read into a prompt. The differences between "a character's voice," "a world's naming rule," "a promise the story has made," and "who knows what by chapter 40" are differences of *kind*, not of *structure*. Modeling each kind as its own table encodes an accidental difference as a schema difference — and pays for it forever in migrations, editors, and retrieval code.

### 2.2 Why multiple library tables were rejected

The project deliberately rejected the multi-table design (ADR-003). The reasoning, in short:

- **Per-library tables are a debt bomb.** Ten tables become ten editors and ten retrieval paths for what is, structurally, one document model (ADR-003 §4-B; `architecture-final-minimal.md` §2). RFC-001 makes this a hard constraint: *if a per-library table ever appears in a migration, the architecture has failed* (RFC-001 §7.1, §8.5).
- **A new capability must be cheap.** Under the multi-table design, a new kind of knowledge is a migration, a new editor, and new retrieval wiring. Under one model it is a **new `type` string** and a prompt facet — the two cheapest things in software to change (RFC-001 §2.4, §7.1). This is the whole evolution strategy of the system.
- **The EAV alarm was overstated.** The original objection to a single knowledge model was that it would degenerate into an Entity-Attribute-Value "God-Table." On re-examination this was wrong (ADR-003 §1, §4-C): the Entry model is **not** classic EAV. EAV shreds one logical object into many attribute rows and loses type safety and integrity. The Entry model is a **discriminated single-model document** whose primary field is *prose*, with a narrow structured escape hatch used only where a check needs it. The genuine EAV harms do not apply.
- **A knowledge graph / ontology is worse, not better.** The most attractive over-engineering trap in this product category is to model knowledge as a graph or ontology (ADR-003 §4-D). It produces *worse* prompts than well-written provenanced paragraphs, and it adds a second storage engine — breaking the zero-cost, single-database posture. Rejected; a derived read-only projection remains possible far later if ever needed.

### 2.3 Why Entry became the canonical representation

So the Entry is not a compromise; it is the deliberate canonical form. **One model carries all creative knowledge** — character and world knowledge, the craft libraries, and all the accumulating ledgers of an ongoing story — as one uniformly-typed, prose-first body (RFC-001 §3.1; ADR-003 §2). This yields the properties the architecture is organized around:

- **One editor** renders every kind of knowledge, dispatched by its `type` (ADR-003 §5).
- **One retrieval function** serves the entire Store — chat memory, Bible facts, DNA, exemplars, ledgers — uniformly (RFC-001 §3.1; ADR-018 §2).
- **One review gate** governs every write into canon, because every write is a write of the same kind of thing (RFC-001 §2.6).
- **One evolution surface**: growth is `type` strings and prompt files, not services and schemas (RFC-001 §2.4).

The Entry is what lets the system's three verbs stay three verbs. *The model's shape, fields, and DDL are defined in RFC-014; the `type` vocabulary's concrete strings are defined in RFC-002-adjacent component RFCs as noted below — this RFC governs the concept only.*

---

## 3. Entry Philosophy

An Entry is governed by five commitments. These are principles, not fields; **no concrete field is defined here** (fields are Defined in RFC-014).

### 3.1 Prose-first

An Entry's primary substance is **prompt-ready prose**. Creative knowledge is written the way it will be read into a prompt, not normalized into columns, ontologies, or graphs (RFC-001 §2.5; ADR-003 §2). The justification is specific and load-bearing: **the only heavy consumer of Entries is prompt assembly, and language models read well-written prose better than they read schemas.** A provenanced paragraph outperforms an attribute table as prompt material.

Structure is admitted **only where a deterministic check needs it** — for example, a promise's due window, a knowledge-state lookup, a relationship's stage, a summary's granularity level. Where such a check exists, a narrow structured facet may accompany the prose; everywhere else, prose stands alone. Structure never becomes the primary representation, and it is never introduced speculatively (ADR-003 §2). *Which checks consume structure, and the structured facets they read, are Defined in RFC-004 and RFC-014.* Prose-first is consciously the architecture's **riskiest bet** (RFC-001 §2.5), examined honestly in §10.

### 3.2 Provenance

Every Entry carries **where it came from**. Knowledge is never anonymous: an Entry traces to a reference excerpt, an accepted chapter, or a batch of author edits (ADR-003 §2, §6; `architecture-final-minimal.md` §2). Provenance is what makes the knowledge *trustworthy* rather than merely present — it powers the "why does the AI think this?" explanation surface (ADR-003 §6; ADR-014) and it lets conflicting knowledge be adjudicated by source rather than silently overwritten. Provenance is mandatory, not optional metadata.

### 3.3 Confidence

Every Entry carries **how strongly it is believed**. Not all knowledge is equally certain: a fact stated once in one reference is weaker than one corroborated across many. Confidence lets retrieval prefer stronger knowledge when budget is scarce, and lets genuinely-conflicting knowledge coexist rather than forcing a premature merge — both entries exist, and the more-confident one is preferred (ADR-003 §6; `architecture-final-minimal.md` §4). Confidence is a property of the Entry, not a global ranking; *how retrieval weighs it is Defined in RFC-003.*

### 3.4 Review before Canon

An Entry's **status** distinguishes *proposed* knowledge from *canonical* knowledge from *rejected* knowledge. This is the architectural expression of RFC-001's governing gate: **the model reads canon freely but writes to canon only through human review** (RFC-001 §2.6, §8.2). No AI-proposed Entry becomes canon by any path other than a human approving it. A proposed Entry *is* a Review Card (ADR-003 §6; ADR-011); approval is the single write transition into canon. This status is not chrome — it is the only write path from Analyst and Writer proposals into stored truth. *The review interaction, batching, editing, and reversal are Defined in RFC-008.*

### 3.5 Typed Entries

Every Entry declares its **type**, drawn from a **governed, closed vocabulary**. The type is what lets one model behave as many kinds of knowledge: it drives how the single editor renders the Entry, how retrieval weights it, and which checks consume it. Three rules make the type discipline load-bearing (ADR-003 §2, §3):

- **The vocabulary is closed and governed.** Adding a type is a deliberate architectural decision (an ADR/RFC change), never user-supplied data.
- **There is no catch-all type.** A `misc` type would re-open EAV by the back door — an untyped bag of attributes — and is forbidden (ADR-003 §3; RFC-001 §8.6).
- **A new library or ledger is a new type string, never a new table** (RFC-001 §7.1, §8.5).

The conceptual categories the vocabulary spans are described in §5; *the concrete type strings and their governance live with the model definition — Defined in RFC-014, with category-specific detail in RFC-004 (ledgers), RFC-011 (relationship), and RFC-012 (character/world).*

---

## 4. Entry Lifecycle

An Entry is not a static row; it moves through a lifecycle. This section is **high-level only** — it names the stages and the transitions between them, not the mechanics of any stage (each stage's mechanics are Defined in the RFC noted).

```
   creation
      │
      ▼
   proposal   ── an Entry is proposed, not yet trusted
      │
      ▼
   review     ── a human accepts / edits / rejects        (Defined in RFC-008)
      │
      ▼
   canon      ── approved; now part of the source of truth
      │
      ▼
   retrieval  ── read into prompts on demand              (Defined in RFC-003)
      │
      ▼
   revision   ── new knowledge refines or corrects it
      │
      ▼
   superseded ── replaced by a newer Entry; kept, not deleted
      │
      ▼
   archive    ── retained for provenance and history
```

- **Creation.** An Entry comes into being when the Analyst extracts candidate knowledge from text, or the Writer's ingestion step emits newly-observed facts (RFC-001 §3.2, §3.3). Creation never writes canon directly.
- **Proposal.** A newly-created Entry enters the world as *proposed* — knowledge the system believes but has not been authorized to trust. A proposed Entry is a Review Card (§3.4).
- **Review.** A human accepts, edits, or rejects the proposal. This is the single human-gated write path (RFC-001 §2.6). *Defined in RFC-008.*
- **Canon.** An accepted Entry becomes canonical and is immediately available to future retrieval and future drafts (RFC-001 §5.7).
- **Retrieval.** Canonical Entries are read into prompts on demand by the one retrieval function, selected by relevance and budget (§8). Retrieval is read-only and non-mutating. *Defined in RFC-003.*
- **Revision.** As the story or the author's understanding evolves, knowledge changes. Revision produces a *new* Entry rather than mutating canon in place, preserving history and provenance.
- **Superseded.** When a newer Entry replaces an older one, the older is marked superseded — **retained, not deleted.** Supersession keeps the historical record intact and the provenance chain unbroken. *The supersession relationship and its retrieval consequences are Defined in RFC-004 and RFC-014.*
- **Archive.** Superseded and rejected Entries are retained for provenance, audit, and the "why did the AI once think this?" history. The Store forgets nothing silently.

Not every Entry traverses every stage: reference-derived DNA may enter directly as canon on import (its provenance is the reference and the human curates the collection), while story-derived ledger Entries always pass through proposal and review (`architecture-final-minimal.md` §4). *Which categories enter as canon vs. proposed is Defined in RFC-005.* The invariant that holds for all of them: **canon is only ever written through review, and knowledge is superseded rather than destroyed.**

---

## 5. Entry Categories

The single Entry model spans several **conceptual categories** of knowledge. These are *kinds of responsibility*, not schemas — this section defines **no fields and no concrete type strings** (those are Defined in RFC-014, RFC-004, RFC-011, RFC-012). Each category is a region of the governed `type` vocabulary (§3.5).

| Category | Responsibility — what this knowledge is for |
|---|---|
| **Character** | Who a figure *is* — their core identity, their voice, and concrete exemplars of how they speak and act. The material both chat and narration draw on to keep a character consistently themselves. *Organization Defined in RFC-012.* |
| **World** | The rules, naming conventions, places, and lore that make the setting coherent — the constraints a draft must not violate. *Organization Defined in RFC-012.* |
| **Fact** | A concrete, established truth of the ongoing story ("this happened; this is so"), timestamped to the point in the story it became true. The raw material of continuity. *Defined in RFC-004.* |
| **Knowledge** | Who knows what, and when — the state that prevents a character from acting on information they could not possess. The guard against the "everyone is omniscient by chapter 40" failure. *Defined in RFC-004.* |
| **Promise** | A commitment the story has made to the reader — a planted hook, a foreshadowed payoff, an open thread — carrying the sense of when it comes due. The guard against unpaid setups. *Defined in RFC-004.* |
| **Relationship** | The evolving state between characters — where a pairing stands and how it is moving. *Defined in RFC-011.* |
| **Emotion** | The repertoire of emotional beats and how they are rendered — the palette a scene draws on for affect. |
| **Style** | How prose should read — the craft signals of voice, cadence, and surface. The material the style pass applies. |
| **Preference** | The author's own distilled tastes and corrections, learned transparently from their edits, injected into future prompts. *Capture and distillation Defined in RFC-009.* |
| **Summary** | Compressed accounts of what has happened, at multiple granularities (scene / chapter / arc / story-so-far), so long-form context fits a budget. *Multi-level design Defined in RFC-003 and RFC-004.* |

Two further notes on the vocabulary's shape:

- **The list is illustrative of the categories, not exhaustive of the types.** Additional craft categories (for example, plot tropes) and a general annotation category exist within the same governed vocabulary. What matters is that each is a *type region*, absorbed by the one model, the one editor, and the one retrieval path — never a new table (§9).
- **Categories are responsibilities, not boundaries between stores.** All categories live in one Entry space. The category tells the editor how to render, retrieval how to weight, and the Analyst what to look for — it does not fragment the Store.

---

## 6. Store Responsibilities

The Store's ownership is exclusive, and its non-ownership is as binding as its ownership (RFC-001 §4). Ambiguity here is what re-creates the engine sprawl the architecture exists to prevent.

### 6.1 What the Store owns

- **The one knowledge model** — the Entry, in all its categories — and **all persisted creative knowledge** (RFC-001 §4.1). The Store *is* the Story Bible, the character/world knowledge, and every story ledger, as one uniformly-typed body.
- **The governed, closed `type` vocabulary** as a curated set (RFC-001 §4.1; §3.5 here). The Store is the authority on what kinds of knowledge exist.
- **The status of every Entry** — *proposed*, *canon*, or *rejected* — and the supersession chain that records how knowledge evolved (RFC-001 §4.1; §4 here).
- **Provenance and confidence** as first-class, mandatory properties of every Entry (§3.2, §3.3).
- **The single retrieval capability** — the one function that answers *"given this situation and this budget, what knowledge is relevant right now?"* (RFC-001 §3.1). *Its mechanics are Defined in RFC-003.*

### 6.2 What the Store explicitly does NOT own

- **Extraction.** The Store never turns text into knowledge; that is the Analyst (RFC-001 §3.2, §4.1). The Store *receives* candidate knowledge; it does not *produce* it.
- **Generation.** The Store never writes prose for the reader; that is the Writer (RFC-001 §3.3, §4.1).
- **Quality judgment.** The Store never scores or critiques; that is the Bench and the Writer's checks (RFC-001 §4.1).
- **The promotion decision.** The Store never decides on its own that *proposed* should become *canon*; that is human review (RFC-001 §2.6, §4.1). The Store *records* the decision; it does not *make* it.
- **A monolithic facade.** The Store exposes **no God-object "Store" class.** It is a data model, plus a small retrieval function, plus typed access — not a subsystem with a thousand methods (RFC-001 §4.1; ADR-002). This non-ownership is what keeps the Store ~100 lines of retrieval over one model rather than an engine (ADR-018 §2).

---

## 7. Store Interfaces

This section describes the Store's interfaces **conceptually**. It defines **no APIs, no method signatures, no call shapes** — those are Defined in RFC-003 (retrieval) and RFC-014 (persistence). The point here is the *character* of the Store's boundary: what it accepts, what it emits, and what it refuses to do.

- **The Store receives knowledge — as proposals, through a gate.** Knowledge enters only as candidate Entries emitted by the Analyst or the Writer's ingestion step, and it crosses into canon only when a human approves it (§3.4; RFC-001 §2.6). The Store never accepts a silent, unreviewed write to canon.
- **The Store retrieves knowledge — read-only, budgeted.** Any component may *read* the Store. Retrieval answers one question — *what knowledge is relevant to this situation, within this budget?* — and returns Entries without mutating them (§8; RFC-001 §3.1). Reading canon is unrestricted; this is the "read freely" half of the gate (RFC-001 §8.7).
- **The Store never generates knowledge.** It holds and returns; it does not invent, extract, summarize, or infer. Every Entry it contains was put there by an upstream producer and approved by a human. A Store that started generating its own knowledge would have absorbed the Analyst and broken the three-verb separation (RFC-001 §2.3).
- **The Store records decisions; it does not make them.** Promotion, rejection, and supersession are transitions the Store *stores*; the *authority* for each lives with the human (promotion/rejection) or the producing pass (supersession proposal). The Store is the ledger of truth, not the judge of it.

These four sentences are the whole contract. Everything a component may do with the Store reduces to *propose into it through review*, or *read from it freely* — and nothing else.

---

## 8. Retrieval Philosophy

Retrieval is the Store's outward-facing capability — the one question it answers for the rest of the system (RFC-001 §3.1). This section states the **philosophy only**; it defines **no algorithm, no ranking formula, no budgeting math, no keyword-vs-embedding mechanism** — all of those are Defined in RFC-003.

- **Retrieval, not dumping.** The Store does not hand the Writer the whole Bible and let the prompt sort it out. Past roughly chapter 50 the Bible exceeds any context window; the value is in *selection* — putting the *right* knowledge in front of the model, not all of it (ADR-018 §2). Retrieval is the act of choosing relevance.
- **Relevance is situational.** What is relevant is a function of the situation being written — which characters are on stage, where the scene is set, what beat it hits, what promises are coming due, what each character currently knows. Retrieval selects against the situation, not against a fixed priority list. *The situational inputs are Defined in RFC-003.*
- **Ranking blends kind, relevance, and recency.** Conceptually, an Entry's pull toward the prompt combines *what kind of knowledge it is* (some kinds matter more for a given task), *how relevant it is* to the situation, and *how recent* it is — with confidence and status as guards (§3.3, §3.4). This is a philosophy of blended ranking; **the concrete weighting is Defined in RFC-003** and is expected to be tuned on the Bench, not fixed here (ADR-018 §6).
- **Context budgeting is a first-class constraint.** Retrieval always works against a token budget: it selects the most relevant knowledge that *fits*, and stops. Budgeting is not an afterthought or a truncation step — it is the reason retrieval must rank at all. Multi-granularity summaries exist precisely so that long-range context can be included at a coarseness the budget can afford (ADR-018 §2, §4; §5 "Summary" here).
- **One retrieval path, keyword-first, embeddings deferred.** There is exactly one retrieval function over the whole Store; there is no parallel lorebook scanner and no second RAG subsystem (RFC-001 §3.1; ADR-018 §2, §4-B). It begins with keyword-first ranking and adds embedding-based retrieval **only** when keyword recall demonstrably misses, measured on the Bench — behind the same single seam, never as a competing system (ADR-018 §2, §6). *The seam and its trigger are Defined in RFC-003.*

---

## 9. Evolution Strategy

The Entry model exists so that the system can evolve for years by changing the two cheapest things in software — **typed data and prompt files** — rather than services and schemas (RFC-001 §2.4, §7). This section states how the Store grows.

### 9.1 A new kind of knowledge is a new `type` string

When the author wants a new library, a new ledger, or a new craft signal, the answer is a **new `type` string** in the governed vocabulary — absorbed automatically by the one model, the one editor, the one retrieval function, and the one review queue (RFC-001 §7.1; ADR-003 §3). It is **never** a new table, a new editor, or a new service. RFC-001 makes the failure condition explicit: *if a per-library table ever appears in a migration, the architecture has failed* (RFC-001 §7.1, §8.5).

Adding a type is a **governed** act, not user data: it is a deliberate ADR/RFC decision, precisely so the vocabulary stays closed and coherent and never degrades into an untyped bag (§3.5; ADR-003 §3). *The governance process for the vocabulary is Defined in RFC-014.*

### 9.2 New analytical depth is a new prompt facet, not new storage

A richer understanding of references, or of the author's preferences, is a **new Analyst facet** — a prompt file producing the same shape of proposals into the same review queue and the same Store (RFC-001 §7.2, §7.3). New craft is a prompt stage or facet; it does not touch the Store's structure. The Store's storage surface and the system's analytical surface evolve independently — which is the point.

### 9.3 Why schema evolution should be minimized

The Store's structure is deliberately the *stillest* part of the system. The loop runner, the retrieval function, and the Entry model are "written once" code (RFC-001 §2.4); the constant change happens in `prompts/` and in `type` strings. Minimizing schema evolution is not conservatism for its own sake — it is what keeps a single maintainer able to own the system for years (RFC-001 §1.1). Every migration is a cost a one-person team pays disproportionately; the Entry model's whole value is that most growth costs *no migration at all* (ADR-003 §5).

### 9.4 The one sanctioned structural escape valve

There is exactly one legitimate way the Store's schema grows: **promote a `type` to its own dedicated model** when — and only when — that type's deterministic checks start doing "parsing gymnastics" against prose-plus-narrow-structure (RFC-001 §8.10; ADR-003 §6). This is examined as a risk in §10.3. It is cheap *precisely because* everything routes through one Store, and it is the **only** sanctioned place a new table is added later. Speculative promotion — adding a table before the pressure is real and visible — is forbidden (ADR-003 §6). *The migration path for a promotion is Defined in RFC-014.*

---

## 10. Architectural Risks

This section is deliberately honest rather than defensive. The Entry model is a strong bet, and strong bets have failure modes. Three are worth naming plainly.

### 10.1 Can Entry become a God Object?

**Yes — this is the model's central risk.** One model carrying all knowledge is, by construction, a concentration point: a single bug, a single bad migration, or a single mis-designed transition affects *everything* the system knows (ADR-003 §5, "concentrated risk"). The multi-table design distributed this risk; the Entry model concentrates it.

The architecture accepts the concentration but guards against the *God-object* form of it in two specific ways:

- **The Store is a data model plus a small function, not a facade class.** RFC-001 forbids a monolithic "Store" object with unbounded responsibility (RFC-001 §4.1; §6.2 here). The concentration is in the *data's shape*, which is simple and uniform, not in a *class's behavior*, which is where God-objects actually rot. A uniform prose-first document with provenance and status is a small surface; a class that grows a method per capability is not — and the latter is explicitly disallowed.
- **The category responsibilities stay conceptual, not procedural.** Categories (§5) tell the editor how to render and retrieval how to weight; they do not accrete category-specific *code paths* inside the Store. When category-specific behavior is genuinely needed, it lives in the consumer (an Analyst facet, a Writer check), not in the Store. The moment the Store itself grows large per-`type` branches is the moment to consider §10.3.

The honest position: the Entry model trades *distributed* risk for *concentrated but simple* risk, on the bet that one simple thing is easier for one maintainer to keep correct than ten interacting things. That bet can be wrong for a specific `type`; §10.3 is the exit.

### 10.2 Can too many Entry types create chaos?

**Yes — `type` proliferation is a real failure mode**, and the architecture names it (ADR-003 §5, "future risks: `type` vocabulary creep"). If the vocabulary grows unboundedly, the "one model, many types" clarity degrades into an ad-hoc pile — the very disorder the closed vocabulary exists to prevent.

The guards are procedural, and their strength depends on discipline:

- **The vocabulary is closed and governed.** A new type is a deliberate ADR/RFC decision, never user-supplied data (§3.5; ADR-003 §3). Growth is intentional, reviewed, and documented.
- **There is no `misc` catch-all.** The single most dangerous crack — an untyped bag that quietly re-opens EAV — is forbidden outright (§3.5; RFC-001 §8.6; ADR-003 §3).
- **Categories bound the sprawl.** New types should fall within the existing conceptual categories (§5); a type that fits no category is a signal to reconsider, not to invent a category casually.

The honest caveat: these guards are *governance*, not *mechanism* — nothing in the code prevents a careless future ADR from adding a redundant type. The defense is that adding a type is friction-full enough (an ADR/RFC change) to force deliberation, and cheap types are the *feature* the whole model is built to deliver. The risk is not that types are cheap; it is that cheapness without governance becomes chaos. The governance is therefore not optional chrome.

### 10.3 When should an Entry type be promoted into its own dedicated model?

The prose-first, one-model bet is consciously the architecture's **riskiest** (RFC-001 §2.5; `architecture-final-minimal.md` §9). It has a specific, *visible* failure mode and a specific, sanctioned exit (ADR-003 §6; RFC-001 §8.10):

> **Promote a `type` to its own dedicated model when that type's deterministic checks begin doing "parsing gymnastics"** against prose-plus-narrow-structure — heavy timeline arithmetic, large who-knows-what graph traversal, or structured state that the `data` escape hatch strains to hold.

The discipline around this exit is what keeps it honest:

- **The trigger must be real and visible, not anticipated.** Promotion happens when checks *demonstrably* strain, not when someone predicts they might. Speculative promotion is forbidden (ADR-003 §6). The failure mode announces itself — checks start parsing rather than reading — which is exactly why the bet is acceptable: the day it's wrong, you can *see* it.
- **Promotion is cheap precisely because everything routes through one Store.** Because there is one model, one retrieval path, and one review queue, extracting a single strained `type` into its own dedicated model is a bounded, local change — not a rewrite (RFC-001 §8.10; ADR-003 §6). The concentration that §10.1 flags as a risk is here a *benefit*: the escape valve is cheap because the core is unified.
- **This is the *only* sanctioned way the Store's schema grows a table later** (RFC-001 §8.10; §9.4 here). It is a pressure valve, not a habit. Candidate types to watch are the ones whose knowledge is most structural rather than prose-like — the promise, knowledge, and timeline-bearing ledgers (`architecture-final-minimal.md` §9; ADR-003 §5). *The migration path is Defined in RFC-014.*

The goal of stating all three risks openly is architectural honesty: the Entry model is the right default for this system and this maintainer, *and* it has a concentration risk, a proliferation risk, and a prose-first risk — each with a named guard and, where structure eventually wins, a named exit.

---

## 11. Out of Scope

This RFC deliberately defines **none** of the following. Each is named so that no later reader mistakes this document for defining it, and each belongs to a later RFC:

- **The database schema** — tables, columns, keys, DDL, migrations. *Defined in RFC-014.*
- **Entry fields** — the concrete field list, the `data` structured escape hatch's shape, `superseded_by`, `created_at_chapter`, and every other attribute. *Defined in RFC-014.*
- **Indexes** — any indexing, query-performance, or storage-layout decision. *Defined in RFC-014.*
- **JSON structures** — the shape of any structured facet a check consumes (promise due windows, knowledge state, relationship stage, summary level). *Defined in RFC-004 and RFC-014.*
- **Retrieval algorithms** — ranking formulas, budgeting math, recency/relevance/type-weight computation, keyword mechanics, the embedding seam. *Defined in RFC-003.*
- **Prompt assembly** — how retrieved Entries are composed into a prompt, block/budget assembly, injection order. *Defined in RFC-007.*
- **The concrete `type` vocabulary strings** and their per-category detail — the exact discriminator values and their governance mechanics. *Defined in RFC-014, with category detail in RFC-004, RFC-011, RFC-012.*
- **The Review Card UX** — the interaction, batching, editing, and reversal of proposals. *Defined in RFC-008.*
- **The ledger internals** — the fact ledger, knowledge matrix, promise ledger, contradiction gate, and continuity loop that operate over `fact` / `knowledge` / `promise` / `summary` Entries. *Defined in RFC-004.*
- **Learning capture and distillation** — how author edits become `preference` Entries. *Defined in RFC-009.*

Wherever this document needed such a detail, it wrote **"Defined in RFC-00X"** and stopped, by rule.

---

## 12. Dependencies

RFC-002 depends on **RFC-001** and must conform to its principles, boundaries, and constraints; where they conflict, RFC-001 governs (RFC-001 §10). The following future RFCs **build on** the Entry Store defined here — they may define the details this RFC defers, but none may override the Entry concept, the review gate, or the closed typed vocabulary established above:

| Future RFC | Topic | Builds on the Entry Store for |
|---|---|---|
| **RFC-003** | Retrieval Strategy | The single retrieval function and its philosophy (§8); ranks and budgets over the one Entry space. |
| **RFC-004** | Living Story Bible & Continuity Loop | The `fact` / `knowledge` / `promise` / `summary` categories (§5) and their structured facets; the ledger internals over Entries. |
| **RFC-005** | Analyst & Reference Analysis | The Store as the sink for proposals; which categories enter as canon vs. proposed (§4); provenance/confidence tagging. |
| **RFC-006** | Writer Pipeline & Scene/Episode Unit | Reading the Store via retrieval; emitting ingestion proposals back into the review gate (§7). |
| **RFC-007** | Prompt Architecture | Assembling retrieved prose-first Entries into prompts (§3.1, §8). |
| **RFC-008** | Review Card UX | The *proposed → canon / rejected* transition and the human-gated write path (§3.4, §4). |
| **RFC-009** | Learning Capture & Distillation | The `preference` category (§5); distilled edits as reviewable Entries. |
| **RFC-011** | Relationship System | The `relationship` category as Entries plus a stage and a check, not an engine. |
| **RFC-012** | Character / World DNA Organization | The `character.*` / `world.*` categories (§5); five-layer organization as prompt/render order, not schema. |
| **RFC-014** | Persistence & DB-Swap Strategy | The Entry model's DDL, fields, indexes, the `type` vocabulary strings, and the promote-a-type migration path (§9.4, §10.3). |

> The RFC numbering above follows RFC-001 §10's planned series; only RFC-001 and this document are authoritative until each successor is written. Successor RFCs own the details this RFC defers, but their **dependence on the Entry concept, the review-before-canon gate, the prose-first principle, and the closed typed vocabulary is fixed**. Where a successor and this RFC appear to conflict on those, this RFC — and behind it RFC-001 and the ADR set — governs.

---

## Appendix A — Traceability

| RFC-002 Section | Primary sources |
|---|---|
| §1 Purpose | RFC-001 §3.1; ADR-003 |
| §2 Why Entry Exists | ADR-003 §1–§4; RFC-001 §1.2, §2.5, §7.1, §8.5–§8.6; `architecture-final-minimal.md` §2 |
| §3 Entry Philosophy | RFC-001 §2.5, §2.6, §8.6; ADR-003 §2, §3, §6; ADR-011; ADR-014 |
| §4 Entry Lifecycle | RFC-001 §2.6, §5; ADR-003 §6; ADR-011; `architecture-final-minimal.md` §4 |
| §5 Entry Categories | ADR-003 §2, §3; `architecture-final-minimal.md` §2; RFC-001 §3.1 |
| §6 Store Responsibilities | RFC-001 §3.1, §4.1; ADR-002; ADR-018 §2 |
| §7 Store Interfaces | RFC-001 §2.3, §2.6, §3.1, §8.7 |
| §8 Retrieval Philosophy | RFC-001 §3.1; ADR-018 §2, §4, §6 |
| §9 Evolution Strategy | RFC-001 §2.4, §7, §8.5, §8.10; ADR-003 §3, §5, §6 |
| §10 Architectural Risks | ADR-003 §5, §6; RFC-001 §2.5, §4.1, §8.10; `architecture-final-minimal.md` §9 |
| §11 Out of Scope | RFC-001 §9 (RFC boundary conventions) |
| §12 Dependencies | RFC-001 §10 |

*End of RFC-002.*
