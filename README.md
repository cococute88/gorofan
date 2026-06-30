# AI Native Creative Workspace (`ai-creative-workspace`)

> "나만의 로판AI + 하트픽션" — 하나의 세계관·캐릭터 DB를 중심으로 **AI 캐릭터 채팅**과 **AI 장편 소설 창작**을 통합한 개인용 AI 네이티브 창작 워크스페이스.

본 저장소는 `.kiro/specs/ai-creative-workspace/`의 `design.md` · `requirements.md` · `tasks.md`를 단일 진실 공급원으로 구현한다.

## 모노레포 구조

```
ai-creative-workspace/
├── docker-compose.yml      # 단일 명령 기동
├── .env.example            # 환경변수 템플릿
├── backend/                # FastAPI + SQLAlchemy 2.0 (async)
├── frontend/               # Next.js (App Router) PWA
└── .kiro/specs/            # 설계/요구사항/작업 문서
```

## 빠른 시작 (로컬)

### 1) 환경변수
```bash
cp .env.example .env
# APP_SECRET_KEY 등 채우기 (로컬 모드는 AUTH_ENABLED=false 기본)
```

### 2) Docker Compose (권장)
```bash
docker compose up --build
# frontend: http://localhost:3000
# backend:  http://localhost:8000  (docs: /docs, health: /healthz)
```

### 3) 백엔드 단독 개발
```bash
cd backend
python -m venv .venv && . .venv/Scripts/activate   # Windows
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 4) 프론트엔드 단독 개발
```bash
cd frontend
npm install
npm run dev    # http://localhost:3000
```

## 핵심 설계 원칙
- Personal/Local-First · Zero-Cost · No Vendor Lock-in · Prompt/Memory 분리 · Mobile-First PWA · Modular Auth · DB Swap-Ready.

## 테스트
```bash
cd backend && pytest          # unit / property(Hypothesis) / integration
cd frontend && npm test       # 컴포넌트/유닛
```

자세한 내용은 `.kiro/specs/ai-creative-workspace/design.md` 참조.
