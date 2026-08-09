"""P1-6 seam: Entry Store canon -> Context Assembly -> generation prompt blocks.

This module is the single production call site for ``EntryService.retrieve()``
and ``assemble_entry_context()``. Chat and Novel hand it the context they can
prove (owner, character, world, work), and receive already-assembled
``PromptBlock`` objects plus a prompt-trace section. Neither service builds
Entry prompt text itself, and neither one re-implements ranking or budgeting.

Boundaries this module keeps (RFC-002, RFC-003, ADR-003):

* canon only — the retrieval request never opts into proposed/rejected/
  superseded, and orphaned anchors are dropped by ``retrieve()`` itself;
* owner-rooted — ``user_id`` comes from the authenticated caller;
* no scope guessing — only anchors the caller actually holds are declared;
* chat-private ``Memory`` is untouched; it stays a separate prompt block.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.engines.prompt.blocks import PromptBlock
from app.engines.prompt.entry_context import (
    EntryContextAssemblyRequest,
    assemble_entry_context,
    build_entry_context_trace,
    disabled_entry_context_trace,
)
from app.schemas.entry import (
    EntryRetrievalTaskKind,
    EntryRetrieveRequest,
    EntryScope,
    EntryScopeSelector,
)
from app.services.entry_service import EntryService

# Share of the model context window allocated to the Entry knowledge slice
# (RFC-003 §11.1: the caller must supply a budget derived from the context plan).
# Held well below the chat memory hint (0.4) because P1-6 is additive: the legacy
# character/world/lore path is still the authoritative context source until the
# separately approved P1-8 cutover.
ENTRY_CONTEXT_BUDGET_RATIO = 0.15
ENTRY_CONTEXT_MIN_BUDGET = 256

# Safety cap subordinate to the token budget (RFC-003 §11.2).
ENTRY_CONTEXT_LIMIT = 20

# Characters of the current chapter tail folded into the Novel keyword beat.
# Mirrors the tail NovelEngine already shows the model, so the retrieved canon
# is relevant to the passage actually being continued.
NOVEL_BEAT_TAIL_CHARS = 1200


@dataclass(frozen=True)
class EntryGenerationContext:
    """Assembled Entry blocks plus the trace section for the final prompt."""

    blocks: list[PromptBlock] = field(default_factory=list)
    trace: dict[str, object] = field(default_factory=dict)


def entry_context_budget(context_window: int) -> int:
    """Deterministic knowledge-slice budget for one generation request."""

    return max(ENTRY_CONTEXT_MIN_BUDGET, int(context_window * ENTRY_CONTEXT_BUDGET_RATIO))


def _disabled() -> EntryGenerationContext:
    return EntryGenerationContext(blocks=[], trace=disabled_entry_context_trace())


def _scope_selectors(
    *,
    work_id: str | None = None,
    world_id: str | None = None,
    character_ids: list[str] | None = None,
) -> list[EntryScopeSelector]:
    """Declare only reachable anchors, in a stable order (RFC-003 §5.1)."""

    selectors = [EntryScopeSelector(scope_kind=EntryScope.USER)]
    if work_id:
        selectors.append(
            EntryScopeSelector(scope_kind=EntryScope.WORK, scope_id=work_id)
        )
    if world_id:
        selectors.append(
            EntryScopeSelector(scope_kind=EntryScope.WORLD, scope_id=world_id)
        )
    for character_id in sorted(set(character_ids or [])):
        selectors.append(
            EntryScopeSelector(scope_kind=EntryScope.CHARACTER, scope_id=character_id)
        )
    return selectors


def build_chat_retrieve_request(
    *,
    user_id: str,
    character: object | None,
    world: object | None,
    user_message: str | None,
    context_window: int,
) -> EntryRetrieveRequest:
    """Chat situation: user + the active character + that character's world.

    No ``work`` scope is ever declared. A ``ChatSession`` records a character and
    an optional persona but no work, and RFC-003 §13.3 forbids guessing among
    works, so chat canon stops at character/world/user scope.
    """

    character_id = getattr(character, "id", None) if character is not None else None
    world_id = getattr(world, "id", None) if world is not None else None
    return EntryRetrieveRequest(
        user_id=user_id,
        scopes=_scope_selectors(
            world_id=world_id,
            character_ids=[character_id] if character_id else [],
        ),
        cast=[character_id] if character_id else [],
        beat=user_message or None,
        budget=entry_context_budget(context_window),
        task_kind=EntryRetrievalTaskKind.CHAT,
        limit=ENTRY_CONTEXT_LIMIT,
    )


def build_novel_retrieve_request(
    *,
    user_id: str,
    work: object,
    world: object | None,
    characters: list,
    chapter: object,
    instruction: str | None,
    context_window: int,
) -> EntryRetrieveRequest:
    """Novel situation: user + this work + its world + its linked cast."""

    world_id = getattr(world, "id", None) if world is not None else None
    character_ids = [
        character_id
        for character_id in (getattr(c, "id", None) for c in characters)
        if character_id
    ]
    tail = (getattr(chapter, "content_text", "") or "")[-NOVEL_BEAT_TAIL_CHARS:]
    beat = " ".join(part for part in (instruction or "", tail) if part).strip()
    return EntryRetrieveRequest(
        user_id=user_id,
        scopes=_scope_selectors(
            work_id=getattr(work, "id", None),
            world_id=world_id,
            character_ids=character_ids,
        ),
        cast=sorted(set(character_ids)),
        beat=beat or None,
        budget=entry_context_budget(context_window),
        task_kind=EntryRetrievalTaskKind.SCENE,
        limit=ENTRY_CONTEXT_LIMIT,
    )


async def load_entry_context(
    session: AsyncSession,
    *,
    settings: Settings,
    request_factory,
    entry_service: EntryService | None = None,
) -> EntryGenerationContext:
    """Run retrieval + Context Assembly once, or nothing at all when flagged off.

    The flag is checked before ``request_factory`` runs, so a disabled feature
    issues zero Entry queries and builds no retrieval request.

    Failures are **not** swallowed. Entry retrieval sits in the same pre-stream
    context-building stage as ``MemoryEngine.build_memory_context()`` and the
    legacy lore load, both of which already abort the turn on failure. Silently
    degrading to canon-less output would produce continuity-broken prose that
    looks successful, which the trace contract exists to prevent.
    """

    if not settings.entry_store_context_enabled:
        return _disabled()

    service = entry_service or EntryService()
    request = request_factory()
    result = await service.retrieve(session, request)
    assembled = assemble_entry_context(
        EntryContextAssemblyRequest(result, budget=request.budget)
    )
    return EntryGenerationContext(
        blocks=list(assembled.blocks),
        trace=build_entry_context_trace(
            request=request, result=result, assembled=assembled
        ),
    )
