"""Worldbuilding context models (design 3, 4.2)."""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import BaseModel, SoftDeleteMixin
from app.db.types import JSONList


class World(BaseModel, SoftDeleteMixin):
    __tablename__ = "worlds"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    era: Mapped[str] = mapped_column(String(200), default="")
    races: Mapped[list[str]] = mapped_column(JSONList, default=list)
    nations: Mapped[list[str]] = mapped_column(JSONList, default=list)
    taboos: Mapped[list[str]] = mapped_column(JSONList, default=list)

    lorebooks: Mapped[list["Lorebook"]] = relationship(
        back_populates="world", cascade="all, delete-orphan"
    )
    glossary_terms: Mapped[list["GlossaryTerm"]] = relationship(
        back_populates="world", cascade="all, delete-orphan"
    )


class GlossaryTerm(BaseModel):
    __tablename__ = "glossary_terms"

    world_id: Mapped[str] = mapped_column(
        ForeignKey("worlds.id", ondelete="CASCADE"), index=True
    )
    term: Mapped[str] = mapped_column(String(200))
    definition: Mapped[str] = mapped_column(Text, default="")

    world: Mapped[World] = relationship(back_populates="glossary_terms")


class Lorebook(BaseModel):
    __tablename__ = "lorebooks"

    world_id: Mapped[str] = mapped_column(
        ForeignKey("worlds.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200), default="기본 로어북")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    world: Mapped[World] = relationship(back_populates="lorebooks")
    entries: Mapped[list["LoreEntry"]] = relationship(
        back_populates="lorebook", cascade="all, delete-orphan"
    )


class LoreEntry(BaseModel):
    __tablename__ = "lore_entries"

    lorebook_id: Mapped[str] = mapped_column(
        ForeignKey("lorebooks.id", ondelete="CASCADE"), index=True
    )
    keywords: Mapped[list[str]] = mapped_column(JSONList, default=list)
    content: Mapped[str] = mapped_column(Text, default="")
    priority: Mapped[int] = mapped_column(Integer, default=50)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    scan_depth: Mapped[int] = mapped_column(Integer, default=4)  # 최근 N메시지 스캔

    lorebook: Mapped[Lorebook] = relationship(back_populates="entries")
