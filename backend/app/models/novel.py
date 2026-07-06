"""Novel context models: Work, Chapter, WorkCharacter (design 3, 4.2, 4.8).

Chapter content authoritative source is content_doc (TipTap JSON); content_text
is a plaintext mirror for search/summary/token counting (design 11.6). version
provides optimistic concurrency (autosave vs continue, design 6.5).
"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel, SoftDeleteMixin
from app.db.types import JSONDict, JSONList


class Work(BaseModel, SoftDeleteMixin):
    __tablename__ = "works"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    world_id: Mapped[str | None] = mapped_column(
        ForeignKey("worlds.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    synopsis: Mapped[str] = mapped_column(Text, default="")
    genre: Mapped[str] = mapped_column(String(120), default="")
    tags: Mapped[list[str]] = mapped_column(JSONList, default=list)

    chapters: Mapped[list[Chapter]] = relationship(
        back_populates="work", cascade="all, delete-orphan"
    )
    work_characters: Mapped[list[WorkCharacter]] = relationship(
        back_populates="work", cascade="all, delete-orphan"
    )


class Chapter(BaseModel):
    __tablename__ = "chapters"
    __table_args__ = (UniqueConstraint("work_id", "index", name="uq_chapter_work_index"),)

    work_id: Mapped[str] = mapped_column(
        ForeignKey("works.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), index=True)  # denormalized (4.1-1)
    index: Mapped[int] = mapped_column(Integer)  # unique per work; continuity NOT enforced (4.8)
    title: Mapped[str] = mapped_column(String(300), default="")
    content_doc: Mapped[dict] = mapped_column(JSONDict, default=dict)  # TipTap JSON (authoritative)
    content_text: Mapped[str] = mapped_column(Text, default="")  # plaintext mirror
    summary: Mapped[str] = mapped_column(Text, default="")
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)  # optimistic concurrency

    work: Mapped[Work] = relationship(back_populates="chapters")


class WorkCharacter(BaseModel):
    __tablename__ = "work_characters"
    __table_args__ = (UniqueConstraint("work_id", "character_id", name="uq_work_character"),)

    work_id: Mapped[str] = mapped_column(
        ForeignKey("works.id", ondelete="CASCADE"), index=True
    )
    character_id: Mapped[str] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    role_in_work: Mapped[str] = mapped_column(String(60), default="조연")

    work: Mapped[Work] = relationship(back_populates="work_characters")
