# Personal AI Author OS — Product Architecture Roadmap

- **Status:** Product direction and dependency plan
- **North Star:** prepare one complete, human-readable Generation Prompt Packet without requiring a paid provider API call inside rfrf
- **Architecture relationship:** extends the frozen Store → Analyst → Writer architecture; does not replace it

## 1. Product outcome

The target daily loop is:

```text
rfrf 열기
→ 작품 선택
→ 다음 장면 준비
→ 평소 취향 / 🍰 별식 선택
→ Prompt Packet 생성
→ 전체 복사
→ ChatGPT/Claude에 붙여넣기
→ 결과 가져오기
→ 읽고 수정
→ edit-diff evidence 축적
→ 다음 생성의 취향 적중률 개선
```

rfrf's core value is selecting and assembling the right Story, Taste, Voice, Scene, and Context before prose generation. Existing direct provider generation remains supported, but it is no longer the only route to the product's central value.

## 2. Compatibility with Architecture Frozen

The direction is compatible if the existing nouns retain their meanings.

| Existing component | Author OS role |
|---|---|
| Store / Entry | owned creative knowledge and canon; not operation-local packet state |
| Story Bible | work-scoped canonical view used as Story Canon |
| Retrieval | selects the minimum relevant canon within budget and emits trace |
| Context Assembly / PromptEngine | deterministic ordering, budgeting, and provider-neutral assembly substrate |
| Prompt Assets | repository-authoritative packet instructions and section templates |
| Analyst | later converts accepted chapters, references, and edit diffs into proposed knowledge/preferences |
| Writer | existing RFC-004 provider-backed novel orchestration remains; it may consume the same prepared context but is not redefined as packet copying |
| Provider adapters | optional execution after preparation; retained for direct generation |
| Memory | chat-private context only; never silently widened into Story Canon or Taste |
| Review Card | human gate for AI-proposed Entries; not automatically reused for every Taste UX without a semantics review |
| Bench | developer-only deterministic and optional judge-based evaluation of selection, packet, and prose behavior |

RFC-009 already places provider-neutral prompt composition before generation. The Prompt Packet compiler belongs at that preparation seam. Existing Writer and Chat execution continue to call providers; the packet path stops after producing a copyable artifact. A dedicated Prompt Packet contract is still required before code because the current RFCs do not define its persisted metadata, editable preview, target formatting, or import linkage.

## 3. Domain boundaries

### 3.1 Story Canon

Story Canon means what is true in one work. It uses the existing work/world/character Entry scopes and Story Bible view. It has a work lifecycle and is retrieved selectively, never dumped wholesale.

### 3.2 Taste Profile

Taste means what this user likes or dislikes in stories. It is not Story Canon. The existing `user.preference` vocabulary is a viable Store representation for atomic preference knowledge, but a Taste Profile is a user-facing projection/lifecycle over those records, not a Story Bible Entry disguised as canon.

The foundation must support:

- positive Taste and Anti-Taste/hard avoid, including narrative patterns rather than only blocked words;
- Character, Relationship/Romance, Narrative, Preferred Pattern, and Hard Avoid categories;
- explicit versus inferred source;
- explicit preference outranking inferred preference;
- confidence, evidence count, provenance, and human-confirmed state;
- editable, deletable, and disableable user controls;
- rejected-candidate lifecycle that prevents immediate unsupported reactivation;
- global user default with a future work override seam, without overbuilding overrides initially.

The first taxonomy must be able to express, without hard-coded example data:

- **Character Taste:** personality, appearance, occupation/species, power relationship, and character-level hard avoids;
- **Relationship / Romance:** emotional progression speed, power gap, awareness timing, directness of affection, which person changes first, and how long tension is maintained;
- **Narrative Taste:** atmosphere, comedy intensity, event/romance ratio, directness of emotional narration, pacing, and tolerated repetition;
- **Preferred Patterns:** recurring narrative structures the user actively wants;
- **Anti-Taste / Hard Avoid:** words when appropriate, but also unwanted relationship, pacing, characterization, and plot patterns.

One edit diff is evidence, not a strong preference. Repeated evidence may raise confidence; a threshold may create a proposal, and user confirmation promotes it to strong active preference.

### 3.3 Voice Profile

Voice means how prose should sound. It is separate from Taste and from character dialogue voice. It may apply by work or selected preset and must be extensible to multiple presets.

High-level characteristics include POV, tense, sentence length and variance, paragraph density, dialogue ratio, inner-monologue ratio, description/metaphor/body-reaction density, emotion directness, punctuation tendencies, narrative distance, vocabulary characteristics, and dialogue rhythm.

Analyst may later propose these high-level characteristics from user-supplied samples. The system must not be designed to reproduce a named living author's text or copy a specific copyrighted work; it uses high-level traits and user-provided examples.

Whether a named multi-preset Voice Profile is a true aggregate or a projection over `style.preference` Entries requires the Prompt Packet architecture decision. No speculative table is authorized by this roadmap.

### 3.4 Scene Brief

Scene Brief means what should happen now. It is operation-local working state under RFC-002 §4.2, not Story Canon. Its minimum candidate fields are POV, cast, starting state, purpose, conflict, reveal, relationship change, emotion change, facts to preserve, end state, and forbidden patterns.

The UI must not require every field every time. Existing Canon and current Chapter can seed a deterministic draft, while the user can supply a minimal purpose/instruction without any provider API. Persistence, if later needed, must be decided from the actual Chapter/scene substrate; result import does not authorize a speculative Scene table.

### 3.5 🍰 별식 mode

Cake mode is a per-generation request option, not a data mutation.

- excludes Taste Profile and Taste-derived Anti-Taste from that packet;
- preserves Story Canon, work settings, Scene Brief, retrieved Entries, and Voice by default;
- requires a separate explicit switch if Voice is also disabled;
- records the mode in packet/import provenance;
- excludes imported results from Taste-learning evidence by default;
- may later allow explicit user opt-in to learn from a cake result.

## 4. Prompt Packet contract direction

A Generation Prompt Packet is a complete, human-readable, editable artifact that can be copied once into ChatGPT, Claude, or a generic LLM chat UI. Creating it requires no provider credential, provider call, or network call.

It can assemble these ordered layers:

1. repository-managed generation instruction;
2. Story Core;
3. Taste Profile or an explicit cake-mode marker;
4. Voice Profile;
5. Scene Brief;
6. retrieved Story Canon Entries;
7. character and relationship current state;
8. recent summary and necessary previous-scene context;
9. current generation request;
10. Anti-Taste / hard avoids;
11. output format and length constraints.

Small always-on context (identity, selected Voice, hard constraints) and relevance-retrieved context are separate inputs. The compiler does not insert every Canon Entry or every preference. It reuses the existing budget/retrieval trace for selective context and gives protected structural sections an explicit bounded budget rather than hiding them in model-specific formatting.

Selection is model-neutral. `ChatGPT`, `Claude`, and `Generic` adapters are thin formatting layers only; they must not duplicate retrieval, Taste, Voice, budget, or exclusion logic.

Packet metadata must preserve section source, Entry ids, retrieval policy, prompt-asset id/version/digest, budget, selected/excluded reasons, Taste/Voice state, cake mode, target format, and size estimates. Character/token estimates may be approximate but deterministic and clearly labelled.

The Context Inspector is a user-friendly view over this trace. It explains included, low-relevance excluded, budget-excluded, mode-excluded, and manually excluded context. It is not a raw JSON debug dump. Manual exclusions affect one generation request unless the user explicitly changes source data.

The import loop is deliberately simple:

```text
Prompt Packet 전체 복사
→ 외부 ChatGPT/Claude 생성 결과 전체 복사
→ rfrf 생성 결과 가져오기
→ 현재 Chapter draft에 저장
→ 사용자 수정
→ 기존 edit-diff capture
→ 후속 Taste/Voice evidence 분석
```

## 5. Dependency-ordered PR roadmap

Every row is one reviewable PR. A design PR and its implementation PR remain separate where a contract changes durable semantics.

| Order | PR | Prerequisite | Purpose and user value |
|---|---|---|---|
| 1 | P1-8 design | P1-5, P1-6 | freeze read-only legacy/Entry comparison semantics |
| 2 | P1-8 implementation | approved design | produce real equivalence evidence without writes or cutover |
| 3 | AOS-1 Prompt Packet architecture contract | P1-8 evidence | freeze Story/Taste/Voice/Scene boundaries, packet artifact/trace, optional execution seam, import linkage, and explicit canon-source precedence |
| 4 | AOS-2 Scene Brief minimum | AOS-1 | let the user prepare the next scene with minimal manual input and deterministic defaults |
| 5 | AOS-3 explicit Taste foundation | AOS-1 | remember user-authored positive/anti preferences; no inference yet; cake-mode request semantics |
| 6 | AOS-4 Voice foundation | AOS-1 | save/select high-level voice guidance or a work default; no imitation engine |
| 7 | AOS-5 Prompt Packet compiler + API | AOS-2/3/4 | deterministically compile Story/Scene/Taste/Voice/context with Generic/ChatGPT/Claude formatters and no API key |
| 8 | AOS-6 Prompt Packet UI | AOS-5 | preview sections, choose normal/cake, inspect context, estimate size, manually exclude, copy all on desktop/tablet/mobile |
| 9 | AOS-7 External result import | AOS-5 | paste generated prose into the existing Work/Chapter draft flow with packet provenance |
| 10 | AOS-8 edit-diff read contract | P1-7, AOS-7 | expose owned before/after evidence safely to Analyst; no inference yet |
| 11 | AOS-9 Taste/Voice candidate Analyst | AOS-8, Taste/Voice contracts | accumulate repeated evidence, confidence, count, source, and proposals; never auto-confirm from one diff |
| 12 | AOS-10 Taste/Voice review UX | AOS-9 | confirm/reject/edit/disable candidates and prevent unsupported reactivation |
| 13 | AOS-11 Writer alignment | AOS-5 | let direct provider execution consume the same preparation result without deleting current generation paths |
| 14 | AOS-12 Bench expansion | AOS-5 onward | deterministic Story/character/relationship/Taste/Voice/repetition/pacing/goal/forbidden-pattern metrics; optional LLM judge only |

P1-9 review actor/action persistence remains an independent Phase 1 architecture task. It should not block Milestone A unless AOS-1 proves packet/Taste review needs the same durable audit semantics.

P1-8 evidence is a decision gate, not an automatic cutover. If the report is clean enough, a separate P1-8 authority-rollout PR may enable Entry reads and later retire legacy scanning under the documented gate. If gaps remain, AOS-1 must name one temporary authoritative source per packet section and trace compatibility supplements; the compiler may not silently treat both legacy and Entry text as equal authorities or depend permanently on the diagnostic bridge.

## 6. Milestones

### Milestone A — first useful no-API Prompt Packet

Required after this design PR:

1. P1-8 implementation;
2. AOS-1 packet architecture contract;
3. AOS-2 Scene Brief minimum;
4. AOS-3 explicit Taste foundation;
5. AOS-4 Voice foundation;
6. AOS-5 compiler/API;
7. AOS-6 preview/Context Inspector/copy UI.

This milestone supports one-copy ChatGPT/Claude/Generic packets without Taste learning. Do not delay it for automated scene suggestions, deep Analyst extraction, full Writer loops, or fine-tuning.

### Milestone B — import, read, and edit external prose

Add AOS-7. Prefer the existing Chapter document and optimistic-concurrency path. Do not create a Scene table merely for import. Imported text must retain packet id/target/mode provenance and enter normal edit-diff capture where the existing boundary supports it.

### Milestone C — edits begin improving later generations

Add AOS-8, AOS-9, and AOS-10. Learning begins only when repeated evidence can produce reviewable Taste/Voice candidates and confirmed preferences can enter packet selection. Fine-tuning and LoRA remain out of scope.

## 7. Required test plan

### 7.1 Prompt Packet

- Taste ON and Taste OFF/cake;
- cake keeps Story Canon, work state, Scene Brief, retrieved Entries, and Voice by default;
- explicit independent Voice OFF;
- relevant Entry included and irrelevant Entry excluded;
- deterministic exclusion under budget;
- ChatGPT, Claude, and Generic formatting from one shared selection;
- output is a complete single-copy prompt;
- creation succeeds with no API key and no network/provider call;
- source metadata and provenance survive compilation;
- manual exclusion has its own trace reason and does not mutate canon;
- imported result links to packet metadata;
- cake result is excluded from Taste evidence by default.

### 7.2 Taste

- explicit outranks inferred;
- repeated evidence increases confidence/count deterministically;
- one edit diff cannot auto-confirm a strong preference;
- rejection prevents unsupported immediate reactivation;
- positive and Anti-Taste patterns apply correctly;
- cake excludes Taste without deleting it;
- Story Canon and Taste remain in separate scopes/views;
- deleting a Work does not delete global user Taste;
- provenance and human-confirmed state survive edits and disable/enable transitions.

### 7.3 Voice

- work default and selected preset resolve deterministically;
- Voice remains enabled in cake mode;
- Voice OFF is independent from Taste OFF;
- high-level features and user examples retain provenance;
- no target-author identity is required or emitted by the profile contract.

### 7.4 Performance and UX

- not all Entries or preferences are inserted;
- selection and budget remain deterministic and local;
- packet preview avoids repeated network work and remains responsive for large text;
- large clipboard copy preserves the entire packet;
- generation preparation, normal/cake choice, preview, copy, and Context Inspector are readable and touchable on desktop, tablet, and mobile.

### 7.5 Import and learning safety

- import never overwrites a newer Chapter version silently;
- source packet, target, cake mode, and user opt-in are traceable;
- edit-diff capture remains intact;
- no imported or inferred data becomes Story Canon or confirmed Taste without its governing human action.

## 8. Bench direction

Bench expands incrementally with deterministic measures first:

- Story Canon adherence;
- character and relationship-state consistency;
- Taste adherence and Anti-Taste violations;
- Voice feature similarity;
- repetition and pacing;
- scene-goal completion;
- forbidden-pattern occurrence.

An automatic LLM judge is optional and out of band. It is never required for packet generation and never gates a user's live result.

## 9. Explicit non-goals

- deleting OpenAI, Anthropic, Gemini, or Ollama adapters;
- making a provider API key mandatory for packet creation;
- replacing Entry Store, PromptEngine, MemoryEngine, NovelEngine, or existing generation;
- creating StoryCore, StoryBible, Taste, Voice, or Scene tables without a separately approved need;
- treating Taste or Voice as Story Canon;
- fine-tuning, LoRA, automatic strong preferences from one edit, or named-author cloning;
- a maximal NovelCrafter-style settings surface or many unrelated AI buttons.

## 10. Decision checkpoints

Only these points currently require architecture decisions before implementation:

1. P1-8 exact equivalence semantics — fixed in the companion P1-8 design.
2. Prompt Packet artifact identity, editable/persisted boundary, preparation/execution seam, and import linkage — AOS-1.
3. Taste candidate lifecycle and whether existing Review Card semantics can be reused without conflating Story Canon review — AOS-1/AOS-3.
4. Voice preset identity and persistence — AOS-1/AOS-4.
5. Scene Brief persistence only if operation-local state proves insufficient — AOS-2, based on actual use.

Everything else should proceed as small, reversible implementation PRs after those contracts are fixed.
