# Implementation Status (검증 기준 스냅샷)

- **확정 시각:** 2026-07-27
- **기준 커밋:** `bdc2cfb` — `feat(review): add Entry Review Card API` (로컬 `main` == `origin/main`, ahead/behind 0/0)
- **판정 기준:** 파일 존재만으로 완료 처리하지 않는다. **실행되는 코드 경로 + API 노출 + 통과하는 테스트**를 근거로 `완료 / 부분 완료 / 미구현`을 판정한다.
- **문서 우선순위:** ADR → RFC-001 → RFC-002…RFC-012 → `docs/architecture/README.md` → 본 문서 → (참고용) 구 `.kiro/specs` M0~M7 계획.

> Architecture Frozen 이후 결정과 구 `.kiro/specs/.../design.md` · `tasks.md`가 충돌하면 **ADR/RFC가 이긴다.** 본 문서는 그 판정을 코드 근거와 함께 기록한다.

---

## 1. 검증 실행 결과 (본 스냅샷 작성 시점)

| 검증 항목 | 명령 | 결과 |
|---|---|---|
| 백엔드 전체 테스트 | `backend/.venv/Scripts/python -m pytest -q` | **77 passed, 0 failed** (exit 0) |
| 프론트엔드 테스트 | `npm test` (vitest) | **2 files / 10 tests passed** |
| 프론트엔드 린트 | `npm run lint` | **No ESLint warnings or errors** |
| 프론트엔드 빌드 | `npm run build` | **성공** (16 라우트 프리렌더/동적 생성) |
| Alembic head | `alembic heads` | `0002_entry_store (head)` |
| Alembic chain | `alembic history` | `<base> → 0001_initial → 0002_entry_store` |
| 공백/개행 오류 | `git diff --check` | 오류 없음 |
| 작업 트리 | `git status --porcelain` | 클린 |

### 1.1 로컬 환경에서만 발견된 이상 (커밋 대상 아님)

1. **로컬 개발 DB의 alembic 스탬프 불일치.** `alembic current`가 `FAILED: Can't locate revision identified by '0002_story_bible'`를 반환한다. `backend/data/app.db`(gitignore 대상)가 저장소에 존재하지 않는 리비전으로 스탬프되어 있다. 이는 아래 2번 stash의 폐기된 작업 흔적이다. **저장소 마이그레이션 체인 자체는 정상**(`0001 → 0002_entry_store`)이며, 테스트는 격리된 임시 SQLite에서 수행되므로 영향이 없다. 조치는 로컬 DB 재생성 또는 `alembic stamp`가 필요하지만 **사용자 데이터가 들어있을 수 있어 이번 작업에서 건드리지 않았다.**
2. **stash 2건 존재.**
   - `stash@{0}` (`codex/phase1-review-card-api`): Review Card API 작업본 — 내용이 이미 `bdc2cfb`로 main에 병합됨. 사실상 중복.
   - `stash@{1}` (`codex/new`): **Architecture Frozen 이전의 폐기 노선** — `engines/reference/*`, `engines/planning/*`, `models/reference.py`, `models/planning.py`, 마이그레이션 `0002_story_bible.py` / `0003_reference.py`, 프론트 `reference/`·`plan/` 화면 등 43파일 5,081줄. ADR-002/ADR-003(엔진·per-도메인 테이블 금지), ADR-004(별도 Story Bible 스토어 금지)와 정면 충돌한다. **병합하지 말 것.** 필요한 개념은 Entry `type` + Analyst facet + 프롬프트 파일로 재구현한다.
3. **빈 잔여 디렉터리:** `backend/app/engines/reference/`, `backend/app/engines/planning/` — git 추적 파일 없음(`git ls-files` 확인). 2번 폐기 노선의 흔적.
4. **열린 원격 브랜치 10개**(`codex/phase1-*` 8개 등)는 모두 main에 병합 완료된 Phase 1 작업 브랜치이거나 폐기 노선이다. 진행 중인 미병합 기능 브랜치는 없다.

---

## 2. Architecture Phase 1 — 완료로 확정된 항목

| 항목 | 근거 (코드) | 근거 (테스트) |
|---|---|---|
| Alembic `0001` baseline freeze | `backend/app/db/migrations/versions/0001_initial.py` (`down_revision = None`, 이후 수정 금지) | `tests/integration/test_migrations.py` (PostgreSQL 컴파일 + 라운드트립) |
| RFC-002 Entry Model Contract | `docs/architecture/rfc/RFC-002-Entry-Model-Contract.md` | — (문서) |
| RFC-003 Store Retrieval Contract | `docs/architecture/rfc/RFC-003-Store-Retrieval-Contract.md` | — (문서) |
| Entry persistence foundation | `models/entry.py` (scope 5종·type 14종·status 5종 CHECK 제약, 소유자 FK, 5개 인덱스), `repositories/entry_repository.py`, `schemas/entry.py`, 마이그레이션 `0002_entry_store.py` (additive, `down_revision=0001_initial`) | `tests/unit/test_entry_schema.py`, `tests/integration/test_entry_service.py` |
| Entry canon lifecycle · supersession | `services/entry_service.py` — `captured→proposed→canon/rejected`, `canon→superseded`, `supersede()` 원자 경로, `relationship.state`/`story.summary` single-current 규칙, 앵커 생존성 검증 | `tests/integration/test_entry_service.py` |
| Store-wide `retrieve()` | `services/entry_retrieval.py` + `EntryService.retrieve()` — 소유자/스코프/타입/서브젝트/status 필터, keyword-first 랭킹, 결정적 tie-break, whole-Entry 예산 선택, trace | `tests/unit/test_entry_retrieval.py`, `tests/integration/test_entry_retrieval.py` |
| Retrieval → Context Assembly 브리지 | `engines/prompt/entry_context.py` — 선택 결과만 입력받는 순수 모듈, PromptBlock 변환, 렌더 재추정, 통째 제외 | `tests/unit/test_entry_context_assembly.py` |
| Retrieval/Context 골든 회귀 픽스처 | `tests/golden/retrieval_context_fixture.py`, `tests/golden/test_retrieval_context_golden.py` | 동일 |
| Entry Review Card 백엔드 API | `api/v1/entries.py` — `GET /entries/review`, `GET /entries/review/{id}`, `POST .../accept|reject|edit`; 라우터 등록 `api/router.py`; `docs/architecture/review-card-api.md` | `tests/integration/test_entry_review_api.py` |

**보존된 불변식(코드로 확인됨):** `status=canon`을 직접 받는 API 없음 · AI 생산자의 canon 직접 기록 경로 없음 · chat-private `Memory`는 Entry로 저장되지 않음 · per-library 테이블 없음 · `misc` 타입 없음 · `0001` 미수정.

---

## 3. Architecture Phase 1 — 남은 gap (코드 확인 결과)

| # | gap | 확인 결과 |
|---|---|---|
| G1 | **Review Card supersede API 부재** | 확인됨. `EntryService.supersede()`는 존재하지만 이를 노출하는 review 엔드포인트가 없다(`api/v1/entries.py`에 accept/reject/edit만). `docs/architecture/review-card-api.md`가 "intentional deferral"로 명시. → 기존 canon 교체를 UI/API에서 완결할 수 없다. |
| G2 | **Review Card 프론트엔드 부재** | 확인됨. `frontend/src`에서 `/entries` 호출은 **레거시 lorebook entries뿐**(`lib/api/endpoints.ts:55,57`). Review 큐/카드/훅/화면 없음. RFC-011의 gate가 사용자에게 노출되지 않는다. |
| G3 | **repository-managed prompt asset 구조 부재** | 확인됨. 저장소에 `prompts/` 디렉터리가 없다(glob 결과 0건). 프롬프트 로더/버전 관리 자산 계층 없음. ADR-013/RFC-009 요구를 아직 만족하지 않는다. |
| G4 | **코드에 하드코딩된 creative prompt** | 확인됨. `engines/chat/engine.py: DEFAULT_CHAT_TEMPLATE`, `engines/novel/engine.py: DEFAULT_NOVEL_TEMPLATE`, `engines/shared/summarizer.py: SUMMARY_TEMPLATE` 3건이 파이썬 상수로 존재. G3 해결 시 파일 자산으로 이관 대상. |
| G5 | **DB `PromptTemplate` 레거시와 새 Architecture 관계 미정리** | 확인됨. `models/ai_config.py`의 `PromptTemplate` 테이블 + `api/v1/ai_config.py` CRUD가 살아 있고 `0001`에 포함되어 있다. ADR-013은 **프롬프트 body의 DB 저장 금지**를 요구한다. 파괴적 제거 대신 "입력만 저장, body 자산은 파일" 경계를 문서·검증으로 고정해야 한다. |
| G6 | **legacy Character/World/Lore ↔ Entry Store 미연결** | 확인됨. `Character.personality`/`speech_style`, `World` 배열, `Lorebook`/`LoreEntry`가 여전히 유일한 생성 컨텍스트 소스다. `PromptEngine._make_lore_blocks()`(키워드 lore 스캔)가 `chat_service`/`novel_service`에서 실사용 중. Entry 백필/듀얼리드/동등성 비교 없음. |
| G7 | **retrieve()/Context Assembly가 실사용 경로에 미연결** | 확인됨. `EntryService.retrieve()`와 `assemble_entry_context()`의 호출자는 **테스트뿐**이다(프로덕션 호출 0건). 즉 RFC-003 §16.8이 경고한 "두 개의 권위 있는 검색 경로" 상태가 아직 해소되지 않았고, Entry 지식이 실제 생성에 주입되지 않는다. |
| G8 | **edit-diff capture 미구현** | 확인됨. `edit-diff`는 `schemas/entry.py`의 provenance source-kind **열거값으로만** 존재한다(`ProvenanceSourceKind.EDIT_DIFF`). draft↔accepted diff를 계산·저장하는 코드/컬럼/테이블 없음. ADR-010·RFC-001 §8.8의 "day-one capture, 소급 수집 불가" 요구 미충족 — **잔여 gap 중 유일하게 시간이 지날수록 데이터가 영구 손실되는 항목.** |
| G9 | **Entry 작성/조회 API 부재** | 확인됨. `api/v1/entries.py`에 review 5개 엔드포인트만 있다. 사용자 직접 authoring(명시적 사용자 행위로서의 canon)·감사/이력 조회 API가 없어 Entry Store는 서비스 계층에서만 접근 가능하다. |
| G10 | **review 감사 필드 미결정** | 확인됨. `accepted_at`/`rejected_at`/`superseded_at`/`human-edited` provenance는 있으나 review actor·action history·edit diff·되돌림 메타데이터가 없다. `review-card-api.md`가 별도 승인된 persistence 설계 필요로 명시. |

---

## 4. Analyst / Writer / Story Bible / Character Chat / Bench 현황

### 4.1 Analyst — **미구현**
`analyst`, `facet` 관련 프로덕션 코드가 없다(grep 결과: `entry_service.py`/테스트의 무관한 매치뿐). text → proposed Entries 변환기, facet 프롬프트 카탈로그, chapter ingestion / reference / edit-diff 3개 입력 경로 모두 없다.
**주의:** stash@{1}의 `engines/reference/*`(chunking·extractors·prompts·taxonomy·schema)는 Analyst가 **아니다.** 자체 테이블·자체 파이프라인을 가진 별도 엔진이며 RFC-008의 stateless transformer 조건을 위반한다. Analyst는 private store/index/cache를 가져서는 안 된다.

### 4.2 Writer — **미구현 (기존 NovelEngine과 구분됨)**
`engines/novel/engine.py`는 **single-pass continue**다: `assemble_continue()` → `continue_stream()`. 선언적 stage 목록, loop runner, validate/revise, scene/episode 단위, 제안 emit이 전부 없다. 기존 이어쓰기 기능이 동작한다는 사실은 **RFC-004 Writer 완료의 근거가 아니다.** 기존 NovelEngine은 Writer의 draft stage가 흡수할 substrate로 보존한다(재작성 금지).

### 4.3 Story Bible — **미구현 (그리고 별도 스토어를 만들지 않는다)**
별도 `story_bible` 테이블·서비스·스토어는 **존재하지 않으며**, 이는 아키텍처상 **올바른 상태**다(RFC-005: Bible = Entry Store의 work-scoped canonical view). 미구현인 것은 *뷰와 연속성 루프*다: work 스코프 canonical 뷰 조회, continuity 루프(accepted chapter → 제안 → review → canon → 다음 draft), Bible UI. 향후에도 별도 knowledge store를 만들지 않는다. (stash@{1}의 `0002_story_bible.py` 마이그레이션은 이 금지 사항의 반례이므로 폐기 대상.)

### 4.4 Character Chat — **기존 구현 완료 / 공유 지식 통합 미구현**
- 동작함: `services/chat_service.py` SSE 스트리밍, 사용자 메시지 선저장, AI 메시지 1회 저장, 재생성, `MemoryEngine` 롤링 요약·랭킹, persona/world/lore 주입, 멱등키.
- 미구현: Entry Store 기반 공유 지식(Character DNA / relationship.state / world canon / Bible) 주입, chat 북마크 → `character.exemplar` 제안 경로.
- 유지할 경계: Character Chat은 **독립 제품**이며 Writer 하위 기능이 아니다. chat-private `Memory`는 Entry Store로 통합하지 않는다(둘은 Context Assembly에서 별도 블록으로만 만난다).

### 4.5 Bench — **골든 픽스처만 존재 / 러너 미구현**
- 존재: `tests/golden/` retrieval·context 골든 회귀(결정성·선택 ID·trace 검증). 이는 **pytest 회귀 테스트**다.
- 미구현: dev-only Bench 러너, 골든 씬(프로즌 시나리오+지식 스냅샷), Writer checks를 메트릭으로 재사용, pairwise 판정, A/B 리포트. Bench는 개발자 전용이며 사용자 출력을 게이팅하지 않는다.

---

## 5. 구 M0~M7 계획의 실제 상태 (검증 근거)

`[x]` 완료 · `[~]` 부분 완료 · `[ ]` 미구현. 근거는 코드 경로/테스트다.

| 마일스톤 | 상태 | 근거 및 예외 |
|---|---|---|
| **M0 기반** | `[x]` | `main.py` 앱 팩토리+lifespan(엔진/레지스트리/스토리지/잡큐/default-user 시드), `config.py`, `db/base.py`·`session.py`, `models/*` 전량, `0001_initial`, `/healthz`·`/readyz`, `RequestContextMiddleware`, `docker-compose.yml`, Next.js+PWA 골격. |
| **M1 코어 CRUD** | `[x]` | `repositories/base.py`(`_scoped`/`_active`/커서), World/Character/Persona/Novel 서비스·라우터·스키마, 프론트 목록/폼/상세 + TanStack Query 훅, 소프트 삭제(`deleted_at`) 전파. |
| **M2 채팅 MVP** | `[~]` | 완료: PromptEngine(collect→resolve→inject→fit→finalize·예산·보호 블록), lore 스캔 블록, `adapters/base.py`+`registry.py`, `openai_compat`, `ChatEngine`, ChatService SSE·단일 저장·멱등키, 세션 직렬화, ModelConfig/Credential/PromptTemplate CRUD+마스킹, 프론트 채팅/설정. **미구현: 2.2의 Prompt Cache(LRU, memory.version)** — `functools.lru_cache`는 설정 캐시 용도일 뿐. |
| **M3 기억** | `[~]` | 완료: `core/jobs.py` InProcessJobQueue(멱등키·drain), 공유 `Summarizer`, `MemoryEngine`(build/needs_summary/maybe_summarize/rank, version), PromptEngine memory 블록 연결, `summarize` 잡 등록. **미구현: 3.6 누적 압축 상한(메타 요약), 3.7 프론트 "기억 정리 중" 배지 미확인.** |
| **M4 소설 이어쓰기** | `[x]` | `NovelEngine.assemble_continue`/`continue_stream`, NovelService SSE + version CAS, `/chapters/{id}/continue`·`PATCH`·`:reorder`, 프론트 TipTap 에디터·챕터 화면·소설 생성 위저드. (단 §4.2 참조: 이는 Writer가 아니다.) |
| **M5 멀티 공급자** | `[x]` | `anthropic.py`(system 분리), `gemini.py`(systemInstruction), `ollama.py`, `registry.stream_with_resilience`(재시도/폴백), capability 메타. |
| **M6 인증·배포** | `[~]` | 완료: `core/security.py` access/refresh 발급·검증, Google OAuth(PKCE/state/id_token) `auth/providers/google.py`, `auth/service.py`, `/auth/*` 라우터+쿠키, `get_current_user` 로컬 모드 분기, 프론트 로그인/콜백, `Dockerfile`·compose, PWA(`sw.js`·`manifest.json`·`offline.html`). **미구현: refresh 회전/denylist(6.1 일부), Lighthouse 실측 미기록.** |
| **M7 견고화** | `[~]` | 완료: Hypothesis 속성 테스트(`tests/property/test_prompt_budget.py`), JSON 구조화 로깅(`core/logging.py`, request_id, 시크릿 미기록), SSE 통합 테스트(`test_streaming.py`), CI(`.github/workflows/ci.yml`). **미구현: 7.4 JSON Export(코드 없음), 7.1 속성 테스트 커버리지가 Property 7 중심으로 협소.** |

### 5.1 구 계획과 새 계획의 관계 (명시적 기록)

- 구 M0~M7은 **substrate 구축 계획**이었고, 그 목적(실행 가능한 앱 + CRUD + 채팅 + 기억 + 이어쓰기 + 멀티공급자 + 인증/배포)은 위 표대로 **대부분 달성되었다.** 따라서 구 tasks.md의 미체크 박스는 "미구현"이 아니라 **"추적 누락"**이었다.
- 구 계획의 **Story Bible Engine / Planning Engine / Reference Intelligence / per-library 테이블** 방향은 ADR-002·ADR-003·ADR-004에 의해 **폐기**되었다. 대체 경로는 Entry `type` + Analyst facet + Writer stage + 프롬프트 파일이다.
- 구 M2.2의 lore 키워드 스캐너는 **잠정 유지**한다. RFC-003 §16.8에 따라 Entry 검색이 권위를 가진 이후 별도 승인된 마이그레이션으로 비활성화한다(즉시 제거 금지).
- 구 M7의 회귀 체크리스트 R1~R12는 **여전히 유효**하며, 새 Phase 작업의 회귀 테스트 항목으로 계속 사용한다.

---

## 6. 요약 진행도

| 영역 | 진행도 |
|---|---|
| Substrate (M0~M7 기반) | 약 90% — 잔여는 Prompt Cache, 메타 요약 상한, refresh 회전/denylist, JSON Export |
| Architecture Phase 1 (Store/Retrieval/Review gate) | 약 65% — 계약·영속·생명주기·검색·브리지·Review 백엔드 완료 / 실사용 연결·supersede API·프론트·프롬프트 자산·edit-diff 미완 |
| Phase 2 Analyst | 0% |
| Phase 3 Writer | 0% (기존 single-pass 이어쓰기는 substrate로 보존) |
| Phase 4 Story Bible | 0% (별도 스토어 없음 = 의도된 상태) |
| Phase 5 Character Chat 공유 지식 통합 | 0% (Chat 자체 기능은 완료) |
| Phase 6 Bench | 약 15% — retrieval/context 골든 픽스처만 |

전체적으로 **"substrate는 서 있고, 새 Architecture의 뼈대(Store)는 놓였으나 아직 제품 경로에 연결되지 않은 상태"** 다.
