# AI Author OS — Architecture & Creative System Design Review

**Scope:** critical review of the gorofan creative architecture (Story Bible Engine, Planning Engine, Novel Engine, Reference Intelligence Engine, Reference Library, Character DNA, World DNA, Style Profile, Plot/Dialogue/Emotion Libraries) with concrete recommendations to maximize generated-novel quality while keeping UI at or below Heart Fiction complexity.

**How to read:** every recommendation carries a four-line rubric — **Problem** (what it solves), **Quality** (why the novel gets better), **Stage** (MVP or Future), **UI** (complexity cost + how to hide it). Recommendations are numbered `R1…R30` so you can reference them.

---

## 0. Verdict in one page

Your architecture is directionally right and better-conceived than most commercial tools: reference-derived DNA instead of hand-filled forms, Story Bible as source of truth, style applied late, minimal UI. Keep all of that.

The single biggest structural gap: **your pipeline is feed-forward, and quality lives in loops.** Planning → Bible → Draft → Style → Output describes a factory line. Great novels — and great AI novels — come from four closed loops your architecture doesn't yet have:

1. **The Analysis loop** — references → DNA → generation → *comparison back against references* (does output actually resemble what was extracted?).
2. **The Drafting loop** — draft → specialized critics → targeted revision, per scene, before the user ever sees text.
3. **The Continuity loop** — every accepted chapter writes facts *back into* the Story Bible automatically; the Bible is a living ledger, not a static config.
4. **The Learning loop** — every user edit to generated text is a preference signal that updates the Style Profile and DNA weights. This loop is what makes it an *Author OS* rather than a generator. Nobody in the market does this well; it is your moat.

Second biggest gap: **the generation unit is wrong.** Chapters are too big to draft coherently in one pass and too big to critique. The atomic unit must be the **scene** (with a goal, conflict, outcome, and value shift), assembled into Korean-webnovel **episodes** (회차) with engineered hooks. Serialization craft (절단신공, recap, arc cadence) is a missing engine entirely.

Third: **knowledge-state tracking.** The #1 immersion-breaking LLM failure in long fiction is characters knowing things they shouldn't know yet. No amount of DNA fixes this; it needs a dedicated ledger (R8).

Everything below serves those three points. None of it requires new UI beyond one pattern: the **Review Card** (AI proposes → user approves/edits/rejects), which replaces forms everywhere.

---

## 1. Ground truth: repository vs. vision

To keep this review honest: the pushed repository currently implements the *substrate* — provider adapters, token-budgeted PromptEngine, MemoryEngine with rolling summaries, Character (`name / greeting / speech_style / personality / tags`), World (`era / races / nations / taboos` + lorebooks + glossary), Work/Chapter with per-chapter summaries, and a NovelEngine that does single-pass "continue writing" with a flat character/world block (`backend/app/engines/novel/engine.py`).

The engines under review (Story Bible, Planning, Reference Intelligence, DNA libraries) are the design layer above this. Good news: the substrate is genuinely reusable — the PromptEngine's block/budget system is exactly what a multi-source context assembler needs, the MemoryEngine's rank-and-budget pattern generalizes directly to Bible-fact retrieval, and the chat engine is a hidden strategic asset (see R21). Nothing needs to be thrown away. But be aware that today's `Character.personality` free-text field and the DNA vision are different data models; plan the migration as "DNA becomes the source, legacy fields become a rendered view of DNA."

---

## 2. Reference Intelligence Engine — the signal catalog

You asked for every creative signal worth extracting. This is the master list, organized into ten facets. Each facet becomes an **extraction pass** in the analysis pipeline and feeds a specific downstream consumer. Signals marked ★ are the highest-leverage ones that typical systems miss.

### 2.1 Narrative structure signals → Planning Engine, Plot Library
- Scene and chapter **length distributions** (chars, not words — CJK).
- **Scene/summary ratio** — how much is dramatized vs. narrated. ★ This single number explains much of why AI prose feels "summarized."
- Opening strategies per chapter (in medias res, dialogue-first, sensory-first, time-skip).
- **Chapter-ending taxonomy** ★: cliffhanger types actually used (revelation, interruption, decision, threat, emotional suspension) and their frequency mix.
- POV discipline: person, tense, head-hopping rules, POV-switch cadence.
- Timeline devices: flashback frequency, dream sequences, time skips and how they're signposted.
- Arc shape: how many chapters per mini-arc, where reversals land, midpoint behavior.

### 2.2 Character signals → Character DNA
- Archetype + **deviation from archetype** ★ (what makes this 츤데레 different from the stock one — the deviation is the reusable pattern, not the archetype).
- Inner architecture: desire (wants) / need (should learn) / wound (backstory injury) / **lie the character believes** / flaw that costs them.
- **Contradiction pairs** ★: the two traits in tension (ruthless-but-sentimental). Extracted contradictions are the strongest anti-flatness device available.
- Entrance construction: how the character is introduced (action, reputation-first, misdirection).
- Competence display patterns; vulnerability display patterns and their rarity.
- Growth arc shape: what changes, what never changes (the fixed point is as important).

### 2.3 Voice & dialogue signals → Dialogue Library, Character DNA (Voice layer)
Everything you listed (endings, honorifics, favorite expressions, rhythm, vocabulary, recurring phrases, emotional transitions), plus:
- **Subtext patterns** ★: how characters say things without saying them; deflection habits, question-dodging styles.
- **Honorific shift events** ★: when 존댓말↔반말 transitions happen — in K-romance these ARE relationship beats, extract them as events with triggers, not just as static register.
- Banter structure: who escalates, who retreats, turn length asymmetry between characters.
- Dialogue/narration ratio per scene type; beat lines (action between dialogue) density and repertoire.
- What each character **never says** — negative space of a voice is as identifying as positive space.
- Address terms map: what each character calls each other character, and when it changes.

### 2.4 Prose style signals → Style Profile
- Sentence-length distribution and **burstiness** (variance), paragraph shape, one-line-paragraph frequency.
- Narrative distance repertoire (deep interiority ↔ camera-eye) and when it shifts.
- Imagery source domains ★ (does this author metaphorize via weather, machinery, food, religion?).
- Sensory channel balance (visual-dominant vs. sound/smell/touch).
- **의성어/의태어 usage rate and inventory** ★ — onomatopoeia density is a huge, extractable component of Korean web-novel texture.
- Punctuation habits: ellipses, dashes, ?! stacking; chapter-title conventions; scene-break markers.
- Interiority style: italic thought vs. free indirect discourse vs. explicit "라고 생각했다".

### 2.5 Emotion signals → Emotion Library
- **Physiological repertoire** ★: how this author shows each emotion in the body (throat tightening vs. cold hands vs. white knuckles). This is the show-don't-tell lookup table and the single best cure for "그녀는 슬펐다"-style telling.
- Escalation curves: how many beats from irritation to explosion; slow-burn vs. flashpoint.
- Emotional aftermath handling: does the author linger after a peak or cut away?
- Restraint patterns: which emotions are deliberately understated (understatement is a style signature).
- Catharsis construction: what setup precedes payoff scenes and at what distance.

### 2.6 World signals → World DNA
- **Naming morphology** ★: phonology and structure of person/place/organization names — extract as generative rules so new names sound native to the world. Nothing breaks immersion faster than off-morphology names.
- Rule systems with **costs and limits** (magic price, status mechanics) — extract constraints, not just capabilities; constraints generate plot.
- Institutional logic: who holds power, how status is displayed, what money/rank gestures appear.
- Sensory palette per location type; recurring set-pieces (the academy dining hall, the duke's conservatory).
- Taboo logic: not just what is forbidden, but what enforcement looks like — enforceable taboos are plot engines.

### 2.7 Genre & trope signals → Plot Library, Planning Engine
- Trope inventory **plus execution style** ★: played straight, delayed, subverted, lampshaded — the same trope executed differently defines the author's flavor.
- **Obligatory scenes** for the genre (로판: first meeting, misunderstanding, rescue, jealousy trigger, forced proximity, confession) and how far apart they are spaced.
- 사이다/고구마 rhythm ★: frustration-buildup vs. payoff cadence measured in scenes — Korean web-novel readers are exquisitely sensitive to this ratio.
- Genre promises made in chapter 1 and where each is paid off.

### 2.8 Relationship signals → Character DNA (Relational layer), new Relationship tracker (R9)
- **Relationship stage ladder** ★: the discrete stages this author moves couples/rivals through, with the trigger event for each transition.
- Chemistry mechanics: what actually generates spark on the page (competence exposure, forced vulnerability, banter friction).
- Power-balance oscillation: who leads each scene and how it flips.

### 2.9 Serialization signals → Serialization Engine (R11)
- Episode length norms and tolerance band; hook placement (last N lines).
- Recap technique: how prior context is re-woven without info-dumping.
- Reveal scheduling: information-release rate per arc; how many open questions run in parallel (typically 2–4).

### 2.10 Theme & motif signals → Story Bible (theme contract, R7)
- Recurring motifs/objects/phrases and their reappearance cadence.
- The thematic question the story keeps asking; which characters embody which answer.

**Pipeline shape** (backend-only, zero UI): segment reference → classify scenes → run facet extractors → aggregate across references in a Collection → dedupe/reconcile → write DNA entries **with provenance (source excerpt + confidence)**. Provenance is non-negotiable: it powers the "why does the AI think this?" popover that makes the DNA Editor trustworthy (R14), and it lets low-confidence attributes be hidden instead of shown as noise.

> **R1 — Facet-pass analysis pipeline with provenance.**
> **Problem:** one-shot "analyze this novel" prompts produce shallow, generic extractions.
> **Quality:** each facet extractor is a focused expert; aggregation across a Collection separates *author pattern* from *single-book incident*, which is exactly the "patterns not copies" requirement.
> **Stage:** MVP for facets 2.1–2.6; 2.7–2.10 fast-follow.
> **UI:** zero. Analysis runs on upload with a progress state. Only surfaced result: richer DNA cards.

> **R2 — Cross-reference reconciliation.**
> **Problem:** three novels in one Collection disagree (different endings-style, different pacing).
> **Quality:** prevents mushy averaged DNA; produces either "consistent author signature" (merge) or "distinct modes" (keep as variants the Planning Engine can choose between).
> **Stage:** Future (MVP: naive frequency-weighted merge).
> **UI:** zero.

> **R3 — Signature vs. genre-baseline separation.**
> **Problem:** extraction can't tell "this author's quirk" from "every 로판 does this."
> **Quality:** ship a built-in genre baseline; DNA stores the *delta* from baseline. Generation then gets "genre-correct by default + author-flavored where it matters," which is precisely how human authors read influences.
> **Stage:** Future — but design DNA storage for it now (store baseline-relative where possible).
> **UI:** zero.

---

## 3. Story Bible Engine — from config to living ledger

**Challenged assumption:** you treat the Story Bible as the static source of truth that generation reads from. For long serialization, the Bible must be **written to** as much as read from. A Bible that doesn't ingest what chapter 37 established is stale by chapter 40, and staleness is where contradictions come from.

Missing Bible fields (beyond synopsis/characters/world):

| Ledger | Contents | Why |
|---|---|---|
| **Fact ledger** | Canonical facts with the chapter that established them ("R2's eyes are gray — ch.3") | Contradiction checking needs timestamped facts, not prose |
| **Knowledge matrix** ★ | Who knows which secret, as of which chapter | Kills the #1 LLM long-fiction failure: premature knowledge |
| **Promise ledger** ★ | Setups, foreshadowing, Chekhov's guns — each with `planted @ ch / due window / status: open·paid·abandoned` | Payoff discipline is what makes stories feel *authored* |
| **Relationship state** | Current stage per pair on the extracted stage ladder + last transition event | Romance progression must be monotonic-with-intent, not oscillating randomly |
| **Timeline/calendar** | In-world dates, elapsed time, season | Prevents "three winters in ten days" errors |
| **State tracker** | Injuries, possessions, locations, titles, who is currently dead | Mundane but immersion-critical |
| **Open threads** | Unresolved conflicts ranked by reader-visible urgency | Feeds the Planning Engine's "what must this arc address" |
| **Tone & theme contract** | 2–3 sentences: what this story promises, what it will never do | Cheap to store, powerful as a top-of-prompt guardrail |

> **R4 — Auto-ingestion: chapter accepted → facts extracted → Bible updated.**
> **Problem:** manual Bible upkeep dies by chapter 20; stale Bible causes contradictions.
> **Quality:** consistency at chapter 100 becomes possible at all. This is the continuity loop.
> **Stage:** MVP (it's the difference between a demo and a serialization tool).
> **UI:** near zero — new facts appear as a small "Bible updated: 3 new facts" toast; a Review Card queue lets the user veto wrong extractions. No forms.

> **R5 — Bible retrieval, not Bible dumping.**
> **Problem:** by chapter 50 the Bible exceeds any context window; naive truncation drops the fact you needed.
> **Quality:** scene-relevant retrieval (which characters are on stage, which locations, which open promises are due) puts the *right* facts in context. Your MemoryEngine's rank-and-budget design (`engines/memory/engine.py`) is already the correct pattern — generalize it from chat memories to Bible entries.
> **Stage:** MVP.
> **UI:** zero.

> **R6 — Contradiction gate.**
> **Problem:** drafts silently violate established facts.
> **Quality:** post-draft check of the scene against retrieved fact-ledger entries + knowledge matrix; violations trigger an automatic targeted revision (not a user-facing error).
> **Stage:** MVP (facts + knowledge matrix only; timeline checking Future).
> **UI:** zero — users just experience "it doesn't contradict itself."

> **R7 — Theme/tone contract at prompt top.**
> **Problem:** long generations drift tonally (comedy creeping into dark drama).
> **Quality:** a standing 3-line contract is the cheapest known drift-anchor.
> **Stage:** MVP. Auto-drafted from references + premise; user can edit one small text box (the only new visible field, and it's optional).
> **UI:** one optional text box on the work settings page.

---

## 4. Planning Engine — plan scenes, not summaries

**Challenged assumption:** chapter-level planning ("ch.12: they visit the capital") is too coarse. The unit that makes drafts good is the **scene card**:

```
Scene: POV / cast / location / goal → conflict → outcome (win, lose, win-but…)
       value shift (e.g., trust − → +) / emotional beat / promise refs (plants or pays)
       exit hook
```

Planning stages that are missing:

> **R8 — Premise → Promise → Arc → Scene cascade.**
> **Problem:** jumping from synopsis to chapter text skips the layers where causality is engineered.
> **Quality:** each layer is checkable: does the arc pay the premise's promises? does each scene turn (change a value)? Scenes that don't turn get flagged *before* drafting — the cheapest possible place to fix boring.
> **Stage:** MVP (premise → arc → scene cards). The intermediate "promise contract" doc can be internal-only.
> **UI:** the user sees what Heart Fiction shows — a synopsis and an episode list. Scene cards render as 2–3 bullet lines per episode, editable as plain text. The cascade is backend structure, not UI structure.

> **R9 — Relationship arc planner (로판-critical).**
> **Problem:** LLMs oscillate relationships (cold, warm, cold, warm) with no macro direction.
> **Quality:** plan the relationship-stage transitions (from the extracted stage ladder, §2.8) across the arc *first*, then place scenes to justify each transition. Romance readers consume exactly this curve.
> **Stage:** MVP for the primary couple; Future for full relationship graphs.
> **UI:** zero by default; optionally a single read-only progress strip ("현재 단계: 적대 → 균열") on the work page.

> **R10 — Foreshadowing scheduler.**
> **Problem:** twists that were never planted feel cheap; plants that never pay feel sloppy.
> **Quality:** planner assigns each major reveal a plant-chapter and a due window in the Promise ledger; the drafting prompt for a plant-chapter carries a "plant this quietly" instruction. This is the most "feels like a real author" upgrade available per unit of effort.
> **Stage:** MVP-lite (track + remind); auto-planting instructions Future.
> **UI:** zero.

> **R11 — Serialization Engine (missing engine).**
> **Problem:** web novels are consumed in 회차 (~4,500–5,500 chars): each episode needs an in-hook, a micro-arc, and an exit hook (절단신공); none of your engines owns this.
> **Quality:** episode-shaped output with engineered hooks and 사이다 cadence (from §2.9 signals) is the difference between "a novel cut into pieces" and "a serial." Also owns recap weaving and target-length control.
> **Stage:** MVP — this is arguably part of the product's definition for the Korean market.
> **UI:** one setting: episode target length (default from references). Everything else automatic.

---

## 5. Novel Engine — the drafting loop

**Challenged assumption:** single-pass generation (what `NovelEngine.continue_stream` does today) has a hard quality ceiling regardless of prompt quality. The fix is a fixed-shape loop, invisible to the user:

```
scene card + retrieved bible + DNA + exemplars
   → DRAFT (voice-in, see §7)
   → CRITICS (parallel, cheap, specialized)
        continuity critic  (vs fact ledger + knowledge matrix)
        voice critic       (vs Voice DNA — see R13)
        pacing critic      (vs scene card: did it turn? hook present?)
        cliché critic      (LLM-ism / repetition, see R19–R20)
   → targeted REVISE (one pass, critic notes as instructions)
   → STYLE LAYER (surface style only, §7)
   → QA gate → user sees it
```

> **R12 — Critic ensemble with targeted revision.**
> **Problem:** "make it better" self-critique is useless; specialized critics with ground truth to check against (ledgers, DNA, scene card) produce actionable notes.
> **Quality:** this is the drafting loop — the largest single quality lever in this document after scene-level planning. Two passes with focused critics reliably beat five passes of generic critique.
> **Stage:** MVP with continuity + voice critics; pacing + cliché critics fast-follow.
> **UI:** zero. Latency is the real cost — mitigate by streaming the draft to the user optimistically while critics run, then offering "polish ready" as a one-tap upgrade, or by running critics per-scene rather than per-episode.

> **R13 — Voice critic = dialogue attribution test.**
> **Problem:** "does this sound like her?" is unfalsifiable for a critic.
> **Quality:** make it falsifiable: strip speaker tags from the draft's dialogue and ask a checker to attribute each line using Voice DNA profiles. Lines that misattribute (or attribute to "anyone") are exactly the flat lines — revise those specifically. This turns voice from vibes into a measurement.
> **Stage:** MVP (it's cheap and it's your dialogue-quality story).
> **UI:** zero.

> **R14 — Exemplar retrieval at generation time.**
> **Problem:** DNA descriptions tell the model *about* the style; models imitate *examples* far better than descriptions.
> **Quality:** for each scene, retrieve 1–2 scene-type-matched excerpts from the Reference Library (a confession scene retrieves confession-scene exemplars) and inject as "texture reference — imitate the *manner*, never the content." Description + exemplar together outperform either alone by a wide margin.
> **Stage:** MVP. Requires scene-type indexing of references, which the R1 pipeline already produces.
> **UI:** zero. (Guardrail: the cliché/plagiarism check in the QA gate also screens for verbatim leakage from exemplars.)

---

## 6. Character DNA — layered schema and the editor

Flat tags (츤데레, 집착) can't drive generation. Structure DNA in five layers; each layer has a distinct consumer:

| Layer | Contents | Consumed by |
|---|---|---|
| **Core** | archetype + deviation, desire/need/wound/lie, contradiction pair | Planning (arcs), Drafting |
| **Behavioral** | decision patterns under pressure, competence/vulnerability display, habits | Drafting |
| **Voice** | full §2.3 profile + address-term map + never-says list + **generated example dialogue** | Drafting, Voice critic |
| **Relational** | stage ladder positions, chemistry mechanics, power-balance style | Relationship planner |
| **Arc** | what changes / what never changes, growth triggers | Planning |

Tags become **axes with intensity** (냉정 0.8, 다정함-숨김 0.6) auto-scored from references, not booleans. User-created custom tags remain simple labels that the engine expands into axes on first use.

> **R15 — Five-layer DNA with axes, auto-populated.**
> **Problem:** flat trait lists produce flat characters; and asking users to fill five layers would be Heart Fiction squared.
> **Quality:** contradiction pairs + never-says lists + example dialogue are the three highest-yield fields for perceived character depth.
> **Stage:** MVP: Core + Voice layers. Behavioral/Relational/Arc: fast-follow.
> **UI:** see R16 — the editor shows a card, not a schema.

> **R16 — DNA Editor as "portrait + dials," not a form.**
> **Problem:** rich DNA vs. simple UI tension.
> **Quality/UX resolution:** the editor's default view is a **generated character card**: a 3-sentence portrait, the contradiction ("겉은 얼음, 아이 앞에서만 무장해제"), and 3 lines of example dialogue. Below it, the *five most identity-defining* axes as sliders (engine picks which five by information value). Everything else lives behind a single "자세히" disclosure. Every attribute shows its provenance excerpt on tap ("근거: 참고작 2, 3화 — …"). **Editing the example dialogue is the primary editing gesture**: the user fixes a line to sound right, and the engine back-propagates the correction into Voice-layer attributes. Users think in examples, not parameters — let them edit the example.
> **Stage:** MVP (card + 5 sliders + editable example dialogue); provenance popovers fast-follow.
> **UI:** *simpler* than a tag-picker form, despite 10× richer backend.

> **R17 — Character generation = constraint solving, honor the fixed points.**
> **Problem:** Story Bible + Collections + DNA tags + user description can conflict.
> **Quality:** define precedence explicitly: user description > Story Bible > selected tags > Collection DNA > genre baseline. Surface conflicts as a single Review Card ("설명에는 '과묵', 선택 태그는 '수다스러움' — 어느 쪽?") rather than silently averaging.
> **Stage:** MVP.
> **UI:** occasional one-tap conflict card; otherwise zero.

---

## 7. Style Profile — the assumption to half-keep

**Challenged assumption:** "Style should not control planning; style is applied near the end." Half right. Split style into two different things:

- **Surface style** (sentence rhythm, 의성어 density, punctuation, imagery domains, paragraph shape): yes — apply late, as you designed. A late style pass on a structurally-sound draft is correct and keeps planning clean.
- **Voice and structural style** (dialogue voice, narrative distance, interiority level, scene/summary ratio, POV discipline): **must be in the draft from the first token.** You cannot retrofit deep-POV interiority onto a camera-eye draft, and restyling dialogue late destroys the Voice DNA work. A style pass that rewrites dialogue is a bug.

> **R18 — Two-tier style: Voice-in-draft, Surface-at-end; style pass must not touch dialogue.**
> **Problem:** a monolithic late style layer either does too little (cosmetic) or too much (destroys voice/pacing).
> **Quality:** drafts carry the structural fingerprint; the final pass does what final passes are good at — texture — with an explicit "dialogue lines are frozen" constraint.
> **Stage:** MVP (it's a pipeline-ordering decision, cheapest possible time to make it is now).
> **UI:** zero.

> **R19 — LLM-ism screen (distinct from the user's Forbidden list).**
> **Problem:** you correctly forbid auto-inferring the user's forbidden expressions — but there's a separate, universal problem: AI-slop tells (모종의, 그 순간 깨달았다, 형언할 수 없는, ~할 수밖에 없었다 spam, triple-adjective stacks, summarizing final sentences).
> **Quality:** a built-in, curated screen for these in the QA gate, entirely separate from the user's personal forbidden list (which stays manual, permanent, and user-owned in settings exactly as you specified).
> **Stage:** MVP — cheap, and it's the first thing skeptical writers test.
> **UI:** zero (a settings toggle to disable, default on).

> **R20 — Cross-chapter repetition memory.**
> **Problem:** models re-use their own pet phrases; by chapter 30 "서늘한 눈빛" has appeared 40 times.
> **Quality:** maintain a per-work n-gram/phrase frequency index; the QA gate flags over-used non-signature phrases (signature phrases from Style DNA are exempt — repetition of *those* is style).
> **Stage:** Fast-follow.
> **UI:** zero.

---

## 8. World DNA, Dialogue, Emotion, Plot libraries

> **R21 — World DNA: "reproduce by default" + naming morphology + rule-costs.**
> Keep your design: default = reproduce the Collection's world characteristics, no big editor. Two additions with outsized returns: (a) **naming-morphology rules** so generated names sound native (§2.6★); (b) store every world rule with its **cost/limit**, because constraints generate plots and prevent deus-ex-machina fixes. Expose exactly one customization surface: a Review Card when generation needs a world fact that doesn't exist yet ("마법 계약의 위반 시 대가가 필요합니다 — 제안: …" approve/edit). The world grows through play, not through an editor. **Stage:** MVP. **UI:** review cards only.

> **R22 — Dialogue Library as scene-typed exemplar bank + chat as the voice gym.**
> Your analysis list (§2.3) becomes searchable **dialogue exemplars indexed by scene type and emotional beat**, feeding R14 retrieval. Then use what you already built: the **character chat engine**. Chatting with a character is voice calibration disguised as play — let the user mark any chat line as "정확해, 이 말투야," and it enters that character's Voice DNA as a canonical exemplar. This converts your existing chat feature from a toy into the DNA-refinement loop, with zero new UI beyond a bookmark gesture. **Stage:** MVP-lite (bookmark → exemplar). **UI:** one long-press action in chat.

> **R23 — Emotion Library = physiological repertoire + escalation curves.**
> Store per-author show-don't-tell tables (§2.5★) and escalation shapes; the drafting prompt for a scene with emotional beat X injects that author's repertoire for X. This is the most direct lever on "emotional impact" you asked about. **Stage:** MVP. **UI:** zero.

> **R24 — Plot Library = trope cards with execution style + spacing norms.**
> Not plot summaries — **trope execution patterns** (§2.7★): how this Collection plays each trope, with typical setup distance and payoff shape. The Planning Engine composes from these. **Stage:** fast-follow. **UI:** zero.

---

## 9. The Learning loop — what makes it an OS (most important new proposal)

> **R25 — Edit-diff preference learning.**
> **Problem:** today, when the user rewrites a generated paragraph, the correction evaporates. The system never gets better *for this author* — which is the entire premise of an AI Author OS.
> **Quality:** diff every accepted chapter against its generated draft. Classify edits (deleted adverb clusters? shortened sentences? changed a character's ending particles? cut interiority?). Aggregate into standing adjustments to the Style Profile and Voice DNA, applied to all future generation. After 10 chapters the system writes measurably closer to the author's hand; after 50 it's *theirs*. No competitor does this. It also compounds: the longer someone uses your product, the worse every alternative looks — a genuine retention moat.
> **Stage:** MVP-lite (track diffs + apply the 3 coarsest signals: sentence length, adverb rate, per-character particle fixes). Full taxonomy: Future.
> **UI:** zero. Optionally a monthly "당신의 문체 리포트" — delight, not configuration.

> **R26 — Reader-sim check (Future, flagged for honesty).**
> A "target reader" critic that reads each episode cold and reports: confused where? bored where? hooked? Genuinely useful signal for pacing, but expensive and noisy — do it after the critic ensemble proves out, and only per-arc, not per-episode. **Stage:** Future. **UI:** zero.

---

## 10. UI: how all of this stays simpler than Heart Fiction

Five patterns carry the entire complexity budget:

1. **Generated defaults everywhere.** No empty form fields, ever. Every surface shows an already-good AI-generated value with an edit affordance. Configuration becomes correction. (Heart Fiction's sin isn't having many settings — it's making users *produce* the values.)
2. **Review Cards as the universal write-path.** Bible fact ingestion (R4), world-fact creation (R21), DNA conflicts (R17) — all one pattern: proposal card → approve / edit / reject, one tap. A single queue, dismissible in bulk. Users never navigate to a form to keep the system consistent.
3. **One knob per engine, maximum.** Reference influence: one slider ("참고작 반영 강도"). Episode length: one number with a reference-derived default. Everything else is DNA-derived. If a proposed feature needs a second knob, the second knob is a backend heuristic wearing a costume — send it back.
4. **Examples are the editing surface.** Users edit the example dialogue, the sample paragraph, the character portrait — the engine back-propagates to parameters (R16). Parameter sliders exist one disclosure level down for the 5% who want them.
5. **Provenance on tap.** Any AI-derived attribute can show its source excerpt. Trust without configuration.

Surface map stays at three tabs — **쓰기 (Write)** · **바이블 (Bible)** · **서재 (Library: Collections + DNA cards)** — plus settings (API keys, forbidden-expression list, toggles). Every engine in this document lives behind those three tabs.

---

## 11. End-to-end pipeline (revised)

```
REFERENCES ──R1 facet passes──▶ DNA libraries (+provenance)
                                   │
USER: premise + Collections ✔      ▼
        │              ┌─ Planning Engine ─────────────────┐
        └─────────────▶│ premise → promise contract → arcs │
                       │ → relationship curve (R9)         │
                       │ → foreshadow schedule (R10)       │
                       │ → scene cards (R8)                │
                       └───────────────┬───────────────────┘
                                       ▼  per scene
     Bible retrieval (R5) + DNA + exemplars (R14)
                                       ▼
        DRAFT (voice-in, R18) ─▶ CRITICS (R12,R13) ─▶ REVISE
                                       ▼
             Serialization Engine: episode assembly + hooks (R11)
                                       ▼
        SURFACE STYLE pass (R18) ─▶ QA gate (R6,R19,R20 + user forbidden list)
                                       ▼
                                 USER reads/edits
                                   │         │
              R4 fact ingestion ◀──┘         └──▶ R25 edit-diff learning
              (Bible stays alive)                 (Style/DNA stay yours)
```

---

## 12. Priority table

**MVP (quality-defining, do first):**

| # | Item | One-line reason |
|---|---|---|
| R8 | Scene-card planning cascade | Right generation unit; everything else attaches to it |
| R12+R13 | Critic ensemble + voice attribution test | The drafting loop; largest draft-quality lever |
| R4+R5+R6 | Living Bible: ingestion, retrieval, contradiction gate | Serialization consistency is the product promise |
| R11 | Serialization Engine | Episodes with hooks = Korean-market table stakes |
| R14 | Exemplar retrieval | Models imitate examples, not descriptions |
| R15+R16 | Layered DNA + card/dials editor | Character depth with *less* UI than a tag form |
| R18 | Voice-in-draft / surface-style-late split | Pipeline-order decision; cheapest now |
| R1 | Facet-pass reference analysis | Feeds everything above |
| R19 | LLM-ism screen | First thing skeptics test |
| R23 | Emotion physiological repertoire | Direct lever on emotional impact |
| R9 | Relationship arc planner (primary couple) | 로판 core loop |
| R25-lite | Edit-diff learning (coarse signals) | The moat; start collecting diffs day one |

**Fast-follow:** R10 full foreshadow automation, R17 conflict cards, R20 repetition memory, R22 chat-as-voice-gym, R24 trope cards, R16 provenance popovers.

**Future:** R2 reconciliation, R3 genre-baseline deltas, R25 full edit taxonomy, R26 reader-sim, full relationship graphs.

---

## 13. Assumptions challenged — summary

1. **"Pipeline"** → it's four loops (analysis, drafting, continuity, learning). Feed-forward architecture caps quality regardless of component excellence.
2. **"Story Bible = static source of truth"** → source of truth, yes; static, no. It must auto-ingest what generation establishes (R4) or it decays into the source of contradictions.
3. **"Chapter as the unit"** → scene is the drafting unit, episode (회차) is the delivery unit, and they need different engines (R8, R11).
4. **"Style applied at the end"** → only *surface* style. Voice and structural style must be in the draft; a late pass that touches dialogue is a defect (R18).
5. **"Tags describe characters"** → contradictions, never-says lists, and example dialogue describe characters; tags are search keys. Make the example the editing surface (R15, R16).
6. **"More analysis categories = better"** → only with provenance and confidence gating; otherwise DNA becomes noise the user distrusts (R1).
7. **Unasked but decisive:** the system must *learn from being edited* (R25). Without the learning loop you've built a very good generator; with it you've built an Author OS.
