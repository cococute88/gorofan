# Personal Long-form Novel Author OS — Product Architecture Roadmap

- **Status:** Product direction and dependency plan
- **North Star:** provide a personal long-form novel authoring/generation workspace that builds one high-quality, provider-neutral Generation Preparation and lets the user either execute it through an rfrf Provider Adapter or copy it as a complete Prompt Packet into an external LLM UI
- **Architecture relationship:** extends the frozen Store → Analyst → Writer architecture; does not replace it

## 1. Product outcome

Long-form novel authoring is the primary product. AI Character Chat remains a supported, independent/auxiliary feature, but it does not set the dependency order for the novel workflow.

The target daily loop is:

```text
→ 작품 선택
→ 현재 Chapter / 다음 Scene 준비
→ Story Canon + Character/Relationship state + 최근 문맥 선택
→ Scene Brief 또는 간단한 사용자 지시 입력
→ provider-neutral Generation Preparation 생성
→ 직접 Provider API 생성 또는 Prompt Packet 전체 복사
→ 생성 결과 확인
→ Chapter draft 반영 또는 외부 결과 import
→ 읽고 수정
→ edit-diff evidence 축적
→ 다음 Scene / Chapter 생성
```

rfrf's core value is selecting and assembling the right Story, character/relationship state, recent context, Scene request, and constraints before prose generation, then carrying the result forward across many Chapters. Taste and Voice improve that preparation when available; neither is required for the first useful loop.

The two first-class execution routes share the same selection, ordering, budget, prompt authority, and trace:

```text
Generation Preparation
├─ direct: existing provider formatter/adapter → provider call → streamed/generated prose
└─ external: thin human-readable target formatter → complete Prompt Packet → stop without provider call
```

`ChatGPT`, `Claude`, and `Generic` external targets do not own separate retrieval or prompt policy. The route choice occurs only after provider-neutral preparation.

## 2. Compatibility with Architecture Frozen

The direction is compatible if the existing nouns retain their meanings.

| Existing component | Author OS role |
|---|---|
| Store / Entry | owned creative knowledge and canon; not operation-local packet state |
| Story Bible | work-scoped canonical view used as Story Canon |
| Retrieval | selects the minimum relevant canon within budget and emits trace |
| Context Assembly / PromptEngine | deterministic ordering, budgeting, and provider-neutral assembly substrate shared by both execution routes |
| Prompt Assets | repository-authoritative generation instructions and section templates for both routes |
| Analyst | later converts accepted chapters, references, and edit diffs into proposed knowledge/preferences |
| Writer | existing RFC-004 provider-backed novel orchestration remains; it may consume the same prepared context but is not redefined as packet copying |
| Provider adapters | direct execution after preparation; existing registry and adapters are reused rather than duplicated |
| Memory | chat-private context only; never silently widened into Story Canon or Taste |
| Review Card | human gate for AI-proposed Entries; not automatically reused for every Taste UX without a semantics review |
| Bench | developer-only deterministic and optional judge-based evaluation of selection, packet, and prose behavior |

RFC-009 already places provider-neutral prompt composition before generation. Generation Preparation belongs at that seam. Existing Writer/provider execution remains intact; the external packet path stops after producing a copyable artifact. A dedicated contract is still required before code because the current RFCs do not define the shared preparation identity/trace, editable preview, target formatting, or import linkage. That contract must not create a second Store or require preparation to be durable by default.

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

Whether a named multi-preset Voice Profile is a true aggregate or a projection over `style.preference` Entries requires the AOS-1 Generation Preparation architecture decision. No speculative table is authorized by this roadmap.

### 3.4 Scene Brief

Scene Brief means what should happen now. It is operation-local working state under RFC-002 §4.2, not Story Canon. Its minimum candidate fields are POV, cast, starting state, purpose, conflict, reveal, relationship change, emotion change, facts to preserve, end state, and forbidden patterns.

The UI must not require every field every time. Existing Canon and current Chapter can seed a deterministic draft, while the user can supply a minimal purpose/instruction without any provider API. Persistence, if later needed, must be decided from the actual Chapter/scene substrate; result import does not authorize a speculative Scene table.

### 3.5 🍰 별식 mode

Cake mode is a per-generation request option, not a data mutation.

- excludes Taste Profile and Taste-derived Anti-Taste from that packet;
- preserves Story Canon, work settings, Scene Brief, retrieved Entries, and Voice by default;
- requires a separate explicit switch if Voice is also disabled;
- records the mode in shared preparation/output provenance;
- excludes imported results from Taste-learning evidence by default;
- may later allow explicit user opt-in to learn from a cake result.

### 3.6 Character Chat boundary

Character Chat may reuse Character DNA, Relationship state, Story Bible/Entry retrieval, and provider adapters where an explicit owned work/session anchor makes that appropriate. It remains independently usable and must not be forced through the novel Scene/Chapter flow.

Chat-private `Memory` remains scoped to its `ChatSession`. It is never promoted to Story Canon, injected into Novel generation, or used as Taste/Voice evidence without a separately authorized user action and contract. Character Chat capability does not gate the novel roadmap below.

## 4. Generation Preparation and Prompt Packet contract direction

Generation Preparation is the provider-neutral, operation-local result of selecting and assembling the inputs for one novel-generation attempt. It is not a new knowledge Store. At minimum it must work with Story Canon, current Character/Relationship state, recent Chapter context, a Scene Brief or simple instruction, and generation constraints. Taste and Voice sections are optional: an absent profile is represented explicitly and is never a preparation error.

Both execution routes consume the same preparation and context-selection evidence. Provider adapters may translate the assembled messages into wire format, while external formatters may render a human-readable target layout. Neither may re-run retrieval, choose different canon, recalculate Taste/Voice, or apply an independent budget policy.

A Generation Prompt Packet is one rendering of Generation Preparation: a complete, human-readable, editable artifact that can be copied once into ChatGPT, Claude, or a generic LLM chat UI. Creating it requires no provider credential, provider call, or network call.

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

Small always-on context (identity and hard constraints, plus selected Voice when present) and relevance-retrieved context are separate inputs. Preparation does not insert every Canon Entry or every preference. It reuses the existing budget/retrieval trace for selective context and gives protected structural sections an explicit bounded budget rather than hiding them in route-specific formatting.

Selection is model-neutral. `ChatGPT`, `Claude`, and `Generic` external formatters are thin formatting layers only; they must not duplicate retrieval, Taste, Voice, budget, or exclusion logic. They are distinct from the existing provider adapters that own API wire formats.

Shared preparation evidence must preserve section source, Entry ids, retrieval policy, prompt-asset id/version/digest, budget, selected/excluded reasons, optional Taste/Voice state, cake mode, route/target format, and size estimates. Direct and external outputs should reference the same evidence identity when persistence is justified. Character/token estimates may be approximate but deterministic and clearly labelled.

The Context Inspector is a user-friendly view over this trace. It explains included, rank/limit-excluded, budget-excluded, mode-excluded, and manually excluded context according to the active retrieval policy. It is not a raw JSON debug dump. Manual exclusions affect one generation request unless the user explicitly changes source data.

The import loop is deliberately simple:

```text
직접 API 결과 확인 또는 Prompt Packet 전체 복사
→ 외부 경로이면 ChatGPT/Claude 생성 결과 전체 복사
→ 현재 Chapter draft에 직접 반영 또는 외부 결과 가져오기
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
| 3 | AOS-1 Generation Preparation + dual-route architecture contract | P1-8 evidence | freeze Story/Character/Relationship/Chapter/Scene boundaries, shared trace and budget, direct/external terminal seam, import linkage, and explicit canon-source precedence; Taste/Voice optional |
| 4 | AOS-2 minimum Novel preparation + Scene input | AOS-1 | build owned provider-neutral preparation from current Story/Canon, cast/state, recent Chapter context, simple Scene Brief/instruction, and constraints without requiring Taste/Voice |
| 5 | AOS-3 dual execution API | AOS-2 | feed the same preparation to the existing direct Provider Adapter path or thin Generic/ChatGPT/Claude Prompt Packet formatters; no duplicated selection policy |
| 6 | AOS-4 Novel generation workspace UI | AOS-3 | choose direct generation or complete prompt copy, inspect the shared context trace, and receive streamed/generated prose on desktop/tablet/mobile |
| 7 | AOS-5 Chapter apply/import loop | AOS-3 | apply direct output or paste external output into the existing Chapter draft flow with optimistic concurrency, preparation provenance, and P1-7 edit-diff continuity |
| 8 | AOS-6 explicit Taste foundation | AOS-1, usable novel loop | add user-authored positive/anti preferences and cake-mode semantics as optional preparation sections; no inference yet |
| 9 | AOS-7 Voice foundation | AOS-1, usable novel loop | save/select optional high-level voice guidance or a work default; no imitation engine and no generation dependency |
| 10 | AOS-8 edit-diff read contract | P1-7, AOS-5 | expose owned before/after evidence safely to Analyst; no inference yet |
| 11 | AOS-9 Taste/Voice candidate Analyst | AOS-6/7/8 | accumulate repeated evidence, confidence, count, source, and proposals; never auto-confirm from one diff |
| 12 | AOS-10 Taste/Voice review UX | AOS-9 | confirm/reject/edit/disable candidates and prevent unsupported reactivation |
| 13 | AOS-11 Writer-loop evolution | AOS-3 | evolve RFC-004 orchestration on the shared preparation without deleting the usable single-pass path |
| 14 | AOS-12 Bench expansion | AOS-2 onward | deterministic Story/character/relationship/Taste/Voice/repetition/pacing/goal/forbidden-pattern metrics; optional LLM judge only |

P1-9 review actor/action persistence remains an independent Phase 1 architecture task. It should not block Milestone A unless AOS-1 proves packet/Taste review needs the same durable audit semantics.

P1-8 evidence is a decision gate, not an automatic cutover. If the report is clean enough, a separate P1-8 authority-rollout PR may enable Entry reads and later retire legacy scanning under the documented gate. If gaps remain, AOS-1 must name one temporary authoritative source per packet section and trace compatibility supplements; the compiler may not silently treat both legacy and Entry text as equal authorities or depend permanently on the diagnostic bridge.

## 6. Milestones

### Milestone A — first useful dual-generation novel loop

Required after this design PR:

1. P1-8 implementation;
2. AOS-1 Generation Preparation + dual-route contract;
3. AOS-2 minimum Novel preparation + Scene input;
4. AOS-3 dual execution API;
5. AOS-4 Novel generation workspace UI;
6. AOS-5 Chapter apply/import loop.

At AOS-3 the backend can produce a complete Prompt Packet and execute direct generation; at AOS-4 both are usable from the product UI; AOS-5 closes the daily continuation loop. Taste/Voice profiles, automated scene suggestions, deep Analyst extraction, full Writer loops, and fine-tuning must not delay this milestone.

### Milestone B — optional authored Taste and Voice

Add AOS-6 and AOS-7 as independent optional preparation sections. Explicit user guidance comes before automatic learning. Generation remains valid when either profile is absent.

### Milestone C — edits begin improving later generations

Add AOS-8, AOS-9, and AOS-10. Learning begins only when repeated evidence can produce reviewable Taste/Voice candidates and confirmed preferences can enter preparation selection. Fine-tuning and LoRA remain out of scope.

## 7. Provider execution priority

The repository already has a `GeminiAdapter` registered beside Anthropic, OpenAI-compatible providers, and Ollama. AOS-3 should therefore reuse, not recreate, that adapter and use Gemini as a practical first validation path for low-cost direct novel generation.

This is a delivery priority, not architectural authority. At AOS-3 implementation time, the current Gemini API, supported models, streaming behavior, context/output capabilities, quota, and free/paid availability must be revalidated. No model name, context limit, quota, or price policy is frozen in this roadmap. Provider selection continues through the existing registry/configuration seam, and Anthropic, OpenAI-compatible, and Ollama routes remain supported fallbacks.

## 8. Required test plan

### 8.1 Shared preparation and dual execution

- minimum preparation succeeds without Taste or Voice;
- Story Canon, Character/Relationship state, recent Chapter context, Scene instruction, and constraints are selected once;
- direct and external routes share selection ids, ordering, budget decisions, prompt-asset digest, and exclusion trace;
- direct execution uses the existing provider registry/adapter and can stream prose;
- Gemini validation uses implementation-time capabilities rather than roadmap constants;
- provider failure does not alter preparation, Canon, Chapter, or feature flags;
- external rendering performs no provider call and requires no credential;
- ChatGPT, Claude, and Generic formatting cannot re-run retrieval or change selected canon;
- current/future Chapter context follows story chronology, never DB timestamp alone;
- not all Entries are inserted; unresolved facts and continuity state remain selectively retrievable.

### 8.2 Prompt Packet

- Taste ON and Taste OFF/cake;
- cake keeps Story Canon, work state, Scene Brief, retrieved Entries, and Voice by default;
- explicit independent Voice OFF;
- relevant Entry ranks ahead of an otherwise equal unmatched Entry under the current retrieval policy;
- deterministic exclusion under budget;
- ChatGPT, Claude, and Generic formatting from one shared selection;
- output is a complete single-copy prompt;
- creation succeeds with no API key and no network/provider call;
- source metadata and provenance survive compilation;
- manual exclusion has its own trace reason and does not mutate canon;
- imported result links to packet metadata;
- cake result is excluded from Taste evidence by default.

### 8.3 Taste

- explicit outranks inferred;
- repeated evidence increases confidence/count deterministically;
- one edit diff cannot auto-confirm a strong preference;
- rejection prevents unsupported immediate reactivation;
- positive and Anti-Taste patterns apply correctly;
- cake excludes Taste without deleting it;
- Story Canon and Taste remain in separate scopes/views;
- deleting a Work does not delete global user Taste;
- provenance and human-confirmed state survive edits and disable/enable transitions.

### 8.4 Voice

- work default and selected preset resolve deterministically;
- Voice remains enabled in cake mode;
- Voice OFF is independent from Taste OFF;
- high-level features and user examples retain provenance;
- no target-author identity is required or emitted by the profile contract.

### 8.5 Performance and UX

- not all Entries or preferences are inserted;
- selection and budget remain deterministic and local;
- packet preview avoids repeated network work and remains responsive for large text;
- large clipboard copy preserves the entire packet;
- generation preparation, normal/cake choice, preview, copy, and Context Inspector are readable and touchable on desktop, tablet, and mobile.

### 8.6 Apply/import and learning safety

- import never overwrites a newer Chapter version silently;
- source packet, target, cake mode, and user opt-in are traceable;
- edit-diff capture remains intact;
- no imported or inferred data becomes Story Canon or confirmed Taste without its governing human action.
- chat-private Memory never enters novel preparation or canon implicitly.

## 9. Bench direction

Bench expands incrementally with deterministic measures first:

- Story Canon adherence;
- character and relationship-state consistency;
- Taste adherence and Anti-Taste violations;
- Voice feature similarity;
- repetition and pacing;
- scene-goal completion;
- forbidden-pattern occurrence.

An automatic LLM judge is optional and out of band. It is never required for preparation or generation and never gates a user's live result.

## 10. Explicit non-goals

- deleting OpenAI, Anthropic, Gemini, or Ollama adapters;
- making a provider API key mandatory for preparation or packet creation;
- duplicating the existing Gemini adapter or freezing a Gemini model/quota/price in architecture;
- making Taste, Voice, or Analyst learning a prerequisite for the first useful novel loop;
- making Character Chat the primary novel workflow or injecting chat-private Memory into it;
- replacing Entry Store, PromptEngine, MemoryEngine, NovelEngine, or existing generation;
- creating StoryCore, StoryBible, Taste, Voice, or Scene tables without a separately approved need;
- treating Taste or Voice as Story Canon;
- fine-tuning, LoRA, automatic strong preferences from one edit, or named-author cloning;
- a maximal NovelCrafter-style settings surface or many unrelated AI buttons.

## 11. Decision checkpoints

Only these points currently require architecture decisions before implementation:

1. P1-8 exact equivalence semantics — fixed in the companion P1-8 design.
2. Generation Preparation identity/trace, editable/persisted boundary, shared direct/external seam, target rendering, and import linkage — AOS-1.
3. Taste candidate lifecycle and whether existing Review Card semantics can be reused without conflating Story Canon review — AOS-1/AOS-6.
4. Voice preset identity and persistence — AOS-1/AOS-7.
5. Scene Brief persistence only if operation-local state proves insufficient — AOS-2, based on actual use.

Everything else should proceed as small, reversible implementation PRs after those contracts are fixed.
