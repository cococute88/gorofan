# Implementation Plan: AI Native Creative Workspace (Architecture Frozen 기준 재확정)

- **재확정 시각:** 2026-07-27 · **기준 커밋:** `bdc2cfb` (로컬 `main` == `origin/main`)
- **상태 근거 문서:** [`implementation-status.md`](./implementation-status.md) — 파일 존재가 아닌 *실행 코드 경로 · API 노출 · 통과 테스트*로 판정한 검증 스냅샷.
- **단일 진실 공급원(우선순위):** `docs/architecture/adr/*` → `docs/architecture/rfc/RFC-001` → `RFC-002…RFC-012` → `docs/architecture/README.md` → **본 문서** → (참고 이력) `design.md` · `requirements.md`.

> **이 문서의 위상 변경.** 이전 판(구 M0~M7 계획)은 substrate 구축 계획이었고 대부분 달성되었다. Architecture Frozen(ADR-001~020, RFC-001~012) 이후에는 **구 계획의 미체크 박스를 그대로 따르면 중복 구현·아키텍처 위반이 발생한다.** 구 계획의 검증된 상태는 §1에 보존하고, 앞으로의 작업은 §3의 Architecture Phase 1~6을 따른다. 구 `design.md`와 ADR/RFC가 충돌하면 **ADR/RFC가 이긴다.**

## 불변식 (모든 작업이 지켜야 함)

1. **Store → Analyst → Writer + Bench** 3동사 + 1정직성 장치. 새 "엔진"을 만들지 않는다.
2. **Everything is Entry.** 새 지식 종류 = 새 `type` 문자열. **도메인별 신규 knowledge 테이블 금지.**
3. **Character DNA ≠ Relationship ≠ Story Event.** 정체성/관계/사건은 분리된 집으로 남는다.
4. **Relationship = Shared Narrative State.** 어느 캐릭터의 DNA도, Writer의 소유도 아니다.
5. **Story Bible = Entry Store의 work-scoped canonical view.** **별도 Bible 스토어/테이블을 만들지 않는다.**
6. **AI는 canon을 직접 수정하지 않는다.** 모든 AI-inferred canon 변경은 **Review Card gate**를 통과한다.
7. **Retrieval(선택)과 Context Assembly(구성)는 분리**된다. retrieval은 messages[]를 만들지 않는다.
8. **Prompt body는 저장소의 versioned file asset.** DB에 프롬프트 body를 저장하지 않는다(사용자는 *입력*만 커스터마이즈).
9. **Bench는 개발자 전용** 회귀 도구다. 사용자 출력을 게이팅하지 않는다.
10. **Character Chat은 독립 제품**이며 Writer 하위 기능이 아니다.
11. **chat-private `Memory`와 공유 Entry Store를 합치지 않는다.** 두 결과는 Context Assembly에서 별도 블록으로만 만난다.
12. **파괴적 마이그레이션 금지.** frozen `0001` 수정 금지, 기존 기능/데이터 제거 금지. 새 구조는 항상 **additive**.
13. **기존 substrate를 재작성하지 않는다.** PromptEngine·MemoryEngine·NovelEngine·어댑터·인증·PWA는 새 Architecture가 감싸거나 흡수한다.

---

## 1. 구 M0~M7 계획 — 검증된 최종 상태 (아카이브)

`[x]` 완료 · `[~]` 부분 완료 · `[ ]` 미구현. 상세 근거는 `implementation-status.md` §5.

- [x] **M0 기반** — 앱 팩토리+lifespan, 설정, DB 세션/베이스, ORM 전량, `0001_initial`, `/healthz`·`/readyz`, 미들웨어, compose, Next.js+PWA 골격.
- [x] **M1 코어 CRUD** — BaseRepository(`_scoped`/`_active`/커서), World/Character/Persona/Work/Chapter 서비스·라우터·스키마, 프론트 CRUD 화면, 소프트 삭제 전파.
- [~] **M2 채팅 MVP** — PromptEngine·어댑터·ChatEngine·SSE ChatService·멱등·마스킹·프론트 완료. **잔여: 2.2 Prompt Cache(LRU, memory.version).**
- [~] **M3 기억** — JobQueue·공유 Summarizer·MemoryEngine·memory 블록 연결 완료. **잔여: 3.6 누적 압축 상한(메타 요약), 3.7 프론트 비차단 배지.**
- [x] **M4 소설 이어쓰기** — single-pass 이어쓰기 SSE·version CAS·TipTap·위저드. ※ 이는 **Writer(RFC-004) 완료가 아니다** → §3.3.
- [x] **M5 멀티 공급자** — Anthropic/Gemini/Ollama + 재시도·폴백 + capability.
- [~] **M6 인증·배포** — OAuth/JWT/로컬 모드/컨테이너/PWA 완료. **잔여: refresh 회전·denylist, Lighthouse 실측.**
- [~] **M7 견고화** — 구조화 로깅·SSE 통합·CI·Property(예산) 완료. **잔여: 7.4 JSON Export, 속성 테스트 커버리지 확대.**

### 1.1 구 계획 중 **폐기된** 방향 (다시 착수하지 말 것)

| 구 계획/폐기 노선 | 폐기 근거 | 대체 경로 |
|---|---|---|
| Story Bible **Engine** / 별도 bible 테이블 (`0002_story_bible`) | ADR-004, RFC-005 | Entry Store의 work-scoped canonical **view** (§3.4) |
| Reference Intelligence **Engine** (`engines/reference/*`, `models/reference.py`, `0003_reference`) | ADR-002 §4-B, ADR-008, RFC-008 | **단일 Analyst** + facet 프롬프트 (§3.2) |
| Planning **Engine** (`engines/planning/*`, `models/planning.py`) | ADR-002, ADR-005 | Writer의 **plan stage** + 프롬프트 파일 (§3.3) |
| per-library 테이블(dialogue/emotion/plot 라이브러리 등) | ADR-003 §2·§4-B | Entry `type` 문자열 추가 |
| DB `PromptTemplate`에 creative prompt body 저장 확대 | ADR-013 | 저장소 prompt asset (§3.1 P1-3/P1-4) |

> 위 폐기 노선의 실제 코드가 `stash@{1}`(브랜치 `codex/new`)에 5,081줄 남아 있다. **병합 금지.** 이력 참고용으로만 둔다.

### 1.2 계승되는 것

- 회귀 체크리스트 **R1~R12**(구 §Notes)는 계속 유효하며, 아래 각 작업의 "회귀 테스트" 항목에서 참조한다.
- Property 1~9 속성 테스트 목록도 계속 유효하다.

---

## 2. Architecture Phase 로드맵

```
Phase 1  잔여 Core 정리          ← 지금 여기 (약 65%)
  └→ Phase 2  Analyst (text → proposed Entries)
       ├→ Phase 3  Writer (loop over declarative stages)
       │    └→ Phase 4  Story Bible (canonical view + continuity loop)
       └→ Phase 5  Character Chat shared knowledge integration
Phase 6  Bench 확장  ← Phase 3 checks 확보 후 본격화(픽스처는 Phase 1부터 누적)
```

**작업 규칙:** 1 작업 = 1 PR. PR은 additive·되돌릴 수 있어야 하며, 기능 구현과 상태정리/문서 정리를 섞지 않는다. 모든 텍스트 파일은 UTF-8.

**모델/effort 표기 규칙:** Architecture·cross-cutting·대규모 multi-file → **Claude Opus 5** · bounded 구현/UI/API → **GPT-5.6 Terra** · 복잡한 terminal 조사/디버깅/대규모 검증 → **GPT-5.6 Sol**. 기본 effort **High**, 위험도가 매우 높은 아키텍처 변경만 **XHigh**.

---

## 3. 작업 목록

### 3.1 Phase 1 — 잔여 Core 정리

#### P1-1 Review Card supersede 엔드포인트
- **목적:** 기존 canon 교체를 review gate 안에서 완결한다(현재 `EntryService.supersede()`가 API로 노출되지 않아 `relationship.state`/`story.summary` 교체가 UI/API에서 불가능).
- **선행 의존성:** 없음 (기존 review API·supersede 서비스 존재).
- **예상 변경 범위:** `backend/app/api/v1/entries.py`, `schemas/entry.py`(supersede 요청 DTO), 필요 시 `services/entry_service.py` 얇은 래퍼, `docs/architecture/review-card-api.md`(deferral 해제 기록), `tests/integration/test_entry_review_api.py`.
- **완료 조건:** `POST /entries/review/{id}/supersede`가 교체 대상 현행 canon을 **명시적으로 지명**받아 원자적으로 `proposed→canon` + `canon→superseded` 수행 · 소유권/스코프/서브젝트/앵커 재검증 · 비-proposed·타 소유자·앵커 소실 시 명시적 lifecycle 오류 · 마이그레이션/스키마 변경 0.
- **회귀 테스트:** 신규 supersede 통합 테스트(성공·중복·교차소유자·앵커 소실·비-proposed) + `test_entry_service.py`/`test_entry_review_api.py` 전량 + R2.
- **추천 모델/effort:** GPT-5.6 Terra / High.

#### P1-2 Entry Review Card 프론트엔드 (하나의 큐, 하나의 카드)
- **상태:** 완료 — 기존 Home 화면에 단일 Review Queue와 type-agnostic Review Card를 배치했고, Review API hook·Accept·Edit-then-accept·Reject·Supersede·공유 Queue cache helper/오류 메시지 단위 테스트를 추가했다. 최상위 내비게이션은 변경하지 않았으며, 2026-07-28에 `npm test`(3 files/13 tests)·`npm run lint`·`npm run build`를 통과했다.
- **목적:** RFC-011의 gate를 사용자에게 노출한다. 제안 종류별 화면을 만들지 않고 **단일 큐 + 단일 카드**로 구현한다.
- **선행 의존성:** P1-1 (supersede 액션 포함 위해). 없이도 accept/edit/reject만으로 착수 가능.
- **예상 변경 범위:** `frontend/src/lib/api/endpoints.ts`, `hooks/use-entry-review.ts`(신규), `components/review/*`(신규 카드/큐), 기존 화면 내 진입점(최상위 내비 항목 추가 금지 — ADR-011 §5/ADR-014 §4), `types/index.ts`, vitest 테스트.
- **완료 조건:** 제안 목록·상세·Accept·Edit-then-accept·Reject 동작 · provenance/confidence 노출("왜 이렇게 생각하나") · 비차단(작성/채팅 흐름을 가로막지 않음) · 모바일 터치 타깃/키보드 순회 충족 · `npm run lint`·`build`·`test` 통과.
- **회귀 테스트:** 프론트 유닛(큐 상태 전이·에러 처리), R11(접근성), R12(PWA 빌드), 기존 프론트 테스트 전량.
- **추천 모델/effort:** GPT-5.6 Terra / High.

#### P1-3 저장소 관리 prompt asset 구조 도입
- **상태:** 완료 — `backend/prompts/` 자산, allow-listed UTF-8 loader, trace identity/version/digest, 3개 legacy body 이관 및 회귀 테스트가 구현되었다.
- **목적:** ADR-013/RFC-009의 "prompt body는 versioned file asset" 요구를 충족하는 최소 자산 계층(디렉터리 규약 + 로더 + 버전 식별자)을 만든다.
- **선행 의존성:** 없음. Phase 2/3의 사실상 선행 작업.
- **예상 변경 범위:** `prompts/`(신규, 저장소 루트 또는 `backend/prompts/`), `backend/app/engines/prompt/assets.py`(신규 로더: 이름+버전 조회, 파일 해시/버전 노출), 기존 하드코딩 3건 이관 — `engines/chat/engine.py: DEFAULT_CHAT_TEMPLATE`, `engines/novel/engine.py: DEFAULT_NOVEL_TEMPLATE`, `engines/shared/summarizer.py: SUMMARY_TEMPLATE`, 유닛 테스트.
- **완료 조건:** 프롬프트 body가 파일에서 로드됨 · 코드 상수는 fallback 없이 제거 또는 파일 참조로 대체 · 프롬프트 식별자+버전이 조립 결과 metadata/trace에 기록 · 기존 채팅/이어쓰기/요약 출력 계약 불변 · DB에서 프롬프트 body를 읽지 않음.
- **회귀 테스트:** `tests/property/test_prompt_budget.py`, `test_streaming.py`, R3/R4, 신규 asset 로더 테스트(누락 파일·버전 불일치 오류).
- **추천 모델/effort:** GPT-5.6 Terra / High.

#### P1-4 legacy `PromptTemplate` 경계 고정 (비파괴)
- **상태:** 완료 — frozen `0001`의 legacy/user-authored `PromptTemplate`과 기존 `GET/POST` compatibility API를 비파괴적으로 유지하고, repository default asset이 같은 이름 또는 유사 body의 DB template에 의해 override되지 않음을 격리 DB 테스트로 고정했다.
- **목적:** DB `PromptTemplate`(0001 포함, CRUD 노출 중)과 새 prompt asset의 관계를 확정한다. **테이블/데이터를 지우지 않고** "사용자 입력만 저장, creative body는 파일" 경계를 코드·문서·테스트로 고정한다.
- **선행 의존성:** P1-3.
- **완료 조건:** 현재 Chat/Novel/Summary와 향후 Analyst/Writer/Bench architecture 경로는 DB template body를 읽지 않음 · 기존 사용자 template 데이터/API 하위호환 유지 · 마이그레이션 0 · 향후 제거는 별도 승인 필요임을 문서화.
- **회귀 테스트:** `test_prompt_template_boundary.py`(DB 무의존 asset load, Chat/Novel/Summary repository-default 우선), `test_api.py`(legacy POST/GET-list compatibility), 기존 `test_prompt_assets.py`, Property 8/R1.
- **추천 모델/effort:** GPT-5.6 Terra / High.

#### P1-5 Entry authoring / 조회 API (사용자 직접 canon + 감사 뷰)
- **목적:** 현재 Entry Store는 review 5개 엔드포인트만 노출되어 사용자가 직접 지식을 작성·열람할 수 없다. 명시적 사용자 행위(=human gate)로서의 canon 작성과 이력/감사 조회 경로를 만든다.
- **선행 의존성:** 없음.
- **예상 변경 범위:** `api/v1/entries.py`(생성/목록/상세/수정 — status는 서비스 규칙이 결정), `schemas/entry.py`, 필요 시 `services/entry_service.py` 조회 필터, 통합 테스트.
- **완료 조건:** 사용자 authoring은 RFC-002 §7.2에 따라 허용 상태만 생성 · AI 생산자용 `status=canon` 직접 지정 경로 없음 · 기본 조회는 canon만, `proposed/rejected/superseded`는 명시 요청 시에만 라벨과 함께 반환 · 소유자 격리 유지 · 마이그레이션 0.
- **회귀 테스트:** 신규 authoring 통합 테스트 + `test_entry_service.py` 전량 + R2.
- **현재 상태:** 구현 및 API/schema 통합 테스트는 `feature/entry-authoring-api`에 추가되었다. 그러나 현재 Windows shell wrapper가 실행 명령을 손상시키므로 pytest/Ruff/MyPy/CI 실측 전에는 본 항목을 완료로 체크하지 않는다.
- **추천 모델/effort:** GPT-5.6 Terra / High.

#### P1-6 retrieve() → Context Assembly를 실제 생성 경로에 연결 (flag 기반, 추가만)
- **목적:** 현재 `EntryService.retrieve()`와 `assemble_entry_context()`의 호출자는 테스트뿐이다. 실사용 경로에 **추가 블록**으로 주입해 Store가 실제로 작동하게 한다. 레거시 lore 키워드 스캔은 **유지**한다(RFC-003 §16.8: 두 경로 공존은 승인된 마이그레이션 시점까지 잠정 허용).
- **선행 의존성:** P1-5 (검증 데이터 작성 경로), 권장 P1-3.
- **예상 변경 범위:** `services/chat_service.py`·`services/novel_service.py`(retrieval 호출 + Entry 블록 병합), `engines/prompt/engine.py`(외부 블록 수용 지점), `config.py`(기능 플래그 기본 OFF), 통합/골든 테스트.
- **완료 조건:** 플래그 OFF 시 기존 프롬프트 조립 결과가 **바이트 동일** · ON 시 Entry 블록이 예산 내에서 별도 블록으로 주입되고 trace에 retrieval/assembly 제외 사유가 분리 기록 · chat-private Memory는 Entry로 섞이지 않음 · 전체 프롬프트 토큰 ≤ context_window 유지.
- **회귀 테스트:** `tests/golden/*` 전량, `test_prompt_budget.py`, `test_streaming.py`, R3/R4/R10(플래그 OFF 영향 0).
- **추천 모델/effort:** Claude Opus 5 / High.

#### P1-7 edit-diff capture (day-one 데이터 수집)
- **목적:** ADR-010·RFC-001 §8.8 — draft ↔ 사용자 확정본의 차이는 **소급 수집이 불가능**하다. 분석(distillation)은 미루되 **capture는 지금 시작**한다. 현재는 provenance 열거값만 존재한다.
- **선행 의존성:** 없음 (단, 영속 설계 승인 필요).
- **예상 변경 범위:** 신규 additive 마이그레이션 `0003_*`(diff capture 테이블 — Entry가 아닌 **운영 기록**이므로 aggregate로 취급), `models/`·`services/novel_service.py`(이어쓰기 확정 시 캡처), `services/chat_service.py`(선택), 통합 테이블 테스트.
- **완료 조건:** `0001`·`0002` 미수정 · 다운그레이드 가능 · 캡처 실패가 사용자 작성 흐름을 깨지 않음(비차단) · 캡처 데이터는 Entry가 아니며 canon 경로에 진입하지 않음 · Analyst 소비 계약(입력 형태) 문서화.
- **회귀 테스트:** `test_migrations.py`(체인·PG 컴파일·라운드트립), R6(이어쓰기), R9(마이그레이션 무손실).
- **추천 모델/effort:** Claude Opus 5 / High (스키마 결정이 되돌리기 어려우므로 설계 리뷰 필수).

#### P1-8 legacy Character/World/Lore ↔ Entry 동등성 브릿지 (읽기 비교, 백필 없음)
- **목적:** RFC-002 §12의 안전 순서 중 4단계(레거시 ↔ Entry 투영 비교)를 먼저 확보한다. 전환 스위치·삭제는 하지 않는다.
- **선행 의존성:** P1-5, P1-6.
- **예상 변경 범위:** `backend/app/services/`(레거시 → Entry 투영 순수 함수), `tests/golden/`(레거시/Entry 컨텍스트 동등성 픽스처), 문서(전환 기준·잔여 격차 목록).
- **완료 조건:** `Character.personality`/`speech_style`, `World` 배열, `Lorebook`/`LoreEntry`, `Chapter.summary`의 Entry 투영이 결정적으로 생성됨 · 레거시 컨텍스트와의 차이가 테스트로 가시화됨 · **DB 쓰기 0, 삭제 0, 마이그레이션 0** · lore 스캐너 비활성화 조건을 문서화.
- **회귀 테스트:** 신규 동등성 골든 + `test_api.py`(world/character CRUD) + R1/R2.
- **추천 모델/effort:** GPT-5.6 Sol / High (대규모 대조·검증 성격).

#### P1-9 review 감사(actor/action history) persistence 결정
- **목적:** `review-card-api.md`가 남긴 미결 사항(리뷰 행위자·이력·되돌림 메타데이터)을 **버전 없는 JSON 즉흥 스키마 없이** 결정한다.
- **선행 의존성:** P1-1.
- **예상 변경 범위:** ADR 초안 또는 RFC-011 구현 노트(`docs/architecture/`), 결정에 따른 additive 마이그레이션 후속 작업 분리.
- **완료 조건:** 감사 대상 필드·보존 기간·되돌림 의미가 문서로 확정 · Entry 상태 기계와 충돌 없음 · 구현은 별도 PR로 분리.
- **회귀 테스트:** 문서 작업(코드 변경 없음). 아키텍처 문서 상호 모순 검사.
- **추천 모델/effort:** Claude Opus 5 / High.

#### P1-10 로컬 개발 환경 정리 (선택, 사용자 확인 필요)
- **목적:** 로컬 `backend/data/app.db`가 저장소에 없는 리비전 `0002_story_bible`로 스탬프되어 `alembic current`가 실패한다. 폐기 노선 stash 2건도 정리 판단이 필요하다.
- **선행 의존성:** 없음.
- **예상 변경 범위:** 저장소 코드 변경 **없음**. 로컬 DB 재생성 또는 `alembic stamp` 절차 문서화(`README.md` 트러블슈팅 절 정도).
- **완료 조건:** `alembic current`가 head를 보고함 · 기존 로컬 데이터 손실 없음(백업 후 진행) · stash 처리(보존/드롭) 사용자 승인 기록.
- **회귀 테스트:** `alembic upgrade head` 후 `pytest` 전량, 앱 기동 `/healthz`.
- **추천 모델/effort:** GPT-5.6 Sol / High. **주의: 데이터 영향 작업이므로 반드시 사용자 확인 후 실행.**

### 3.2 Phase 2 — Analyst (text → proposed Entries)

> **경계:** Analyst는 **stateless transformer**다. 자체 store/index/cache/테이블을 갖지 않고, canon을 절대 쓰지 않으며, 무엇을 추출할지는 **facet 프롬프트 파일**이다. 새 엔진을 만드는 것이 아니다(RFC-008 §2.2, §4, §10.1).

#### P2-1 Analyst 골격 + facet 레지스트리
- **목적:** 단일 진입점 `analyze(text, scope, facets) → proposed Entries` 구현. 코드에 facet 분기를 만들지 않는다.
- **선행 의존성:** P1-3(prompt asset), P1-5(Entry 작성 경로), P1-1/P1-2(제안 처리 경로).
- **예상 변경 범위:** `backend/app/services/analyst/`(신규, 얇게), `prompts/analyst/*`(facet 파일), 어댑터 호출은 기존 registry 재사용, 유닛/통합 테스트.
- **완료 조건:** 출력은 항상 `status=proposed` Entry(+필수 provenance·confidence) · 영속 상태·캐시·인덱스 0 · facet 추가가 파일 추가만으로 가능 · 동일 입력 → 동일 제안(모델 스텁 기준 결정성) · canon 직접 기록 경로 부재가 테스트로 고정.
- **회귀 테스트:** 신규 Analyst 통합(제안만 생성·소유자 격리·잘못된 type 거부) + `test_entry_service.py` + R2.
- **추천 모델/effort:** Claude Opus 5 / High.

#### P2-2 facet: accepted chapter ingestion
- **목적:** 확정 챕터에서 `story.fact`·`story.knowledge`·`story.promise`·`story.summary`·`relationship.state` 제안을 생성한다(연속성 루프의 입력).
- **선행 의존성:** P2-1.
- **예상 변경 범위:** `prompts/analyst/chapter/*`, ingestion 트리거(작성 흐름 비차단, 기존 `core/jobs.py` 재사용), 통합 테스트.
- **완료 조건:** 챕터 확정 시 백그라운드 제안 생성 · 실패가 작성 흐름을 깨지 않음 · 제안은 review 큐에 그대로 노출 · `created_at_chapter` 등 story-order provenance 기록.
- **회귀 테스트:** 신규 ingestion 통합, R5(요약 비차단 성격), R6, 프롬프트 예산 R4.
- **추천 모델/effort:** GPT-5.6 Terra / High.

#### P2-3 facet: reference 분석 (collection scope)
- **목적:** 사용자가 소유한 참고 텍스트에서 `character.*`·`world.*`·`style.preference` 제안을 생성한다. 별도 reference 엔진/테이블을 만들지 않는다.
- **선행 의존성:** P2-1, P2-4.
- **예상 변경 범위:** `prompts/analyst/reference/*`, collection 스코프 처리, 통합 테스트.
- **완료 조건:** 결과가 `scope=collection` Entry 제안으로 적립 · 원문 전량 저장 없이 provenance + 최소 발췌만 보존(저작권 규율) · 큐레이션 배치 승인 경로를 쓰더라도 Analyst가 canon을 결정하지 않음.
- **회귀 테스트:** 신규 reference facet 통합 + Entry 검증 테스트 + R2.
- **추천 모델/effort:** GPT-5.6 Terra / High.

#### P2-4 reference 입력 substrate (최소)
- **목적:** 참고 텍스트를 시스템에 넣는 최소 경로(붙여넣기/업로드 1종)를 만든다. 별도 지식 스토어를 만들지 않는다.
- **선행 의존성:** P2-1.
- **예상 변경 범위:** collection aggregate 최소 정의(신규 additive 마이그레이션 가능), 업로드/텍스트 등록 API, 프론트 최소 화면.
- **완료 조건:** 원문은 Entry가 아니라 소스 레코드로 보관 · 소유자 격리 · Analyst 입력으로만 사용 · 기존 기능 영향 0.
- **회귀 테스트:** `test_migrations.py`, 신규 통합, R1/R9.
- **추천 모델/effort:** GPT-5.6 Terra / High.

#### P2-5 facet: edit-diff distillation (주기적 패스)
- **목적:** P1-7이 모아둔 diff를 `user.preference` 제안으로 증류한다. 온라인 학습이 아니라 **주기적·검토 가능·되돌릴 수 있는** 패스다.
- **선행 의존성:** P1-7, P2-1.
- **예상 변경 범위:** `prompts/analyst/preference/*`, 주기 실행 트리거(수동 실행 우선), 통합 테스트.
- **완료 조건:** 실행이 사용자 요청 경로에 없음 · 결과는 제안뿐 · 불투명 모델 학습 없음 · 되돌림은 Entry 상태 전이로만.
- **회귀 테스트:** 신규 distillation 통합 + R2.
- **추천 모델/effort:** GPT-5.6 Terra / High.

### 3.3 Phase 3 — Writer (loop over declarative stages)

> **경계:** 기존 `NovelEngine`의 single-pass 이어쓰기는 **Writer 완료가 아니다.** 기존 구현은 draft stage가 흡수할 substrate로 보존하고, 기존 `/chapters/{id}/continue` 계약은 깨지 않는다. Writer는 지식을 소유하지 않고 canon을 조용히 쓰지 않는다.

#### P3-1 stage 계약 + loop runner 골격
- **목적:** retrieve → assemble → generate → validate → revise → persist를 **선언적 stage 목록**으로 실행하는 작은 러너를 한 번 작성한다.
- **선행 의존성:** P1-3, P1-6.
- **예상 변경 범위:** `backend/app/services/writer/`(신규 러너 + stage 계약), `prompts/writer/*`, 기존 NovelEngine 호출을 stage 뒤로 배치, 유닛 테스트.
- **완료 조건:** stage 추가가 파일+선언 목록 변경만으로 가능 · 러너에 창작 정책(계획/비평/문체) 코드 부재 · 기존 이어쓰기 API 동작 불변 · scene을 원자 단위로 표현 · canon 직접 쓰기 경로 부재.
- **회귀 테스트:** 신규 러너 유닛(stage 순서·실패 격리·예산), `test_streaming.py`, R3/R4/R6.
- **추천 모델/effort:** Claude Opus 5 / **XHigh** (cross-cutting 계약이며 잘못 잡으면 이후 전 Phase가 오염됨).

#### P3-2 plan / draft stage
- **목적:** scene 계획과 초안 생성을 stage 프롬프트로 구현하고 기존 single-pass 경로를 이 stage로 재배선한다(재작성 아님).
- **선행 의존성:** P3-1.
- **예상 변경 범위:** `prompts/writer/plan|draft`, 러너 파이프라인 정의, `services/novel_service.py` 얇은 연결.
- **완료 조건:** 기존 이어쓰기 SSE·부분 보존·version CAS 동작 유지 · 계획 결과가 임시 작업 지식으로만 존재(canon 아님) · 프롬프트 자산 버전이 trace에 기록.
- **회귀 테스트:** R6, `test_streaming.py`, 골든 컨텍스트 픽스처.
- **추천 모델/effort:** GPT-5.6 Terra / High.

#### P3-3 validate stage (연속성 + 목소리 귀속 검사)
- **목적:** 초안을 canon(Entry)에 대해 검사하는 **결정적 체크** 2종을 도입한다. Bench가 재사용할 메트릭의 원천.
- **선행 의존성:** P3-1, P1-6.
- **예상 변경 범위:** `services/writer/checks/`(신규), `prompts/writer/check/*`(LLM 보조가 필요한 부분만), 유닛 테스트.
- **완료 조건:** 검사는 canon만 신뢰(proposed 불신) · 결과가 사용자 출력을 차단하지 않음 · 위반 항목이 구조적으로 보고됨(다음 stage가 소비 가능).
- **회귀 테스트:** 신규 체크 유닛(위반/무위반 픽스처) + 골든 회귀.
- **추천 모델/effort:** Claude Opus 5 / High.

#### P3-4 revise stage (bounded loop)
- **목적:** 검사 실패 항목에 대해 **횟수 상한이 있는** 수정 루프를 돌린다.
- **선행 의존성:** P3-3.
- **예상 변경 범위:** 러너 루프 정책, `prompts/writer/revise`, 유닛 테스트.
- **완료 조건:** 반복 상한·비용 상한 명시 · 무한 루프 불가 · 스트리밍 UX 저하 시 우회 경로 존재 · 사용자 출력 게이팅 없음.
- **회귀 테스트:** 신규 루프 유닛(상한 도달·조기 종료), R3/R4.
- **추천 모델/effort:** GPT-5.6 Terra / High.

#### P3-5 episode(회차) assembly + 기존 Chapter 저장 연결
- **목적:** scene들을 회차로 조립하고 기존 Chapter 영속 경로에 연결한다.
- **선행 의존성:** P3-2.
- **예상 변경 범위:** 러너 assembly stage, `services/novel_service.py`, 프론트 최소 노출.
- **완료 조건:** 기존 Chapter 스키마·API 하위호환 · `content_doc`/`content_text` 동기 유지 · 조립 결과가 사용자 확정 전에는 canon을 만들지 않음.
- **회귀 테스트:** R6, 낙관적 동시성 409 테스트, 프론트 빌드.
- **추천 모델/effort:** GPT-5.6 Terra / High.

#### P3-6 Writer ingestion → 제안 emit
- **목적:** 확정된 출력에서 관찰된 새 사실/약속을 **제안으로만** 내보낸다(인라인 canon 기록 금지).
- **선행 의존성:** P3-5, P2-2.
- **예상 변경 범위:** 러너 persist 단계, Analyst 호출 연결, 통합 테스트.
- **완료 조건:** Writer가 canon을 직접 쓰지 않음이 테스트로 고정 · 제안은 단일 review 큐로 유입 · 실패 비차단.
- **회귀 테스트:** 신규 통합 + R2 + review API 전량.
- **추천 모델/effort:** GPT-5.6 Terra / High.

### 3.4 Phase 4 — Story Bible (Entry Store의 canonical view)

> **금지:** 별도 Bible 테이블·별도 knowledge store·별도 retriever를 만들지 않는다. Bible은 work 스코프 canon **뷰**다(RFC-005, ADR-004).

#### P4-1 work-scoped canonical view (읽기 전용)
- **목적:** 하나의 작품 canon(`story.*`, `relationship.state`, 관련 world/character, 요약, 타임라인)을 **기존 `retrieve()` + task profile**로 조회하는 뷰를 제공한다.
- **선행 의존성:** P1-5, P1-6.
- **예상 변경 범위:** `api/v1/`(뷰 조회 엔드포인트), retrieval task profile 추가, 통합 테스트.
- **완료 조건:** 새 테이블·새 검색 함수 0 · proposed는 기본 제외 · 삭제/superseded 제외 · 소유자 격리 · 응답이 프롬프트가 아니라 지식 목록.
- **회귀 테스트:** `test_entry_retrieval.py`, 골든 회귀, R2.
- **추천 모델/effort:** GPT-5.6 Terra / High.

#### P4-2 continuity loop 결선
- **목적:** accepted chapter → Analyst 제안 → human review → canon → 다음 draft 검색 → 검사로 이어지는 플라이휠을 닫는다.
- **선행 의존성:** P2-2, P3-3, P4-1.
- **예상 변경 범위:** 루프 결선(잡 트리거·검색 프로필·검사 입력), 통합 테스트, 문서.
- **완료 조건:** 사람 승인 없이는 canon 증가 0 · 승인 즉시 다음 draft 검색에 반영 · 실패 지점이 사용자 흐름을 깨지 않음 · 루프 각 단계가 trace로 설명 가능.
- **회귀 테스트:** 종단 통합(챕터 확정 → 제안 → 승인 → 검색 반영), 골든 회귀, R2/R5/R6.
- **추천 모델/effort:** Claude Opus 5 / High.

#### P4-3 Bible 읽기 UI (기존 화면 내부)
- **목적:** 작품 화면 안에서 canon을 열람하고 review 큐로 자연스럽게 이동한다. 최상위 내비 항목을 늘리지 않는다.
- **선행 의존성:** P4-1, P1-2.
- **예상 변경 범위:** `frontend/src/app/(main)/novels/[id]/*`, 공통 Entry 렌더러(review 카드와 **동일 컴포넌트** 재사용).
- **완료 조건:** 제안/캐논 시각적 구분 · 하나의 에디터/렌더러 재사용 · lint/build/test 통과 · 모바일 우선.
- **회귀 테스트:** 프론트 테스트 전량, R11/R12.
- **추천 모델/effort:** GPT-5.6 Terra / High.

### 3.5 Phase 5 — Character Chat 공유 지식 통합

> **경계:** Chat은 독립 제품이며 자체 생성 경로(기존 ChatEngine)를 유지한다. 공유되는 것은 **지식**(Store/DNA/Relationship/Bible)과 review gate뿐이다. chat-private `Memory`를 Entry로 통합하지 않는다.

#### P5-1 chat 생성에 공유 canon 주입
- **목적:** 활성 캐릭터의 `character.*`, 공유 `relationship.state`, 선택된 work canon, world canon을 chat 프롬프트에 별도 블록으로 주입한다.
- **선행 의존성:** P1-6.
- **예상 변경 범위:** `services/chat_service.py`, retrieval chat task profile(exemplar 우선순위 포함), 통합 테스트.
- **완료 조건:** work canon은 **명시적으로 지정된 work만** 사용(추측 금지) · Memory 블록과 Entry 블록이 분리 유지 · 예산 초과 시 결정적 제외 · 플래그 OFF 시 기존 동작 동일.
- **회귀 테스트:** `test_streaming.py`, 골든 회귀, R3/R4/R10.
- **추천 모델/effort:** GPT-5.6 Terra / High.

#### P5-2 chat 북마크 → `character.exemplar` 제안
- **목적:** "이게 딱 이 캐릭터 말투다"라는 사용자 행위를 공유 지식으로 승격시키는 유일한 경로를 만든다.
- **선행 의존성:** P5-1, P1-2.
- **예상 변경 범위:** 북마크 API + 제안 생성(chat-message provenance), 프론트 북마크 액션, 통합 테스트.
- **완료 조건:** 원 대화는 private 유지 · 승격은 제안 → review → canon 경로만 · Memory 테이블은 그대로.
- **회귀 테스트:** 신규 통합 + review API 전량 + R2.
- **추천 모델/effort:** GPT-5.6 Terra / High.

#### P5-3 relationship shared state의 chat 반영 (읽기)
- **목적:** 소설과 채팅이 **하나의** 관계 상태를 읽게 한다(쌍 정체성 정규화 유지).
- **선행 의존성:** P5-1, P4-1.
- **예상 변경 범위:** retrieval 프로필·chat 조립, 통합 테스트.
- **완료 조건:** `(A,B)`/`(B,A)` 중복 없음 · single-current 규칙 준수 · chat이 관계 canon을 쓰지 않음(제안만 가능).
- **회귀 테스트:** `test_entry_service.py`(관계 single-current), 골든 회귀.
- **추천 모델/effort:** GPT-5.6 Terra / High.

### 3.6 Phase 6 — Bench 확장

> **구분:** 현재 존재하는 것은 `tests/golden/`의 **retrieval/context 회귀 픽스처(pytest)** 다. Bench는 그와 별개의 **개발자 전용 out-of-band 하네스**이며 사용자 출력을 게이팅하지 않는다.

#### P6-1 Bench 러너 골격 (dev-only)
- **목적:** 골든 씬(프로즌 시나리오 + 프로즌 지식 스냅샷)에 대해 실제 코드 경로를 호출하는 CLI 러너를 만든다.
- **선행 의존성:** P1-6 (권장 P3-3).
- **예상 변경 범위:** `bench/`(신규, 프로덕션 코드 밖), 기존 `tests/golden/` 픽스처 재사용, 러너 문서.
- **완료 조건:** 프로덕션 경로에 Bench import 0 · 사용자 API 노출 0 · 실행이 결정적(고정 `now`/정책 버전) · 리포트가 파일로 산출.
- **회귀 테스트:** 러너 자체 스모크 + `tests/golden/*` 전량 + 전체 pytest.
- **추천 모델/effort:** GPT-5.6 Sol / High.

#### P6-2 Writer checks를 메트릭으로 재사용
- **목적:** 별도 평가 로직을 만들지 않고 P3-3의 검사를 그대로 지표화한다.
- **선행 의존성:** P6-1, P3-3.
- **예상 변경 범위:** `bench/metrics/*`(얇은 어댑터), 리포트 포맷.
- **완료 조건:** 검사 코드 중복 0 · 지표가 씬별/집계로 출력 · 사용자 경로 영향 0.
- **회귀 테스트:** 체크 유닛 + 러너 스모크.
- **추천 모델/effort:** GPT-5.6 Terra / High.

#### P6-3 pairwise 판정 + A/B 리포트
- **목적:** 프롬프트/stage/검색 변경의 방향성 증거를 만든다(오라클이 아님).
- **선행 의존성:** P6-2.
- **예상 변경 범위:** `bench/judge/*`, 리포트 diff.
- **완료 조건:** 판정 프롬프트도 파일 자산 · 결과가 재현 가능(모델/시드/버전 기록) · 사용자 출력 게이팅 없음 · 골든 씬 버전이 리포트에 기록.
- **추천 모델/effort:** GPT-5.6 Terra / High.

#### P6-4 검색 랭킹 정책 회귀 + 한국어 keyword-miss 케이스
- **목적:** 랭킹 정책 변경과 (향후) 임베딩 도입 게이트의 증거 기반을 만든다(RFC-003 §14).
- **선행 의존성:** P6-1.
- **예상 변경 범위:** 골든 씬 확장(한국어 패러프레이즈/동의어 miss), 정책 버전 비교 리포트.
- **완료 조건:** 정책 버전별 결과 비교 가능 · 임베딩 없이 실패 사례가 문서화됨 · 임베딩 도입은 여전히 게이트 뒤에 있음.
- **회귀 테스트:** `tests/golden/*`, `test_entry_retrieval.py` 전량.
- **추천 모델/effort:** GPT-5.6 Sol / High.

---

## 4. 권장 다음 PR (순서 및 근거)

| 순서 | 작업 | 근거 | 추천 모델 / effort |
|---|---|---|---|
| 1 | **P1-1** Review Card supersede 엔드포인트 | 작고 독립적이며, review gate의 마지막 구멍(canon 교체)을 닫는다. 후속 프론트 작업의 계약을 먼저 고정한다. | GPT-5.6 Terra / High |
| 2 | **P1-3** prompt asset 구조 도입 | Phase 2/3의 사실상 모든 작업이 프롬프트 파일 자산을 전제한다. 하드코딩 3건도 함께 해소된다. | GPT-5.6 Terra / High |
| 3 | **P1-2** Review Card 프론트엔드 | 백엔드 gate가 사용자에게 노출되지 않으면 Analyst 제안이 쌓여도 canon이 자라지 않는다(플라이휠 정지). | GPT-5.6 Terra / High |

**병행 가능:** P1-7(edit-diff capture)은 위 3건과 독립적이며, *데이터가 지금부터만 모인다*는 점 때문에 착수를 미룰수록 손실이 누적된다. 여력이 있으면 1~3과 병행한다(Claude Opus 5 / High).

---

## 5. 매 PR 공통 완료 조건

- [ ] `cd backend && pytest` 전량 통과
- [ ] `cd frontend && npm test && npm run lint && npm run build` 통과
- [ ] `alembic heads`가 단일 head · `0001`/`0002` 미수정 · 새 마이그레이션은 additive + 다운그레이드 가능
- [ ] `git diff --check` 무오류 · 모든 텍스트 파일 UTF-8
- [ ] 회귀 체크리스트 관련 항목(R1~R12) 확인
- [ ] ADR/RFC 불변식(§불변식 1~13) 위반 없음 — 특히 새 knowledge 테이블·AI direct-to-canon·별도 Bible 스토어·chat Memory 통합 여부
- [ ] 기능 구현과 문서/상태 정리를 같은 PR에 섞지 않음
