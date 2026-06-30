# Requirements Document
# AI Native Creative Workspace (`ai-creative-workspace`)

## Introduction

본 문서는 승인된 기술 설계서(`design.md`)에서 직접 도출된 정식 요구사항 명세다. EARS(Easy Approach to Requirements Syntax) 표기를 사용하며, 모든 요구사항은 고유 식별자를 가진다. 각 요구사항은 설계 문서의 Phase·불변식(INV)·정확성 속성(Property)과 추적성을 유지한다.

제품은 AI 캐릭터 채팅과 AI 장편 소설 창작을 단일 캐릭터·세계관 DB 위에 통합한 개인용 AI 네이티브 창작 워크스페이스다. 내부는 고도로 모듈화되어 있으나 최종 사용자 경험은 단순함을 최우선으로 한다.

## Glossary

| 용어 | 정의 |
|------|------|
| 캐릭터(Character) | 채팅 상대이자 소설 등장인물이 되는 통합 엔티티 |
| 세계관(World) | 채팅/소설이 공유하는 배경·로어·용어집의 원천 |
| 로어북/로어 항목(Lorebook/LoreEntry) | 키워드 트리거로 컨텍스트에 주입되는 설정 단위 |
| 페르소나(Persona) | 사용자가 채팅에서 연기하는 자아 |
| 작품/챕터(Work/Chapter) | 소설과 그 화(話) 단위 본문 |
| 메모리(Memory) | 대화 요약·사실·이벤트로 압축된 장기 기억 |
| Prompt Engine | 컨텍스트 블록을 우선순위·예산 기반으로 조립하는 엔진 |
| Memory Engine | 단기/장기 기억과 요약·검색을 관리하는 엔진 |
| Provider Adapter | LLM 공급자를 OpenAI-compatible 중립 인터페이스로 추상화 |
| SSE | 토큰 스트리밍에 사용하는 Server-Sent Events |
| Property 1~9 | design 3.6의 정확성 속성(불변식 검증 대상) |

### ID 규약 (ID Convention)

| 접두사 | 의미 |
|--------|------|
| `FR-*` | 기능 요구사항 (Functional Requirement) |
| `NFR-*` | 비기능 요구사항 (Non-Functional Requirement) |
| `AC-*` | 수용 기준 (Acceptance Criteria) — 각 FR 하위 |
| `BR-*` | 비즈니스 규칙 (Business Rule) |
| `CON-*` | 제약 (Constraint) |
| `ERR-*` | 에러 처리 요구사항 |
| `PERF-*` | 성능 요구사항 |
| `SEC-*` | 보안 요구사항 |
| `A11Y-*` | 접근성 요구사항 |
| `MOB-*` | 모바일 요구사항 |
| `FUT-*` | 향후 호환성 요구사항 |
| `OOS-*` | 범위 외 항목 (Out-of-Scope) |

## Requirements

### Requirement 1: 캐릭터 관리 (FR-CHAR)
**User Story:** 창작자로서, 채팅과 소설에서 공유되는 단일 캐릭터 엔티티를 만들고 관리하고 싶다. 그래야 설정을 한 곳에서 유지하며 흩어지지 않게 할 수 있다.

#### Acceptance Criteria
- **AC-CHAR-1:** WHEN 사용자가 캐릭터 생성을 요청하면 THE 시스템 SHALL 이름(필수)·아바타·첫인사·말투·성격·태그·세계관 연결(선택)을 가진 캐릭터를 생성한다.
- **AC-CHAR-2:** THE 시스템 SHALL 캐릭터에 대한 생성/조회/수정/소프트 삭제(CRUD)를 제공한다. (참조: design 4.7)
- **AC-CHAR-3:** WHERE 캐릭터가 세계관에 연결되면 THE 시스템 SHALL 채팅·소설 컨텍스트 조립 시 해당 세계관을 자동 주입한다.
- **AC-CHAR-4:** WHEN 캐릭터에 `world_id`가 설정되면 THE 시스템 SHALL 그 World가 동일 사용자 소유인지 검증한다(불일치 시 거부). (INV-2 / Property 2)
- **AC-CHAR-5:** WHEN 캐릭터가 소프트 삭제되면 THE 시스템 SHALL 기존 채팅 세션·작품 연결을 보존하고 "보관됨"으로 표시하며 신규 채팅 생성만 차단한다. (design 4.7)
- **AC-CHAR-6:** THE 시스템 SHALL 캐릭터 목록을 태그·세계관 필터와 커서 페이지네이션으로 제공한다.

### Requirement 2: 세계관 / 로어 관리 (FR-WORLD)
**User Story:** 창작자로서, 세계관·로어북·용어집을 구축하고 싶다. 그래야 채팅과 소설이 같은 무대를 공유하고 AI가 일관되게 기억할 수 있다.

#### Acceptance Criteria
- **AC-WORLD-1:** THE 시스템 SHALL 세계관(이름·설명·시대·종족·국가·금기)에 대한 CRUD를 제공한다.
- **AC-WORLD-2:** THE 시스템 SHALL 로어북과 로어 항목(키워드 트리거·내용·우선순위·스캔 깊이·활성 여부)을 관리한다.
- **AC-WORLD-3:** WHEN 대화/집필 컨텍스트의 최근 `scan_depth` 메시지에 로어 키워드가 등장하면 THE 시스템 SHALL 해당 로어 항목을 우선순위 순으로 프롬프트에 주입한다. (design 9.11.2)
- **AC-WORLD-4:** THE 시스템 SHALL 세계관 용어집(GlossaryTerm) CRUD를 제공한다.
- **AC-WORLD-5:** WHEN 세계관이 소프트 삭제되면 THE 시스템 SHALL 로어북·로어 항목·용어집을 연쇄 숨김 처리하고, 연결된 캐릭터/작품의 `world_id`를 해제(`null`)하여 채팅·집필이 계속 가능하게 한다. (design 4.7)

### Requirement 3: 소설 창작 (FR-NOVEL)
**User Story:** 창작자로서, 작품·챕터를 만들고 AI 이어쓰기로 장편을 집필하고 싶다. 그래야 일관된 서사를 효율적으로 확장할 수 있다.

#### Acceptance Criteria
- **AC-NOVEL-1:** THE 시스템 SHALL 작품(Work) 생성·조회·수정·소프트 삭제와 챕터 생성·조회·수정·삭제를 제공한다.
- **AC-NOVEL-2:** THE 시스템 SHALL 작품에 등장인물(캐릭터)·세계관을 연결한다(`WORK_CHARACTER`, `world_id`).
- **AC-NOVEL-3:** WHEN 사용자가 "이어쓰기"를 요청하면 THE 시스템 SHALL 이전 챕터 요약 + 관련 로어 + 등장인물/세계관 설정을 컨텍스트로 다음 분량을 SSE 스트리밍 생성한다. (FR-NOVEL-3, design 11.6)
- **AC-NOVEL-4:** THE 시스템 SHALL 동일 `work_id` 내 챕터 `index`의 유일성을 보장한다(연속성은 강제하지 않음). (INV-3 / Property 3 / design 4.8)
- **AC-NOVEL-5:** WHEN 챕터 삭제 또는 재정렬이 요청되면 THE 시스템 SHALL `PATCH /works/{id}/chapters:reorder`로 `index`를 원자적으로 재계산한다. (design 4.8)
- **AC-NOVEL-6:** WHEN 이어쓰기가 정상 종료되면 THE 시스템 SHALL 평문 토큰을 TipTap 문서 노드(`content_doc`)에 반영하고 `content_text`·`word_count`를 동기 갱신하며 백그라운드로 `chapter.summary`를 생성한다. (design 11.6, 11.9)
- **AC-NOVEL-7:** WHEN 자동저장과 이어쓰기 확정이 경합하면 THE 시스템 SHALL `version` 기반 낙관적 동시성으로 충돌을 감지하고 `409 CONFLICT`로 응답한다. (design 6.5, 11.6)

### Requirement 4: AI 채팅 (FR-CHAT)
**User Story:** 창작자로서, 캐릭터와 페르소나·세계관·기억을 조합한 스트리밍 대화를 하고 싶다. 그래야 몰입감 있는 캐릭터 채팅을 경험할 수 있다.

#### Acceptance Criteria
- **AC-CHAT-1:** WHEN 사용자가 메시지를 전송하면 THE 시스템 SHALL 선택된 캐릭터·페르소나·세계관·로어·기억을 조합해 SSE 스트리밍 응답을 생성한다.
- **AC-CHAT-2:** THE 시스템 SHALL 사용자 메시지를 스트리밍 시작 전에 영속화하여 단절 시에도 입력이 유실되지 않게 한다. (design 8.5.2 T1 / Property 9)
- **AC-CHAT-3:** WHEN AI 응답 스트림이 정상 종료되면 THE 시스템 SHALL AI 메시지를 정확히 1회 저장한다(불변, append-only). (INV-4 / Property 4)
- **AC-CHAT-4:** WHEN 사용자가 재생성을 요청하면 THE 시스템 SHALL 직전 assistant 메시지를 `is_active=false`로 표시하고 동일 `parent_message_id`로 새 메시지를 생성한다(기존 메시지 보존). (design 4.6, 12.9)
- **AC-CHAT-5:** THE 시스템 SHALL 세션 생성 시 캐릭터 첫인사(greeting)를 첫 assistant 메시지로 시드한다.
- **AC-CHAT-6:** WHEN 동일 세션에 동시 스트리밍 요청이 들어오면 THE 시스템 SHALL 요청을 직렬화하거나 `409 CONFLICT`로 응답하여 메시지 순서를 보장한다. (design 12.12)
- **AC-CHAT-7:** THE 시스템 SHALL 메시지 목록을 `before` 커서 역방향 페이지네이션으로 제공한다. (design 6.5)

### Requirement 5: Memory Engine (FR-MEM)
**User Story:** 창작자로서, 장편 대화에서도 캐릭터가 과거를 기억하길 원한다. 그래야 서사의 지속성이 유지된다.

#### Acceptance Criteria
- **AC-MEM-1:** WHEN 미요약 메시지 토큰이 임계치를 초과하면 THE 시스템 SHALL 오래된 메시지를 요약하여 장기 메모리(Memory)로 압축한다. (FR-MEM-1)
- **AC-MEM-2:** THE 시스템 SHALL 컨텍스트 조립 시 관련 메모리를 검색(MVP: 키워드)·랭킹(recency+relevance+priority)하여 예산 내에서 주입한다. (FR-MEM-2, design 10.8~10.9)
- **AC-MEM-3:** WHEN 요약이 저장되면 THE 시스템 SHALL `cover_up_to_message_id`가 동일 세션의 실재 메시지를 가리키고 단조 증가함을 보장한다. (INV-5 / Property 5)
- **AC-MEM-4:** THE 시스템 SHALL 요약 작업을 백그라운드(비차단)로 수행하여 채팅 응답 지연에 영향을 주지 않는다. (design 8.8, NFR-1)
- **AC-MEM-5:** WHERE 사용자가 요약 전용 ModelConfig를 지정하면 THE 시스템 SHALL 요약 생성에 그 모델을 사용한다(미지정 시 채팅 모델 폴백). (design 10.7)
- **AC-MEM-6:** WHEN 사용자가 강제 요약을 요청하면(`POST /chats/{id}/summarize`) THE 시스템 SHALL 즉시 요약을 트리거한다.

### Requirement 6: Prompt Engine (FR-PROMPT)
**User Story:** 시스템 통합자로서, 흩어진 컨텍스트를 우선순위 기반으로 조립하고 토큰 예산을 넘지 않게 하고 싶다. 그래야 어떤 모델에서도 안정적으로 동작한다.

#### Acceptance Criteria
- **AC-PROMPT-1:** THE 시스템 SHALL 프롬프트 템플릿을 변수 치환(`{{char}}` 등)·블록 조립 방식으로 관리하며, 미해소 변수는 공백으로 안전 치환한다. (design 9.10)
- **AC-PROMPT-2:** THE 시스템 SHALL `contextWindow ≥ maxTokens`를 검증한다(위반 시 거부). (INV-6 / Property 6)
- **AC-PROMPT-3:** THE 시스템 SHALL 조립 결과 토큰 수가 `contextWindow` 이하가 되도록 우선순위 기반 truncation/drop을 수행한다. (INV-7 / Property 7)
- **AC-PROMPT-4:** THE 시스템 SHALL `user_message`와 system 블록을 truncation에서 보호한다(절대 보존). (design 9.9)
- **AC-PROMPT-5:** THE 시스템 SHALL 공급자 중립 `messages[]` 구조를 산출하고, 공급자별 system 처리는 Adapter에 위임한다. (design 9.13)
- **AC-PROMPT-6:** WHERE 정확한 토크나이저가 없는 공급자이면 THE 시스템 SHALL 근사 카운트 + 상향된 safety margin을 적용한다. (design 9.7)

### Requirement 7: Provider Adapter (FR-AI)
**User Story:** 창작자로서, LLM 공급자를 코드 변경 없이 교체하고 싶다. 그래야 특정 공급자에 종속되지 않는다(No Vendor Lock-in).

#### Acceptance Criteria
- **AC-AI-1:** THE 시스템 SHALL OpenAI-compatible 중립 인터페이스(`LLMProvider`)로 다중 공급자(OpenAI/Anthropic/Gemini/DeepSeek/Qwen/Ollama/OpenRouter)를 추상화한다. (FR-AI-1)
- **AC-AI-2:** WHEN 사용자가 모델 설정을 변경하면 THE 시스템 SHALL 코드 변경 없이 런타임에 공급자를 교체한다. (FR-AI-2)
- **AC-AI-3:** THE 시스템 SHALL 각 공급자의 스트림 wire 포맷을 Phase 6.4 중립 토큰 델타로 정규화한다. (design 13.6)
- **AC-AI-4:** WHEN 공급자가 일시 오류(429/5xx/timeout)를 반환하면 THE 시스템 SHALL 지수 백오프 재시도를 수행하고(스트림 시작 전 한정) 선택적 폴백 체인을 적용한다. (design 13.8)
- **AC-AI-5:** WHEN ModelConfig 저장 시 THE 시스템 SHALL 어댑터 capability와 정합성을 검증한다(`context_window` 초과 입력 거부 또는 기본값 채움). (design 13.10)
- **AC-AI-6:** THE 시스템 SHALL 지원 공급자/모델 메타데이터를 `GET /providers`로 제공한다.

### Requirement 8: 인증 (FR-AUTH)
**User Story:** 사용자로서, 로컬에서는 로그인 없이 즉시 쓰고, 공유 배포 시에는 Google 로그인을 쓰고 싶다. 그래야 개인용·멀티유저를 모두 지원한다.

#### Acceptance Criteria
- **AC-AUTH-1:** THE 시스템 SHALL Authorization Code + PKCE 기반 Google OAuth 2.0 로그인을 제공한다. (FR-AUTH-1, design 14.7)
- **AC-AUTH-2:** WHERE `AUTH_ENABLED=False`이면 THE 시스템 SHALL 시드된 `default-user`를 주입하여 로컬 단일 사용자 모드로 동작한다. (FR-AUTH-2, design 14.2/14.9)
- **AC-AUTH-3:** THE 시스템 SHALL 인증 모듈을 환경변수 하나(`AUTH_ENABLED`)로 코어 변경 없이 활성/비활성한다.
- **AC-AUTH-4:** THE 시스템 SHALL 짧은 수명 access JWT와 HttpOnly·Secure 쿠키 refresh 토큰(회전)을 발급하며, 로그아웃 시 refresh를 폐기한다. (design 14.4)
- **AC-AUTH-5:** THE 시스템 SHALL OAuth `state`(CSRF) 검증과 id_token 서명/`iss`/`aud`/`exp` 검증을 수행한다. (design 14.7)
- **AC-AUTH-6:** THE 시스템 SHALL `GET /auth/me`로 현재 사용자를, 인증 실패 시 `401`을 반환한다.

### Requirement 9: AI 이미지 (FR-IMG, 확장)
**User Story:** 창작자로서, 향후 캐릭터/장면 이미지를 생성하고 싶다.

#### Acceptance Criteria
- **AC-IMG-1:** THE 시스템 SHALL 이미지 생성을 위한 별도 `ImageProvider` 어댑터 seam을 제공한다(확장 단계, 기능 플래그). (design 13.12)

---

## 2. 비기능 요구사항 (Non-Functional Requirements)

| ID | 분류 | 요구사항 | 검증 |
|----|------|----------|------|
| NFR-1 | 성능 | 채팅 첫 토큰 지연(TTFB) < 2s(공급자 응답 제외 시스템 오버헤드 < 200ms) | PERF-1 |
| NFR-2 | 비용 | API 사용료 외 인프라 비용 0원(셀프 호스팅 + SQLite + 로컬 스토리지) | — |
| NFR-3 | 이식성 | 단일 `docker compose up`으로 전체 기동 | design 15 |
| NFR-4 | 확장성 | DB·인증·공급자 모듈 교체가 코어 변경 없이 가능 | FUT-* |
| NFR-5 | 모바일 | Lighthouse PWA 점수 ≥ 90, 모바일 우선 반응형 | MOB-* |
| NFR-6 | 데이터 소유 | 전체 데이터 로컬 저장 + Export(JSON/EPUB/PDF, 확장) | design 15.9 |
| NFR-7 | 보안 | API Key는 백엔드에서만 보관, FE 노출 금지 | SEC-* / Property 8 |
| NFR-8 | 오프라인 | Ollama 사용 시 완전 오프라인 동작 | design 15 |

---

## 3. 수용 기준 요약 (Acceptance Criteria — 추적성)

본 명세의 모든 `AC-*`는 위 기능 요구사항 하위에 직접 명시된다. 각 AC는 설계의 정확성 속성(Property 1~9, design 3.6)과 불변식(INV-1~7, design 3.4)에 추적 가능하다. 속성 기반 테스트(Hypothesis)로 Property 1·3·4·5·7·8을 검증하고, 통합 테스트로 SSE 순서/단절(Property 9)을 검증한다.

---

## 4. 비즈니스 규칙 (Business Rules)

- **BR-1:** 캐릭터·세계관·작품·채팅은 모두 채팅과 소설에서 **단일 진실 공급원**을 공유한다(통합 플라이휠). (design 1.1, 3.5)
- **BR-2:** 모든 도메인 엔티티는 정확히 하나의 사용자에 소속된다. (INV-1 / Property 1)
- **BR-3:** 메시지는 불변이며, 편집/재생성은 새 행으로만 표현한다. (INV-4 / 4.6)
- **BR-4:** 챕터 표시 순번("N화")은 정렬 기반 표시값이며 저장 `index`와 분리한다. (4.8)
- **BR-5:** 평문 API Key/토큰은 어떤 응답·로그에도 노출되지 않는다(항상 마스킹 `sk-...abcd`). (Property 8)
- **BR-6:** 요약은 사용자 대화 흐름을 절대 차단하지 않는다(백그라운드·격리·실패 무영향). (8.8, 10.13)
- **BR-7:** 신규 고급/확장 기능은 MVP 최상위 내비게이션을 변경하지 않는다(기능 플래그·슬롯로만 진입). (7.15)

---

## 5. 제약 (Constraints)

- **CON-1:** 백엔드는 FastAPI + SQLAlchemy 2.0 + Alembic, 프론트엔드는 Next.js(App Router) + TypeScript + Tailwind + shadcn/ui를 사용한다. (design 2.5)
- **CON-2:** 원시 SQL 금지 — 모든 쿼리는 SQLAlchemy ORM/Core 표현식으로 작성(방언 격리). (4.4)
- **CON-3:** DB 전환은 `DATABASE_URL` 환경변수 하나로 수행(SQLite ↔ PostgreSQL). (4.4, 8.6)
- **CON-4:** SQLite 사용 시 단일 워커로 구동한다(단일 라이터 제약). (15.3)
- **CON-5:** 레이어드 의존성은 단방향이다: Router → Service → Engine → Adapter/Repository → Model. 역방향 import 금지. (2.3)
- **CON-6:** Engine은 Adapter/Repository(읽기) Protocol에만 의존한다. 공유 `Summarizer`는 독립 컴포넌트로 두어 Engine→Engine 직접 import를 금지한다. (11.9)
- **CON-7:** 시크릿은 커밋 금지(`.env.example`만 제공). `APP_SECRET_KEY` 분실 시 암호화 데이터 복호 불가. (4.5, 15.3)

---

## 6. 에러 처리 요구사항 (Error Handling Requirements)

- **ERR-1:** THE 시스템 SHALL RFC 7807 유사 구조의 표준 에러 응답(`code`/`message`/`details`)을 반환한다. (6.1)
- **ERR-2:** THE 시스템 SHALL 에러를 HTTP 코드에 매핑한다: 400 VALIDATION_ERROR / 401 UNAUTHENTICATED / 403 FORBIDDEN / 404 RESOURCE_NOT_FOUND / 409 CONFLICT / 422 UNPROCESSABLE / 429 PROVIDER_RATE_LIMIT(+Retry-After) / 502 PROVIDER_ERROR. (6.1, 6.5)
- **ERR-3:** WHEN 스트리밍 중 오류가 발생하면 THE 시스템 SHALL `event: error`(code/message)로 전달하고 부분 토큰을 best-effort로 보존한다. (6.4, 8.7.4 / Property 9)
- **ERR-4:** WHEN SSE 연결이 단절되면 THE 시스템 SHALL 누적 부분 메시지를 `status="partial"`로 저장하고 공급자 스트림을 닫는다. (8.7.4)
- **ERR-5:** THE 시스템 SHALL 소유권 불일치를 `404`(존재 은닉) 또는 `403`으로 처리한다. (8.12)
- **ERR-6:** THE 프론트엔드 SHALL 폼 검증·네트워크·인증 만료·공급자 한도/오류·SSE 끊김·자동저장 실패에 대해 화면별 복구 UX(재시도/재생성/부분 보존)를 제공한다. (7.13)
- **ERR-7:** WHEN 공급자 응답이 비어 있으면 THE 시스템 SHALL `done(token_count=0, finish_reason="empty")`로 종료하고 재생성을 안내한다. (12.11)

---

## 7. 성능 요구사항 (Performance Requirements)

- **PERF-1:** 채팅 첫 토큰까지 시스템 오버헤드 < 200ms(공급자 시간 제외). (NFR-1)
- **PERF-2:** SSE 스트리밍 중 DB 세션을 점유하지 않는다(커넥션 풀 보호). (8.5.2)
- **PERF-3:** 메모리 요약은 백그라운드로 처리하여 응답 지연에 영향이 없다. (8.8)
- **PERF-4:** 목록 조회는 커서 기반·결정적 정렬(`created_at,id`)과 FK/`user_id` 인덱스를 사용한다. (4.3, 8.3.2)
- **PERF-5:** 연관 적재는 `selectinload`/`joinedload`로 N+1을 회피한다. (8.16)
- **PERF-6:** 공급자 동시 호출은 `Semaphore(PROVIDER_MAX_CONCURRENCY)`로 제한한다. (8.6.2)
- **PERF-7:** 토큰 카운팅 등 블로킹 작업은 스레드풀로 오프로딩한다. (8.6.1)
- **PERF-8:** Prompt Cache(블록 해시 + memory.version)로 반복 조립 재계산을 회피한다. (9.11.3)

---

## 8. 보안 요구사항 (Security Requirements)

- **SEC-1:** THE 시스템 SHALL `provider_credentials.api_key_enc`·`oauth_accounts.*_token_enc`를 애플리케이션 레벨 대칭 암호화(Fernet/AES-GCM, `APP_SECRET_KEY`)로 저장한다. (4.5, 14)
- **SEC-2:** THE 시스템 SHALL 복호화를 백엔드 메모리 내 공급자 호출 시점에만 수행하고 FE에 평문을 전달하지 않는다. (NFR-7 / Property 8)
- **SEC-3:** THE 시스템 SHALL API 응답·로그에서 평문 키/토큰/프롬프트 본문/사용자 메시지 본문을 기록하지 않는다(마스킹/길이만). (8.11)
- **SEC-4:** THE 시스템 SHALL OAuth에서 `state`(CSRF)·PKCE·redirect_uri 화이트리스트·id_token 검증을 적용한다. (14.7)
- **SEC-5:** THE 시스템 SHALL CORS 허용 Origin을 `CORS_ORIGINS`로 제한한다(프로덕션 와일드카드 금지). (8.14.3)
- **SEC-6:** THE 시스템 SHALL 외부 노출 배포 시 `AUTH_ENABLED=True`와 TLS를 요구한다. (14.1, 15.3)
- **SEC-7:** THE 시스템 SHALL 모든 쿼리를 `user_id`로 스코프하여 교차 사용자 접근을 차단한다. (Property 1)
- **SEC-8:** THE 시스템 SHALL 업로드 파일을 크기·MIME·매직바이트로 검증한다. (8.9.3)

---

## 9. 접근성 요구사항 (Accessibility Requirements)

- **A11Y-1:** THE 시스템 SHALL 모든 인터랙션을 키보드로 순회 가능하게 하고 Dialog/Sheet에 포커스 트랩을 적용한다. (7.14)
- **A11Y-2:** THE 시스템 SHALL `focus-visible` 가시 포커스 링(`--ring` 2px)을 제공한다.
- **A11Y-3:** THE 채팅 메시지 영역 SHALL `role="log" aria-live="polite"`로 스트리밍을 낭독 지원한다.
- **A11Y-4:** THE 시스템 SHALL 본문 대비 ≥ 4.5:1, 큰 텍스트/아이콘 ≥ 3:1을 충족한다.
- **A11Y-5:** THE 시스템 SHALL 터치 타깃 최소 44×44px, 항목 간격 ≥ 8px를 보장한다.
- **A11Y-6:** WHERE `prefers-reduced-motion`이면 THE 시스템 SHALL 스트리밍 커서 점멸·전환 애니메이션을 비활성화한다.
- **A11Y-7:** THE 폼 SHALL `<label htmlFor>` 연결과 오류 `aria-invalid`/`aria-describedby`를 제공한다.
- **A11Y-8:** THE 채팅 입력 SHALL `Enter` 전송 / `Shift+Enter` 줄바꿈 / `Esc` 중단을 지원한다.

> 완전한 WCAG 준수는 보조기술 실사용 테스트와 전문가 검토가 필요하다. 본 명세는 구현 기준을 제시한다.

---

## 10. 모바일 요구사항 (Mobile Requirements)

- **MOB-1:** THE 시스템 SHALL 360px 폭부터 설계된 모바일 우선 반응형 레이아웃을 제공한다. (7.6)
- **MOB-2:** THE 시스템 SHALL 모바일에서 고정 하단 탭 바(홈·캐릭터·소설·채팅·더보기)를 제공한다. (7.2.2)
- **MOB-3:** THE 시스템 SHALL 설치형 PWA(manifest + Service Worker)로 동작하고 Lighthouse PWA ≥ 90을 충족한다. (NFR-5)
- **MOB-4:** THE 시스템 SHALL 어떤 핵심 작업도 홈에서 3탭 이내 도달하게 한다(3-Tap Rule). (7.0)
- **MOB-5:** THE 시스템 SHALL 고급 옵션을 Progressive Disclosure(고급 토글/Drawer)로 숨긴다. (7.0)
- **MOB-6:** THE 시스템 SHALL iOS safe-area inset을 반영한 56px 탭 바를 사용한다.

---

## 11. 향후 호환성 요구사항 (Future Compatibility Requirements)

- **FUT-1:** THE 시스템 SHALL 멀티유저 활성화를 기존 `user_id` FK + `AUTH_ENABLED=True`로 코어 변경 없이 지원한다. (8.17)
- **FUT-2:** THE 시스템 SHALL RAG 임베딩 검색을 `Retriever` Protocol + `MEMORY.embedding`(nullable) 옵션 컬럼으로 스키마 무파괴 추가한다. (10.12)
- **FUT-3:** THE 시스템 SHALL StorageBackend(local→S3)·JobQueue(inproc→Celery/ARQ)를 Protocol 교체로 확장한다. (8.9, 8.8)
- **FUT-4:** THE 시스템 SHALL 신규 LLM/OAuth 공급자를 레지스트리 등록만으로 추가한다. (8.17, 13.10, 14.17)
- **FUT-5:** THE 시스템 SHALL Story Timeline·관계도·Lore Consistency·Prompt/Model Playground·Cost Dashboard·Auto Backup을 기능 플래그·슬롯로 추가하며 MVP 내비를 불변 유지한다. (7.15)
- **FUT-6:** THE 시스템 SHALL EPUB/PDF/JSON Export를 StorageBackend + 챕터 합성 seam으로 확장한다. (11.15, NFR-6)

---

## 12. 범위 외 항목 (Out-of-Scope — MVP 제외)

- **OOS-1:** AI 이미지 생성 (확장)
- **OOS-2:** TTS/STT 음성 (확장)
- **OOS-3:** RAG 임베딩 검색 (MVP는 키워드 검색)
- **OOS-4:** 관계도/타임라인 시각화 (확장)
- **OOS-5:** 멀티유저 협업·실시간 다중기기 동기화 (확장)
- **OOS-6:** 클라우드 동기화 (확장)
- **OOS-7:** EPUB/PDF Export (MVP는 JSON Export까지)
- **OOS-8:** 멀티모델 비교/Playground (확장)
- **OOS-9:** 그룹 채팅(다중 캐릭터 동시) (확장)

---

## 13. 추적성 매트릭스 (Traceability — 요약)

| 요구사항 | 설계 Phase | 불변식/속성 |
|----------|-----------|-------------|
| FR-CHAR | 3, 4, 6, 7 | INV-1/2, Property 1/2 |
| FR-WORLD | 3, 4, 9.11 | — |
| FR-NOVEL | 4.6/4.8, 11 | INV-3, Property 3 |
| FR-CHAT | 8.5/8.7, 12 | INV-4, Property 4/9 |
| FR-MEM | 8.8, 10 | INV-5, Property 5 |
| FR-PROMPT | 9 | INV-6/7, Property 6/7 |
| FR-AI | 13 | — |
| FR-AUTH | 14 | Property 1 |
| SEC-* | 4.5, 8.11, 8.14, 14 | Property 8 |
