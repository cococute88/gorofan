# Implementation Plan: AI Native Creative Workspace

## Overview

본 문서는 승인된 `design.md`와 `requirements.md`에서 도출된 구현 로드맵이다. 마일스톤은 design Phase 16(M0~M7)을 기반으로 하며, 각 마일스톤은 **완료 후에도 애플리케이션이 실행 가능**하도록 점진적으로 누적된다. 모든 작업은 design의 레이어 경계(Router→Service→Engine→Adapter/Repository→Model, 단방향)를 준수한다. 프로덕션 코드는 생성하지 않는다.

**구현 순서 원칙**
- 리팩터링 최소화: 스키마·인터페이스를 처음부터 확장 가능하게 정의(전 테이블 `user_id`, Protocol/Registry).
- 점진적 진행: 각 마일스톤 종료 시 데모 가능한 기능 추가.
- 항상 실행 가능: M0부터 `docker compose up`으로 기동, 이후 기능만 누적.
- 경계 준수: 하위 레이어는 상위를 import 하지 않음, Engine은 Protocol에만 의존.

### 개발 우선순위 (Development Priority)

| 우선 | 마일스톤 | 사유 |
|------|----------|------|
| P0 | M0 기반 | 모든 것의 전제(스키마·앱 팩토리·DI·마이그레이션) |
| P0 | M1 코어 CRUD | 채팅/소설의 데이터 토대 |
| P0 | M2 채팅 MVP | 제품 핵심 가치 1 (스트리밍 대화) |
| P1 | M3 기억 | 장편 지속성(차별점) |
| P1 | M4 소설 | 제품 핵심 가치 2 (이어쓰기) |
| P1 | M5 멀티공급자 | No Vendor Lock-in |
| P2 | M6 인증·배포 | 공유 가능·프로덕션화 |
| P2 | M7 견고화 | 품질·속성 테스트·관측 |

## Tasks

## 마일스톤 M0 — 기반 (Foundation)

- **Goal:** 모노레포·DB 스키마·앱 팩토리·DI·마이그레이션·헬스체크가 동작하는 실행 가능한 골격.
- **Scope:** design Phase 4(스키마), 5(폴더), 8.1/8.4/8.10(앱 팩토리·DI·설정), 14.2(default-user).
- **Dependencies:** 없음.
- **Deliverables:** `docker compose up`으로 기동되는 빈 FastAPI + Next.js, Alembic 초기 마이그레이션, `/healthz`/`/readyz`.
- **Estimated Complexity:** M (중).
- **Testing Requirements:** 마이그레이션 up/down 무손실, 헬스체크 200, 설정 로딩 단위 테스트.
- **Definition of Done:** 깨끗한 환경에서 단일 명령 기동, 헬스체크 통과, ORM 모델↔ERD(Phase 4) 1:1 일치, `user_id` 스코프·`ON DELETE` 정책·부분 유니크 제약 반영.

### Tasks
- [ ] 0.1 모노레포 스캐폴딩(`frontend/`, `backend/`, `docker-compose.yml`, `.env.example`). _Req: CON-1, NFR-3_
- [ ] 0.2 백엔드 의존성·`pyproject.toml`·`app/main.py` 앱 팩토리 + lifespan(엔진/레지스트리/스토리지/잡큐 초기화). _Req: design 8.1_
- [ ] 0.3 `app/config.py` Pydantic Settings(`DATABASE_URL`·`AUTH_ENABLED`·`APP_SECRET_KEY`·CORS·플래그). _Req: CON-3, CON-7_
- [ ] 0.4 `db/base.py` BaseMixin(UUID PK, timestamps), `db/session.py` async 엔진/세션 팩토리, SQLite WAL+`foreign_keys=ON` pragma. _Req: CON-2, CON-4_
- [ ] 0.5 ORM 모델 전체 정의(`models/*`)와 ERD 일치: User/OAuthAccount/World/Lorebook/LoreEntry/GlossaryTerm/Character/Persona/ChatSession/Message/Memory/Work/Chapter/WorkCharacter/ModelConfig/PromptTemplate/ProviderCredential. 비정규화 `user_id`(messages/memories/chapters), `parent_message_id`/`is_active`/`status`, `content_doc`/`content_text`/`version`, 부분 유니크(`is_default`). _Req: BR-2, BR-3, AC-NOVEL-4_
- [ ] 0.6 Alembic 초기 마이그레이션 + 명시적 `ON DELETE`(CASCADE/SET NULL) 정책. _Req: ERR-5, design 4.7_
- [ ] 0.7 `default-user` 멱등 시드(데이터 마이그레이션/startup). _Req: AC-AUTH-2_
- [ ] 0.8 미들웨어 스택(CORS·RequestId·Logging·AuthContext) + 예외 핸들러(6.1 코드 매핑) + `/healthz`·`/readyz`. _Req: ERR-1, ERR-2_
- [ ] 0.9 프론트엔드 Next.js App Router + Tailwind + shadcn/ui + PWA manifest 골격, API 클라이언트(`lib/api/client.ts`). _Req: CON-1, MOB-3_
- [ ] 0.10 `docker-compose.yml`(proxy/frontend/backend/volume) + entrypoint `alembic upgrade head` + `--workers 1`. _Req: NFR-3, CON-4_

---

## 마일스톤 M1 — 코어 CRUD (Core CRUD)

- **Goal:** 세계관·캐릭터·페르소나·작품·로어·용어집 CRUD를 UI까지 제공.
- **Scope:** Repository/Service/Schema/Router(Phase 6), 프론트 목록·폼·상세(Phase 7), 소프트 삭제·전파(4.7).
- **Dependencies:** M0.
- **Deliverables:** 캐릭터/세계관/소설/페르소나 생성·편집·삭제 UI 흐름, 태그/세계관 필터, 커서 페이지네이션.
- **Estimated Complexity:** L (대).
- **Testing Requirements:** Repository `_scoped` 단위 테스트(Property 1), 소유권 일치(Property 2), CRUD 통합 테스트, 소프트 삭제 전파 테스트.
- **Definition of Done:** 모든 코어 엔티티 CRUD 동작, 소유권 격리 검증, 빈 상태/로딩/에러 UX 구현, 3-Tap Rule 충족.

### Tasks
- [ ] 1.1 `repositories/base.py` BaseRepository[T](CRUD, `_scoped`, `_active`, 커서 페이지네이션). _Req: PERF-4, SEC-7_
- [ ] 1.2 World/Character/Novel 리포지토리 + `selectinload` 적재 정책. _Req: PERF-5_
- [ ] 1.3 Pydantic 스키마(`schemas/*`) 요청/응답 DTO + 검증(경계). _Req: ERR-2, AC-CHAR-1_
- [ ] 1.4 WorldService(로어북/로어/용어집 추가) + 트랜잭션 경계. _Req: AC-WORLD-1~5_
- [ ] 1.5 CharacterService(생성/수정/소프트삭제, INV-2 검증). _Req: AC-CHAR-2/4/5, Property 2_
- [ ] 1.6 PersonaService + NovelService(작품/챕터 CRUD, `index` 유일성, reorder). _Req: AC-NOVEL-1/4/5, Property 3_
- [ ] 1.7 라우터(`api/v1/worlds|characters|personas|novels`) + `get_current_user`/`get_db` 의존성. _Req: 6.2_
- [ ] 1.8 프론트: AppShell(반응형 셸·사이드바·하단 탭바), 공통 컴포넌트(EntityCard/Fab/FormField/AdvancedDisclosure/EmptyState/ListSkeleton/ConfirmDialog/ToastUndo). _Req: MOB-1/2, A11Y-1_
- [ ] 1.9 프론트: 캐릭터/세계관/소설/페르소나 목록·폼·상세 화면 + TanStack Query 훅. _Req: AC-CHAR-6, MOB-4/5_
- [ ] 1.10 소프트 삭제 전파(작품→챕터, 세계관→로어/world_id 해제). _Req: AC-WORLD-5, AC-CHAR-5_

---

## 마일스톤 M2 — 채팅 MVP (Streaming Chat)

- **Goal:** 캐릭터와의 SSE 스트리밍 대화. PromptEngine 최소 + OpenAI-compatible Adapter.
- **Scope:** Phase 9(Prompt 핵심), 13(OpenAICompat), 8.5.2/8.7(SSE·트랜잭션), 12(ChatEngine), 7.7.11(채팅 UI).
- **Dependencies:** M1.
- **Deliverables:** 채팅방 진입→첫인사→메시지 전송→토큰 스트리밍→메시지 확정, 재생성, 중단.
- **Estimated Complexity:** L (대).
- **Testing Requirements:** PromptEngine 예산 속성 테스트(Property 7), fake provider SSE 통합 테스트(token/done/error 순서), 단일 저장(Property 4), 멱등 전송.
- **Definition of Done:** TTFB 오버헤드 < 200ms(로컬 fake), 사용자 메시지 선저장, AI 메시지 정확히 1회 저장, 재생성이 새 행 생성, SSE 단절 시 부분 보존.

### Tasks
- [ ] 2.1 `engines/prompt/`(blocks·budget·tokenizer·engine) 조립 파이프라인(collect→resolve→inject→fit→finalize), 예산 계산(safety_ratio 차등), user/system 보호. _Req: AC-PROMPT-1~6, Property 6/7_
- [ ] 2.2 `engines/prompt` LoreScanner(history 기반 키워드 매칭) + Prompt Cache(LRU, memory.version). _Req: AC-WORLD-3, PERF-8_
- [ ] 2.3 `adapters/base.py` LLMProvider Protocol + `ModelCapability`, `adapters/registry.py` ProviderRegistry. _Req: AC-AI-1, FUT-4_
- [ ] 2.4 `adapters/openai_compat.py` 스트림/비스트림 + wire→중립 정규화 + 에러 매핑(429/5xx→6.1). _Req: AC-AI-3, ERR-2_
- [ ] 2.5 `engines/chat/engine.py`(assemble_turn·stream·regenerate). _Req: AC-CHAT-1/4_
- [ ] 2.6 ChatService SSE(T1 사용자 메시지 선저장→T3 AI 메시지 1회 저장→T4 요약 enqueue 자리), 단일 저장 가드(committed/idempotency). _Req: AC-CHAT-2/3, ERR-3/4, Property 4/9_
- [ ] 2.7 채팅 라우터(`POST /chats/{id}/messages` SSE, `/regenerate`, `before` 페이지네이션, `Idempotency-Key`). _Req: AC-CHAT-7, 6.5_
- [ ] 2.8 세션 단위 직렬화(인메모리 lock, MVP 단일 워커). _Req: AC-CHAT-6_
- [ ] 2.9 ModelConfig/Credential/PromptTemplate CRUD + capability 정합 검증 + 마스킹 응답. _Req: AC-AI-5/6, SEC-1/2/3, Property 8_
- [ ] 2.10 프론트: 채팅방(MessageBubble/StreamingBubble/ChatComposer), SSE 파서(`lib/api/sse.ts`) 누적·done·error·부분 보존, 중단 버튼. _Req: ERR-6, A11Y-3/8_
- [ ] 2.11 프론트: 설정 화면(모델·API Key 마스킹·기본 모델 지정, 고급 토글). _Req: MOB-5, SEC-2_

---

## 마일스톤 M3 — 기억 (Memory Engine)

- **Goal:** 토큰 임계 초과 시 롤링 요약으로 장기 기억 유지, 컨텍스트 주입.
- **Scope:** Phase 10(Memory), 8.8(JobQueue inproc), 공유 Summarizer.
- **Dependencies:** M2.
- **Deliverables:** 자동 백그라운드 요약, 키워드 검색·랭킹·예산 선택, 강제 요약 API.
- **Estimated Complexity:** M (중).
- **Testing Requirements:** needs_summary 임계 단위 테스트, `cover_up_to_message_id` 유효/단조 속성(Property 5), 요약 실패 시 대화 무영향, 멱등키 중복 방지.
- **Definition of Done:** 임계 초과 시 요약 생성·주입, 요약이 응답을 차단하지 않음, 요약 실패가 대화 플로우를 깨지 않음.

### Tasks
- [ ] 3.1 `core/jobs.py` JobQueue Protocol + InProcessJobQueue(멱등키·재시도·drain). _Req: BR-6, AC-MEM-4_
- [ ] 3.2 `engines/shared/summarizer.py` 공유 Summarizer(요약 프롬프트 구성, 요약 전용 ModelConfig 우선). _Req: AC-MEM-5, CON-6_
- [ ] 3.3 `engines/memory/`(engine·retriever[Keyword]·ranker) build_memory_context·needs_summary·maybe_summarize·rank. _Req: AC-MEM-1/2, Property 5_
- [ ] 3.4 메모리 컨텍스트를 PromptEngine memory 블록으로 연결(version 기반 캐시 무효화). _Req: PERF-8_
- [ ] 3.5 ChatService 요약 트리거(T4 enqueue) + `POST /chats/{id}/summarize`. _Req: AC-MEM-6_
- [ ] 3.6 누적 압축 상한(메타 요약) 정책. _Req: design 10.7_
- [ ] 3.7 프론트: "기억 정리 중" 비차단 토스트/배지. _Req: ERR-6_

---

## 마일스톤 M4 — 소설 이어쓰기 (Novel Engine)

- **Goal:** 이전 챕터 요약·로어·등장인물 컨텍스트로 SSE 이어쓰기, 챕터 자동 요약 환류.
- **Scope:** Phase 11(Novel), TipTap 에디터, 동시성(version).
- **Dependencies:** M2, M3(공유 Summarizer).
- **Deliverables:** 챕터 에디터(이어쓰기/중단), 자동저장, 챕터 요약 환류, reorder.
- **Estimated Complexity:** L (대).
- **Testing Requirements:** build_story_context 구성 단위 테스트, index 유일성 속성(Property 3), 조립 예산(Property 7), SSE 단절 부분 보존, 낙관적 동시성 409.
- **Definition of Done:** 이어쓰기 스트리밍·중단·부분 보존, content_doc/content_text 동기, 자동저장 vs 이어쓰기 경합 해결, 챕터 요약 후속 컨텍스트 반영.

### Tasks
- [ ] 4.1 `engines/novel/engine.py`(build_story_context·continue_chapter·summarize_chapter, Summarizer 주입). _Req: AC-NOVEL-3/6, CON-6_
- [ ] 4.2 PromptEngine Chapter Injection(prior_summaries·캐릭터·세계관·로어) + target_words→max_tokens clamp(CJK soft target). _Req: AC-NOVEL-3_
- [ ] 4.3 NovelService 이어쓰기 SSE(T1 로드→스트림→T3 content append·version CAS→백그라운드 요약). _Req: AC-NOVEL-6/7, ERR-3_
- [ ] 4.4 라우터 `POST /chapters/{id}/continue`(SSE), `PATCH /chapters/{id}`(If-Match version), `:reorder`. _Req: AC-NOVEL-5/7_
- [ ] 4.5 프론트: TipTapEditor + StreamingInsertion + ContinueWriteBar + 자동저장(version) + 챕터 Sheet/사이드패널. _Req: ERR-6, MOB-1_
- [ ] 4.6 소설 생성 Wizard(Step1~3) + 작품 상세·챕터 목록. _Req: AC-NOVEL-1/2_

---

## 마일스톤 M5 — 멀티 공급자 (Multi-Provider)

- **Goal:** Anthropic/Gemini/Ollama 어댑터로 No Vendor Lock-in 실현 + 폴백.
- **Scope:** Phase 13(어댑터·정규화·재시도/폴백·capability).
- **Dependencies:** M2.
- **Deliverables:** 4종+ 공급자 런타임 교체, system 처리 차등(message/param/instruction), 폴백 체인(옵션), `GET /providers`.
- **Estimated Complexity:** M (중).
- **Testing Requirements:** 어댑터별 wire→정규화 픽스처 테스트, 청크 분할 결합성 속성, 에러 매핑, 폴백 경로 통합 테스트.
- **Definition of Done:** 설정 변경만으로 공급자 전환, 모든 공급자 SSE 정규화 일치, 폴백 동작(설정 시), capability 정합 검증.

### Tasks
- [ ] 5.1 `adapters/anthropic.py`(system 파라미터 분리, content_block_delta 정규화). _Req: AC-AI-1/3_
- [ ] 5.2 `adapters/gemini.py`(systemInstruction/contents 매핑). _Req: AC-AI-1/3_
- [ ] 5.3 `adapters/ollama.py`(OpenAICompat 재사용, 로컬 base_url, 오프라인). _Req: NFR-8_
- [ ] 5.4 재시도/백오프 + 선택적 폴백 체인(스트림 시작 전 한정). _Req: AC-AI-4_
- [ ] 5.5 PromptEngine 중립 구조 ↔ Adapter system 렌더 차등 검증. _Req: AC-PROMPT-5_
- [ ] 5.6 `GET /providers` capability 메타 + 프론트 모델 선택 연동. _Req: AC-AI-6_

---

## 마일스톤 M6 — 인증·배포 (Auth & Deployment)

- **Goal:** Google OAuth + 로컬 모드 토글, 프로덕션 배포·PWA 마감.
- **Scope:** Phase 14(Auth), 15(Deployment), NFR-5(PWA).
- **Dependencies:** M1+ (인증 가드는 전 라우터 적용).
- **Deliverables:** OAuth 로그인/로그아웃/me, 로컬 모드, Docker Compose 프로덕션 프로파일, 백업 가이드.
- **Estimated Complexity:** M (중).
- **Testing Requirements:** JWT 발급/검증/만료 단위 테스트, fake OAuth login→callback→me→logout 통합, Property 8 마스킹, 로컬 모드 default-user 주입.
- **Definition of Done:** `AUTH_ENABLED` 토글 동작, PKCE/state/id_token 검증, TLS·단일워커 배포 문서화, Lighthouse PWA ≥ 90.

### Tasks
- [ ] 6.1 `auth/jwt.py`(access 발급/검증, refresh 회전, denylist). _Req: AC-AUTH-4_
- [ ] 6.2 `auth/oauth.py` + `auth/providers/google.py`(PKCE·state·id_token 검증, OAuthProvider Protocol). _Req: AC-AUTH-1/5, SEC-4_
- [ ] 6.3 `auth/router.py`(`/auth/{provider}/login|callback`, `/logout`, `/me`) + 토큰 암호화 저장. _Req: AC-AUTH-6, SEC-1_
- [ ] 6.4 `get_current_user` 인증/로컬 모드 분기 + 전 라우터 가드. _Req: AC-AUTH-2/3, SEC-7_
- [ ] 6.5 프론트: 로그인 화면(Google/로컬 모드), 토큰 관리, 401 리다이렉트. _Req: ERR-6_
- [ ] 6.6 배포: 프로덕션 compose 프로파일(Caddy TLS, PG 옵션, Ollama profile), 백업/복구 가이드, 헬스체크 와이어링. _Req: NFR-3/8, SEC-6_
- [ ] 6.7 PWA 마감(Service Worker 캐시·오프라인·아이콘) + Lighthouse 점검. _Req: MOB-3_

---

## 마일스톤 M7 — 견고화 (Hardening)

- **Goal:** 품질·속성 테스트·관측·복원력 강화.
- **Scope:** Phase 8.11(로깅), 8.15(테스트), 속성 1~9, 멱등/부분보존 강화.
- **Dependencies:** M2~M6.
- **Deliverables:** Hypothesis 속성 테스트 스위트, 구조화 로깅(request_id·마스킹), 회귀 스위트, JSON Export.
- **Estimated Complexity:** M (중).
- **Testing Requirements:** Property 1·3·4·5·7·8 속성 테스트, SSE 단절·재시도 통합, 마이그레이션 무손실, 시크릿 미기록 검증.
- **Definition of Done:** 전 Property 테스트 통과, 로그에 시크릿 부재, 회귀 체크리스트 통과, JSON Export 동작.

### Tasks
- [ ] 7.1 Hypothesis 속성 테스트(Property 1·3·4·5·7·8) 인코딩. _Req: 3.6 Properties_
- [ ] 7.2 구조화 로깅(JSON, request_id, 마스킹 규칙) + 로깅 포인트. _Req: SEC-3_
- [ ] 7.3 SSE 통합 테스트(token/done/error 순서, 단절 부분 보존) + 멱등 전송/재생성. _Req: Property 9_
- [ ] 7.4 JSON Export(작품/캐릭터/세계관 논리 백업, StorageBackend). _Req: NFR-6, FUT-6_
- [ ] 7.5 회귀 스위트 자동화(아래 체크리스트) + CI 통합. _Req: 전체_

---

## Task Dependency Graph

### 임계 경로 (Critical Path)

```
M0(스키마·앱팩토리·DI)
  └→ M1(Repository·Service·CRUD API)
       └→ M2(PromptEngine 최소 + OpenAICompat Adapter + SSE ChatService)
            ├→ M3(MemoryEngine + 백그라운드 요약)
            │     └→ M4(NovelEngine 이어쓰기, 요약 공유)
            └→ M5(추가 어댑터: Anthropic/Gemini/Ollama)
M6(인증·배포)·M7(견고화)는 M2 이후 부분 병행 가능
```
**임계 경로:** M0 → M1 → M2 → M3 → M4. (M5는 M2에만 의존, M4와 병행 가능)

### 마일스톤 의존 관계

| 마일스톤 | 의존 |
|----------|------|
| M0 | — |
| M1 | M0 |
| M2 | M1 |
| M3 | M2 |
| M4 | M2, M3(공유 Summarizer) |
| M5 | M2 |
| M6 | M1+ (전 라우터 가드) |
| M7 | M2~M6 |

### 실행 웨이브 정의 (Execution Waves)

```json
{
  "waves": [
    { "wave": 1, "milestone": "M0", "tasks": ["0.1","0.2","0.3","0.4","0.5","0.6","0.7","0.8","0.9","0.10"], "depends_on": [] },
    { "wave": 2, "milestone": "M1", "tasks": ["1.1","1.2","1.3","1.4","1.5","1.6","1.7","1.8","1.9","1.10"], "depends_on": ["M0"] },
    { "wave": 3, "milestone": "M2", "tasks": ["2.1","2.2","2.3","2.4","2.5","2.6","2.7","2.8","2.9","2.10","2.11"], "depends_on": ["M1"] },
    { "wave": 4, "milestone": "M3", "tasks": ["3.1","3.2","3.3","3.4","3.5","3.6","3.7"], "depends_on": ["M2"] },
    { "wave": 4, "milestone": "M5", "tasks": ["5.1","5.2","5.3","5.4","5.5","5.6"], "depends_on": ["M2"] },
    { "wave": 5, "milestone": "M4", "tasks": ["4.1","4.2","4.3","4.4","4.5","4.6"], "depends_on": ["M2","M3"] },
    { "wave": 5, "milestone": "M6", "tasks": ["6.1","6.2","6.3","6.4","6.5","6.6","6.7"], "depends_on": ["M1"] },
    { "wave": 6, "milestone": "M7", "tasks": ["7.1","7.2","7.3","7.4","7.5"], "depends_on": ["M2","M3","M4","M5","M6"] }
  ]
}
```

> 동일 `wave` 값은 병렬 실행 가능을 의미한다(M3∥M5, M4∥M6). `depends_on`은 선행 마일스톤 완료 조건이다.

### 병렬화 가능 작업 (Parallelizable Tasks)

| 병렬 그룹 | 작업 | 조건 |
|-----------|------|------|
| A (M1 내) | 1.8/1.9 프론트 UI ∥ 1.1~1.7 백엔드 CRUD | API 계약(Phase 6) 합의 후 |
| B | M5(추가 어댑터) ∥ M3/M4 | M2 완료 후, M5는 M3/M4와 독립 |
| C (M2 내) | 2.10/2.11 프론트 ∥ 2.1~2.9 백엔드 | SSE 프로토콜(6.4) 고정 후 |
| D | M6 인증 백엔드(6.1~6.4) ∥ 6.5 프론트 로그인 | JWT/쿠키 계약 후 |
| E | M7 7.1 속성 테스트 ∥ 7.2 로깅 ∥ 7.4 Export | 상호 독립 |

**직렬 필수(병렬 불가):** PromptEngine(2.1) → ChatService SSE(2.6) → MemoryEngine(3.x) → NovelEngine(4.x).

## Notes

### 회귀 테스트 체크리스트 (Regression Test Checklist)

매 마일스톤 종료 시 실행:
- [ ] R1 코어 CRUD(생성/조회/수정/소프트삭제) 전 엔티티 동작.
- [ ] R2 소유권 격리: 타 사용자 데이터 접근 차단(Property 1).
- [ ] R3 채팅 SSE: token→done 순서, 단절 시 부분 보존, 재생성이 새 행 생성(Property 4/9).
- [ ] R4 프롬프트 예산: 임의 입력에도 토큰 ≤ context_window(Property 7), user_message 보존.
- [ ] R5 메모리: 임계 초과 요약 생성·주입, `cover_up_to` 유효·단조(Property 5), 요약 실패 무영향.
- [ ] R6 소설: index 유일성(Property 3), 이어쓰기 부분 보존, 자동저장 vs 이어쓰기 409.
- [ ] R7 공급자 전환: 설정 변경만으로 4종 동작, 정규화 일치, 폴백.
- [ ] R8 인증: 로컬 모드 default-user, OAuth 로그인/로그아웃, 401 처리, 마스킹(Property 8).
- [ ] R9 마이그레이션: up/down 무손실, SQLite↔PG 스키마 동일.
- [ ] R10 기능 플래그 OFF 시 MVP 내비/성능 영향 0(7.15).
- [ ] R11 접근성: 키보드 순회·대비·터치 타깃·reduced-motion.
- [ ] R12 PWA: Lighthouse ≥ 90, 오프라인(Ollama) 동작.

### MVP 릴리스 계획 (Release Plan for MVP)

| 릴리스 | 포함 마일스톤 | 사용자 가치 | 게이트 |
|--------|---------------|-------------|--------|
| **0.1 Alpha (Local)** | M0+M1+M2 | 캐릭터 생성 + 스트리밍 채팅(로컬 모드) | R1~R4 통과 |
| **0.2 Beta (Memory+Novel)** | +M3+M4 | 장편 기억 + 소설 이어쓰기 | R5~R6 통과 |
| **0.3 RC (Multi-Provider)** | +M5 | 공급자 자유 교체 + 오프라인(Ollama) | R7 통과 |
| **1.0 MVP (Shareable)** | +M6+M7 | OAuth·배포·PWA·품질 | R1~R12 통과 |

**MVP 출시 기준(Go/No-Go):** 전 회귀 체크리스트(R1~R12) 통과 + Property 1~9 속성 테스트 통과 + `docker compose up` 단일 명령 기동 + Lighthouse PWA ≥ 90 + 시크릿 미노출 확인.

**MVP 제외(범위 외):** OOS-1~9(이미지·TTS/STT·RAG·관계도/타임라인·협업·클라우드 동기화·EPUB/PDF·Playground·그룹채팅).
