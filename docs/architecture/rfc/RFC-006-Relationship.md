# RFC-006: Relationship

- **Status:** Draft
- **Date:** 2026-07-10
- **Author:** Chief Software Architect
- **Project:** AI Native Creative Workspace (`ai-creative-workspace` / "gorofan") — "나만의 로판AI + 하트픽션"
- **Conforms to:** RFC-001, RFC-002, RFC-008, RFC-004, RFC-005; ADR-006, ADR-003, ADR-004, ADR-005, ADR-020
- **Supersedes:** nothing
- **RFC layer:** Component — the relationship-state reference the continuity, Writer-planning, character-chat, and retrieval RFCs build on

> **Reading order.** RFC-001 is the system-level reference; RFC-002 defines the Entry Store; RFC-008 the Analyst; RFC-004 the Writer; RFC-005 the Story Bible. Read all five first. This RFC defines the **Relationship** model — how characters relate to one another across the lifetime of a work — and explains *why it exists*, *what it owns and does not own*, *how it integrates with the Story Bible*, and *how it supports both novel generation and character chat*. It does **not** define relationship attributes, dialogue rules, retrieval, prompts, or algorithms — each is named and deferred.
>
> **Source of truth.** The RFC documents take precedence over this one, in order (RFC-001, then RFC-002, RFC-008, RFC-004, RFC-005); behind them the ADR set (`docs/architecture/adr/`) is authoritative, and the two reviews (`docs/design-review-ai-author-os.md`, `docs/architecture-final-minimal.md`) supply rationale only. Where anything here appears to conflict with an RFC or an ADR, **those win** and this document is in error.
>
> **This RFC is implementation-neutral.** It is the conceptual charter of the Relationship model. Whenever an implementation detail is needed, this document writes **"Defined in the corresponding RFC"** (naming the topic) and stops. It defines no attributes and no schemas.

---

## 1. Purpose

This RFC defines the **Relationship** model — the representation of **how characters relate to one another throughout the lifetime of a work**.

For a romance-forward product — 로판 (romance-fantasy) and Heart-Fiction — the *relationship* is not a detail of the story; it is very often *the* story. Whether a pairing moves from wary to trusting to devoted, and whether that movement feels *earned* rather than random, is the core loop a reader consumes (ADR-006 §1). The system must therefore hold relationship state as something explicit, retrievable, plannable, and checkable — not as an accident of whatever the model happened to write last chapter.

Crucially, the Relationship model is **not a new subsystem**. A relationship is a kind of canonical, work-scoped knowledge — a `relationship` Entry in the Store (RFC-002), part of the Living Story Bible (RFC-005 §3), planned for by a Writer stage and checked by a Writer assertion (ADR-006 §2). This RFC explains:

- **why Relationship exists** — why relationship state must be represented explicitly rather than left to LLM memory;
- **what it owns** — the evolving state between characters, as canonical knowledge;
- **what it explicitly does NOT own** — dialogue generation, extraction, planning, prompt execution, human editing;
- **how it integrates with the Story Bible** — as living, human-gated, work-scoped canon (RFC-005);
- **how it supports both novel generation and character chat** — as shared state both consume, neither owns.

It does **not** define the relationship's attributes, the stage ladder's structure, the planning stage, or the check (§13).

---

## 2. Why Relationship Exists

### 2.1 Why relationship state must be represented explicitly

Left to its own memory, an LLM does not hold a relationship steady. Across a long serialization it **oscillates**: a pairing runs cold, then warm, then cold again, with no direction and no cause — because each draft re-derives the relationship from whatever context happens to be in the window, not from a durable record of where the pairing actually stands (ADR-006 §1, §4-D). Both project reviews name this as a core failure mode, and it is fatal for romance specifically: readers consume *progression*, and a relationship that lurches at random reads as broken (ADR-006 §1, §4-D).

Relationship state is represented **explicitly** so that this cannot happen. When the current stage of a pairing, and the event that last moved it, are recorded as canonical knowledge, three things become possible that are impossible with implicit memory (ADR-006 §2):

- the state can be **retrieved** into every draft that involves the pair, so the model writes *from* the relationship rather than guessing it;
- progression can be **planned** across an arc — stage transitions placed deliberately, so movement is *monotonic-with-intent* rather than oscillating (ADR-006 §2, §4-D);
- a draft that moves a pairing **backward without an intended trigger** can be *caught* by a check and revised (ADR-006 §3).

This is the same principle the Story Bible rests on: long-form coherence is a *memory* problem, and the answer is durable, checkable, retrievable knowledge — not a better prompt (RFC-005 §2.1). Relationship state is the memory that keeps a romance a romance.

### 2.2 Why it is knowledge, not a subsystem

The explicit representation could have been a dedicated relationship-graph subsystem — a typed-edge store, a traversal API, an interactive editor. Both reviews independently reject this: a relationship is *"three things — an entry type, two lines in the retrieval list, and one check … rows and prompt clauses,"* not a module (ADR-006 §1; `architecture-final-minimal.md` §3). A graph database would be a second storage engine, breaking the zero-cost, single-database posture for no benefit at personal cast sizes (ADR-006 §4-C; ADR-003 §4-D). So Relationship exists as **canonical knowledge in the one Store**, riding the Entry model, the one retrieval function, and the Writer's stages — never as a subsystem of its own (ADR-006 §2, §5; RFC-001 §8.5).

---

## 3. Relationship Responsibilities

The Relationship model's ownership is the **evolving state between characters**, held as canonical knowledge. This section defines *responsibilities* — high-level, **no attributes, no schemas** (those are Defined in the corresponding RFC). Each responsibility below is a *facet of relationship state*, carried within `relationship` Entries in the Store (RFC-002; ADR-006 §2) — not a field this RFC defines.

- **Relationship stage.** Where a pairing currently stands on its progression — the single most load-bearing piece of state, because it is what makes progression plannable and regression checkable (ADR-006 §2). *The stage ladder is extracted from references and Defined in the corresponding RFCs.*
- **Trust.** How much the characters rely on and are open with one another — a dimension that moves as the story earns or breaks it.
- **Affinity.** How warm the pairing is — attraction, fondness, the emotional pull that romance turns on.
- **Conflict.** The live tension between the characters — the friction, opposition, or wound that gives the relationship somewhere to go.
- **Shared history.** What the characters have been through together — the accumulated events that make the present state *earned* rather than asserted.
- **Interaction context.** The current circumstances shaping how the pair behaves together — the standing situation a scene or a chat turn should honor.

Across all of these, one responsibility is constant: the model holds relationship state **canonically, provenanced, and human-gated**, and it records *how the state last moved* — the transition and its cause — not merely a static value (ADR-006 §2). The Relationship model is the *keeper* of the pairing's evolving truth; it does not generate the prose, plan the arc, or run the chat that use it (§4).

---

## 4. What Relationship Does NOT Own

The Relationship model's non-ownership is as binding as its ownership; ambiguity here re-creates the engine sprawl the architecture exists to prevent (RFC-001 §4). Relationship is **state held**, not work done.

- **Dialogue generation.** Relationship state does not write dialogue. Producing the lines two characters say is the **Writer's** job (in novels) and the chat engine's (in character chat) (RFC-004 §3). Relationship supplies the state the dialogue should reflect; it does not author the dialogue. *Dialogue rules are Defined in the corresponding RFC.*
- **Knowledge extraction.** Relationship state does not extract itself from prose. New relationship movement is inferred by the **Analyst** on chapter acceptance and emitted as proposals (RFC-008 §3; ADR-006 §1). The model *receives* proposed relationship knowledge; it does not produce it.
- **Narrative planning.** Relationship state does not plan the arc. Placing scenes to justify each stage transition is a **Writer planning stage** that *reads* relationship state — not a Relationship-owned planner (ADR-006 §2; RFC-004 §3). The reviews are explicit: the "Relationship Planner" is deleted as a component; planning is a Writer stage over relationship Entries (`architecture-final-minimal.md` §3, §6).
- **Prompt execution.** Relationship state does not assemble or run prompts, and it does not own the retrieval that selects it for a prompt — that single capability belongs to the **Store** (RFC-002). It is *read from*; it does not do the reading. *Retrieval and prompt assembly are Defined in the corresponding RFCs.*
- **Human editing.** Relationship state does not own the interface through which a human reviews or edits it. Approving proposed relationship movement is the Review Card queue; browsing or visualizing it is a Bible surface — both defined elsewhere (ADR-011; ADR-006 §4; ADR-014). The model owns the *state and its status*, not the screen. *The review and visualization surfaces are Defined in the corresponding RFCs.*
- **The relationship check.** Catching an unintended regression is a **Writer `qa` assertion**, not a Relationship feature (ADR-006 §3; RFC-004 §7). The model provides the ground truth; the Writer runs the check against it. *Validation is Defined in the corresponding RFC.*
- **Visualization.** Any relationship graph or visual overview is a **deferred, read-only projection** computed on demand from `relationship` Entries — never a second source of truth and never the canonical model (ADR-006 §4, §6). The model owns the canon; a projection is disposable.

The one-way discipline that governs the whole system governs Relationship too: **the model reads relationship canon freely and writes it only through review** (RFC-001 §2.6; ADR-004 §5; ADR-006 §1).

---

## 5. Relationship Lifecycle

Relationship state moves through a lifecycle across the life of a work. This section names the stages **conceptually** — no algorithms, no attributes.

```
   formation    ── a pairing first appears; its initial state is established
      │
      ▼
   growth       ── the relationship deepens as the story earns it
      │             (movement is monotonic-with-intent, not oscillating — §2.1)
      ▼
   conflict     ── tension, rupture, or a wound gives the pairing somewhere to go
      │
      ▼
   transition   ── the pairing moves to a new stage, justified by an event
      │             (the transition and its cause are recorded — §3)
      ▼
   canon        ── the movement, once reviewed and approved, becomes canonical
      │             (proposal → review → canon — RFC-005 §5)
      ▼
   revision     ── later knowledge refines or supersedes the state
                    (superseded, not deleted — RFC-002)
```

- **Formation.** A pairing enters the work and its initial state is established — often extracted from references (a stage ladder, a starting dynamic) or set as the story opens (ADR-006 §1–§2).
- **Growth / Conflict.** The relationship deepens and strains as the narrative earns each movement. This is where *monotonic-with-intent* matters: progression has direction, and conflict is a step along an arc, not random noise (ADR-006 §2, §4-D).
- **Transition.** The pairing moves to a new stage, and the model records **both the new stage and the event that caused the move** — because a transition without a cause is exactly the oscillation the model exists to prevent (§2.1; ADR-006 §2).
- **Canon.** Relationship movement inferred from an accepted chapter is *proposed*, reviewed by a human, and only then canonical — the same gate all Bible knowledge passes (RFC-005 §5; ADR-006 §1). The model never writes relationship canon silently.
- **Revision.** As the story develops (or retcons), relationship state is refined or superseded — movement *within* the Entry model, preserving history rather than erasing it (RFC-002). *Supersession mechanics are Defined in the corresponding RFC.*

One invariant holds across the lifecycle: relationship state is **living and gated** — it evolves continuously, but every increment to canon passes through human review (RFC-005 §5, §7).

---

## 6. Relationship Philosophy

The Relationship model rests on one conceptual commitment: **a relationship is living narrative state, not a static character attribute.**

- **A relationship is between characters, and it moves.** A character's core identity and voice are relatively stable — who they *are*. A relationship is *what is happening between two of them*, and its whole nature is to change over the arc (ADR-006 §2). Modeling it as a fixed attribute ("they are friends") would freeze the one thing that must move, and lose the transition history that makes progression legible.
- **Static attributes cannot be planned, checked, or progressed.** If a relationship were buried in a character's free text, it could not be retrieved by stage, checked for regression, or planned across an arc without re-parsing prose (ADR-006 §4-B). It would be too lossy to support the romance loop — which is precisely why the reviews reject the free-text approach (ADR-006 §4-B). Living, typed relationship state is what makes the pairing a *tracked trajectory* rather than a label.
- **Living state is what "feels authored."** The difference between a relationship that oscillates and one that progresses with intent is the difference between a generator and an authored serial (ADR-006 §2; RFC-005 §2.2). Relationship-as-living-state is the mechanism that delivers the monotonic-with-intent progression readers consume.
- **Living, but never rotting.** Like all Bible knowledge, relationship state stays current *safely* because its growth is gated: continuous evolution, every increment reviewed (RFC-005 §5, §7). Living does not mean unattended.

The philosophy in one line: **a relationship is a trajectory the work tracks and earns — not a badge a character wears.**

---

## 7. Relationship as Shared Narrative State

This section is the architecturally load-bearing one: **a relationship belongs neither to a Character nor to the Writer — it is shared narrative state for the entire work.** Getting this ownership wrong is how the model would fracture.

- **It cannot belong to a Character.** A relationship is *between* two characters; it is not a property of either one. If it lived inside Character A's knowledge, it would be invisible or duplicated in Character B's — and the two copies would drift. A pairing has *one* state, and that state is not owned by either participant. This is exactly why relationship state is not folded into character DNA: a character owns *who they are*; the pairing's trajectory is a separate, shared thing (ADR-006 §2, §4-B). *Character/World DNA organization is Defined in the corresponding RFC.*
- **It cannot belong to the Writer.** The Writer is an orchestration layer that *consumes* knowledge and owns none of it (RFC-004 §4, §6). If relationship state lived inside the Writer, it would be trapped there — unavailable to character chat, unreviewable through the Bible's gate, and lost the moment a generation completed (which is working knowledge, not canon — RFC-005 §6). The Writer plans against relationship state and checks against it, but it must not *hold* it.
- **Therefore it is shared state in the Store, at work scope.** A relationship is canonical, work-scoped knowledge — a `relationship` Entry in the one Store, part of the Living Story Bible (RFC-002; RFC-005 §3; ADR-006 §2). This placement is what lets *every* consumer see the *same* state: the Writer draws on it to draft and plan, character chat draws on it to stay in character, the Analyst proposes movement into it, and the human reviews it — all against one shared truth, with no copies to reconcile (§8, §9, §10).
- **Why the distinction matters.** Shared narrative state is the reason the product's two capabilities — novel writing and character chat — draw on *one* body of relationship truth rather than two divergent ones (RFC-001 §1.1). It is the same argument that made the Entry model canonical: knowledge that several components use belongs in the shared Store, not inside any one component (RFC-002). A relationship is the clearest case of knowledge that is nobody's private property and everybody's shared context.

The distinction in one line: **a character owns who they are; the Writer orchestrates; the *pairing's trajectory* is shared canon the whole work reads from and proposes to.**

---

## 8. Relationship and Story Bible

Relationship state is part of the Living Story Bible — it is one of the kinds of canonical, work-scoped knowledge the Bible keeps (RFC-005 §3).

- **Relationship is Bible canon, not a parallel store.** A `relationship` Entry at work scope, once approved, is exactly the canonical knowledge the Story Bible comprises (RFC-005 §3, §8; ADR-006 §2). It rides the same Entry model, the same provenance and status, the same retrieval, and the same review gate as every other kind of Bible knowledge — no separate relationship store, no relationship-specific table (RFC-005 §8; RFC-002). If a relationship ledger table ever appeared, the architecture would have failed (RFC-001 §8.5).
- **It grows through the continuity loop.** When an accepted chapter moves a pairing, the Analyst proposes the new relationship state; the human reviews it; approved movement joins canon and is immediately available to the next draft and the next chat (RFC-005 §7; ADR-004 §3; ADR-006 §1). Relationship state is *living* by the same mechanism the rest of the Bible is (RFC-005 §7).
- **It is gated by the same canon rule.** AI-inferred relationship movement is *proposed*, never asserted as canon; only human approval writes it (RFC-005 §5; ADR-006 §1). This is the highest-regret operation guarded exactly as the Bible guards all canon: no silent mutation of the state that feeds future drafts (RFC-005 §5).
- **It is subject to the same size and supersession disciplines.** Relationship history accumulates over a long work; it is retrieved by relevance, not dumped, and obsolete state is superseded rather than deleted — the Bible's general handling applies unchanged (RFC-005 §11; RFC-002). **This RFC does not redefine the Bible — RFC-005 does.**

---

## 9. Relationship and Character Chat

Character chat is one of the product's two core capabilities (RFC-001 §1.1), and it **consumes** relationship state without owning or redefining it. *This RFC does not define the chat architecture; it describes only how chat relates to relationship state.*

- **Chat reads relationship state as shared context.** When the author converses with a character, the character should behave consistently with where the relationship actually stands — warm or wary, trusting or guarded — as recorded in the shared `relationship` canon (§7; ADR-006 §2). Chat retrieves that state the same way any consumer does: through the Store's one retrieval function (RFC-002). *Retrieval is Defined in the corresponding RFC.*
- **Chat consumes; it does not own.** Relationship state is shared work canon, not chat-private memory. Chat's own private conversational memory stays chat-private and is *not* extended toward this shared knowledge; where chat produces something worth keeping (a bookmarked line, an established beat), it flows into the shared Store as an Entry through the normal path — never by widening chat memory into a second relationship store (RFC-002; ADR-018 §6). Chat is a reader of relationship canon and, through review, a proposer to it — like everyone else.
- **One relationship truth serves both chat and novel.** Because relationship state is shared (§7), a pairing's progression established in the novel is visible in chat, and vice versa — the two capabilities draw on *one* body of relationship truth rather than diverging (RFC-001 §1.1). This unity is the direct payoff of placing relationship state in the shared Store rather than inside either capability.

The relationship in one line: **chat reflects the shared relationship state; it does not hold a copy of it.**

---

## 10. Relationship and Writer

The Writer **consumes** relationship state to plan, draft, and check — but owns none of it (RFC-004 §4, §6; ADR-006 §2).

- **The Writer plans against relationship state.** A Writer planning stage retrieves relationship (and promise) knowledge and places scenes to justify each intended stage transition — the arc plan that makes progression *monotonic-with-intent* (ADR-006 §2; RFC-004 §3). This planning is a **Writer stage over relationship Entries**, not a Relationship-owned planner (§4; `architecture-final-minimal.md` §3). *The planning stage is Defined in the corresponding RFC.*
- **The Writer drafts from relationship state.** Each scene involving a pairing is drafted from the retrieved relationship state, so the prose reflects where the pairing actually stands rather than re-guessing it (RFC-004 §6; ADR-006 §2). The Writer consumes the state; it does not store it.
- **The Writer checks against relationship state, and proposes back to it.** A cheap `qa` assertion flags a scene that moves a pairing backward without an intended trigger — a regression caught and revised rather than shipped (ADR-006 §3; RFC-004 §7). And when an accepted draft moves the relationship, the Writer's ingestion step emits the movement as a *proposal* into the same gate (RFC-004 §4; RFC-005 §7). The Writer both draws from and contributes to relationship canon — but contribution is always gated (RFC-004 §4).
- **The Writer never holds relationship state.** Consistent with §7, the state lives in the shared Store, not inside the Writer; the Writer is a consumer and a gated proposer, never an owner (RFC-004 §6; §7 here). **This RFC does not redefine the Writer — RFC-004 does.**

The relationship in one line: **the Writer plans, drafts, and checks against relationship state, and proposes movement back through review — it never owns the state.**

---

## 11. Evolution Strategy

The Relationship model is designed to grow with a work — and with the product — without architectural change (RFC-001 §7).

- **A richer relationship dimension is a richer `relationship` Entry, not a new store.** Tracking a new facet of a pairing is carried within the existing `relationship` Entry type and its prose, or — if a new *kind* of knowledge is genuinely needed — a new Entry `type` in the governed vocabulary plus an Analyst facet that proposes it (RFC-002; RFC-008 §9; ADR-006 §2). It is **never** a new relationship subsystem or table (RFC-001 §8.5; ADR-006 §5).
- **Richer relationship understanding is a richer Analyst facet and Writer stage.** Better inference of relationship movement is an improved Analyst facet; better arc planning or a sharper regression check is an improved Writer stage or assertion — prompt files, tuned weekly and Bench-measured, not new components (RFC-008 §9; RFC-004 §9; ADR-006 §2–§3). The relationship model gains no code; the extraction, planning, and checking that use it gain prompts.
- **Scope grows from the primary couple outward, on demand.** The launch scope is the primary couple; extending to full relationship graphs across a large cast is deferred until a real work demands it (ADR-006 §4, §6). Growth in scope is a matter of more Entries, not more architecture.
- **Visualization and graph queries are a deferred, disposable projection.** If a large cast with intricate webs ever justifies visual overviews or graph queries, the answer is a **derived, read-only projection** computed from `relationship` Entries — built only when the maintainer actually has enough relationships to pay off, and never a second source of truth (ADR-006 §4, §6). *The projection is Defined in the corresponding RFC.*
- **Deferred structure waits for a real, visible trigger.** If stage-transition math ever starts doing "parsing gymnastics" against prose-first storage, `relationship` is a candidate for the one sanctioned escape valve — promoting a `type` to a structured table, only when the strain is demonstrable (RFC-002; ADR-003 §6; ADR-006 §6). Speculative promotion is forbidden (RFC-002).

---

## 12. Architectural Risks

The relationships-as-shared-canon design is a strong bet; honesty requires naming its failure modes and the guard on each.

### 12.1 Can relationships become inconsistent?

**Yes.** Extraction is model-dependent, and a weak inference or a careless approval can record relationship movement that contradicts what the prose actually shows, or that jumps a stage without cause (ADR-006 §5; ADR-004 §5-Future-risks). Because relationship state is shared and feeds future drafts, an inconsistency here propagates.

The guards:

- **The review gate is the primary defense.** Every relationship canon write passes through human review, so silently-committed bad movement is structurally excluded (§8; RFC-005 §5). A human is the last check before a transition becomes truth.
- **The regression check catches backward movement at draft time.** The Writer's `qa` assertion flags a pairing moving backward without an intended trigger, so drafts stay consistent with canon (ADR-006 §3; RFC-004 §7). *The check is Defined in the corresponding RFC.*
- **One shared state cannot diverge into copies.** Because relationship state lives once in the shared Store — not duplicated inside characters, chat, or the Writer (§7) — there are no copies to fall out of sync. The single-source placement is itself a consistency guard.

### 12.2 How should conflicting relationship history be handled?

The architecture's answer is the Store's general one: **provenance, confidence, and supersession — not silent overwrite.**

- **Genuine conflicts coexist and are adjudicated by confidence.** When two sources disagree about where a pairing stands, both Entries can exist with their provenance, and retrieval prefers the higher-confidence one rather than one silently clobbering the other (RFC-002; ADR-008 §7). Conflict is surfaced, not hidden.
- **Superseded history is retained, not deleted.** When newer movement replaces older state, the older is marked superseded and kept — preserving the record of how the pairing evolved and why (RFC-002; ADR-006 §2). The transition history is part of the value, not disposable.
- **Retconning a relationship is a gated, human decision.** Changing established relationship canon — like establishing it — is surfaced as a proposal and approved by a human, never an automatic purge (RFC-005 §5, §11).

### 12.3 When should relationship history be summarized?

Relationship history accumulates over a long work, and unmanaged it would swell retrieval and prompts. The handling is the Bible's general size discipline (RFC-005 §11):

- **Retrieval, not dumping.** Only the budgeted, relevant relationship state — typically the current stage and the last transition — enters a prompt; the full history is not loaded (RFC-002; ADR-006 §2).
- **Multi-level summaries carry the deep past.** The far history of a pairing can be carried at a coarser granularity via the Bible's multi-level summaries, so long arcs stay within budget (RFC-005 §3; ADR-018 §4). *Summary levels are Defined in the corresponding RFC.*
- **Summarize when history outgrows the budget for detail** — a Bible-wide concern governed by retrieval and summary strategy, not a relationship-specific rule (RFC-005 §11).

### 12.4 Can relationship complexity become excessive?

**Yes.** Large casts with intricate political and romantic webs can produce relationship state that is awkward to query and heavy to reason over on flat Entries (ADR-006 §5, §6). Deep timeline math over stage transitions is exactly where prose-first storage is most likely to strain (ADR-006 §2-Negative; ADR-003 §6).

The guards:

- **Scope is bounded to what a real work needs.** The launch scope is the primary couple; full graphs are deferred until demanded (ADR-006 §4, §6). Complexity is admitted on evidence, not anticipated.
- **Complex querying is a disposable projection, never the canon.** If graph queries become genuinely needed, they are served by a derived read model, leaving the canonical Entries untouched (ADR-006 §4, §6; §11 here).
- **Structural strain has one sanctioned exit.** If stage-transition math strains prose-first `data`, `relationship` may be promoted to a structured table under the promote-a-type valve — only when the strain is visible and demonstrable (RFC-002; ADR-003 §6; ADR-006 §6).

---

## 13. Out of Scope

This RFC deliberately defines **none** of the following. Each is named so no later reader mistakes this document for defining it:

- **Schemas / relationship attributes** — the `relationship` Entry's fields, the stage ladder's structure, the `data` facets (current stage, last-transition event), how trust/affinity/conflict are represented. *Owned by RFC-002; Defined in the corresponding RFC (the Persistence RFC).*
- **Prompt assembly** — how relationship state is composed into a generation or chat prompt. *Defined in the corresponding RFC (the Prompt Architecture RFC).*
- **Algorithms** — extraction of relationship movement, stage-transition logic, regression detection, arc planning, projection computation. *Defined in the corresponding RFCs.*
- **Dialogue rules** — how relationship state shapes the lines characters say. *Defined in the corresponding RFC.*
- **Generation logic** — how the Writer drafts against relationship state; how chat responds. *Owned by RFC-004 and the chat architecture; Defined in the corresponding RFCs.*
- **Retrieval** — ranking or budgeting relationship state for a prompt. *Owned by the Store; Defined in the corresponding RFC (the Retrieval RFC).*
- **Visualization / editing UI** — the relationship projection, the Bible browser, the Review Card queue for relationship proposals. *Defined in the corresponding RFCs.*

Wherever this document needed such a detail, it wrote **"Defined in the corresponding RFC"** (naming the topic) and stopped, by rule.

---

## 14. Dependencies

RFC-006 depends on **RFC-001**, **RFC-002**, **RFC-008**, **RFC-004**, and **RFC-005** and must conform to them; where they conflict, they govern (RFC-001 §10; and the dependency notes of RFC-002, RFC-008 §12, RFC-004 §12, RFC-005 §13). The following areas of the system **depend on the Relationship model** defined here — they detail its state, consume it, or govern its review, and none may override the shared-narrative-state, knowledge-not-subsystem, canon-only-through-review boundaries established above:

| Depends on the Relationship model | Depends on it for |
|---|---|
| **The Living Story Bible & Continuity Loop RFC** | Relationship movement as work-scoped canon proposed on chapter acceptance and kept current through the loop. |
| **The Writer Pipeline & Scene/Episode RFC** | The planning stage that places scenes to justify stage transitions, and the regression `qa` check. |
| **The Retrieval RFC** | Selecting the budgeted, relevant relationship state (current stage, last transition) for a prompt. |
| **The Analyst-facet RFC** | The facet that infers relationship movement from accepted chapters into proposals. |
| **The Character Chat RFC** | Consuming shared relationship state so characters behave consistently with where the pairing stands. |
| **The Character / World DNA Organization RFC** | The boundary between a character's stable identity and the pairing's shared, evolving state. |
| **The Review Card RFC** | Human approval of proposed relationship movement into canon. |
| **The Persistence RFC** | The `relationship` Entry, its `data` facets, and the promote-a-type escape valve if stage math strains. |
| **The UI & Information Architecture RFC** | The deferred, read-only relationship visualization projection inside existing screens. |
| **The Bench RFC** | Measuring relationship-inference precision and regression-catch quality. |

> The forward references above are named by title rather than by number, because the Relationship model's shared-narrative-state placement, its knowledge-not-subsystem nature, and its canon-only-through-review discipline are what those RFCs build on regardless of final numbering. Their **dependence on relationship-as-shared-canon, the one-Store model, and the human-gated continuity loop is fixed**; where a successor and this RFC appear to conflict on those, this RFC — and behind it RFC-001 through RFC-005 and the ADR set — governs.

---

## Appendix A — Traceability

| RFC-006 Section | Primary sources |
|---|---|
| §1 Purpose | RFC-001 §1.1; RFC-002; RFC-005 §3; ADR-006 §1–§2 |
| §2 Why Relationship Exists | ADR-006 §1–§2, §4; `architecture-final-minimal.md` §3; RFC-005 §2.1; RFC-001 §8.5; ADR-003 §4-D |
| §3 Responsibilities | ADR-006 §2; RFC-002; RFC-005 §3 |
| §4 Does NOT Own | RFC-001 §2.6, §4; RFC-002; RFC-008 §3; RFC-004 §3, §7; ADR-006 §2–§4, §6; ADR-004 §5; ADR-011 |
| §5 Relationship Lifecycle | ADR-006 §1–§2, §4-D; RFC-005 §5, §7; RFC-002 |
| §6 Relationship Philosophy | ADR-006 §2, §4-B, §4-D; RFC-005 §2.2, §5, §7 |
| §7 Relationship as Shared Narrative State | ADR-006 §2, §4-B; RFC-002; RFC-004 §4, §6; RFC-005 §3, §6; RFC-001 §1.1 |
| §8 Relationship and Story Bible | RFC-005 §3, §5, §7, §8, §11; RFC-002; ADR-004 §3; ADR-006 §1–§2; RFC-001 §8.5 |
| §9 Relationship and Character Chat | RFC-001 §1.1; RFC-002; ADR-018 §6; ADR-006 §2 |
| §10 Relationship and Writer | RFC-004 §3, §4, §6, §7; ADR-006 §2–§3; RFC-005 §7; `architecture-final-minimal.md` §3 |
| §11 Evolution Strategy | RFC-001 §7; RFC-002; RFC-008 §9; RFC-004 §9; ADR-006 §2–§6; ADR-003 §6 |
| §12 Architectural Risks | ADR-006 §2–§6; RFC-002; RFC-005 §5, §11; ADR-008 §7; ADR-018 §4; RFC-004 §7 |
| §13 Out of Scope | RFC-001 §9 (RFC boundary conventions) |
| §14 Dependencies | RFC-001 §10; RFC-002; RFC-005 §13 |

*End of RFC-006.*
