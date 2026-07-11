# RFC-012: Character Chat Architecture

- **Status:** Draft
- **Date:** 2026-07-10
- **Author:** Chief Software Architect
- **Project:** AI Native Creative Workspace (`ai-creative-workspace` / "gorofan") — "나만의 로판AI + 하트픽션"
- **Conforms to:** RFC-001, RFC-002, RFC-008, RFC-004, RFC-005, RFC-006, RFC-007, RFC-003, RFC-009, RFC-010, RFC-011; ADR-014, ADR-018, ADR-007, ADR-008, ADR-002
- **Supersedes:** nothing
- **RFC layer:** Component — the character-chat reference the DNA, relationship, retrieval, review, and UI RFCs relate to as a peer capability

> **Reading order.** RFC-001 is the system-level reference; RFC-002 the Entry Store; RFC-008 the Analyst; RFC-004 the Writer; RFC-005 the Story Bible; RFC-006 the Relationship model; RFC-007 Character DNA; RFC-003 Store-wide Retrieval; RFC-009 the Prompt System; RFC-010 the Bench; RFC-011 Human Review. Read them first. This RFC defines **Character Chat** as an **independent product capability** — *not* a sub-feature of novel writing — that nonetheless **shares the same knowledge foundation** as novel authoring. It explains *why Character Chat exists*, *what it owns and does not own*, and *how it shares knowledge with the rest of the system*. It does **not** define dialogue prompts, conversation memory, models, or algorithms — each is named and deferred.
>
> **Source of truth.** The RFC documents take precedence over this one, in order (RFC-001, then RFC-002…RFC-011); behind them the ADR set (`docs/architecture/adr/`) is authoritative, and the two reviews (`docs/design-review-ai-author-os.md`, `docs/architecture-final-minimal.md`) supply rationale only. Where anything here appears to conflict with an RFC or an ADR, **those win** and this document is in error.
>
> **This RFC is implementation-neutral.** Whenever an implementation detail is needed, it writes **"Defined in the corresponding RFC"** (naming the topic) and stops. It defines no dialogue prompts and no conversation memory.

---

## 1. Purpose

The product has **two core capabilities**, and Character Chat is one of them. RFC-001 opens by naming the system's dual identity: **AI character chat (로판AI)** — conversing with richly-characterized figures — and **AI long-form novel writing (하트픽션)** — drafting serialized fiction (RFC-001 §1.1). These are peers, not a feature and its accessory: character chat is *half the product's identity*, and demoting it below a first-class mode is explicitly rejected (ADR-014 §3).

The architectural insight that makes this work is that the two capabilities **draw on one shared body of creative knowledge** — characters, worlds, style, relationships, and the accumulating facts of a story — rather than two disconnected knowledge bases (RFC-001 §1.1). Character Chat is therefore an *independent capability over a shared foundation*: its own way of engaging a character (conversation), built on the *same* Entry Store, Character DNA, Relationship state, and Story Bible that novel authoring uses.

This RFC explains:

- **why Character Chat exists** — why it is a first-class capability and not merely a testing interface;
- **what it owns** — interactive conversation, in-conversation character consistency, relationship-aware dialogue, and conversation continuity;
- **what it explicitly does NOT own** — the Story Bible, extraction, narrative generation, canon management, and review;
- **how it shares knowledge** — consuming DNA, relationships, and canon without owning them, and contributing back only through the review gate.

It does **not** define how chat generates a reply, how it remembers a conversation, or which model it uses (§12).

---

## 2. Why Character Chat Exists

### 2.1 Why Character Chat is a first-class capability

Conversing with a character is a *distinct creative activity* with its own value, not a means to some other end. A reader-author wants to *talk to* the ice-cold heir or the guarded knight — to experience the character interactively — and that experience is a founding half of what the product is (로판AI) (RFC-001 §1.1; ADR-014 §3). The architecture treats it as first-class for concrete reasons:

- **It is half the product's identity.** The product is "나만의 로판AI + 하트픽션" — chat *and* novel — and removing chat as a peer capability would gut half the value proposition (RFC-001 §1.1; ADR-014 §3). The Board explicitly disagrees with any framing that subordinates chat to the authoring pipeline (ADR-014 §3, §4-B).
- **It has its own surface and mode.** Chat keeps its own first-class mode in the product, not a panel inside the writing tools (ADR-014 §3). *The exact information architecture — whether chat is a peer top-level tab or nests within character surfaces — is a flagged, deferred UI question, Defined in the corresponding RFC (the UI & Information Architecture RFC) (ADR-014 §5).*
- **It exercises the shared foundation differently and valuably.** Chat consumes the same DNA, relationships, and canon as the novel, but interactively — a different, legitimate use of the one knowledge base that makes that base more valuable, not a duplicate of the novel path (§3, §6–§8; RFC-001 §1.1).

### 2.2 Why it is not simply a testing interface

There is a real and useful *secondary* effect — chatting with a character is voice calibration disguised as play, and a bookmarked line can refine that character's Voice DNA (the "voice gym," R22) (design-review R22; ADR-014 §3). But Character Chat is **not merely** that. The reviews, scoped to novel-writing quality, lean toward reducing chat to a voice-calibration tool; the Board rejects that reduction — chat is a *peer capability that also happens to serve voice calibration*, not a calibration harness that happens to look like chat (ADR-014 §3, §4-B). Treating chat as merely a testing interface for the novel engine would misread the product's identity and forfeit half its reason to exist. Voice calibration is a **welcome by-product** of a first-class capability (§10), not its purpose.

---

## 3. Independent Capability, Shared Knowledge

This is the RFC's central thesis, stated as a dedicated commitment: **Character Chat is an independent product capability, while Character DNA, Relationship, the Story Bible, and the Entry Store remain shared architectural foundations.** Capabilities are independent; knowledge is shared. Getting this split right is what lets the product be two things at once without becoming two disconnected systems.

### 3.1 What is independent

Character Chat owns its own *way of engaging* a character: interactive conversation, its own generation path (distinct from the Writer's loop — §9), its own conversational continuity, and its own private conversation memory (§4; ADR-018 §6). As a capability it stands on its own — it can be used, evolved, and reasoned about independently of novel authoring (§10). The novel could not exist without the Writer; chat does not use the Writer at all (§9). In *capability* terms, chat and novel are peers that do not depend on each other.

### 3.2 What is shared

The *knowledge* both capabilities act on is **one shared foundation**, owned by neither:

- **The Entry Store** is the one home for all creative knowledge (RFC-002). Chat and novel both read from it; neither owns it.
- **Character DNA** is the enduring identity of a character — portable, reusable, consumed by both chat and novel, owned by neither (RFC-007 §1, §9).
- **Relationship state** is shared narrative state that belongs to *neither* a character nor a capability — one pairing's trajectory, read by both chat and novel (RFC-006 §7, §9).
- **The Story Bible** is a work's canonical knowledge, drawn on by both, owned by neither (RFC-005 §3, §8).

### 3.3 Why the split matters

This is the same principle that made the Entry model canonical in the first place: **knowledge that several components use belongs in the shared Store, not inside any one component** (RFC-002). Placing identity, relationships, and canon in the shared foundation — rather than inside either chat or the novel — is exactly what guarantees a character is *the same character* across both: one identity, one relationship trajectory, one canon, consumed by two independent capabilities (RFC-001 §1.1; RFC-006 §7; RFC-007 §9). If chat held its own copy of a character's DNA or a pairing's state, the two capabilities would drift into two divergent versions of the same person — the failure the shared foundation exists to prevent (§11.1). Independence of *capability* plus sharing of *knowledge* is the design that delivers the dual product without the divergence.

The thesis in one line: **chat is its own capability; the character, the relationship, the canon, and the Store are shared foundations it consumes — never owns.**

---

## 4. Character Chat Responsibilities

Character Chat's ownership is **the interactive conversational experience of a character**. This section defines *responsibilities* — high-level, **no dialogue prompts, no conversation-memory design** (those are Defined in the corresponding RFC).

- **Interactive conversation.** Conducting a real-time, turn-by-turn conversation between the user and a character — the core experience chat exists to deliver (RFC-001 §1.1; ADR-014 §3). This is chat's characteristic activity, distinct from producing narrative prose.
- **Character consistency (in conversation).** Keeping the character *recognizably themselves* across a conversation — their voice, values, and contradictions — by drawing on shared Character DNA (§6; RFC-007 §9). Chat owns *applying* identity in dialogue; it does not own the identity (§5).
- **Relationship-aware dialogue.** Making the character behave consistently with where the relationship actually stands — warm or wary, trusting or guarded — by drawing on shared Relationship state (§7; RFC-006 §9). Chat owns *reflecting* relationship state in conversation; it does not own the state.
- **Conversation continuity.** Maintaining coherence *within* an ongoing conversation — remembering what was just said — via its own conversation memory, which stays **chat-private** and is not a general knowledge store (ADR-018 §6). Chat owns its conversational memory; that memory is not canon and not part of the Bible (§5, §11). *Conversation memory is Defined in the corresponding RFC; this RFC does not define it.*

Across all of these, Character Chat **consumes shared knowledge and produces conversation** — it applies identity, relationship, and canon in dialogue, and it holds only its own transient conversational context (§3, §5).

---

## 5. What Character Chat Does NOT Own

Character Chat's non-ownership is as binding as its ownership; ambiguity here would let chat fork the shared foundation or open a second write-path to canon (RFC-001 §4). Chat is a **consumer of shared knowledge and a producer of conversation** — nothing more.

- **The Story Bible.** Chat does not own the work's canonical knowledge. The **Story Bible** is a shared foundation chat reads from; chat holds no canon of its own and is not a second source of story truth (RFC-005 §3, §8; §6 here).
- **Knowledge extraction.** Chat does not turn text into knowledge. Extraction is the **Analyst's** job; even a bookmarked chat line becomes knowledge only by being proposed and reviewed, not extracted by chat itself (RFC-008 §3; §10 here).
- **Narrative generation.** Chat does not write novel prose, and it does not use the Writer's pipeline to do so (§9; RFC-004 §3). Producing serialized fiction is the **Writer's** exclusive job; chat produces conversation, a different thing.
- **Canon management.** Chat does not create, edit, or manage canon. The `proposed → canon` transition is owned by **Human Review** (RFC-011 §5); chat has no path to write canon (§11.4). Chat's private conversation memory is explicitly *not* canon and is not folded into the Entry Store (ADR-018 §6).
- **Review.** Chat does not approve anything into canon. When chat contributes knowledge (a bookmarked exemplar), it emits a **proposal** that Human Review disposes of — chat never approves its own contribution (§10; RFC-011 §5). 

The discipline: **chat consumes DNA, relationships, and canon, and produces conversation; it never owns the Bible, extracts knowledge, writes narrative, manages canon, or reviews — and it never writes canon.**

---

## 6. Relationship with Character DNA

Character Chat is, in large part, *generating from a character's shared DNA* — but it **consumes DNA without owning it** (RFC-007 §9).

- **Chat is powered by shared DNA.** Conversing as a character means drawing on that character's enduring identity — voice (exemplars first), values, contradictions — which lives in shared `character.*` Entries (RFC-007 §2, §9). Chat retrieves DNA the same way any consumer does, through the Store's one retrieval function (RFC-002; RFC-003). DNA is what makes the chatted character recognizably the same person the novel writes (RFC-007 §9).
- **Chat consumes; it does not own.** DNA is shared identity knowledge in the Store, not chat-private state. Chat holds no copy of a character's identity; if it did, chat's character and the novel's character would drift apart (§3.3; RFC-007 §9). Chat reads the one shared identity and applies it in dialogue (§4).
- **One identity serves both capabilities.** Because DNA is shared, a character voiced in chat and written in the novel draw on *one* identity and cannot diverge into two versions of the same person (RFC-001 §1.1; RFC-007 §9). **This RFC does not redefine Character DNA — RFC-007 does.**

---

## 7. Relationship with Story Bible

Character Chat **uses canonical knowledge** from the Story Bible where the conversation calls for it — as a reader, never an owner (RFC-005 §8, §9).

- **Chat reads the Bible's canon.** When a conversation touches the story's established facts, the current state of things, or what a character knows, chat retrieves the relevant canonical knowledge — the same work-scoped canon the novel draws on (RFC-005 §3; RFC-003). This keeps a character's conversation consistent with what has actually happened in the story, not just with their static identity.
- **Chat honors the same knowledge boundaries.** A character in chat should not know what the Bible's knowledge-state says they cannot yet know; canon — including the knowledge matrix — is shared ground truth for chat as much as for the novel (RFC-005 §3; ADR-004 §2). Chat consumes canon through the same retrieval path; it applies no privileged access.
- **Chat never mutates the Bible.** Chat reads canon freely and writes it never; anything a conversation reveals that is worth keeping enters as a *proposal* through review, exactly like any other knowledge (RFC-005 §5; RFC-011 §5; §10 here). **This RFC does not redefine the Story Bible — RFC-005 does.**

---

## 8. Relationship with Relationship State

Character Chat **shares Relationship state with Novel Authoring** — the clearest case of why the shared foundation matters (RFC-006 §7, §9).

- **Chat reflects the shared pairing state.** A character in chat should behave consistently with where the relationship stands — the same current stage and history the novel uses — which lives in shared `relationship` Entries owned by neither capability (RFC-006 §7, §9). Chat retrieves that state through the one retrieval function and reflects it in dialogue (RFC-006 §9; RFC-003).
- **Why chat and novel share it.** Relationship state is *shared narrative state* precisely because it must be one thing across everything that uses it: a pairing's progression established in the novel is visible in chat, and a warmth expressed in chat is consistent with the novel's canon — because both read the *same* state (RFC-006 §7, §9; RFC-001 §1.1). If chat kept its own relationship state, the pairing would stand in two different places at once — the divergence the shared model exists to prevent (§3.3; §11.1).
- **Chat consumes; it does not own, and contributes only through review.** Chat holds no relationship state of its own; where a conversation moves a relationship in a way worth keeping, that movement is a *proposal* through review, never a silent write (RFC-006 §8; RFC-011 §5). **This RFC does not redefine the Relationship model — RFC-006 does.**

---

## 9. Relationship with Writer

Character Chat **does not use the Writer pipeline** — and this boundary is a defining feature of chat's independence, not a limitation (RFC-004 §3; §3.1 here).

- **The Writer is the novel-authoring loop; chat is a different generation path.** The Writer is one loop runner executing declarative stages — plan, draft, validate, revise, compose episodes — for serialized fiction (RFC-004 §1, §3; ADR-005 §2). Chat's activity is real-time conversation, which has a fundamentally different shape: turn-by-turn interaction, not a bounded draft→validate→revise loop over scenes. Chat therefore has its **own generation path** (the substrate chat engine), not the Writer's pipeline (RFC-001 §3; architecture-final-minimal.md §1). *Chat's generation path is Defined in the corresponding RFC.*
- **But chat and the Writer share the *substrate* beneath generation.** Not using the Writer does not mean chat reinvents infrastructure: chat uses the same Store-wide retrieval contract (RFC-003), deterministic prompt composition (RFC-009; ADR-009), and provider adapter (ADR-016). The shared layer is the knowledge-and-assembly substrate; the generation orchestration remains different.
- **Chat does not borrow the Writer's canon discipline by accident — it inherits the same gate.** Like the Writer, chat contributes to canon only through review (§10; RFC-011 §5). The two capabilities are peers under one architecture: independent generation, shared knowledge, same write-gate. **This RFC does not redefine the Writer — RFC-004 does.**

The one-line boundary: **chat and the novel share the knowledge-and-assembly substrate and the review gate, but chat has its own generation path — it does not run the Writer's pipeline.**

---

## 10. Voice Calibration

Chatting with a character can **strengthen that character's DNA** — a genuine, valuable loop — *without* reducing chat to a "Voice Gym" (design-review R22; ADR-014 §3).

- **A bookmarked line can become a canonical exemplar.** When the user marks a chat line as *"정확해, 이 말투야,"* that line can be captured as a proposed `character.exemplar` — and, once approved, it enters that character's Voice DNA as a canonical exemplar (design-review R22; ADR-007 §4; ADR-014 §1 pattern). Because exemplars outrank descriptions in identity, a few bookmarked lines meaningfully sharpen how the character is rendered everywhere — in both chat and the novel (RFC-007 §7, §11).
- **The contribution flows through the gate, never silently.** A bookmarked line is a *proposal*, not a canon write: it goes through Human Review like any other knowledge, and only human approval makes it canonical DNA (RFC-011 §5; §5 here). Voice calibration is a *proposal source*, not a bypass of the gate (§11.4). And the shared knowledge stays shared: the bookmark writes an **Entry**, not a widening of chat-private memory into a knowledge store (RFC-002; ADR-018 §6).
- **Calibration is a by-product, not the purpose.** This loop is a welcome consequence of chat being a first-class capability over the shared foundation — it turns everyday conversation into optional DNA refinement "with zero new UI beyond a bookmark gesture" (design-review R22). But chat's purpose remains the conversational experience itself; the Board is explicit that chat is a peer capability that *also* calibrates voice, not a calibration harness (ADR-014 §3; §2.2 here). *The capture-and-distillation path is Defined in the corresponding RFC (the Learning Capture RFC); the bookmark surface is Defined in the corresponding RFC (the UI RFC).*

The one-line framing: **conversation can propose better exemplars through the gate — a bonus of a first-class capability, not chat's reason to exist.**

---

## 11. Evolution Strategy

Character Chat is designed to **evolve independently while continuing to share the common architecture** (RFC-001 §7; §3 here).

- **Chat evolves as a capability without touching the shared foundation.** Improvements to the conversational experience — richer interaction, better in-conversation continuity — are changes to chat's own path, made without altering the Entry Store, DNA, Relationship, or Bible it consumes (§3.1). Because knowledge is shared and chat only reads it, chat can advance on its own schedule.
- **Chat improves for free as the shared foundation improves.** When DNA grows richer, a relationship deepens, or the Bible accumulates, chat's characters become richer *automatically* — no chat-specific change required — because chat consumes the same knowledge the novel does (§3.2; RFC-007 §9; RFC-006 §9). The shared foundation is a rising tide for both capabilities.
- **New chat knowledge needs is a new `type` and a retrieval clause, not a new store.** If chat should draw on a new kind of knowledge, that is a new Entry `type` (owned by RFC-002) plus a retrieval request — never a chat-owned knowledge store (RFC-002; RFC-003). Chat grows by consuming more of the shared foundation, not by forking it.
- **Chat uses the same evolving substrate.** Chat inherits improvements to retrieval, prompt composition, and provider support because it uses the same substrate as the novel (RFC-003; RFC-009 §11; ADR-016 §6). Its prompts, like all prompts, are versioned and Bench-measured (RFC-009 §7; RFC-010). *Chat's prompt bodies and generation path are Defined in the corresponding RFCs.*
- **The chat information architecture is a deliberate, deferred question.** Whether chat is a peer top-level tab or nests within character surfaces is flagged as Needs-Validation and resolved by real usage — a conscious amendment, never silent drift (ADR-014 §5). *The IA is Defined in the corresponding RFC (the UI & Information Architecture RFC).*

---

## 12. Architectural Risks

The independent-capability-over-shared-knowledge design is a strong bet; honesty requires naming its failure modes and the guard on each.

### 12.1 Can chat and novel diverge?

**They cannot diverge in *knowledge*, by construction — but the risk is real if the boundary is violated.** Because DNA, relationships, and canon are shared and chat only *reads* them, a character, a pairing, and the story's facts are the same in chat and novel by design (§3.3; RFC-006 §9; RFC-007 §9). The divergence risk appears only if the boundary erodes:

- **The guard is that chat owns no knowledge.** Chat holds no private DNA, no private relationship state, no private canon — only transient conversation memory (§4, §5; ADR-018 §6). As long as chat consumes the shared foundation and never copies it, there is nothing to diverge.
- **The failure to prevent is chat-private memory creeping toward a knowledge store.** The explicit rule is that chat's conversational memory stays chat-private and is *not* extended toward shared knowledge; shared knowledge flows through Entries, not by widening chat memory (ADR-018 §6). Violating this would create a second, divergent knowledge source — precisely the failure the rule forbids.

### 12.2 How should continuity be preserved?

Two different continuities must be distinguished:

- **In-conversation continuity** is chat's own responsibility, held in its chat-private conversation memory (§4; ADR-018 §6). *Its mechanism is Defined in the corresponding RFC.*
- **Story continuity** is *not* chat's to hold — it is the shared Story Bible's, consumed via retrieval (§7; RFC-005 §3). Chat stays consistent with the story by reading canon, not by remembering the story itself. Keeping these two continuities separate is what prevents chat memory from drifting into a shadow Bible (§12.1; ADR-018 §6).

### 12.3 When should chat interactions become canonical?

**Only when a human deliberately approves them — never by default.** A conversation is, by default, *working interaction* that does not touch canon; the vast majority of chat is play and produces no canonical knowledge (§4; RFC-005 §6). The sanctioned path for a chat interaction to *become* canonical is the **bookmark-to-exemplar** proposal: the user marks a line as definitive, it becomes a proposed exemplar, and Human Review approves it into DNA (§10; ADR-007 §4; RFC-011 §5). Canonicalization is a deliberate, human, gated act — consistent with the propose-cheaply/canonize-deliberately principle (RFC-011 §3). Everything else a conversation contains stays working knowledge and is discarded.

### 12.4 Should chat ever modify canon automatically?

**No.** Chat has no automatic path to canon, and must not acquire one. This is the same absolute rule that governs every producer: no AI-proposed change reaches canon except through review, and chat is no exception (RFC-001 §2.6; RFC-011 §12.3). A bookmarked line is a *proposal*, disposed of by a human — not a silent write (§10; RFC-011 §5). Auto-writing canon from conversation would reintroduce exactly the compounding-corruption risk the review gate exists to prevent (RFC-005 §5; RFC-011 §2.1). Any future bounded auto-accept would be a human-configured, reversible, audited *policy on the gate* for a narrow high-precision kind — never a chat-specific bypass (RFC-011 §11, §12.2).

---

## 13. Out of Scope

This RFC deliberately defines **none** of the following. Each is named so no later reader mistakes this document for defining it:

- **Dialogue generation** — how chat produces a reply, the conversational generation path. *Defined in the corresponding RFC.*
- **Prompt implementation / dialogue prompts** — the chat prompt bodies, their composition, their wording. *Owned by the Prompt System; Defined in the corresponding RFCs (the Prompt Architecture and chat-prompt RFCs).*
- **Models** — which model powers chat, provider selection. *Defined in the corresponding RFC (the Provider Adapter RFC).*
- **Algorithms** — turn handling, memory summarization, retrieval tuning for chat. *Defined in the corresponding RFCs.*
- **Conversation memory** — the structure, retention, and summarization of chat-private memory. *Defined in the corresponding RFC.*
- **UI** — the chat surface, the bookmark gesture, the chat information architecture. *Defined in the corresponding RFC (the UI & Information Architecture RFC).*
- **Character DNA, Relationship, the Story Bible, the Entry Store, retrieval, prompt assembly, and review** — owned by their respective RFCs; consumed here, not redefined.

Wherever this document needed such a detail, it wrote **"Defined in the corresponding RFC"** (naming the topic) and stopped, by rule.

---

## 14. Dependencies

Character Chat sits at the *consuming* edge of the shared foundation, so its dependencies run in both directions. Where any conflict arises with the RFCs it depends on, they govern (RFC-001 §10; and the dependency notes of the prior RFCs).

### 14.1 What Character Chat depends on

| Character Chat depends on | For |
|---|---|
| **RFC-002 Entry Store** | The one shared home for all knowledge chat consumes. |
| **RFC-007 Character DNA** | The shared identity chat generates a character from. |
| **RFC-006 Relationship** | The shared pairing state chat reflects in dialogue. |
| **RFC-005 Story Bible** | The shared canonical knowledge chat keeps a character consistent with. |
| **RFC-003 Store-wide Retrieval** | The one shared Entry selection and PromptBlock handoff contract used by chat and novel. |
| **RFC-009 Prompt System** | The versioned, standardized composition path chat's prompts use. |
| **RFC-011 Human Review** | The single gate through which a bookmarked line becomes canonical DNA. |
| **The Provider Adapter RFC** | The neutral provider layer chat's generation calls render through. |

### 14.2 What depends on Character Chat

| Depends on Character Chat | For |
|---|---|
| **The Character / World DNA Organization RFC** | Bookmarked chat lines as a source of proposed canonical exemplars that refine Voice DNA. |
| **The Learning Capture & Distillation RFC** | The bookmark-to-exemplar capture path from conversation into proposals. |
| **The UI & Information Architecture RFC** | The chat surface, the bookmark gesture, and the (deferred) chat IA question. |
| **The Bench RFC** | Measuring character fidelity in conversation as a quality signal. |

> The forward references above are named by title rather than by number, because chat's independent-capability-over-shared-knowledge nature, its consume-don't-own discipline, and its no-silent-canon rule are what those RFCs build on regardless of final numbering. Their **dependence on chat as a peer capability, on the shared foundation it consumes, and on the review gate for any contribution is fixed**; where a successor and this RFC appear to conflict on those, this RFC — and behind it RFC-001 through RFC-011 and the ADR set — governs.

---

## Appendix A — Traceability

| RFC-012 Section | Primary sources |
|---|---|
| §1 Purpose | RFC-001 §1.1; ADR-014 §3 |
| §2 Why Character Chat Exists | RFC-001 §1.1; ADR-014 §3, §4-B, §5; design-review R22 |
| §3 Independent Capability, Shared Knowledge | RFC-001 §1.1; RFC-002; RFC-005 §3, §8; RFC-006 §7, §9; RFC-007 §1, §9; ADR-018 §6 |
| §4 Responsibilities | RFC-001 §1.1; RFC-007 §9; RFC-006 §9; ADR-018 §6; ADR-014 §3 |
| §5 What Character Chat Does NOT Own | RFC-001 §4; RFC-005 §3, §8; RFC-008 §3; RFC-004 §3; RFC-011 §5; ADR-018 §6 |
| §6 Relationship with Character DNA | RFC-007 §2, §7, §9; RFC-002; RFC-003; RFC-001 §1.1 |
| §7 Relationship with Story Bible | RFC-005 §3, §5, §8; ADR-004 §2; RFC-003; RFC-011 §5 |
| §8 Relationship with Relationship State | RFC-006 §7, §8, §9; RFC-003; RFC-001 §1.1; RFC-011 §5 |
| §9 Relationship with Writer | RFC-004 §1, §3; ADR-005 §2; RFC-001 §3; RFC-003; RFC-009 §9; ADR-016; RFC-011 §5; `architecture-final-minimal.md` §1 |
| §10 Voice Calibration | design-review R22; ADR-007 §4; ADR-014 §1, §3; RFC-007 §7, §11; RFC-011 §5; RFC-002; ADR-018 §6 |
| §11 Evolution Strategy | RFC-001 §7; RFC-007 §9; RFC-006 §9; RFC-002; RFC-003; RFC-009 §7, §11; RFC-010; ADR-014 §5; ADR-016 §6 |
| §12 Architectural Risks | RFC-006 §9; RFC-007 §9; ADR-018 §6; RFC-005 §3, §5–§6; RFC-011 §2.1, §3, §5, §11–§12; ADR-007 §4; RFC-001 §2.6 |
| §13 Out of Scope | RFC-001 §9 (RFC boundary conventions) |
| §14 Dependencies | RFC-001 §10; and prior RFC dependency notes |

*End of RFC-012.*
