# RFC-007: Character DNA

- **Status:** Draft
- **Date:** 2026-07-10
- **Author:** Chief Software Architect
- **Project:** AI Native Creative Workspace (`ai-creative-workspace` / "gorofan") — "나만의 로판AI + 하트픽션"
- **Conforms to:** RFC-001, RFC-002, RFC-008, RFC-004, RFC-005, RFC-006; ADR-007, ADR-003, ADR-005, ADR-008, ADR-011, ADR-018
- **Supersedes:** nothing
- **RFC layer:** Component — the character-identity reference the DNA-organization, retrieval, character-chat, and Writer RFCs build on

> **Reading order.** RFC-001 is the system-level reference; RFC-002 defines the Entry Store; RFC-008 the Analyst; RFC-004 the Writer; RFC-005 the Story Bible; RFC-006 the Relationship model. Read all six first. This RFC defines **Character DNA** — the enduring identity of a character, the canonical source of *"who this character is."* It explains *why it exists*, *what it owns and does not own*, *how it relates to the Story Bible*, and *how it supports both novel generation and character chat*. It does **not** define DNA fields, dialogue rules, learning algorithms, retrieval, or prompts — each is named and deferred.
>
> **Source of truth.** The RFC documents take precedence over this one, in order (RFC-001, then RFC-002…RFC-006); behind them the ADR set (`docs/architecture/adr/`) is authoritative, and the two reviews (`docs/design-review-ai-author-os.md`, `docs/architecture-final-minimal.md`) supply rationale only. Where anything here appears to conflict with an RFC or an ADR, **those win** and this document is in error.
>
> **This RFC is implementation-neutral.** It is the conceptual charter of Character DNA. Whenever an implementation detail is needed, this document writes **"Defined in the corresponding RFC"** (naming the topic) and stops. It defines no fields and no schemas.

---

## 1. Purpose

This RFC defines **Character DNA** — the **enduring identity of a character**: the canonical source of *who this character is*, stable across a conversation, a chapter, and an entire work.

A character is the product's most reused creative asset. The same figure may be spoken to in character chat and written about across hundreds of episodes, and in both they must remain **recognizably themselves** — the same voice, the same values, the same contradictions — regardless of what is happening to them at any moment. Character DNA is the knowledge that holds that identity steady.

Character DNA is **not a new subsystem**. Like all creative knowledge, it lives as prose-first, provenanced, typed Entries in the one Store — the `character.*` family (RFC-002; ADR-007 §2). Its distinctive commitments are *prose-and-exemplar-first* representation and *the five layers as organization, not schema* (ADR-007 §2). This RFC explains:

- **why Character DNA exists** — why long-form character consistency cannot rely on prompt memory alone, and why identity is more than personality labels;
- **what it owns** — the enduring identity of a character;
- **what it explicitly does NOT own** — relationship state, story events, dialogue generation, extraction, planning, prompt execution;
- **how it relates to the Story Bible** — as identity knowledge alongside a work's evolving canon (RFC-005);
- **how it supports both novel generation and character chat** — as identity both consume, neither owns.

It does **not** define the DNA layers' structure, the exemplar mechanism, or how identity is injected into a prompt (§13).

---

## 2. Why Character DNA Exists

### 2.1 Why long-form character consistency cannot rely on prompt memory alone

Asked to "write this character," an LLM improvises an identity from whatever is in the context window. Across one scene that can pass; across a hundred episodes and a parallel chat history it cannot. Without a durable, canonical record of who the character *is*, the model drifts: the ice-cold heir turns chatty, the guarded knight over-shares, the distinctive voice flattens into generic competence. This is the same **memory** failure the Story Bible answers for facts and the Relationship model answers for pairings (RFC-005 §2.1; RFC-006 §2.1) — here, for identity.

Character DNA exists so identity is **explicit, canonical, and retrievable** rather than re-improvised each call. When who-the-character-is is stored as knowledge, it can be retrieved into every draft and every chat turn, checked against (the voice-attribution check reads Voice DNA as ground truth), and kept trustworthy through provenance and review (ADR-007 §2, §5; ADR-005 §3). Consistency at chapter 100 — and across the chat/novel divide — becomes possible because there is a fixed identity to be consistent *with*.

### 2.2 Why Character DNA is identity, not personality labels

The tempting shortcut is to model a character as a set of labels or dials — trait ontologies (OCEAN), stat blocks, numeric personality axes ("냉정 0.8"), mood/affinity state machines. The architecture **rejects all of these** (ADR-007 §2, §4). They are the exact over-engineering the design deliberately avoids, and — notably — the reviewer who first proposed axes-with-intensity *retracted it* (ADR-007 §1, §4-A). Labels fail for three reasons:

- **Labels don't lift generation; prose and examples do.** A numeric axis must be re-verbalized into prose to matter to a model, and models imitate *examples* better than they interpret descriptions (ADR-007 §2, §4-A). Identity carried as well-written prose and concrete example dialogue produces better characters than any slider array.
- **Identity is depth, and depth lives in specifics.** The three fields that most raise perceived character depth are not axes but prose specifics: the **contradiction pair** ("겉은 얼음, 아이 앞에서만 무장해제"), the **never-says list**, and **example dialogue** (ADR-007 §3). A character is made vivid by their contradictions and their concrete voice, not by a fifty-point trait vector.
- **Labels flatten what identity needs to keep sharp.** A rigid schema averages a character into a type; prose keeps the idiosyncrasy — the specific, contradictory, particular person — that makes them feel authored (ADR-007 §4-B).

Character DNA is therefore **identity-as-prose-and-exemplars**, not a personality form. *The five layers that organize this identity — Core, Behavioral, Voice, Relational, Arc — are prompt/rendering organization, not schema, and are Defined in the corresponding RFC (the Character/World DNA Organization RFC).*

---

## 3. Character DNA Responsibilities

Character DNA's ownership is the **enduring identity of a character**, held as canonical knowledge. This section defines *responsibilities* — high-level, **no schemas, no fields** (those are Defined in the corresponding RFC). Each responsibility below is a *facet of identity*, carried within `character.*` Entries in the Store as prose and exemplars (RFC-002; ADR-007 §2) — not a field this RFC defines.

- **Identity.** The character's core self — who they fundamentally are, the stable center everything else hangs on (ADR-007 §2). This is the most enduring facet and the least likely to change.
- **Voice.** How the character speaks — their distinctive verbal manner, rhythm, and register — carried above all in **example dialogue (exemplars)**, which outrank abstract description (ADR-007 §2, §4; §7 here).
- **Behavior tendencies.** How the character characteristically acts — their habitual patterns of response, the ways they reliably behave under pressure (ADR-007 §2).
- **Values.** What the character holds important — the commitments and lines that drive their choices.
- **Contradictions.** The tension that makes a character feel real — the **contradiction pair** that keeps them from being a flat type (ADR-007 §3). Identity without contradiction is a stereotype; the contradiction is a first-class part of who they are.
- **Motivations.** What the character wants — the enduring drives beneath their moment-to-moment goals.
- **Growth anchors.** The stable reference points a character's *arc* moves relative to — what change means for *this* character, and what remains recognizably them through it (ADR-007 §2, the Arc layer; §12 here).

Across all of these, one responsibility is constant: DNA holds identity **as prose and exemplars, provenanced, and human-gated** — auto-populated from references by the Analyst so the author faces no empty form, and trustworthy because every piece traces to its source (ADR-007 §2, §5; ADR-008 §2). DNA is the *keeper* of who the character is; it does not generate their lines, track their relationships, or record what happens to them (§4).

---

## 4. What Character DNA Does NOT Own

Character DNA's non-ownership is as binding as its ownership; ambiguity here re-creates the engine sprawl the architecture exists to prevent (RFC-001 §4). DNA is **enduring identity held** — not state, not events, not work done.

- **Relationship state.** DNA does not own how two characters currently stand with one another. That is *shared, evolving narrative state* owned by the Relationship model — it belongs to neither character individually (RFC-006 §4, §7). A character's *enduring relational disposition* (how they tend to relate at all) is identity and may live in DNA; the *specific, moving state of a pairing* is not DNA (§6-Identity-vs-State). *The relationship model is Defined in the corresponding RFC (the Relationship System RFC).*
- **Story events.** DNA does not record what happens to a character. The facts, knowledge-state, and promises of the ongoing story are the **Story Bible's** work-scoped canon (RFC-005 §3). DNA is who the character *is*; the Bible is what has *happened* (§6, §8).
- **Dialogue generation.** DNA does not write dialogue. It holds the *voice* a character speaks in; generating the actual lines is the **Writer's** job (in novels) and the chat engine's (in chat) (RFC-004 §3; §7 here). DNA supplies the manner; it does not author the utterance. *Dialogue rules are Defined in the corresponding RFC.*
- **Knowledge extraction.** DNA does not extract itself. It is auto-populated by the **Analyst** from references and refined from accepted material and user corrections — all as proposals (RFC-008 §3; ADR-007 §2). DNA *receives* proposed identity knowledge; it does not produce it.
- **Narrative planning.** DNA does not plan the story or the arc. Placing scenes and planning transitions is a **Writer stage** that *reads* DNA — not a DNA-owned planner (RFC-004 §3).
- **Prompt execution.** DNA does not assemble or run prompts, and it does not own the retrieval that selects it for a prompt — that single capability belongs to the **Store** (RFC-002). It is *read from*; it does not do the reading. *Retrieval and prompt assembly are Defined in the corresponding RFCs.*

The one-way discipline that governs the whole system governs DNA too: **the model reads identity canon freely and writes it only through review** (RFC-001 §2.6; ADR-007 §2; ADR-011).

---

## 5. Identity Philosophy

Character DNA rests on one commitment: **it represents enduring identity, not temporary state.**

- **Identity is what persists.** DNA holds the parts of a character that stay true across scenes, chapters, and conversations — their voice, values, contradictions, and drives (ADR-007 §2). It is deliberately the *slowest-changing* knowledge about a character: who they are does not lurch from paragraph to paragraph.
- **Temporary emotional state is not identity.** How a character feels *right now* — angry in this scene, tender in this chat turn — is transient, situational, and belongs to the moment being written, not to who the character is (§6). A guarded character who is briefly vulnerable has not become a vulnerable character; their identity is the guardedness *and* the specific crack in it (the contradiction pair), not the passing feeling. Folding momentary emotion into DNA would corrupt the stable identity that keeps the character consistent.
- **Enduring identity is what makes a character reusable.** Because DNA is stable, the same character can be spoken to in chat and written across a whole novel and remain themselves (§1; RFC-001 §1.1). Stability is not a limitation; it is the property that lets one identity serve every use of the character.
- **Enduring does not mean frozen.** A character can *grow* — genuinely, permanently — over an arc, and DNA can be revised to reflect it (§11, §12). But growth is a rare, gated, deliberate change to identity, categorically different from the constant churn of emotional state. Identity changes slowly and through review; state changes every scene and is never canonized.

The philosophy in one line: **DNA is who a character durably is — not how they momentarily feel.**

---

## 6. Identity vs State

This is among the most important distinctions in the entire architecture: the system separates four kinds of knowledge about characters, and confusing any two of them is how a character, a story, or a relationship silently corrupts. *The status and scope mechanisms these rest on are owned by RFC-002; this section explains the conceptual boundaries.*

- **Character DNA — enduring identity ("who a character is").** The slowest-changing knowledge: voice, values, contradictions, motivations, growth anchors (§5). It is (typically) portable across works and into chat, and it changes only rarely, only through review (§11). It answers: *who is this person, always?*
- **Relationship — shared, evolving state between characters ("where a pairing stands").** Owned by the Relationship model, this is a *trajectory* between two characters that moves across the arc — and it belongs to **neither** character's DNA, because it is nobody's private property (RFC-006 §7). It changes as the story earns each movement, and it is work-scoped canon. It answers: *how do these two stand, right now, having come this far?*
- **Story Bible — the work's evolving canon ("what has happened").** Owned by the Story Bible, this is the work-scoped record of facts, knowledge-state, promises, and events (RFC-005 §3). It grows chapter by chapter through the continuity loop. It answers: *what is true in this story so far?*
- **Current Emotional State — momentary, working knowledge ("how a character feels now").** This is *temporary working knowledge* that exists only within the operation being performed — a scene being drafted, a chat turn being answered — and is **never canonized** into DNA, the Bible, or the Relationship (RFC-005 §6; §5 here). It lives and dies inside one writing or chat act. It answers: *what is this character feeling in this exact moment?* — and then it is gone.

The distinctions that must never blur:

- **DNA is not State.** Enduring identity vs. momentary feeling. A passing emotion never edits DNA; if it did, the character's stable self would dissolve into their latest mood (§5).
- **DNA is not Relationship.** A character's identity is individual and portable; a pairing's state is shared, work-bound, and owned by neither participant (RFC-006 §7). A character's *relational disposition* (how they tend to relate) is DNA; the *specific pairing's trajectory* is Relationship.
- **DNA is not the Bible.** Who a character is (identity) vs. what has happened to them (events). DNA can precede any story and outlast it; the Bible is one work's accumulating memory (RFC-005 §2, §8).
- **Only DNA, Relationship, and the Bible are canon; Emotional State is never canon.** The first three are durable, provenanced, human-gated knowledge; the fourth is ephemeral working knowledge the system consumes and discards (RFC-005 §6).

Why this matters architecturally: these four are placed in **different homes on purpose** so that each changes at its own rate and through its own gate — identity slowly, relationship along an arc, the Bible per chapter, emotion never persisting. Collapsing them (identity into mood, relationship into a character, events into identity) is precisely how long-form characters, romances, and continuity rot. Keeping them separate is what lets a character stay themselves *while* their relationships move, their story advances, and their feelings change moment to moment.

---

## 7. Voice Philosophy

Voice is the sharpest illustration of DNA's identity/generation boundary: **the way a character speaks belongs to DNA; the lines they generate do not.**

- **Voice is identity; it is stored, not invented per call.** How a character sounds — their diction, rhythm, register, verbal tics, and the things they would *never* say — is an enduring part of who they are, and it is held in DNA (ADR-007 §2, §3). Voice does not get re-guessed each generation; it is canonical knowledge the model writes *from*.
- **Voice lives above all in exemplars, which outrank descriptions.** The most reliable carrier of voice is not an adjective ("sardonic") but **example dialogue** — concrete lines the character has said — because models imitate examples far better than they interpret descriptions (ADR-007 §2, §4-A). Exemplars are first-class DNA and outrank abstract voice description in importance. *How exemplars are organized and prioritized is Defined in the corresponding RFC.*
- **Generated dialogue is not DNA.** The actual lines the Writer or the chat engine produces in a given scene or turn are *output*, not identity — working knowledge shaped by the voice, not part of it (§4, §6). A drafted line is discarded or revised freely; it never becomes DNA merely by being generated.
- **But an approved line can *become* an exemplar.** When the author fixes a line to read as the character truly should — or bookmarks a chat line as *"this is exactly how she talks"* — that corrected line can be stored as a canonical `character.exemplar` with provenance *user* (ADR-007 §2, §4; §11 here). This is the deliberate, gated path by which generated dialogue crosses into identity: not automatically, but by human approval. It is also why the architecture drops edit-to-attribute back-propagation — storing the corrected exemplar achieves the same effect with far less machinery (ADR-007 §2, §4-A).
- **Voice is what makes voice checkable.** Because voice is stored as exemplars, the Writer's voice-attribution check has real ground truth to test drafts against — mis-attributed lines are the flat lines to revise (ADR-005 §3; RFC-004 §7). Identity stored well is identity that can be *verified*. *The check is Defined in the corresponding RFC.*

The philosophy in one line: **DNA owns the voice; the Writer and chat borrow it to speak — and only an approved line is ever adopted back as identity.**

---

## 8. Relationship with Story Bible

Character DNA and the Story Bible are both canonical knowledge in the one Store, but they hold **different kinds of truth** — and DNA participates in a work without replacing the Bible (RFC-005 §8).

- **DNA is identity; the Bible is the work's events.** DNA answers *who a character is*; the Bible answers *what has happened in this story* (§6; RFC-005 §3). A character's guardedness is DNA; the specific betrayal in chapter 12 that hardened them is a Bible fact. The two are complementary, not competing.
- **DNA is (often) portable; the Bible is work-bound.** Character DNA is enduring identity that can precede a work, be reused across works, and serve character chat independent of any novel — conceptually collection-scoped, reusable knowledge (ADR-008 §2). The Story Bible is strictly *one work's* accumulating canon, at work scope (RFC-005 §3, §8). DNA is not owned by any single work's Bible; a work *draws on* the character's identity, but the identity outlives the work.
- **Both are Entries in the one Store; neither is a separate store.** DNA (`character.*`) and the Bible's ledgers are all typed Entries riding the same model, retrieval, editor, and review gate (RFC-002; RFC-005 §8). There is no "DNA store" and no "Bible store"; there is one Store holding both kinds of knowledge, distinguished by type and scope. If a per-character-DNA table ever appeared, the architecture would have failed (RFC-001 §8.5).
- **A work reads DNA and Bible together; DNA does not replace the Bible.** When drafting or chatting, the system retrieves both the character's identity (DNA) and the relevant story canon (Bible) — identity keeps the character themselves, canon keeps them consistent with events (RFC-005 §9; §10 here). DNA supplies the *who*; the Bible supplies the *what-so-far*; retrieval brings the right slice of each. **This RFC does not redefine the Bible — RFC-005 does.**

---

## 9. Relationship with Character Chat

Character chat is one of the product's two core capabilities (RFC-001 §1.1), and it **consumes** Character DNA while remaining an independent capability. *This RFC does not define the chat architecture; it describes only how chat relates to DNA.*

- **Chat is powered by DNA.** Conversing with a character *is*, in large part, generating from that character's identity — their voice (exemplars first), values, and contradictions (ADR-007 §2, §4). Chat retrieves DNA the same way any consumer does, through the Store's one retrieval function (RFC-002). DNA is what makes the chatted character recognizably the same person the novel writes.
- **Chat consumes DNA; it does not own it.** Character DNA is shared identity knowledge in the Store, not chat-private state. Chat's own conversational memory stays chat-private and is not extended toward this shared identity; where chat produces something worth keeping — a line the author bookmarks as definitive voice — it flows into the shared Store as a proposed `character.exemplar` through the normal gate, never by widening chat memory into a second DNA store (RFC-002; ADR-018 §6; ADR-007 §4). Chat is a reader of DNA and, through review, a proposer to it.
- **One identity serves both chat and novel.** Because DNA is shared, a character voiced in chat and written in the novel draw on *one* identity, so they cannot diverge into two versions of the same person (RFC-001 §1.1; §6 here). This unity is the direct payoff of placing identity in the shared Store rather than inside either capability — and chat remains a fully independent product surface built *on* that shared identity, not folded into the Writer.

The relationship in one line: **chat speaks a character by consuming their shared DNA; it holds no private copy, and it may propose new exemplars back through review.**

---

## 10. Relationship with Writer

The Writer **consumes** Character DNA to draft and check — but owns none of it (RFC-004 §4, §6).

- **The Writer drafts from DNA.** Each scene involving a character is drafted from the retrieved identity — voice, values, contradictions — so the prose keeps the character themselves rather than re-improvising them (RFC-004 §6; ADR-007 §2). The Writer consumes identity; it does not store it.
- **The Writer checks against DNA.** The voice-attribution check tests drafted dialogue against the character's Voice DNA exemplars, flagging mis-attributed (flat, off-voice) lines for targeted revision (ADR-005 §3; RFC-004 §7). DNA is the ground truth; the Writer runs the check against it. *The check is Defined in the corresponding RFC.*
- **The Writer proposes DNA refinements back through the gate.** When accepted material or an author correction reveals a truer exemplar, the movement into DNA is a *proposal* reviewed by a human — never a silent write (ADR-007 §2, §4; RFC-004 §4; RFC-005 §5). The Writer both draws from and contributes to DNA, but contribution is always gated.
- **The Writer never holds DNA.** Consistent with the shared-knowledge principle, identity lives in the Store, not inside the Writer; the Writer is a consumer and a gated proposer, never an owner (RFC-004 §6). **This RFC does not redefine the Writer — RFC-004 does.**

The relationship in one line: **the Writer drafts and checks against DNA and proposes refinements back through review — it never owns the identity.**

---

## 11. Evolution Strategy

Character DNA is designed to grow richer over time without architectural change — and, distinctively, to improve through **user-approved examples** (ADR-007 §2, §4).

- **DNA grows by accumulating identity knowledge, not by changing structure.** A richer character is more and better `character.*` Entries — more exemplars, a sharper contradiction pair, a fuller never-says list — flowing in as proposals and approved into canon (ADR-007 §2–§3). The underlying model stays fixed; the evolution surface is *typed prose data and Analyst facets*, the cheapest things in the system to change (RFC-001 §2.4, §7; RFC-002).
- **User-approved examples are the primary refinement path.** The most powerful way DNA improves is the author correcting a line to read as the character truly should, or bookmarking a definitive chat line — stored as a canonical `character.exemplar` with provenance *user* (ADR-007 §2, §4). Because exemplars outrank descriptions, a few corrected lines shift the character's rendered voice more than any amount of description editing — which is exactly why the architecture prefers this to inferring attribute changes from edits (ADR-007 §4-A). *This is a storage-and-review path, not a learning algorithm; learning algorithms are Defined in the corresponding RFC (the Learning Capture & Distillation RFC).*
- **Auto-population from references means no empty forms.** New characters arrive already rich, extracted from references by the Analyst with provenance, rather than as blank trait forms the author must fill (ADR-007 §5; ADR-008 §2). Evolution starts from a populated, trustworthy base.
- **A new identity facet is a new `character.*` type, never a new store.** If a genuinely new dimension of identity proves worth tracking, it is a new `character.*` Entry type plus an Analyst facet — absorbed by the Store, retrieval, editor, and gate (RFC-002; RFC-008 §9; ADR-007 §2). It is never a new DNA subsystem or table (RFC-001 §8.5).
- **Deferred structure waits for a Bench-verified trigger.** A small structured `data` field is added to a `character.*` type **only** if the Bench shows it measurably beats prose-plus-exemplars — never a trait ontology, never numeric axes (ADR-007 §5, §6). Speculative structure is forbidden (RFC-002). *The promotion path is Defined in the corresponding RFC.*

---

## 12. Architectural Risks

The identity-as-prose-and-exemplars design is a strong bet; honesty requires naming its failure modes and the guard on each.

### 12.1 Can Character DNA become too abstract?

**Yes — this is the most likely failure.** Prose identity can drift into vague adjectives — "mysterious, cold, complex" — that read well to a human but give the model nothing concrete to imitate, producing generically competent, characterless prose (ADR-007 §5-Negative).

The guards:

- **Exemplars-first is the primary defense.** Because example dialogue outranks description and is first-class DNA, the character's voice is carried by concrete lines, not abstractions — the model has something specific to imitate even if the descriptions are vague (ADR-007 §2, §4; §7 here).
- **The high-yield fields are concrete by design.** The contradiction pair, the never-says list, and example dialogue — the three depth-raising fields — are inherently specific, not adjective piles (ADR-007 §3). DNA's own guidance pushes toward the concrete.
- **The voice-attribution check catches abstraction's symptom.** Off-voice, flattened dialogue is exactly what the check flags — so DNA that has drifted too abstract surfaces as failing lines to revise (ADR-005 §3; RFC-004 §7).

### 12.2 Can identity become fragmented?

**Yes.** DNA is many `character.*` Entries drawn from multiple sources — references, accepted chapters, chat bookmarks, user edits — and these can disagree, producing an incoherent or self-contradicting identity (ADR-007 §5, §6-Future-risks).

The guards:

- **Declared precedence resolves conflicts predictably.** Conflicting inputs resolve by a declared precedence order (user > bible > tags > collection DNA > genre baseline) rather than silent averaging that would blur the character (ADR-007 §2, §6). *The precedence order and any conflict escalation are Defined in the corresponding RFCs.*
- **Provenance keeps every piece traceable.** Because each Entry carries where it came from, a fragmented identity can be inspected and adjudicated rather than being an anonymous muddle (RFC-002; ADR-007 §2).
- **The five layers keep rendering coherent.** Organizing identity as Core/Behavioral/Voice/Relational/Arc gives a stable rendering order that assembles the pieces into a coherent whole, rather than a flat bag of contradictory statements (ADR-007 §2). *The layer organization is Defined in the corresponding RFC.*
- **A conflict Review Card is the Bench-gated escalation.** If silent precedence resolution is shown to hurt, surfacing genuine conflicts to the human is the sanctioned next step — added on evidence, not speculatively (ADR-007 §2, §6).

### 12.3 When should a character's growth update DNA?

Characters genuinely change over an arc, and DNA must be able to reflect real growth without being churned by every passing mood:

- **Only enduring, arc-level change updates DNA — and only through review.** When a character *permanently* changes — a value shifts, a wound heals, a mask comes off for good — that is an arc-level growth reflected in DNA via a gated proposal that revises or supersedes identity Entries (ADR-007 §2, the Arc layer; RFC-005 §5). Growth anchors exist precisely to make this legible: what changed, relative to what stayed (§3).
- **Temporary state never updates DNA.** A momentary emotion, a single scene's vulnerability, is Current Emotional State — working knowledge that is consumed and discarded, never canonized (§6; RFC-005 §6). The test is durability: *has this character permanently become someone different, or do they merely feel something right now?* Only the former touches DNA.
- **Growth is superseded, not erased.** When identity is revised, the prior identity is superseded and retained — preserving who the character *was* before they grew (RFC-002). The arc is legible in the history, not overwritten.

### 12.4 What should never change?

**The character's core identity — the stable center that makes them recognizably themselves — should be the last thing to change, and never silently.** Honestly, there is real tension here: a character who changes *too* much is no longer the same character, and the architecture cannot fully automate that judgment. The disciplines that bound it:

- **Core is the slowest layer, and the through-line of any arc.** Growth is layered on via arc and behavioral change; the core self and the defining contradiction are the recognizable constant an arc moves *relative to*, not the thing an arc erases (ADR-007 §2; §5 here). A character can soften without ceasing to be themselves.
- **Every change to identity is human-gated.** There is no silent path to rewriting who a character is; core changes, like all DNA changes, pass through review (ADR-007 §2; RFC-005 §5). The human is the final judge of "is this still the same person?"
- **History is never destroyed.** Because identity is superseded rather than deleted, even a profound change leaves the original self on record — so "what should never change" is always recoverable even when growth is intended (RFC-002).

---

## 13. Out of Scope

This RFC deliberately defines **none** of the following. Each is named so no later reader mistakes this document for defining it:

- **Schemas / DNA fields** — the `character.*` Entry fields, the five layers' structure, the exemplar representation, tags, any `data` facet. *Owned by RFC-002; organization Defined in the corresponding RFC (the Character/World DNA Organization RFC); persistence Defined in the corresponding RFC (the Persistence RFC).*
- **Prompt assembly** — how identity is composed and injected into a generation or chat prompt, injection priority, exemplar ordering. *Defined in the corresponding RFC (the Prompt Architecture RFC).*
- **Algorithms** — extraction of identity from references, deduplication, precedence resolution, conflict detection. *Defined in the corresponding RFCs.*
- **Dialogue generation / rules** — how DNA voice shapes the lines a character says. *Owned by RFC-004 and the chat architecture; Defined in the corresponding RFCs.*
- **Learning algorithms** — how user edits or bookmarks become exemplars or preferences beyond the storage-and-review path described conceptually here. *Defined in the corresponding RFC (the Learning Capture & Distillation RFC).*
- **Retrieval** — ranking or budgeting identity for a prompt. *Owned by the Store; Defined in the corresponding RFC (the Retrieval RFC).*
- **The DNA Editor UI** — the character card, its dials, editable example dialogue, the review surfaces. *Defined in the corresponding RFCs.*

Wherever this document needed such a detail, it wrote **"Defined in the corresponding RFC"** (naming the topic) and stopped, by rule.

---

## 14. Dependencies

RFC-007 depends on **RFC-001**, **RFC-002**, **RFC-008**, **RFC-004**, **RFC-005**, and **RFC-006** and must conform to them; where they conflict, they govern (RFC-001 §10; and the dependency notes of the prior RFCs). The following areas of the system **depend on Character DNA** defined here — they organize it, consume it, or govern its review, and none may override the enduring-identity, identity-not-state, canon-only-through-review boundaries established above:

| Depends on Character DNA | Depends on it for |
|---|---|
| **The Character / World DNA Organization RFC** | The five-layer organization (Core/Behavioral/Voice/Relational/Arc), exemplar primacy, and card rendering order that make §3 concrete. |
| **The Retrieval RFC** | Selecting the budgeted, relevant slice of identity (voice exemplars, core, contradictions) for a prompt. |
| **The Character Chat RFC** | Consuming shared DNA so a chatted character is recognizably themselves and consistent with the novel. |
| **The Writer Pipeline & Scene/Episode RFC** | Drafting from identity and running the voice-attribution check against Voice DNA exemplars. |
| **The Analyst-facet RFC** | The facets that extract identity from references and refine it from accepted material into proposals. |
| **The Relationship System RFC** | The boundary between a character's individual identity and a pairing's shared, evolving state. |
| **The Review Card RFC** | Human approval of proposed identity knowledge — including corrected exemplars — into canon. |
| **The Learning Capture & Distillation RFC** | The path by which user corrections and bookmarks become canonical exemplars/preferences. |
| **The Persistence RFC** | The `character.*` Entry types and any Bench-verified structured `data` field. |
| **The Prompt Architecture RFC** | Injecting identity with exemplars outranking descriptions. |
| **The Bench RFC** | Measuring character fidelity and voice-attribution quality, and gating any structured DNA field. |
| **The UI & Information Architecture RFC** | The DNA Editor — the character card, dials, and editable example dialogue. |

> The forward references above are named by title rather than by number, because Character DNA's enduring-identity nature, its prose-and-exemplars-first representation, and its canon-only-through-review discipline are what those RFCs build on regardless of final numbering. Their **dependence on identity-as-shared-canon, the identity-vs-state separation, and the human-gated refinement path is fixed**; where a successor and this RFC appear to conflict on those, this RFC — and behind it RFC-001 through RFC-006 and the ADR set — governs.

---

## Appendix A — Traceability

| RFC-007 Section | Primary sources |
|---|---|
| §1 Purpose | RFC-001 §1.1; RFC-002; ADR-007 §2 |
| §2 Why Character DNA Exists | RFC-005 §2.1; RFC-006 §2.1; ADR-007 §1–§4; ADR-005 §3; `architecture-final-minimal.md` §2 |
| §3 Responsibilities | ADR-007 §2–§3; RFC-002; ADR-008 §2 |
| §4 Does NOT Own | RFC-001 §2.6, §4; RFC-002; RFC-008 §3; RFC-004 §3; RFC-005 §3; RFC-006 §4, §7; ADR-007 §2; ADR-011 |
| §5 Identity Philosophy | ADR-007 §2; RFC-001 §1.1; RFC-005 §6 |
| §6 Identity vs State | ADR-007 §2; RFC-005 §3, §6; RFC-006 §7; RFC-002 |
| §7 Voice Philosophy | ADR-007 §2–§4; ADR-005 §3; RFC-004 §7 |
| §8 Relationship with Story Bible | RFC-005 §3, §8, §9; RFC-002; ADR-008 §2; RFC-001 §8.5 |
| §9 Relationship with Character Chat | RFC-001 §1.1; RFC-002; ADR-018 §6; ADR-007 §2, §4 |
| §10 Relationship with Writer | RFC-004 §4, §6, §7; ADR-005 §3; ADR-007 §2, §4; RFC-005 §5 |
| §11 Evolution Strategy | RFC-001 §2.4, §7; RFC-002; RFC-008 §9; ADR-007 §2–§6; ADR-008 §2 |
| §12 Architectural Risks | ADR-007 §2–§6; ADR-005 §3; RFC-002; RFC-004 §7; RFC-005 §5–§6 |
| §13 Out of Scope | RFC-001 §9 (RFC boundary conventions) |
| §14 Dependencies | RFC-001 §10; RFC-002; RFC-006 §14 |

*End of RFC-007.*
