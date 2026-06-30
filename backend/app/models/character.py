"""Cast context models: Character, Persona (design 3, 4.2)."""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel, SoftDeleteMixin
from app.db.types import JSONList


class Character(BaseModel, SoftDeleteMixin):
    __tablename__ = "characters"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # nullable world link; INV-2 enforced in service layer (Property 2).
    world_id: Mapped[str | None] = mapped_column(
        ForeignKey("worlds.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    greeting: Mapped[str] = mapped_column(Text, default="")
    speech_style: Mapped[str] = mapped_column(Text, default="")
    personality: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list[str]] = mapped_column(JSONList, default=list)


class Persona(BaseModel):
    __tablename__ = "personas"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
