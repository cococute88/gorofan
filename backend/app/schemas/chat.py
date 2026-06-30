"""Chat DTOs (design 6)."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, TimestampedOut


class ChatCreate(BaseModel):
    character_id: str
    persona_id: str | None = None
    model_config_id: str | None = None
    title: str = "새 대화"


class ChatOut(TimestampedOut):
    user_id: str
    character_id: str
    persona_id: str | None
    model_config_id: str | None
    title: str


class MessageCreate(BaseModel):
    content: str = Field(min_length=1)
    client_request_id: str | None = None


class MessageOut(ORMModel):
    id: str
    chat_session_id: str
    parent_message_id: str | None
    role: str
    content: str
    token_count: int
    status: str
    is_active: bool
    created_at: object


class RegenerateRequest(BaseModel):
    client_request_id: str | None = None
