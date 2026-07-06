"""Chat context models: ChatSession, Message, Memory (design 3, 4.2, 4.6).

Message is append-only/immutable (INV-4/Property 4). Regenerate produces a new
row with the same parent_message_id; the prior assistant row is marked
is_active=false (design 4.6). user_id is denormalized on high-traffic child
tables for JOIN-free ownership scoping (design 4.1-1).
"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel
from app.db.types import JSONDict


class ChatSession(BaseModel):
    __tablename__ = "chat_sessions"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    character_id: Mapped[str] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    persona_id: Mapped[str | None] = mapped_column(
        ForeignKey("personas.id", ondelete="SET NULL"), nullable=True
    )
    model_config_id: Mapped[str | None] = mapped_column(
        ForeignKey("model_configs.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300), default="새 대화")

    messages: Mapped[list[Message]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    memories: Mapped[list[Memory]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class Message(BaseModel):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_session_created", "chat_session_id", "created_at"),)

    chat_session_id: Mapped[str] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), index=True)  # denormalized (4.1-1)
    parent_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user|assistant|system
    content: Mapped[str] = mapped_column(Text, default="")
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="complete")  # complete|partial
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    meta: Mapped[dict] = mapped_column(JSONDict, default=dict)

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class Memory(BaseModel):
    __tablename__ = "memories"
    __table_args__ = (Index("ix_memories_session", "chat_session_id"),)

    chat_session_id: Mapped[str] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), index=True)  # denormalized (4.1-1)
    kind: Mapped[str] = mapped_column(String(16), default="summary")  # summary|fact|event
    content: Mapped[str] = mapped_column(Text, default="")
    cover_up_to_message_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)  # monotonic per session
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    # Future RAG: optional embedding column added via migration (design 10.12) — left out for MVP.

    session: Mapped[ChatSession] = relationship(back_populates="memories")
