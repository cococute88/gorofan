"""Aggregate API router (design 8.1.2)."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import ai_config, auth, characters, chats, novels, worlds

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(worlds.router, prefix="/worlds", tags=["worlds"])
api_router.include_router(characters.router, prefix="/characters", tags=["characters"])
api_router.include_router(characters.persona_router, prefix="/personas", tags=["personas"])
api_router.include_router(chats.router, prefix="/chats", tags=["chats"])
api_router.include_router(novels.router, prefix="/works", tags=["novels"])
api_router.include_router(ai_config.router, prefix="", tags=["config"])
