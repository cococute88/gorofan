"""NovelService — works/chapters CRUD + continue writing (design 11, 6.5)."""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.base import StreamEvent
from app.adapters.registry import ProviderRegistry
from app.config import Settings
from app.core.errors import Conflict, NotFound, ValidationAppError
from app.core.logging import get_logger
from app.core.pagination import Page, PageParams
from app.engines.novel.engine import ChapterContext, NovelEngine, words_to_tokens
from app.engines.novel.generation_preparation import (
    CURRENT_CHAPTER_TAIL_CHARS,
    ContinueGenerationInput,
    GenerationPreparation,
    GenerationTarget,
    PreparedChapterContext,
    PreparedCharacterContext,
    PreparedLoreContext,
    PreparedPriorSummary,
    PreparedWorkContext,
    PreparedWorldContext,
    freeze_mapping,
    prepare_continue_generation,
    snapshot_prompt_blocks,
)
from app.models.character import Character
from app.models.novel import Chapter, Work, WorkCharacter
from app.models.world import Lorebook, LoreEntry, World
from app.repositories.base import BaseRepository
from app.repositories.chapter_repository import ChapterRepository
from app.schemas.entry import StorySummaryGenerationOperation
from app.schemas.novel import (
    ChapterCreate,
    ChapterUpdate,
    ContinueRequest,
    WorkCharacterLink,
    WorkCreate,
    WorkUpdate,
)
from app.services.edit_diff_capture import EditDiffCaptureService
from app.services.entry_generation_context import (
    build_novel_retrieve_request,
    load_entry_context,
)
from app.services.provider_resolve import resolve_provider_request
from app.services.story_order_snapshot import begin_story_order_snapshot
from app.services.story_summary_chronology import is_substantive_legacy_summary

_active_continue: set[str] = set()

_logger = get_logger("app.edit_diff")


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
        self.chapters = ChapterRepository()
        self.captures = EditDiffCaptureService()

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

    async def prepare_continue(
        self,
        user_id: str,
        chapter_id: str,
        dto: ContinueRequest,
        *,
        context_window: int,
    ) -> GenerationPreparation:
        """Prepare one continuation without resolving or invoking a provider."""

        async with self.sm() as s:
            await begin_story_order_snapshot(s)
            chapter = await self._owned_chapter(s, user_id, chapter_id)
            work = await self._owned_work(s, user_id, chapter.work_id)
            ctx = await self._build_story_context(s, work, chapter)
            return await self._prepare_continue_context(
                s,
                user_id=user_id,
                work=work,
                chapter=chapter,
                ctx=ctx,
                dto=dto,
                context_window=context_window,
            )

    async def _continue_impl(
        self, user_id: str, chapter_id: str, dto: ContinueRequest
    ) -> AsyncIterator[StreamEvent]:
        async with self.sm() as s:
            await begin_story_order_snapshot(s)
            chapter = await self._owned_chapter(s, user_id, chapter_id)
            work = await self._owned_work(s, user_id, chapter.work_id)
            ctx = await self._build_story_context(s, work, chapter)
            req = await resolve_provider_request(
                s, self.settings, self.registry,
                user_id=user_id, model_config_id=None, purpose="novel",
            )
            req.max_tokens = min(req.max_tokens, words_to_tokens(dto.target_words))
            base_version = chapter.version
            preparation = await self._prepare_continue_context(
                s,
                user_id=user_id,
                work=work,
                chapter=chapter,
                ctx=ctx,
                dto=dto,
                context_window=req.context_window,
            )
            prompt = self.engine.assemble_continue(preparation, req=req)

        # Settle the previous continuation before this one destroys the
        # boundary, and before any token is streamed (design §6.3).
        await self._settle_chapter_captures(user_id, chapter_id)

        asset = prompt.trace.get("prompt_asset") or {}
        asset_id = asset.get("id")
        asset_version = asset.get("version")
        capture_context = {
            "asset_id": asset_id,
            "asset_version": asset_version,
            "provider": req.provider,
            "model": req.model_name,
        }
        producer = (
            f"{asset_id}.{asset_version}" if asset_id and asset_version else asset_id
        )

        buffer = ""
        try:
            async for evt in self.engine.continue_stream(prompt, req):
                if evt.delta:
                    buffer += evt.delta
                yield evt
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "code", "PROVIDER_ERROR")
            try:
                await self._append_chapter(
                    user_id, chapter_id, buffer, base_version, partial=True,
                    capture_context=capture_context, producer=producer,
                )
            except Exception as append_exc:  # noqa: BLE001
                # The provider error is the one the author needs to see; a
                # failure here must not replace it (design §9.2). The append
                # itself still rolled back, so no untraceable segment merged.
                _logger.warning(
                    "edit_diff.partial_append_failed",
                    extra={
                        "user_id": user_id,
                        "meta": {
                            "chapter_id": chapter_id,
                            "failure_class": type(append_exc).__name__,
                        },
                    },
                )
            yield StreamEvent(event="error", code=code, message=str(exc))
            return

        await self._append_chapter(
            user_id, chapter_id, buffer, base_version, partial=False,
            capture_context=capture_context, producer=producer,
        )
        yield StreamEvent(event="done", finish_reason="stop", token_count=len(buffer))

    async def _prepare_continue_context(
        self,
        s: AsyncSession,
        *,
        user_id: str,
        work: Work,
        chapter: Chapter,
        ctx: ChapterContext,
        dto: ContinueRequest,
        context_window: int,
    ) -> GenerationPreparation:
        """Bridge owner-scoped DB results into the pure AOS-1 preparation."""

        # Entry Store canon is retrieved exactly once per request, inside T1,
        # before any token is streamed (P1-6). Flag OFF short-circuits before
        # any Entry query is issued. Chronology eligibility/order is finalized
        # by that existing path; the pure preparation only snapshots the result.
        entry_context = await load_entry_context(
            s,
            settings=self.settings,
            request_factory=lambda: build_novel_retrieve_request(
                user_id=user_id,
                work=work,
                world=ctx.world,
                characters=ctx.characters,
                chapter=chapter,
                instruction=dto.instruction,
                context_window=context_window,
                operation=StorySummaryGenerationOperation.CONTINUE,
                substantive_legacy_summary_chapter_ids=(
                    ctx.substantive_legacy_summary_chapter_ids
                ),
            ),
        )
        if not (
            len(ctx.prior_summaries)
            == len(ctx.prior_summary_chapter_indexes)
            == len(ctx.substantive_legacy_summary_chapter_ids)
        ):
            raise ValueError("Legacy chapter summary chronology evidence is incomplete")
        world_source = cast(World | None, ctx.world)
        world = (
            PreparedWorldContext(
                id=world_source.id,
                owner_id=world_source.user_id,
                name=world_source.name,
                description=world_source.description,
                era=world_source.era,
            )
            if world_source is not None
            else None
        )
        value = ContinueGenerationInput(
            target=GenerationTarget(
                owner_id=user_id,
                work_id=work.id,
                chapter_id=chapter.id,
            ),
            work=PreparedWorkContext(
                id=work.id,
                owner_id=work.user_id,
                title=work.title,
                synopsis=work.synopsis,
                genre=work.genre,
                tags=tuple(work.tags),
            ),
            characters=tuple(
                PreparedCharacterContext(
                    id=character.id,
                    owner_id=character.user_id,
                    name=character.name,
                    personality=character.personality,
                    speech_style=character.speech_style,
                )
                for character in ctx.characters
            ),
            world=world,
            lore=tuple(
                PreparedLoreContext(
                    id=entry.id,
                    content=entry.content,
                    keywords=tuple(entry.keywords),
                    priority=entry.priority,
                    scan_depth=entry.scan_depth,
                    enabled=entry.enabled,
                )
                for entry in ctx.lore_entries
            ),
            prior_summaries=tuple(
                PreparedPriorSummary(chapter_id=chapter_id, chapter_index=index, content=summary)
                for chapter_id, index, summary in zip(
                    ctx.substantive_legacy_summary_chapter_ids,
                    ctx.prior_summary_chapter_indexes,
                    ctx.prior_summaries,
                    strict=True,
                )
            ),
            current_chapter=PreparedChapterContext(
                id=chapter.id,
                work_id=chapter.work_id,
                owner_id=chapter.user_id,
                index=chapter.index,
                title=chapter.title,
                tail=(chapter.content_text or "")[-CURRENT_CHAPTER_TAIL_CHARS:],
            ),
            instruction=dto.instruction,
            target_words=dto.target_words,
            context_window=context_window,
            entry_blocks=snapshot_prompt_blocks(entry_context.blocks),
            entry_context_trace=freeze_mapping(entry_context.trace),
        )
        return prepare_continue_generation(value)

    async def _settle_chapter_captures(self, user_id: str, chapter_id: str) -> None:
        """Bracket this chapter's pending captures against the next segment.

        Requesting more prose is the author's clearest signal that everything
        above it is what they want continued from — the closest thing to
        "accepted" the chapter UX has, and it needs no new endpoint, gesture,
        or UI. The 1.2s autosave is deliberately **not** a settle trigger: the
        first save lands seconds into revision, so settling there would
        systematically record "the human changed nothing" in a corpus whose
        purpose is measuring how the human changes it (design §6.3.1).

        **Tier 3 — best effort.** The after-side still lives in
        ``chapters.content_text``, which nothing destroys, so a failure loses
        no data: the row stays unsettled, a later continuation can settle it,
        and a trailing unsettled row is a normal terminal state resolved at
        read time. A failure must therefore never block the new continuation —
        but it is reported, never silently swallowed, and the warning carries
        ids and a failure class only, never captured prose (design §9.3).
        """
        try:
            async with self.sm() as s:
                chapter = await self._locked_chapter(s, user_id, chapter_id)
                await self.captures.settle_chapter_captures(
                    s,
                    user_id=user_id,
                    chapter_id=chapter_id,
                    after_text=chapter.content_text,
                )
                await s.commit()
        except Exception as exc:  # noqa: BLE001
            _logger.warning(
                "edit_diff.settle_failed",
                extra={
                    "user_id": user_id,
                    "meta": {
                        "chapter_id": chapter_id,
                        "failure_class": type(exc).__name__,
                    },
                },
            )

    async def _append_chapter(
        self, user_id, chapter_id, text, base_version, *, partial,  # noqa: ANN001
        capture_context: dict | None = None,
        producer: str | None = None,
    ) -> int:
        """Merge the streamed segment into the chapter, capturing it first.

        This concatenation is what erases the segment boundary: afterwards no
        query can tell what the model wrote from what the author changed. The
        capture is **Tier 2 — atomic** with the append, so a capture failure
        rolls the append back rather than merging an untraceable segment.

        The chapter is loaded ``with_for_update()``. The previous plain
        ``session.get()`` took no lock, and ``_active_continue`` is an
        in-process set that does not survive multiple workers, so two
        concurrent continuations could derive the same capture ``sequence``
        and collide on the unique constraint (design §10.1).
        """
        async with self.sm() as s:
            chapter = await self._locked_chapter(s, user_id, chapter_id)
            # optimistic concurrency: if changed during stream, still append to latest (design 11.6)
            insert_offset = len(chapter.content_text)
            new_text = (chapter.content_text + ("\n\n" if chapter.content_text else "") + text).strip()
            chapter.content_text = new_text
            chapter.content_doc = _text_to_doc(new_text)
            chapter.word_count = _word_count(new_text)
            chapter.version += 1
            if text:
                # An empty buffer is not "a text produced by the AI"; there is
                # nothing to compare a human revision against (design §4.1a).
                await self.captures.capture_chapter_continuation(
                    s,
                    user_id=user_id,
                    chapter_id=chapter_id,
                    segment_text=text,
                    producer=producer,
                    context={
                        **(capture_context or {}),
                        "insert_offset": insert_offset,
                        "chapter_version": chapter.version,
                        "partial_stream": partial,
                    },
                )
            await s.commit()
            return chapter.version

    async def _build_story_context(self, s: AsyncSession, work: Work, chapter: Chapter) -> ChapterContext:
        prior_stmt = (
            select(Chapter)
            .where(
                Chapter.work_id == work.id,
                Chapter.user_id == work.user_id,
                Chapter.index < chapter.index,
            )
            .order_by(Chapter.index)
        )
        prior = list((await s.execute(prior_stmt)).scalars().all())
        substantive_prior = [
            c for c in prior if is_substantive_legacy_summary(c.summary)
        ]
        prior_summaries = [c.summary for c in substantive_prior]
        character_stmt = (
            select(Character)
            .join(WorkCharacter, WorkCharacter.character_id == Character.id)
            .where(
                WorkCharacter.work_id == work.id,
                Character.user_id == work.user_id,
                Character.deleted_at.is_(None),
            )
            .order_by(WorkCharacter.character_id)
        )
        characters = list((await s.execute(character_stmt)).scalars().all())
        world = None
        if work.world_id:
            world_stmt = select(World).where(
                World.id == work.world_id,
                World.user_id == work.user_id,
                World.deleted_at.is_(None),
            )
            world = (await s.execute(world_stmt)).scalars().first()
        lore = []
        if world is not None:
            lstmt = (
                select(LoreEntry)
                .join(Lorebook, Lorebook.id == LoreEntry.lorebook_id)
                .where(Lorebook.world_id == world.id, LoreEntry.enabled.is_(True))
                .order_by(LoreEntry.priority.desc(), LoreEntry.id)
            )
            lore = list((await s.execute(lstmt)).scalars().all())
        return ChapterContext(
            work=work, current_chapter=chapter, prior_summaries=prior_summaries,
            prior_summary_chapter_indexes=tuple(c.index for c in substantive_prior),
            characters=characters, world=world, lore_entries=lore,
            substantive_legacy_summary_chapter_ids=tuple(
                c.id for c in substantive_prior
            ),
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

    async def _locked_chapter(self, s, user_id, chapter_id) -> Chapter:  # noqa: ANN001
        """Owner-scoped chapter load holding the row lock (design §10.1)."""
        chapter = await self.chapters.get_for_update(s, chapter_id, user_id=user_id)
        if chapter is None:
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
