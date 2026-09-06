"""Frozen P1-8 Chat/Novel projection snapshots used by golden tests."""
from __future__ import annotations

from types import SimpleNamespace

from app.services.legacy_entry_equivalence import (
    EntrySnapshot,
    LegacyEntryProjection,
    project_chapter_summaries,
    project_character,
    project_lore,
    project_world,
)


def _entry(
    projection: LegacyEntryProjection,
    entry_id: str,
    *,
    status: str = "canon",
    content: str | None = None,
) -> EntrySnapshot:
    return EntrySnapshot(
        id=entry_id,
        scope_kind=projection.scope_kind,
        scope_id=projection.scope_id,
        subject_type=projection.subject_type,
        subject_id=projection.subject_id,
        entry_type=projection.entry_type,
        status=status,
        title=projection.title,
        content=content if content is not None else projection.content,
        data_level="chapter"
        if projection.projection_kind.value == "chapter_summary"
        else None,
        priority=50,
        live_anchor=True,
        superseded_by_entry_id=None,
        subject_story_position=projection.story_position,
        created_at_chapter_position=projection.story_position,
    )


def chat_golden() -> tuple[list[LegacyEntryProjection], list[EntrySnapshot]]:
    character = SimpleNamespace(
        id="chat-character",
        name="세라",
        personality="침착하다.",
        speech_style="짧게 말한다.",
    )
    world = SimpleNamespace(
        id="chat-world",
        name="월광계",
        description="달빛이 마력의 근원이다.",
        era="왕국력",
        races=["인간"],
        nations=[],
        taboos=[],
    )
    lore = SimpleNamespace(
        id="chat-lore",
        content="월식에는 거짓말을 할 수 없다.",
        keywords=["월식"],
        priority=50,
        enabled=True,
        scan_depth=4,
    )
    book = SimpleNamespace(id="chat-book", enabled=False)
    projections = [
        *project_character(character).projections,
        *project_world(world).projections,
        *project_lore(world.id, [(lore, book)]).projections,
    ]
    entries = [
        _entry(projections[0], "chat-identity"),
        _entry(projections[1], "chat-voice"),
        _entry(projections[2], "chat-description", content="다른 설명"),
        _entry(projections[-1], "chat-lore-history", status="rejected"),
    ]
    return projections, entries

def novel_golden() -> tuple[list[LegacyEntryProjection], list[EntrySnapshot]]:
    chapters = [
        SimpleNamespace(
            id="chapter-1", work_id="golden-work", index=1, summary="문을 열었다."
        ),
        SimpleNamespace(
            id="chapter-3", work_id="golden-work", index=3, summary="왕을 만났다."
        ),
    ]
    projections = list(project_chapter_summaries(chapters).projections)
    entries = [
        _entry(projections[0], "summary-prior"),
        _entry(projections[1], "summary-future-a"),
        _entry(projections[1], "summary-future-b"),
    ]
    return projections, entries
