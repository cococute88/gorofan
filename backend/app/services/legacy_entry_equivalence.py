"""P1-8 read-only legacy/Entry coverage and runtime diagnostics.

Projection and coverage functions in this module are deterministic and have no
database or provider dependency.  ``LegacyEntryEquivalenceService`` is the one
owner-scoped application reader that snapshots concrete Chat/Novel situations,
runs the existing Entry retrieval/assembly and PromptEngine policies in memory,
and returns typed evidence without mutating either authority.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from types import MappingProxyType, SimpleNamespace
from typing import Any, Literal

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.base import AssembledPrompt
from app.adapters.registry import ProviderRegistry
from app.config import Settings
from app.core.errors import NotFound, ValidationAppError
from app.engines.memory.engine import RETRIEVE_K, SHORT_WINDOW, MemoryEngine, rank_memories
from app.engines.novel.engine import words_to_tokens
from app.engines.prompt.assets import PromptAssetLoader
from app.engines.prompt.blocks import LAYER_ORDER, PromptBlock
from app.engines.prompt.engine import (
    AssembleInput,
    PromptEngine,
    render_character_block,
    render_world_block,
)
from app.engines.prompt.entry_context import (
    ASSEMBLY_POLICY_VERSION,
    EntryContextAssemblyRequest,
    assemble_entry_context,
)
from app.models.ai_config import ModelConfig
from app.models.character import Character, Persona
from app.models.chat import ChatSession, Memory, Message
from app.models.entry import ENTRY_STATUS_VALUES, Entry
from app.models.novel import Chapter, Work
from app.models.world import GlossaryTerm, Lorebook, LoreEntry, World
from app.schemas.entry import EntryRetrievalResult, EntryStatus
from app.schemas.equivalence import (
    CandidateEvidence,
    ChatDiagnosticMode,
    CoverageRecord,
    CoverageReport,
    CoverageState,
    DiagnosticBudgetOverride,
    EntryOnlyEvidence,
    EquivalenceCompareRequest,
    EquivalenceDiagnosticReport,
    PayloadSummary,
    ProjectionEvidence,
    ProjectionKind,
    ProjectionSelectionEvidence,
    RuntimeRecord,
    RuntimeReport,
    RuntimeSelectionEvidence,
    RuntimeState,
    SituationEvidence,
)
from app.services.entry_generation_context import (
    build_chat_retrieve_request,
    build_novel_retrieve_request,
)
from app.services.entry_retrieval import RETRIEVAL_POLICY_VERSION
from app.services.entry_service import EntryService
from app.services.novel_generation_sources import load_novel_generation_sources
from app.services.story_order_snapshot import begin_story_order_snapshot
from app.services.story_summary_chronology import (
    classify_chapter_story_position,
    is_substantive_legacy_summary,
)

PROJECTION_POLICY_VERSION = "legacy-entry-equivalence-v1"
_SUPPORTED_ENTRY_TYPES = {
    "character.identity",
    "character.voice",
    "world.fact",
    "world.term",
    "story.summary",
}
_PREVIEW_LIMIT = 160


def normalize_comparison_text(value: str) -> str:
    """Apply only the normalization explicitly approved by P1-8."""

    return value.replace("\r\n", "\n").replace("\r", "\n").strip()


@dataclass(frozen=True)
class LegacyEntryProjection:
    source_key: str
    source_kind: str
    source_id: str
    source_field: str
    source_order: int
    projection_kind: ProjectionKind
    scope_kind: str
    scope_id: str
    subject_type: str
    subject_id: str
    entry_type: str
    title: str | None
    content: str
    comparison_payload: tuple[str, ...]
    priority: int | None
    story_position: int | None
    runtime_visibility: str
    selection_metadata: Mapping[str, object] = field(
        default_factory=lambda: MappingProxyType({})
    )

    @property
    def structural_key(self) -> tuple[str, str, str, str, str]:
        return (
            self.scope_kind,
            self.scope_id,
            self.subject_type,
            self.subject_id,
            self.entry_type,
        )


@dataclass(frozen=True)
class EntrySnapshot:
    id: str
    scope_kind: str
    scope_id: str | None
    subject_type: str | None
    subject_id: str | None
    entry_type: str
    status: str
    title: str | None
    content: str
    data_level: str | None
    priority: int
    live_anchor: bool
    superseded_by_entry_id: str | None
    subject_story_position: int | None = None
    created_at_chapter_id: str | None = None
    created_at_chapter_position: int | None = None

    @property
    def structural_key(self) -> tuple[str, str | None, str | None, str | None, str]:
        return (
            self.scope_kind,
            self.scope_id,
            self.subject_type,
            self.subject_id,
            self.entry_type,
        )

    @property
    def eligible(self) -> bool:
        return (
            self.status == EntryStatus.CANON.value
            and self.live_anchor
            and self.superseded_by_entry_id is None
        )


@dataclass(frozen=True)
class ProjectionBatch:
    projections: tuple[LegacyEntryProjection, ...]
    blank_source_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class EffectiveBudget:
    context_window: int
    max_tokens: int
    safety_ratio: float
    source: Literal["model_config", "diagnostic_override"]


@dataclass(frozen=True)
class LegacySourceAttribution:
    """Exact source-identity span inside one resolved aggregate prompt block."""

    block_kind: str
    start: int
    end: int
    expected_sha256: str
    resolved_payload_present: bool


@dataclass(frozen=True)
class ChatMemoryShadow:
    user_text: str
    short: list[Any]
    long: list[Memory]
    unsupported_codes: tuple[str, ...] = ()


def _payload_summary(content: str, title: str | None = None) -> PayloadSummary:
    normalized = normalize_comparison_text(content)
    title_normalized = normalize_comparison_text(title or "")
    return PayloadSummary(
        sha256=sha256(normalized.encode("utf-8")).hexdigest(),
        preview=normalized[:_PREVIEW_LIMIT],
        normalized_length=len(normalized),
        title_sha256=(
            sha256(title_normalized.encode("utf-8")).hexdigest()
            if title is not None
            else None
        ),
        title_preview=title_normalized[:_PREVIEW_LIMIT] if title is not None else None,
        title_normalized_length=len(title_normalized) if title is not None else None,
    )


def _projection(
    *,
    source_kind: str,
    source_id: str,
    source_field: str,
    source_order: int,
    source_occurrence: int | None = None,
    kind: ProjectionKind,
    scope_kind: str,
    scope_id: str,
    subject_type: str,
    subject_id: str,
    entry_type: str,
    content: str,
    title: str | None = None,
    priority: int | None = None,
    story_position: int | None = None,
    runtime_visibility: str = "visible",
    metadata: dict[str, object] | None = None,
) -> LegacyEntryProjection:
    normalized = normalize_comparison_text(content)
    payload = (
        (normalize_comparison_text(title), normalized)
        if title is not None
        else (normalized,)
    )
    return LegacyEntryProjection(
        source_key=(
            f"{source_kind}:{source_id}:{source_field}:"
            f"{source_order if source_occurrence is None else source_occurrence}"
        ),
        source_kind=source_kind,
        source_id=source_id,
        source_field=source_field,
        source_order=source_order,
        projection_kind=kind,
        scope_kind=scope_kind,
        scope_id=scope_id,
        subject_type=subject_type,
        subject_id=subject_id,
        entry_type=entry_type,
        title=title,
        content=normalized,
        comparison_payload=payload,
        priority=priority,
        story_position=story_position,
        runtime_visibility=runtime_visibility,
        selection_metadata=MappingProxyType(dict(metadata or {})),
    )


def project_character(character: Any) -> ProjectionBatch:
    """Project only the approved personality and speech-style fields."""

    rows: list[LegacyEntryProjection] = []
    blanks: list[str] = []
    character_id = str(character.id)
    for field_name, kind, entry_type in (
        ("personality", ProjectionKind.CHARACTER_PERSONALITY, "character.identity"),
        ("speech_style", ProjectionKind.CHARACTER_SPEECH_STYLE, "character.voice"),
    ):
        source_key = f"character:{character_id}:{field_name}:0"
        value = normalize_comparison_text(getattr(character, field_name, "") or "")
        if not value:
            blanks.append(source_key)
            continue
        rows.append(
            _projection(
                source_kind="character",
                source_id=character_id,
                source_field=field_name,
                source_order=0,
                kind=kind,
                scope_kind="character",
                scope_id=character_id,
                subject_type="character",
                subject_id=character_id,
                entry_type=entry_type,
                content=value,
                metadata={"aggregate_name": str(getattr(character, "name", ""))[:120]},
            )
        )
    return ProjectionBatch(tuple(rows), tuple(blanks))


def project_world(
    world: Any,
    *,
    glossary_terms: Iterable[Any] = (),
) -> ProjectionBatch:
    rows: list[LegacyEntryProjection] = []
    blanks: list[str] = []
    world_id = str(world.id)

    scalar_specs = (
        ("description", ProjectionKind.WORLD_DESCRIPTION, "visible", ""),
        ("era", ProjectionKind.WORLD_ERA, "not_applicable", "시대: "),
    )
    for field_name, kind, visibility, prefix in scalar_specs:
        source_key = f"world:{world_id}:{field_name}:0"
        raw = normalize_comparison_text(getattr(world, field_name, "") or "")
        if not raw:
            blanks.append(source_key)
            continue
        rows.append(
            _projection(
                source_kind="world",
                source_id=world_id,
                source_field=field_name,
                source_order=0,
                kind=kind,
                scope_kind="world",
                scope_id=world_id,
                subject_type="world",
                subject_id=world_id,
                entry_type="world.fact",
                content=f"{prefix}{raw}",
                runtime_visibility=visibility,
                metadata={"aggregate_name": str(getattr(world, "name", ""))[:200]},
            )
        )

    for field_name, kind, prefix in (
        ("races", ProjectionKind.WORLD_RACE, "종족: "),
        ("nations", ProjectionKind.WORLD_NATION, "국가: "),
        ("taboos", ProjectionKind.WORLD_TABOO, "금기: "),
    ):
        for index, raw_value in enumerate(getattr(world, field_name, []) or []):
            source_key = f"world:{world_id}:{field_name}:{index}"
            value = normalize_comparison_text(str(raw_value))
            if not value:
                blanks.append(source_key)
                continue
            rows.append(
                _projection(
                    source_kind="world",
                    source_id=world_id,
                    source_field=field_name,
                    source_order=index,
                    kind=kind,
                    scope_kind="world",
                    scope_id=world_id,
                    subject_type="world",
                    subject_id=world_id,
                    entry_type="world.fact",
                    content=f"{prefix}{value}",
                    runtime_visibility="not_applicable",
                )
            )

    for term in sorted(glossary_terms, key=lambda value: str(getattr(value, "id", ""))):
        term_id = str(term.id)
        source_key = f"glossary_term:{term_id}:definition:0"
        title = normalize_comparison_text(getattr(term, "term", "") or "")
        content = normalize_comparison_text(getattr(term, "definition", "") or "")
        if not title or not content:
            blanks.append(source_key)
            continue
        rows.append(
            _projection(
                source_kind="glossary_term",
                source_id=term_id,
                source_field="definition",
                source_order=0,
                kind=ProjectionKind.GLOSSARY_TERM,
                scope_kind="world",
                scope_id=world_id,
                subject_type="world",
                subject_id=world_id,
                entry_type="world.term",
                title=title,
                content=content,
                runtime_visibility="not_applicable",
            )
        )
    return ProjectionBatch(tuple(rows), tuple(blanks))


def project_lore(world_id: str, lore_rows: Iterable[tuple[Any, Any]]) -> ProjectionBatch:
    rows: list[LegacyEntryProjection] = []
    blanks: list[str] = []
    material = sorted(lore_rows, key=lambda pair: str(getattr(pair[0], "id", "")))
    effective_depth = max(
        (
            int(getattr(entry, "scan_depth", 4))
            for entry, _book in material
            if bool(getattr(entry, "enabled", True))
        ),
        default=4,
    )
    for entry, book in material:
        entry_id = str(entry.id)
        source_key = f"lore_entry:{entry_id}:content:0"
        content = normalize_comparison_text(getattr(entry, "content", "") or "")
        if not content:
            blanks.append(source_key)
            continue
        keywords = [
            str(value)[:80]
            for value in (getattr(entry, "keywords", []) or [])[:10]
            if isinstance(value, str)
        ]
        rows.append(
            _projection(
                source_kind="lore_entry",
                source_id=entry_id,
                source_field="content",
                source_order=0,
                kind=ProjectionKind.LORE,
                scope_kind="world",
                scope_id=world_id,
                subject_type="world",
                subject_id=world_id,
                entry_type="world.fact",
                content=content,
                priority=int(getattr(entry, "priority", 50)),
                metadata={
                    "keywords": tuple(keywords),
                    "entry_enabled": bool(getattr(entry, "enabled", True)),
                    "lorebook_enabled": bool(getattr(book, "enabled", True)),
                    "lorebook_id": str(getattr(book, "id", "")),
                    "scan_depth": int(getattr(entry, "scan_depth", 4)),
                    "effective_scan_depth": effective_depth,
                    "history_count": 0,
                },
            )
        )
    return ProjectionBatch(tuple(rows), tuple(blanks))


def project_chapter_summaries(chapters: Iterable[Any]) -> ProjectionBatch:
    rows: list[LegacyEntryProjection] = []
    blanks: list[str] = []
    ordered = sorted(
        chapters,
        key=lambda chapter: (int(getattr(chapter, "index", 0)), str(getattr(chapter, "id", ""))),
    )
    for chapter in ordered:
        chapter_id = str(chapter.id)
        source_key = f"chapter:{chapter_id}:summary:0"
        summary = normalize_comparison_text(getattr(chapter, "summary", "") or "")
        if not summary:
            blanks.append(source_key)
            continue
        index = int(chapter.index)
        rows.append(
            _projection(
                source_kind="chapter",
                source_id=chapter_id,
                source_field="summary",
                source_order=index,
                source_occurrence=0,
                kind=ProjectionKind.CHAPTER_SUMMARY,
                scope_kind="work",
                scope_id=str(chapter.work_id),
                subject_type="chapter",
                subject_id=chapter_id,
                entry_type="story.summary",
                content=summary,
                story_position=index,
                metadata={"chapter_index": index},
            )
        )
    return ProjectionBatch(tuple(rows), tuple(blanks))


def _payload_differences(
    projection: LegacyEntryProjection, candidate: EntrySnapshot
) -> list[str]:
    differences: list[str] = []
    if projection.title is not None and normalize_comparison_text(candidate.title or "") != projection.comparison_payload[0]:
        differences.append("title")
    expected_content = projection.comparison_payload[-1]
    if normalize_comparison_text(candidate.content) != expected_content:
        differences.append("content")
    if (
        projection.projection_kind is ProjectionKind.CHAPTER_SUMMARY
        and candidate.data_level not in {None, "chapter"}
    ):
        differences.append("data.level")
    return differences


def compare_coverage(
    projections: Iterable[LegacyEntryProjection], candidates: Iterable[EntrySnapshot]
) -> list[CoverageRecord]:
    """Apply the approved six-step coverage precedence without side effects."""

    projection_list = sorted(
        projections,
        key=lambda item: (
            item.source_kind,
            item.source_id,
            item.source_field,
            item.source_order,
            item.source_key,
        ),
    )
    candidate_list = sorted(candidates, key=lambda item: item.id)
    duplicate_counts: dict[tuple[tuple[str, str, str, str, str], tuple[str, ...]], int] = {}
    for projection in projection_list:
        group = (projection.structural_key, projection.comparison_payload)
        duplicate_counts[group] = duplicate_counts.get(group, 0) + 1

    records: list[CoverageRecord] = []
    for projection in projection_list:
        structural = [
            candidate
            for candidate in candidate_list
            if candidate.structural_key == projection.structural_key
        ]
        exact = [
            candidate
            for candidate in structural
            if not _payload_differences(projection, candidate)
        ]
        eligible_structural = [candidate for candidate in structural if candidate.eligible]
        eligible_exact = [candidate for candidate in exact if candidate.eligible]
        ineligible_exact = [candidate for candidate in exact if not candidate.eligible]

        codes: set[str] = set()
        duplicate_group = (projection.structural_key, projection.comparison_payload)
        if duplicate_counts[duplicate_group] > 1:
            codes.add("duplicate_legacy_payload")
        if len(eligible_exact) > 1:
            state = CoverageState.AMBIGUOUS_MATCH
        elif len(eligible_exact) == 1:
            state = CoverageState.EQUIVALENT
        elif eligible_structural:
            state = CoverageState.CONTENT_MISMATCH
        elif ineligible_exact:
            state = CoverageState.INELIGIBLE_ONLY
        elif structural:
            state = CoverageState.CONTENT_MISMATCH
            codes.add("all_structural_candidates_ineligible")
        else:
            state = CoverageState.MISSING_ENTRY

        evidence: list[CandidateEvidence] = []
        for candidate in structural:
            differences = _payload_differences(projection, candidate)
            evidence.append(
                CandidateEvidence(
                    entry_id=candidate.id,
                    status=candidate.status,
                    live_anchor=candidate.live_anchor,
                    exact_payload=not differences,
                    priority=candidate.priority,
                    differing_fields=differences,
                    payload=_payload_summary(candidate.content, candidate.title),
                    subject_story_position=candidate.subject_story_position,
                    created_at_chapter_position=candidate.created_at_chapter_position,
                )
            )
            if candidate.status != EntryStatus.CANON.value:
                codes.add("entry_status_excluded")
            if not candidate.live_anchor:
                codes.add("entry_orphan_excluded")

        records.append(
            CoverageRecord(
                projection=ProjectionEvidence(
                    source_key=projection.source_key,
                    source_kind=projection.source_kind,
                    source_id=projection.source_id,
                    source_field=projection.source_field,
                    source_order=projection.source_order,
                    projection_kind=projection.projection_kind,
                    scope_kind=projection.scope_kind,
                    scope_id=projection.scope_id,
                    subject_type=projection.subject_type,
                    subject_id=projection.subject_id,
                    entry_type=projection.entry_type,
                    expected=_payload_summary(projection.content, projection.title),
                    priority=projection.priority,
                    story_position=projection.story_position,
                    runtime_visibility=projection.runtime_visibility,
                    selection_metadata=ProjectionSelectionEvidence.model_validate(
                        projection.selection_metadata
                    ),
                ),
                coverage_state=state,
                eligible_exact_entry_ids=[candidate.id for candidate in eligible_exact],
                ineligible_exact_entry_ids=[candidate.id for candidate in ineligible_exact],
                candidates=evidence,
                diagnostic_codes=sorted(codes),
            )
        )
    return records


class LegacyEntryEquivalenceService:
    """One authenticated, read-only diagnostic reader for Chat and Novel."""

    def __init__(
        self,
        settings: Settings,
        registry: ProviderRegistry,
        prompt_engine: PromptEngine,
        prompt_assets: PromptAssetLoader,
        memory_engine: MemoryEngine,
        entry_service: EntryService | None = None,
    ) -> None:
        self.settings = settings
        self.registry = registry
        self.prompt_engine = prompt_engine
        self.prompt_assets = prompt_assets
        self.memory_engine = memory_engine
        self.entries = entry_service or EntryService()

    async def compare(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        request: EquivalenceCompareRequest,
    ) -> EquivalenceDiagnosticReport:
        if request.chat is not None:
            return await self._compare_chat(session, user_id, request)
        assert request.novel is not None
        # Authentication has already read the owner through this request-scoped
        # session. End that read transaction so the Novel diagnostic can pin the
        # same story-order snapshot contract as production preparation.
        await session.rollback()
        await begin_story_order_snapshot(session)
        return await self._compare_novel(session, user_id, request)

    async def _compare_chat(
        self, session: AsyncSession, user_id: str, request: EquivalenceCompareRequest
    ) -> EquivalenceDiagnosticReport:
        dto = request.chat
        assert dto is not None
        chat = (
            await session.execute(
                select(ChatSession).where(
                    ChatSession.id == dto.chat_id, ChatSession.user_id == user_id
                )
            )
        ).scalars().first()
        if chat is None:
            raise NotFound("Chat session not found")
        character = (
            await session.execute(
                select(Character).where(
                    Character.id == chat.character_id, Character.user_id == user_id
                )
            )
        ).scalars().first()
        if character is None:
            raise NotFound("Chat session not found")
        persona = None
        if chat.persona_id:
            persona = (
                await session.execute(
                    select(Persona).where(
                        Persona.id == chat.persona_id, Persona.user_id == user_id
                    )
                )
            ).scalars().first()
        world = await self._owned_world(session, user_id, character.world_id)
        glossary, lore_rows = await self._world_children(session, world)

        batches = [project_character(character)]
        if world is not None:
            batches.extend(
                [
                    project_world(world, glossary_terms=glossary),
                    project_lore(world.id, lore_rows),
                ]
            )
        projections, blanks = _combine_batches(batches)
        scopes = [("user", None), ("character", character.id)]
        if world is not None:
            scopes.append(("world", world.id))
        entries, candidates = await self._load_entry_snapshots(
            session, user_id, scopes=scopes, chapter_positions={}
        )
        coverage = compare_coverage(projections, candidates)
        budget = await self._effective_budget(
            session,
            user_id=user_id,
            model_config_id=chat.model_config_id,
            override=request.budget_override,
            target_words=None,
        )
        memory_shadow = await self._chat_memory_shadow(
            session,
            chat_id=chat.id,
            mode=dto.mode,
            supplied_message=dto.user_message,
            context_window=budget.context_window,
            evaluation_time=dto.evaluation_time,
        )
        if memory_shadow.unsupported_codes:
            runtime = self._unsupported_runtime_report(
                surface="chat",
                projections=projections,
                coverage=coverage,
                diagnostic_codes=set(memory_shadow.unsupported_codes),
            )
            return self._report(
                kind="chat",
                anchor_id=chat.id,
                mode=dto.mode.value,
                memory_evaluation_time=dto.evaluation_time,
                budget=budget,
                coverage=coverage,
                blank_keys=blanks,
                runtime=runtime,
                entries=entries,
                candidates=candidates,
                target_chapter_index=None,
                target_chapter_id=None,
            )
        retrieve_request = build_chat_retrieve_request(
            user_id=user_id,
            character=character,
            world=world,
            user_message=memory_shadow.user_text,
            context_window=budget.context_window,
        )
        retrieval = await self.entries.retrieve(session, retrieve_request)
        assembled = assemble_entry_context(
            EntryContextAssemblyRequest(retrieval, budget=retrieve_request.budget)
        )
        legacy_prompt, entry_prompt, legacy_attribution = self._chat_prompts(
            character=character,
            persona=persona,
            world=world,
            lore_rows=lore_rows,
            short=memory_shadow.short,
            long=memory_shadow.long,
            user_text=memory_shadow.user_text,
            budget=budget,
            entry_blocks=list(assembled.blocks),
        )
        runtime = self._runtime_report(
            surface="chat",
            projections=projections,
            coverage=coverage,
            candidates=candidates,
            legacy_prompt=legacy_prompt,
            entry_prompt=entry_prompt,
            retrieval=retrieval,
            assembled_entry_ids=list(assembled.included_entry_ids),
            target_chapter_index=None,
            target_chapter_id=None,
            legacy_attribution=legacy_attribution,
        )
        return self._report(
            kind="chat",
            anchor_id=chat.id,
            mode=dto.mode.value,
            memory_evaluation_time=dto.evaluation_time,
            budget=budget,
            coverage=coverage,
            blank_keys=blanks,
            runtime=runtime,
            entries=entries,
            candidates=candidates,
            target_chapter_index=None,
            target_chapter_id=None,
        )

    async def _compare_novel(
        self, session: AsyncSession, user_id: str, request: EquivalenceCompareRequest
    ) -> EquivalenceDiagnosticReport:
        dto = request.novel
        assert dto is not None
        chapter = (
            await session.execute(
                select(Chapter)
                .join(Work, Work.id == Chapter.work_id)
                .where(
                    Chapter.id == dto.chapter_id,
                    Chapter.user_id == user_id,
                    Work.user_id == user_id,
                    Work.deleted_at.is_(None),
                )
            )
        ).scalars().first()
        if chapter is None:
            raise NotFound("Chapter not found")
        work = (
            await session.execute(
                select(Work).where(
                    Work.id == chapter.work_id,
                    Work.user_id == user_id,
                    Work.deleted_at.is_(None),
                )
            )
        ).scalars().first()
        if work is None:
            raise NotFound("Chapter not found")
        chapters = list(
            (
                await session.execute(
                    select(Chapter)
                    .where(Chapter.work_id == work.id, Chapter.user_id == user_id)
                    .order_by(Chapter.index, Chapter.id)
                )
            ).scalars().all()
        )
        sources = await load_novel_generation_sources(session, work)
        characters = list(sources.characters)
        world = sources.world
        glossary, lore_rows = await self._world_children(session, world)

        batches = [project_character(character) for character in characters]
        if world is not None:
            batches.extend(
                [
                    project_world(world, glossary_terms=glossary),
                    project_lore(world.id, lore_rows),
                ]
            )
        batches.append(project_chapter_summaries(chapters))
        projections, blanks = _combine_batches(batches)
        scopes: list[tuple[str, str | None]] = [("user", None), ("work", work.id)]
        scopes.extend(("character", character.id) for character in characters)
        if world is not None:
            scopes.append(("world", world.id))
        chapter_positions = {item.id: item.index for item in chapters}
        entries, candidates = await self._load_entry_snapshots(
            session,
            user_id,
            scopes=scopes,
            chapter_positions=chapter_positions,
        )
        coverage = compare_coverage(projections, candidates)
        budget = await self._effective_budget(
            session,
            user_id=user_id,
            model_config_id=None,
            override=request.budget_override,
            target_words=dto.target_words,
        )
        retrieve_request = build_novel_retrieve_request(
            user_id=user_id,
            work=work,
            world=world,
            characters=characters,
            chapter=chapter,
            instruction=dto.instruction,
            context_window=budget.context_window,
            substantive_legacy_summary_chapter_ids=tuple(
                item.id
                for item in chapters
                if item.index < chapter.index
                and is_substantive_legacy_summary(item.summary)
            ),
        )
        retrieval = await self.entries.retrieve(session, retrieve_request)
        assembled = assemble_entry_context(
            EntryContextAssemblyRequest(retrieval, budget=retrieve_request.budget)
        )
        prior = [
            item.summary
            for item in chapters
            if item.index < chapter.index
            and is_substantive_legacy_summary(item.summary)
        ]
        legacy_prompt, entry_prompt, legacy_attribution = self._novel_prompts(
            chapter=chapter,
            characters=characters,
            world=world,
            lore_rows=lore_rows,
            prior_summaries=prior,
            instruction=dto.instruction,
            budget=budget,
            entry_blocks=list(assembled.blocks),
        )
        runtime = self._runtime_report(
            surface="novel",
            projections=projections,
            coverage=coverage,
            candidates=candidates,
            legacy_prompt=legacy_prompt,
            entry_prompt=entry_prompt,
            retrieval=retrieval,
            assembled_entry_ids=list(assembled.included_entry_ids),
            target_chapter_index=chapter.index,
            target_chapter_id=chapter.id,
            legacy_attribution=legacy_attribution,
        )
        return self._report(
            kind="novel",
            anchor_id=chapter.id,
            mode=None,
            memory_evaluation_time=None,
            budget=budget,
            coverage=coverage,
            blank_keys=blanks,
            runtime=runtime,
            entries=entries,
            candidates=candidates,
            target_chapter_index=chapter.index,
            target_chapter_id=chapter.id,
        )

    async def _owned_world(
        self, session: AsyncSession, user_id: str, world_id: str | None
    ) -> World | None:
        if world_id is None:
            return None
        return (
            await session.execute(
                select(World).where(World.id == world_id, World.user_id == user_id)
            )
        ).scalars().first()

    async def _world_children(
        self, session: AsyncSession, world: World | None
    ) -> tuple[list[GlossaryTerm], list[tuple[LoreEntry, Lorebook]]]:
        if world is None:
            return [], []
        glossary = list(
            (
                await session.execute(
                    select(GlossaryTerm)
                    .where(GlossaryTerm.world_id == world.id)
                    .order_by(GlossaryTerm.id)
                )
            ).scalars().all()
        )
        lore_rows = list(
            (
                await session.execute(
                    select(LoreEntry, Lorebook)
                    .join(Lorebook, Lorebook.id == LoreEntry.lorebook_id)
                    .where(Lorebook.world_id == world.id)
                )
            ).tuples().all()
        )
        return glossary, lore_rows

    async def _load_entry_snapshots(
        self,
        session: AsyncSession,
        user_id: str,
        *,
        scopes: list[tuple[str, str | None]],
        chapter_positions: dict[str, int],
    ) -> tuple[list[Entry], list[EntrySnapshot]]:
        predicates = [
            and_(
                Entry.scope_kind == kind,
                Entry.scope_id.is_(None) if scope_id is None else Entry.scope_id == scope_id,
            )
            for kind, scope_id in scopes
        ]
        stmt = (
            select(Entry)
            .where(
                Entry.user_id == user_id,
                or_(*predicates),
                Entry.type.in_(sorted(_SUPPORTED_ENTRY_TYPES)),
                Entry.status.in_(ENTRY_STATUS_VALUES),
            )
            .order_by(Entry.id)
        )
        entries = list((await session.execute(stmt)).scalars().all())
        live, _orphaned = await self.entries._exclude_orphaned_candidates(  # noqa: SLF001
            session, user_id, entries
        )
        live_ids = {entry.id for entry in live}
        snapshots = [
            EntrySnapshot(
                id=entry.id,
                scope_kind=entry.scope_kind,
                scope_id=entry.scope_id,
                subject_type=entry.subject_type,
                subject_id=entry.subject_id,
                entry_type=entry.type,
                status=entry.status,
                title=entry.title,
                content=entry.content,
                data_level=(entry.data or {}).get("level")
                if isinstance((entry.data or {}).get("level"), str)
                else None,
                priority=entry.priority,
                live_anchor=entry.id in live_ids,
                superseded_by_entry_id=entry.superseded_by_entry_id,
                subject_story_position=chapter_positions.get(entry.subject_id or ""),
                created_at_chapter_id=entry.created_at_chapter_id,
                created_at_chapter_position=chapter_positions.get(
                    entry.created_at_chapter_id or ""
                ),
            )
            for entry in entries
        ]
        return entries, snapshots

    async def _effective_budget(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        model_config_id: str | None,
        override: DiagnosticBudgetOverride | None,
        target_words: int | None,
    ) -> EffectiveBudget:
        if override is not None:
            return EffectiveBudget(
                context_window=override.context_window,
                max_tokens=override.max_tokens,
                safety_ratio=override.safety_ratio,
                source="diagnostic_override",
            )
        if model_config_id:
            stmt = select(ModelConfig).where(
                ModelConfig.id == model_config_id, ModelConfig.user_id == user_id
            )
        else:
            stmt = (
                select(ModelConfig)
                .where(ModelConfig.user_id == user_id, ModelConfig.is_default.is_(True))
                .limit(1)
            )
        config = (await session.execute(stmt)).scalars().first()
        if config is None and model_config_id is None:
            config = (
                await session.execute(
                    select(ModelConfig).where(ModelConfig.user_id == user_id).limit(1)
                )
            ).scalars().first()
        if config is None:
            raise NotFound(
                "ModelConfig not found"
                if model_config_id
                else "No ModelConfig configured. Add one in settings."
            )
        capability = self.registry.capabilities(config.provider, config.model_name)
        context_window = config.context_window or capability.context_window
        if capability.context_window > 0:
            context_window = min(context_window, capability.context_window)
        max_tokens = config.max_tokens
        if target_words is not None:
            max_tokens = min(max_tokens, words_to_tokens(target_words))
        if context_window < max_tokens:
            raise ValidationAppError("context_window < max_tokens", {"inv": "INV-6"})
        return EffectiveBudget(
            context_window=context_window,
            max_tokens=max_tokens,
            safety_ratio=capability.safety_ratio,
            source="model_config",
        )

    async def _chat_memory_shadow(
        self,
        session: AsyncSession,
        *,
        chat_id: str,
        mode: ChatDiagnosticMode,
        supplied_message: str | None,
        context_window: int,
        evaluation_time: datetime | None,
    ) -> ChatMemoryShadow:
        active: list[Any] = list(
            (
                await session.execute(
                    select(Message)
                    .where(
                        Message.chat_session_id == chat_id,
                        Message.is_active.is_(True),
                    )
                    .order_by(Message.created_at, Message.id)
                )
            ).scalars().all()
        )
        unsupported_codes: set[str] = set()
        if mode is ChatDiagnosticMode.REGENERATE:
            assistants = [message for message in active if message.role == "assistant"]
            if assistants:
                latest_assistant_time = max(message.created_at for message in assistants)
                if sum(
                    message.created_at == latest_assistant_time for message in assistants
                ) > 1:
                    # A timestamp tie has no production regenerate tie-break.
                    # Stop before selecting any message content or invoking a
                    # content-dependent diagnostic path.
                    return ChatMemoryShadow(
                        user_text="",
                        short=[],
                        long=[],
                        unsupported_codes=("regenerate_assistant_timestamp_tie",),
                    )
                active.remove(assistants[-1])
            users = list(
                (
                    await session.execute(
                        select(Message)
                        .where(
                            Message.chat_session_id == chat_id,
                            Message.role == "user",
                        )
                        .order_by(Message.created_at, Message.id)
                    )
                ).scalars().all()
            )
            if users:
                latest_user_time = max(message.created_at for message in users)
                if sum(message.created_at == latest_user_time for message in users) > 1:
                    # Do not turn an arbitrary id-ordered tie candidate into a
                    # Memory query.  The unsupported report needs no message
                    # payload, so the fail-closed boundary is here.
                    return ChatMemoryShadow(
                        user_text="",
                        short=[],
                        long=[],
                        unsupported_codes=("regenerate_user_timestamp_tie",),
                    )
            user_text = users[-1].content if users else ""
        else:
            assert supplied_message is not None
            user_text = supplied_message
            active.append(
                SimpleNamespace(
                    id="diagnostic:new_message",
                    role="user",
                    content=user_text,
                    token_count=self.prompt_engine.tok.count(user_text),
                    is_active=True,
                )
            )
        short: list[Any] = active[-SHORT_WINDOW:]
        candidates = await self.memory_engine.retriever.search(
            session, chat_id, user_text, RETRIEVE_K
        )
        if candidates and evaluation_time is None:
            unsupported_codes.add("memory_evaluation_time_required")
        if unsupported_codes:
            return ChatMemoryShadow(
                user_text=user_text,
                short=short,
                long=[],
                unsupported_codes=tuple(sorted(unsupported_codes)),
            )
        ranked = rank_memories(
            candidates,
            user_text,
            evaluation_time=evaluation_time,
        ) if evaluation_time is not None else []
        long = self.memory_engine._select_within_budget(  # noqa: SLF001
            ranked, max(256, int(context_window * 0.4))
        )
        return ChatMemoryShadow(user_text=user_text, short=short, long=long)

    def _chat_prompts(
        self,
        *,
        character: Character,
        persona: Persona | None,
        world: World | None,
        lore_rows: list[tuple[LoreEntry, Lorebook]],
        short: list[Any],
        long: list[Memory],
        user_text: str,
        budget: EffectiveBudget,
        entry_blocks: list[PromptBlock],
    ) -> tuple[AssembledPrompt, AssembledPrompt, dict[str, LegacySourceAttribution]]:
        asset = self.prompt_assets.load("chat.default")
        legacy_lore = [entry for entry, _book in lore_rows if entry.enabled]
        legacy_input = AssembleInput(
            template_body=asset.body,
            prompt_asset_id=asset.asset_id,
            prompt_asset_version=asset.version,
            prompt_asset_sha256=asset.sha256,
            character=character,
            persona=persona,
            world=world,
            lore_entries=legacy_lore,
            memory_short=short,
            memory_long=long,
            history=[],
            user_message=user_text,
            context_window=budget.context_window,
            max_tokens=budget.max_tokens,
            safety_ratio=budget.safety_ratio,
        )
        legacy_context = self.prompt_engine._ctx(legacy_input)  # noqa: SLF001
        resolve = lambda value: self.prompt_engine._resolve(  # noqa: E731, SLF001
            value, legacy_context
        )
        attribution: dict[str, LegacySourceAttribution] = {}
        rendered_character = render_character_block(character, transform=resolve)
        for field_name in ("personality", "speech_style"):
            span = rendered_character.field_spans.get(field_name)
            if span is not None:
                source_key = f"character:{character.id}:{field_name}:0"
                attribution[source_key] = _legacy_source_attribution(
                    "character",
                    span,
                    resolve(str(getattr(character, field_name, ""))),
                )
        if world is not None:
            rendered_world = render_world_block(world, transform=resolve)
            span = rendered_world.field_spans["description"]
            attribution[f"world:{world.id}:description:0"] = _legacy_source_attribution(
                "world", span, resolve(str(world.description))
            )
        legacy = self.prompt_engine.assemble(legacy_input)
        character_identity = SimpleNamespace(
            id=character.id, name=character.name, personality="", speech_style=""
        )
        world_identity = (
            SimpleNamespace(id=world.id, name=world.name, description="", era="")
            if world is not None
            else None
        )
        entry = self.prompt_engine.assemble(
            AssembleInput(
                character=character_identity,
                world=world_identity,
                lore_entries=[],
                entry_blocks=entry_blocks,
                template_body=asset.body,
                prompt_asset_id=asset.asset_id,
                prompt_asset_version=asset.version,
                prompt_asset_sha256=asset.sha256,
                persona=persona,
                memory_short=short,
                memory_long=long,
                history=[],
                user_message=user_text,
                context_window=budget.context_window,
                max_tokens=budget.max_tokens,
                safety_ratio=budget.safety_ratio,
            )
        )
        return legacy, entry, attribution

    def _novel_prompts(
        self,
        *,
        chapter: Chapter,
        characters: list[Character],
        world: World | None,
        lore_rows: list[tuple[LoreEntry, Lorebook]],
        prior_summaries: list[str],
        instruction: str,
        budget: EffectiveBudget,
        entry_blocks: list[PromptBlock],
    ) -> tuple[AssembledPrompt, AssembledPrompt, dict[str, LegacySourceAttribution]]:
        asset = self.prompt_assets.load("novel.continue")
        resolution_context = self.prompt_engine._ctx(  # noqa: SLF001
            AssembleInput(template_body="", world=world)
        )

        def body(
            include_legacy: bool,
        ) -> tuple[str, dict[str, LegacySourceAttribution]]:
            raw_parts: list[str] = []
            resolved_length = 0
            source_attribution: dict[str, LegacySourceAttribution] = {}

            def append(
                raw: str,
                *,
                source_key: str | None = None,
                expected: str | None = None,
            ) -> None:
                nonlocal resolved_length
                raw_parts.append(raw)
                resolved = self.prompt_engine._resolve(  # noqa: SLF001
                    raw, resolution_context
                )
                start = resolved_length
                resolved_length += len(resolved)
                if source_key is not None and expected is not None:
                    source_attribution[source_key] = _legacy_source_attribution(
                        "system", (start, resolved_length), resolved
                    )

            append(asset.body)
            if characters:
                append("\n\n[등장인물]\n")
            for index, character in enumerate(characters):
                if index:
                    append("\n")
                append("- ")
                append(str(character.name))
                append(": ")
                personality = str(character.personality) if include_legacy else ""
                append(
                    personality,
                    source_key=(
                        f"character:{character.id}:personality:0" if include_legacy else None
                    ),
                    expected=personality if include_legacy else None,
                )
                append(" / 말투: ")
                speech_style = str(character.speech_style) if include_legacy else ""
                append(
                    speech_style,
                    source_key=(
                        f"character:{character.id}:speech_style:0" if include_legacy else None
                    ),
                    expected=speech_style if include_legacy else None,
                )
            return "".join(raw_parts), source_attribution

        tail = (chapter.content_text or "")[-1200:]
        legacy_body, attribution = body(True)
        if world is not None:
            resolve = lambda value: self.prompt_engine._resolve(  # noqa: E731, SLF001
                value, resolution_context
            )
            rendered_world = render_world_block(world, transform=resolve)
            attribution[f"world:{world.id}:description:0"] = _legacy_source_attribution(
                "world",
                rendered_world.field_spans["description"],
                resolve(str(world.description)),
            )
        legacy = self.prompt_engine.assemble(
            AssembleInput(
                template_body=legacy_body,
                prompt_asset_id=asset.asset_id,
                prompt_asset_version=asset.version,
                prompt_asset_sha256=asset.sha256,
                world=world,
                lore_entries=[entry for entry, _book in lore_rows if entry.enabled],
                chapter_prior_summaries=prior_summaries,
                history=[],
                user_message=f"[현재 챕터 끝부분]\n{tail}" if tail else None,
                instruction=instruction or "자연스럽게 다음 장면을 이어써라.",
                context_window=budget.context_window,
                max_tokens=budget.max_tokens,
                safety_ratio=budget.safety_ratio,
            )
        )
        world_identity = (
            SimpleNamespace(id=world.id, name=world.name, description="", era="")
            if world is not None
            else None
        )
        entry_body, _entry_attribution = body(False)
        entry = self.prompt_engine.assemble(
            AssembleInput(
                template_body=entry_body,
                prompt_asset_id=asset.asset_id,
                prompt_asset_version=asset.version,
                prompt_asset_sha256=asset.sha256,
                world=world_identity,
                lore_entries=[],
                chapter_prior_summaries=[],
                entry_blocks=entry_blocks,
                history=[],
                user_message=f"[현재 챕터 끝부분]\n{tail}" if tail else None,
                instruction=instruction or "자연스럽게 다음 장면을 이어써라.",
                context_window=budget.context_window,
                max_tokens=budget.max_tokens,
                safety_ratio=budget.safety_ratio,
            )
        )
        return legacy, entry, attribution

    def _unsupported_runtime_report(
        self,
        *,
        surface: Literal["chat", "novel"],
        projections: list[LegacyEntryProjection],
        coverage: list[CoverageRecord],
        diagnostic_codes: set[str],
    ) -> RuntimeReport:
        """Return deterministic no-selection evidence for an ambiguous request."""

        coverage_by_key = {record.projection.source_key: record for record in coverage}
        records: list[RuntimeRecord] = []
        unsupported_reason = sorted(diagnostic_codes)[0]
        for projection in projections:
            codes = set(coverage_by_key[projection.source_key].diagnostic_codes)
            if not self.settings.entry_store_context_enabled:
                codes.add("entry_context_feature_flag_off")
            if projection.runtime_visibility == "not_applicable":
                state = RuntimeState.NOT_APPLICABLE
                exclusion = "legacy_not_runtime_visible"
                codes.add(exclusion)
            else:
                state = RuntimeState.UNSUPPORTED_LEGACY_SEMANTICS
                exclusion = unsupported_reason
                codes.update(diagnostic_codes)
            records.append(
                RuntimeRecord(
                    source_key=projection.source_key,
                    runtime_state=state,
                    legacy=RuntimeSelectionEvidence(
                        selected=False,
                        final_prompt_selected=False,
                        exclusion_code=exclusion,
                        trace_ids=[projection.source_key],
                    ),
                    entry=RuntimeSelectionEvidence(
                        selected=False,
                        retrieval_selected=None,
                        assembly_selected=None,
                        final_prompt_selected=None,
                        exclusion_code=exclusion,
                    ),
                    diagnostic_codes=sorted(codes),
                )
            )
        records.sort(key=lambda record: record.source_key or "")
        return RuntimeReport(
            surface=surface,
            records=records,
            counts=_enum_counts(record.runtime_state.value for record in records),
        )

    def _runtime_report(
        self,
        *,
        surface: Literal["chat", "novel"],
        projections: list[LegacyEntryProjection],
        coverage: list[CoverageRecord],
        candidates: list[EntrySnapshot],
        legacy_prompt: AssembledPrompt,
        entry_prompt: AssembledPrompt,
        retrieval: EntryRetrievalResult,
        assembled_entry_ids: list[str],
        target_chapter_index: int | None,
        target_chapter_id: str | None,
        legacy_attribution: dict[str, LegacySourceAttribution],
    ) -> RuntimeReport:
        coverage_by_key = {record.projection.source_key: record for record in coverage}
        candidate_by_id = {candidate.id: candidate for candidate in candidates}
        retrieval_items = list(retrieval.items)
        retrieval_ids = [item.entry.id for item in retrieval_items]
        retrieval_trace = retrieval.trace
        chronology_exclusions_by_id = {
            exclusion.entry_id: exclusion
            for exclusion in retrieval_trace.story_summary_chronology_exclusions
        }
        final_entry_ids = _final_entry_ids(entry_prompt, assembled_entry_ids)
        entry_positions = {entry_id: index for index, entry_id in enumerate(final_entry_ids)}
        legacy_trace_rows = list(legacy_prompt.trace.get("entries", []))
        legacy_trace_by_id = {
            str(item["block_id"]): item for item in legacy_trace_rows
        }
        ordered_included_rows = _ordered_included_trace_rows(legacy_prompt)
        legacy_block_positions = {
            str(item["block_id"]): index
            for index, item in enumerate(ordered_included_rows)
        }
        legacy_block_contents = {
            str(item["block_id"]): message.content
            for item, message in zip(
                ordered_included_rows, legacy_prompt.messages, strict=True
            )
        }
        legacy_included_ids = {
            str(item["block_id"])
            for item in legacy_trace_rows
            if item.get("status") == "included"
        }
        summary_projections = sorted(
            (
                projection
                for projection in projections
                if projection.projection_kind is ProjectionKind.CHAPTER_SUMMARY
                and target_chapter_index is not None
                and projection.story_position is not None
                and projection.story_position < target_chapter_index
            ),
            key=lambda item: (item.story_position or 0, item.source_id),
        )
        summary_trace_rows = sorted(
            (
                item
                for item in legacy_trace_rows
                if item.get("kind") == "chapter"
            ),
            key=lambda item: int(str(item["block_id"]).rsplit(":", 1)[-1]),
        )
        summary_block_ids = {
            projection.source_key: str(item["block_id"])
            for projection, item in zip(
                summary_projections, summary_trace_rows, strict=False
            )
        }
        records: list[RuntimeRecord] = []

        lore_selected_by_priority: dict[int, list[str]] = {}
        for projection in projections:
            if projection.projection_kind is not ProjectionKind.LORE:
                continue
            metadata = projection.selection_metadata
            matched = bool(metadata.get("entry_enabled")) and (
                f"lore:{projection.source_id}" in legacy_trace_by_id
            )
            if matched:
                lore_selected_by_priority.setdefault(projection.priority or 50, []).append(
                    projection.source_key
                )
        unsupported_lore = {
            source_key
            for source_keys in lore_selected_by_priority.values()
            if len(source_keys) > 1
            for source_key in source_keys
        }

        legacy_sequence_pairs: list[tuple[tuple[int, int, int], str]] = []
        entry_sequence_pairs: list[tuple[int, str]] = []
        for projection in projections:
            coverage_record = coverage_by_key[projection.source_key]
            codes = set(coverage_record.diagnostic_codes)
            if not self.settings.entry_store_context_enabled:
                codes.add("entry_context_feature_flag_off")
            applicable = projection.runtime_visibility != "not_applicable"
            initially_selected = applicable
            exclusion: str | None = None
            if not applicable:
                initially_selected = False
                exclusion = "legacy_not_runtime_visible"
                codes.add("legacy_not_runtime_visible")
            elif projection.projection_kind is ProjectionKind.LORE:
                metadata = projection.selection_metadata
                if not bool(metadata.get("lorebook_enabled")):
                    codes.add("ignored_disabled_lorebook")
                if not bool(metadata.get("entry_enabled")):
                    initially_selected = False
                    exclusion = "legacy_disabled_entry"
                    codes.add("legacy_disabled_entry")
                else:
                    if f"lore:{projection.source_id}" not in legacy_trace_by_id:
                        initially_selected = False
                        exclusion = "legacy_keyword_miss"
                        codes.add("legacy_keyword_miss")
            elif projection.projection_kind is ProjectionKind.CHAPTER_SUMMARY:
                if surface != "novel" or target_chapter_index is None:
                    initially_selected = False
                    exclusion = "legacy_not_runtime_visible"
                    codes.add("legacy_not_runtime_visible")
                elif projection.story_position is None or projection.story_position >= target_chapter_index:
                    initially_selected = False
                    exclusion = "future_or_current_legacy_summary"

            if projection.projection_kind in {
                ProjectionKind.CHARACTER_PERSONALITY,
                ProjectionKind.CHARACTER_SPEECH_STYLE,
            }:
                legacy_block_id = next(
                    (
                        str(item["block_id"])
                        for item in legacy_trace_rows
                        if item.get("kind") == ("character" if surface == "chat" else "system")
                    ),
                    None,
                )
            elif projection.projection_kind is ProjectionKind.WORLD_DESCRIPTION:
                legacy_block_id = next(
                    (
                        str(item["block_id"])
                        for item in legacy_trace_rows
                        if item.get("kind") == "world"
                    ),
                    None,
                )
            elif projection.projection_kind is ProjectionKind.LORE:
                legacy_block_id = f"lore:{projection.source_id}"
            elif projection.projection_kind is ProjectionKind.CHAPTER_SUMMARY:
                legacy_block_id = summary_block_ids.get(projection.source_key)
            else:
                legacy_block_id = None
            trace_selected = (
                legacy_block_id is not None
                and legacy_block_id in legacy_included_ids
            )
            legacy_position = (
                legacy_block_positions.get(legacy_block_id)
                if legacy_block_id is not None
                else None
            )
            block_content = (
                legacy_block_contents.get(legacy_block_id, "")
                if legacy_block_id is not None
                else ""
            )
            source_attribution = legacy_attribution.get(projection.source_key)
            if source_attribution is not None:
                source_survived = (
                    legacy_block_id is not None
                    and str(legacy_trace_by_id[legacy_block_id].get("kind"))
                    == source_attribution.block_kind
                    and _attributed_source_survived(
                        source_attribution, block_content
                    )
                )
            else:
                # Lore and Chapter summaries are one-source-per-block. Requiring
                # full normalized equality detects truncation without allowing a
                # coincidental substring in another source to stand in for them.
                source_survived = (
                    normalize_comparison_text(block_content) == projection.content
                )
            legacy_final = initially_selected and trace_selected and source_survived
            if (
                initially_selected
                and source_attribution is not None
                and not source_attribution.resolved_payload_present
            ):
                exclusion = "legacy_resolved_payload_empty"
                codes.add("legacy_resolved_payload_empty")
            elif initially_selected and not legacy_final:
                exclusion = "final_prompt_budget_drop"
                codes.add("final_prompt_budget_drop")
            legacy_position = legacy_position if legacy_final else None
            order_applicable = applicable and projection.source_key not in unsupported_lore
            if legacy_final and legacy_position is not None and order_applicable:
                inner_start = source_attribution.start if source_attribution is not None else 0
                inner_end = (
                    source_attribution.end
                    if source_attribution is not None
                    else len(block_content)
                )
                legacy_sequence_pairs.append(
                    ((legacy_position, inner_start, inner_end), projection.source_key)
                )

            exact_ids = coverage_record.eligible_exact_entry_ids
            retrieved_exact = [entry_id for entry_id in exact_ids if entry_id in retrieval_ids]
            assembled_exact = [entry_id for entry_id in retrieved_exact if entry_id in assembled_entry_ids]
            final_exact = [entry_id for entry_id in assembled_exact if entry_id in final_entry_ids]
            entry_exclusion: str | None = None
            if not final_exact:
                chronology_reasons = sorted(
                    {
                        chronology_exclusions_by_id[entry_id].reason
                        for entry_id in exact_ids
                        if entry_id in chronology_exclusions_by_id
                    }
                )
                if chronology_reasons:
                    entry_exclusion = chronology_reasons[0]
                    codes.add("entry_chronology_excluded")
                    codes.update(chronology_reasons)
                elif any(entry_id in retrieval_trace.limit_rejected_entry_ids for entry_id in exact_ids):
                    entry_exclusion = "entry_limit_rejected"
                    codes.add(entry_exclusion)
                elif any(entry_id in retrieval_trace.budget_rejected_entry_ids for entry_id in exact_ids):
                    entry_exclusion = "entry_retrieval_budget_rejected"
                    codes.add(entry_exclusion)
                elif retrieved_exact and not assembled_exact:
                    entry_exclusion = "entry_rendered_budget_rejected"
                    codes.add(entry_exclusion)
                elif assembled_exact:
                    entry_exclusion = "final_prompt_budget_drop"
                    codes.add(entry_exclusion)
                elif coverage_record.ineligible_exact_entry_ids:
                    entry_exclusion = (
                        "entry_orphan_excluded"
                        if any(
                            not candidate_by_id[entry_id].live_anchor
                            for entry_id in coverage_record.ineligible_exact_entry_ids
                        )
                        else "entry_status_excluded"
                    )
                    codes.add(entry_exclusion)
                elif not exact_ids:
                    entry_exclusion = "no_eligible_exact_entry"

            for entry_id in exact_ids:
                if entry_id in final_exact and order_applicable:
                    entry_sequence_pairs.append(
                        (entry_positions[entry_id], projection.source_key)
                    )
                candidate = candidate_by_id[entry_id]
                codes.add("database_timestamp_recency")
                if projection.projection_kind is ProjectionKind.CHAPTER_SUMMARY:
                    codes.update(
                        _story_position_codes(
                            candidate,
                            target_chapter_index,
                            target_chapter_id,
                            selected=entry_id in final_exact,
                        )
                    )

            if not applicable:
                state = RuntimeState.NOT_APPLICABLE
            elif projection.source_key in unsupported_lore:
                state = RuntimeState.UNSUPPORTED_LEGACY_SEMANTICS
                codes.add("legacy_equal_priority_order_unspecified")
            elif int(legacy_final) == len(final_exact):
                state = RuntimeState.EQUIVALENT
            else:
                state = RuntimeState.SELECTION_MISMATCH
                if int(legacy_final) != len(final_exact):
                    codes.add("runtime_occurrence_mismatch")

            records.append(
                RuntimeRecord(
                    source_key=projection.source_key,
                    runtime_state=state,
                    legacy=RuntimeSelectionEvidence(
                        selected=legacy_final,
                        selection_position=legacy_position,
                        final_prompt_selected=legacy_final,
                        exclusion_code=exclusion,
                        trace_ids=[projection.source_key],
                    ),
                    entry=RuntimeSelectionEvidence(
                        selected=bool(final_exact),
                        selection_position=(
                            min(entry_positions[entry_id] for entry_id in final_exact)
                            if final_exact
                            else None
                        ),
                        retrieval_selected=bool(retrieved_exact),
                        assembly_selected=bool(assembled_exact),
                        final_prompt_selected=bool(final_exact),
                        exclusion_code=entry_exclusion,
                        trace_ids=exact_ids,
                    ),
                    diagnostic_codes=sorted(codes),
                )
            )

        # Coverage may reuse one canon row for duplicate legacy facts, but runtime
        # occurrence counts must remain visible (design §5.4).
        duplicate_groups: dict[tuple[tuple[str, str, str, str, str], tuple[str, ...]], list[str]] = {}
        for projection in projections:
            duplicate_groups.setdefault(
                (projection.structural_key, projection.comparison_payload), []
            ).append(projection.source_key)
        records_by_source = {record.source_key: record for record in records}
        for source_keys in duplicate_groups.values():
            if len(source_keys) < 2:
                continue
            legacy_count = sum(records_by_source[key].legacy.selected for key in source_keys)
            entry_ids = {
                entry_id
                for key in source_keys
                for entry_id in records_by_source[key].entry.trace_ids
                if entry_id in final_entry_ids
            }
            if legacy_count != len(entry_ids):
                for key in source_keys:
                    duplicate_record = records_by_source[key]
                    if duplicate_record.runtime_state is not RuntimeState.NOT_APPLICABLE:
                        duplicate_record.runtime_state = RuntimeState.SELECTION_MISMATCH
                        duplicate_record.diagnostic_codes = sorted(
                            set(duplicate_record.diagnostic_codes)
                            | {"runtime_occurrence_mismatch"}
                        )

        legacy_sequence = [key for _position, key in sorted(legacy_sequence_pairs)]
        entry_sequence = [key for _position, key in sorted(entry_sequence_pairs)]
        if legacy_sequence != entry_sequence:
            differing = set(legacy_sequence) | set(entry_sequence)
            for key in differing:
                order_record = records_by_source.get(key)
                if (
                    order_record is not None
                    and order_record.runtime_state is RuntimeState.EQUIVALENT
                ):
                    order_record.runtime_state = RuntimeState.SELECTION_MISMATCH
                    order_record.diagnostic_codes = sorted(
                        set(order_record.diagnostic_codes) | {"stable_order_mismatch"}
                    )

        matched_exact_ids = {
            candidate.entry_id
            for coverage_record in coverage
            for candidate in coverage_record.candidates
            if candidate.exact_payload
        }
        for entry_id in final_entry_ids:
            if entry_id in matched_exact_ids:
                continue
            entry_only_candidate = candidate_by_id.get(entry_id)
            codes = {"entry_only", "database_timestamp_recency"}
            if not self.settings.entry_store_context_enabled:
                codes.add("entry_context_feature_flag_off")
            if (
                entry_only_candidate is not None
                and entry_only_candidate.entry_type == "story.summary"
            ):
                codes.update(
                    _story_position_codes(
                        entry_only_candidate,
                        target_chapter_index,
                        target_chapter_id,
                        selected=True,
                    )
                )
            records.append(
                RuntimeRecord(
                    entry_id=entry_id,
                    runtime_state=RuntimeState.SELECTION_MISMATCH,
                    legacy=RuntimeSelectionEvidence(
                        selected=False,
                        final_prompt_selected=False,
                        exclusion_code="no_legacy_projection",
                    ),
                    entry=RuntimeSelectionEvidence(
                        selected=True,
                        selection_position=entry_positions[entry_id],
                        retrieval_selected=True,
                        assembly_selected=True,
                        final_prompt_selected=True,
                        trace_ids=[entry_id],
                    ),
                    diagnostic_codes=sorted(codes),
                )
            )
        records.sort(key=lambda record: (record.source_key or "", record.entry_id or ""))
        return RuntimeReport(
            surface=surface,
            records=records,
            counts=_enum_counts(record.runtime_state.value for record in records),
        )

    def _report(
        self,
        *,
        kind: Literal["chat", "novel"],
        anchor_id: str,
        mode: str | None,
        memory_evaluation_time: datetime | None,
        budget: EffectiveBudget,
        coverage: list[CoverageRecord],
        blank_keys: list[str],
        runtime: RuntimeReport,
        entries: list[Entry],
        candidates: list[EntrySnapshot],
        target_chapter_index: int | None,
        target_chapter_id: str | None,
    ) -> EquivalenceDiagnosticReport:
        exact_entry_ids = {
            candidate.entry_id
            for record in coverage
            for candidate in record.candidates
            if candidate.exact_payload
        }
        runtime_selected_ids = {
            entry_id
            for record in runtime.records
            for entry_id in record.entry.trace_ids
            if record.entry.final_prompt_selected
        }
        eligible_ids = {candidate.id for candidate in candidates if candidate.eligible}
        candidate_by_id = {candidate.id: candidate for candidate in candidates}
        entry_only: list[EntryOnlyEvidence] = []
        for entry in sorted(entries, key=lambda value: value.id):
            if (
                entry.status != EntryStatus.CANON.value
                or entry.superseded_by_entry_id is not None
                or entry.id not in eligible_ids
                or entry.id in exact_entry_ids
            ):
                continue
            codes = ["database_timestamp_recency"]
            candidate = candidate_by_id[entry.id]
            runtime_selected = entry.id in runtime_selected_ids
            if entry.type == "story.summary":
                codes.extend(
                    _story_position_codes(
                        candidate,
                        target_chapter_index,
                        target_chapter_id,
                        selected=runtime_selected,
                    )
                )
            entry_only.append(
                EntryOnlyEvidence(
                    entry_id=entry.id,
                    scope_kind=entry.scope_kind,
                    scope_id=entry.scope_id,
                    subject_type=entry.subject_type,
                    subject_id=entry.subject_id,
                    entry_type=entry.type,
                    payload=_payload_summary(entry.content, entry.title),
                    runtime_selected=runtime_selected,
                    diagnostic_codes=sorted(codes),
                )
            )
        return EquivalenceDiagnosticReport(
            situation=SituationEvidence(
                kind=kind,
                anchor_id=anchor_id,
                mode=mode,
                memory_evaluation_time=memory_evaluation_time,
                context_window=budget.context_window,
                max_tokens=budget.max_tokens,
                safety_ratio=budget.safety_ratio,
                budget_source=budget.source,
                entry_context_feature_enabled=self.settings.entry_store_context_enabled,
                retrieval_policy_version=RETRIEVAL_POLICY_VERSION,
                assembly_policy_version=ASSEMBLY_POLICY_VERSION,
                projection_policy_version=PROJECTION_POLICY_VERSION,
            ),
            coverage=CoverageReport(
                records=coverage,
                blank_source_keys=sorted(blank_keys),
                counts=_enum_counts(record.coverage_state.value for record in coverage),
            ),
            runtime=runtime,
            entry_only=entry_only,
        )


def _combine_batches(
    batches: Iterable[ProjectionBatch],
) -> tuple[list[LegacyEntryProjection], list[str]]:
    projections = [projection for batch in batches for projection in batch.projections]
    projections.sort(
        key=lambda item: (
            item.source_kind,
            item.source_id,
            item.source_field,
            item.source_order,
            item.source_key,
        )
    )
    blank_keys = [key for batch in batches for key in batch.blank_source_keys]
    return projections, sorted(blank_keys)


def _enum_counts(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _ordered_included_trace_rows(prompt: AssembledPrompt) -> list[dict[str, object]]:
    rows = [
        item
        for item in prompt.trace.get("entries", [])
        if item.get("status") == "included"
    ]
    order_index: dict[str, int] = {
        str(kind): index for index, kind in enumerate(LAYER_ORDER)
    }

    def order_key(item: dict[str, object]) -> tuple[int, int]:
        priority = item.get("priority")
        return (
            order_index.get(str(item.get("kind")), 99),
            -(priority if isinstance(priority, int) else 0),
        )

    return sorted(rows, key=order_key)


def _legacy_source_attribution(
    block_kind: str, span: tuple[int, int], expected: str
) -> LegacySourceAttribution:
    normalized_expected = normalize_comparison_text(expected)
    return LegacySourceAttribution(
        block_kind=block_kind,
        start=span[0],
        end=span[1],
        expected_sha256=sha256(normalized_expected.encode("utf-8")).hexdigest(),
        resolved_payload_present=bool(normalized_expected),
    )


def _attributed_source_survived(
    attribution: LegacySourceAttribution, block_content: str
) -> bool:
    if not attribution.resolved_payload_present:
        return False
    if attribution.start < 0 or attribution.end < attribution.start:
        return False
    if len(block_content) < attribution.end:
        return False
    retained = normalize_comparison_text(
        block_content[attribution.start : attribution.end]
    )
    return sha256(retained.encode("utf-8")).hexdigest() == attribution.expected_sha256


def _story_position_codes(
    candidate: EntrySnapshot,
    target_chapter_index: int | None,
    target_chapter_id: str | None,
    *,
    selected: bool,
) -> set[str]:
    if target_chapter_index is None or target_chapter_id is None:
        return set()
    codes: set[str] = set()
    unknown = False
    future = False
    if candidate.subject_type == "chapter":
        classification = classify_chapter_story_position(
            target_chapter_id=target_chapter_id,
            target_chapter_index=target_chapter_index,
            source_chapter_id=candidate.subject_id,
            source_chapter_index=candidate.subject_story_position,
        )
        if classification.disposition.value == "unknown":
            unknown = True
        elif classification.disposition.value in {"current", "future"}:
            future = True
    else:
        unknown = True
    if candidate.created_at_chapter_id is not None:
        if candidate.created_at_chapter_position is None:
            unknown = True
        elif candidate.created_at_chapter_position >= target_chapter_index:
            future = True
    if future:
        codes.add(
            "future_story_position_selected"
            if selected
            else "future_story_position_not_selected"
        )
    if unknown:
        codes.add("unknown_story_position")
        codes.add(
            "unknown_story_position_selected"
            if selected
            else "unknown_story_position_not_selected"
        )
    return codes


def _final_entry_ids(prompt: AssembledPrompt, assembly_order: list[str]) -> list[str]:
    included = {
        item["block_id"].split(":", 1)[1]
        for item in prompt.trace.get("entries", [])
        if item.get("kind") == "entry" and item.get("status") == "included"
    }
    return [entry_id for entry_id in assembly_order if entry_id in included]
