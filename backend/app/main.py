"""FastAPI application factory (design 8.1).

Builds app-lifetime singletons in lifespan and exposes them on app.state for DI.
Registers middleware, exception handlers, routers, and health endpoints.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.auth.providers.google import GoogleOAuthProvider
from app.auth.service import AuthService, ensure_default_user
from app.adapters.registry import build_provider_registry
from app.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.jobs import build_job_queue
from app.core.logging import get_logger, init_logging
from app.core.middleware import RequestContextMiddleware
from app.core.storage import build_storage_backend
from app.db.session import create_engine, create_sessionmaker
from app.engines.chat.engine import ChatEngine
from app.engines.memory.engine import MemoryEngine
from app.engines.novel.engine import NovelEngine
from app.engines.prompt.engine import PromptEngine
from app.engines.shared.summarizer import Summarizer
from app.services.ai_config_service import AIConfigService
from app.services.chat_service import ChatService
from app.services.novel_service import NovelService
from app.services.summary_job import make_summarize_handler

log = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    init_logging("INFO")

    engine = create_engine(settings)
    sessionmaker = create_sessionmaker(engine)
    registry = build_provider_registry(settings.PROVIDER_MAX_CONCURRENCY)
    storage = build_storage_backend(settings.STORAGE_BACKEND, settings.MEDIA_ROOT)
    job_queue = build_job_queue(settings.JOB_BACKEND)

    # engines
    prompt_engine = PromptEngine()
    summarizer = Summarizer(prompt_engine=prompt_engine, registry=registry)
    memory_engine = MemoryEngine(summarizer=summarizer)
    chat_engine = ChatEngine(prompt_engine, memory_engine, registry)
    novel_engine = NovelEngine(prompt_engine, registry)

    # services (app-lifetime; session-bound work uses sessionmaker)
    chat_service = ChatService(sessionmaker, settings, registry, chat_engine, job_queue)
    novel_service = NovelService(sessionmaker, settings, registry, novel_engine)
    ai_config_service = AIConfigService(settings, registry)

    # auth (only wired when enabled and configured)
    auth_service = None
    if settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET:
        providers = {
            "google": GoogleOAuthProvider(
                settings.GOOGLE_CLIENT_ID,
                settings.GOOGLE_CLIENT_SECRET.get_secret_value(),
            )
        }
        auth_service = AuthService(sessionmaker, settings, providers)

    # background jobs
    job_queue.register("summarize", make_summarize_handler(sessionmaker, memory_engine))

    # seed default user for local mode (design 14.2)
    if not settings.AUTH_ENABLED:
        await ensure_default_user(sessionmaker, settings.DEFAULT_USER_ID)

    # expose on state
    app.state.db_engine = engine
    app.state.sessionmaker = sessionmaker
    app.state.registry = registry
    app.state.storage = storage
    app.state.job_queue = job_queue
    app.state.chat_service = chat_service
    app.state.novel_service = novel_service
    app.state.ai_config_service = ai_config_service
    app.state.auth_service = auth_service

    log.info("startup.complete")
    try:
        yield
    finally:
        await job_queue.drain()
        await engine.dispose()
        log.info("shutdown.complete")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="AI Creative Workspace API", version="1.0.0", lifespan=lifespan)
    app.state.settings = settings

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Access-Token", "X-Request-Id"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/healthz", tags=["health"])
    async def healthz():
        return {"status": "ok"}

    @app.get("/readyz", tags=["health"])
    async def readyz():
        # readiness: engine present (migrations applied externally via entrypoint)
        ok = getattr(app.state, "db_engine", None) is not None
        return {"status": "ready" if ok else "starting"}

    return app


app = create_app()
