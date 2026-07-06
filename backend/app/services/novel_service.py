"""NovelService — works/chapters CRUD + continue writing (design 11, 6.5)."""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.base import StreamEvent
from app.adapters.registry import ProviderRegistry
from app.config import Settings
from app.core.errors import Conflict, NotFound, ValidationAppError
from app.core.pagination import Page, PageParams
from app.engines.novel.engine import ChapterContext, NovelEngine, words_to_tokens
from app.models.character import Character
from app.models.novel import Chapter, Work, WorkCharacter
from app.models.world import Lorebook, LoreEntry, World
from app.repositories.base import BaseRepository
from app.schemas.novel import (
    ChapterCreate,
    ChapterUpdate,
    ContinueRequest,
    WorkCharacterLink,
    WorkCreate,
    WorkUpdate,
)
from app.services.provider_resolve import resolve_provider_request

_active_continue: set[str] = set()


class NovelService:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        settings: Settings,
        registry: ProviderRegistry,
        novel_engine: NovelEngine,
    ) -> None:
        self.sm = sessionmaker
        self.settings = settings
        self.registry = registry
        self.engine = novel_engine
        self.repo = BaseRepository(Work)

    # ----- works -----
    async def create_work(self, user_id: str, dto: WorkCreate) -> Work:
        async with self.sm() as s:
            work = Work(user_id=user_id, **dto.model_dump())
            s.add(work)
            await s.commit()
            await s.refresh(work)
            return work

    async def list_works(self, user_id: str, page: PageParams) -> Page[Work]:
        async with self.sm() as s:
            return await self.repo.list_page(s, user_id=user_id, page=page)

    async def get_work(self, user_id: str, work_id: str) -> Work:
        async with self.sm() as s:
            work = await self.repo.get(s, work_id, user_id=user_id)
            if work is None:
                raise NotFound("Work not found")
            return work

    async def update_work(self, user_id: str, work_id: str, dto: WorkUpdate) -> Work:
        async with self.sm() as s:
            work = await self.repo.get(s, work_id, user_id=user_id)
            if work is None:
                raise NotFound("Work not found")
            await self.repo.update(s, work, dto.model_dump(exclude_unset=True))
            await s.commit()
            await s.refresh(work)
            return work

    async def delete_work(self, user_id: str, work_id: str) -> None:
        async with self.sm() as s:
            work = await self.repo.get(s, work_id, user_id=user_id)
            if work is None:
                raise NotFound("Work not found")
            await self.repo.soft_delete(s, work)
            await s.commit()

    # ----- chapters -----
    async def list_chapters(self, user_id: str, work_id: str) -> list[Chapter]:
        async with self.sm() as s:
            await self._owned_work(s, user_id, work_id)
            stmt = select(Chapter).where(Chapter.work_id == work_id).order_by(Chapter.index)
            return list((await s.execute(stmt)).scalars().all())

    async def create_chapter(self, user_id: str, work_id: str, dto: ChapterCreate) -> Chapter:
        async with self.sm() as s:
            await self._owned_work(s, user_id, work_id)
            next_index = await self._next_index(s, work_id)
            chapter = Chapter(
                work_id=work_id,
                user_id=user_id,
                index=next_index,
                title=dto.title,
                content_text=dto.content_text,
                content_doc=_text_to_doc(dto.content_text),
                word_count=_word_count(dto.content_text),
            )
            s.add(chapter)
            await s.commit()
            await s.refresh(chapter)
            return chapter

    async def update_chapter(self, user_id: str, chapter_id: str, dto: ChapterUpdate) -> Chapter:
        async with self.sm() as s:
            chapter = await self._owned_chapter(s, user_id, chapter_id)
            if dto.version != chapter.version:
                raise Conflict("Chapter version conflict", {"current_version": chapter.version})
            patch = dto.model_dump(exclude_unset=True, exclude={"version"})
            if "content_text" in patch and patch["content_text"] is not None:
                patch.setdefault("content_doc", _text_to_doc(patch["content_text"]))
                chapter.word_count = _word_count(patch["content_text"])
            for k, v in patch.items():
                setattr(chapter, k, v)
            chapter.version += 1
            await s.commit()
            await s.refresh(chapter)
            return chapter

    async def delete_chapter(self, user_id: str, chapter_id: str) -> None:
        async with self.sm() as s:
            chapter = await self._owned_chapter(s, user_id, chapter_id)
            await s.delete(chapter)
            await s.commit()

    async def reorder_chapters(self, user_id: str, work_id: str, ordered_ids: list[str]) -> None:
        async with self.sm() as s:
            await self._owned_work(s, user_id, work_id)
            # two-phase to avoid unique collisions: offset then assign
            stmt = select(Chapter).where(Chapter.work_id == work_id)
            chapters = {c.id: c for c in (await s.execute(stmt)).scalars().all()}
            for c in chapters.values():
                c.index += 100000
            await s.flush()
            for new_index, cid in enumerate(ordered_ids, start=1):
                if cid in chapters:
                    chapters[cid].index = new_index
            await s.commit()

    # ----- characters link -----
    async def list_characters(self, user_id: str, work_id: str) -> list[WorkCharacter]:
        async with self.sm() as s:
            await self._owned_work(s, user_id, work_id)
            stmt = select(WorkCharacter).where(WorkCharacter.work_id == work_id)
            return list((await s.execute(stmt)).scalars().all())

    async def link_character(self, user_id: str, work_id: str, dto: WorkCharacterLink) -> WorkCharacter:
        async with self.sm() as s:
            await self._owned_work(s, user_id, work_id)
            ch = await s.get(Character, dto.character_id)
            if ch is None or ch.user_id != user_id:
                raise ValidationAppError("character must be your own")
            existing = (
                await s.execute(
                    select(WorkCharacter).where(
                        WorkCharacter.work_id == work_id,
                        WorkCharacter.character_id == dto.character_id,
                    )
                )
            ).scalars().first()
            if existing is not None:
                raise Conflict("Character already linked to this work")
            link = WorkCharacter(work_id=work_id, character_id=dto.character_id, role_in_work=dto.role_in_work)
            s.add(link)
            await s.commit()
            await s.refresh(link)
            return link

    async def unlink_character(self, user_id: str, work_id: str, character_id: str) -> None:
        async with self.sm() as s:
            await self._owned_work(s, user_id, work_id)
            link = (
                await s.execute(
                    select(WorkCharacter).where(
                        WorkCharacter.work_id == work_id,
                        WorkCharacter.character_id == character_id,
                    )
                )
            ).scalars().first()
            if link is None:
                raise NotFound("Character not linked to this work")
            await s.delete(link)
            await s.commit()

    # ----- continue writing (SSE) -----
    async def continue_chapter(
        self, user_id: str, chapter_id: str, dto: ContinueRequest
    ) -> AsyncIterator[StreamEvent]:
        if chapter_id in _active_continue:
            raise Conflict("Already generating for this chapter")
        _active_continue.add(chapter_id)
        try:
            async for evt in self._continue_impl(user_id, chapter_id, dto):
                yield evt
        finally:
            _active_continue.discard(chapter_id)

    async def _continue_impl(
        self, user_id: str, chapter_id: str, dto: ContinueRequest
    ) -> AsyncIterator[StreamEvent]:
        async with self.sm() as s:
            chapter = await self._owned_chapter(s, user_id, chapter_id)
            work = await s.get(Work, chapter.work_id)
            ctx = await self._build_story_context(s, work, chapter)
            req = await resolve_provider_request(
                s, self.settings, self.registry,
                user_id=user_id, model_config_id=None, purpose="novel",
            )
            req.max_tokens = min(req.max_tokens, words_to_tokens(dto.target_words))
            base_version = chapter.version
            prompt = self.engine.assemble_continue(ctx, instruction=dto.instruction, req=req)

        buffer = ""
        try:
            async for evt in self.engine.continue_stream(prompt, req):
                if evt.delta:
                    buffer += evt.delta
                yield evt
        except Exception as exc:  # noqa: BLE001
            await self._append_chapter(user_id, chapter_id, buffer, base_version, partial=True)
            code = getattr(exc, "code", "PROVIDER_ERROR")
            yield StreamEvent(event="error", code=code, message=str(exc))
            return

        await self._append_chapter(user_id, chapter_id, buffer, base_version, partial=False)
        yield StreamEvent(event="done", finish_reason="stop", token_count=len(buffer))

    async def _append_chapter(
        self, user_id, chapter_id, text, base_version, *, partial  # noqa: ANN001
    ) -> int:
        async with self.sm() as s:
            chapter = await self._owned_chapter(s, user_id, chapter_id)
            # optimistic concurrency: if changed during stream, still append to latest (design 11.6)
            new_text = (chapter.content_text + ("\n\n" if chapter.content_text else "") + text).strip()
            chapter.content_text = new_text
            chapter.content_doc = _text_to_doc(new_text)
            chapter.word_count = _word_count(new_text)
            chapter.version += 1
            await s.commit()
            return chapter.version

    async def _build_story_context(self, s: AsyncSession, work: Work, chapter: Chapter) -> ChapterContext:
        prior_stmt = (
            select(Chapter)
            .where(Chapter.work_id == work.id, Chapter.index < chapter.index)
            .order_by(Chapter.index)
        )
        prior = list((await s.execute(prior_stmt)).scalars().all())
        prior_summaries = [c.summary for c in prior if c.summary]
        wc_stmt = select(WorkCharacter).where(WorkCharacter.work_id == work.id)
        links = list((await s.execute(wc_stmt)).scalars().all())
        characters = []
        for link in links:
            c = await s.get(Character, link.character_id)
            if c is not None:
                characters.append(c)
        world = await s.get(World, work.world_id) if work.world_id else None
        lore = []
        if world is not None:
            lstmt = (
                select(LoreEntry)
                .join(Lorebook, Lorebook.id == LoreEntry.lorebook_id)
                .where(Lorebook.world_id == world.id, LoreEntry.enabled.is_(True))
            )
            lore = list((await s.execute(lstmt)).scalars().all())
        return ChapterContext(
            work=work, current_chapter=chapter, prior_summaries=prior_summaries,
            characters=characters, world=world, lore_entries=lore,
        )

    # ----- helpers -----
    async def _owned_work(self, s, user_id, work_id) -> Work:  # noqa: ANN001
        work = await self.repo.get(s, work_id, user_id=user_id)
        if work is None:
            raise NotFound("Work not found")
        return work

    async def _owned_chapter(self, s, user_id, chapter_id) -> Chapter:  # noqa: ANN001
        chapter = await s.get(Chapter, chapter_id)
        if chapter is None or chapter.user_id != user_id:
            raise NotFound("Chapter not found")
        return chapter

    async def _next_index(self, s, work_id) -> int:  # noqa: ANN001
        stmt = select(func.coalesce(func.max(Chapter.index), 0)).where(Chapter.work_id == work_id)
        return int((await s.execute(stmt)).scalar_one()) + 1


def _word_count(text: str) -> int:
    return len(text.split())


def _text_to_doc(text: str) -> dict:
    """Minimal TipTap-compatible doc from plaintext (design 11.6)."""
    paragraphs = [p for p in text.split("\n\n")] if text else []
    return {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": ([{"type": "text", "text": p}] if p else [])}
            for p in paragraphs
        ]
        or [{"type": "paragraph"}],
    }
