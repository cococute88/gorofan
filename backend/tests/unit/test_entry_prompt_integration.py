"""P1-6 Entry block contract and the PromptEngine collection seam.

Covers the parts of the wiring that need no database: the Entry PromptBlock kind
is distinct from `memory` and `lore`, the engine collects already-assembled Entry
blocks without owning retrieval, and the existing budget/ordering guarantees hold
once Entry blocks join the block set.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.adapters.base import AssembledPrompt
from app.engines.prompt.blocks import DEFAULT_PRIORITY, LAYER_ORDER, PromptBlock
from app.engines.prompt.engine import AssembleInput, PromptEngine
from app.engines.prompt.entry_context import (
    EntryContextAssemblyRequest,
    assemble_entry_context,
    build_entry_context_trace,
    disabled_entry_context_trace,
    entry_retrieval_item_to_prompt_block,
)
from app.engines.prompt.tokenizer import default_tokenizer
from app.schemas.entry import (
    EntryRead,
    EntryRetrievalItem,
    EntryRetrievalResult,
    EntryRetrievalScore,
    EntryRetrievalTrace,
    EntryRetrieveRequest,
    EntryScope,
    EntryScopeSelector,
    EntryStatus,
    EntrySubjectType,
    EntryType,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)


class _Lore:
    def __init__(self, lore_id: str, content: str, keywords: list[str]) -> None:
        self.id = lore_id
        self.content = content
        self.keywords = keywords
        self.enabled = True
        self.scan_depth = 4


class _Memory:
    def __init__(self, content: str) -> None:
        self.content = content


def _item(
    entry_id: str,
    *,
    content: str = "황궁의 비밀 통로는 북쪽 벽 뒤에 있다.",
    title: str | None = "비밀 통로",
) -> EntryRetrievalItem:
    entry = EntryRead(
        id=entry_id,
        user_id="owner",
        scope_kind=EntryScope.WORK,
        scope_id="work-1",
        subject_type=EntrySubjectType.WORK,
        subject_id="work-1",
        subject_data={},
        type=EntryType.STORY_FACT,
        status=EntryStatus.CANON,
        title=title,
        content=content,
        data={},
        provenance={
            "source_kind": "user",
            "capture_method": "human-authored",
            "producer": "test",
        },
        confidence=None,
        priority=70,
        created_at_chapter_id=None,
        superseded_by_entry_id=None,
        accepted_at=NOW,
        rejected_at=None,
        superseded_at=None,
        created_at=NOW,
        updated_at=NOW,
    )
    return EntryRetrievalItem(
        entry=entry,
        score=2.75,
        matched_terms=["비밀"],
        score_breakdown=EntryRetrievalScore(
            keyword=1.0,
            identity=0.4,
            type_weight=0.35,
            status=0.25,
            recency=0.2,
            priority=0.7,
            confidence=0.0,
            authority=0.31,
            exemplar=0.0,
        ),
        reason=["keyword"],
        estimated_tokens=default_tokenizer.count(content),
    )


def _result(items: list[EntryRetrievalItem], *, budget: int = 4096) -> EntryRetrievalResult:
    return EntryRetrievalResult(
        items=items,
        total_estimated_tokens=sum(item.estimated_tokens for item in items),
        requested_budget=budget,
        policy_version="entry-keyword-v1",
        trace=EntryRetrievalTrace(),
    )


def _blocks(items: list[EntryRetrievalItem], *, budget: int = 4096) -> list[PromptBlock]:
    return list(
        assemble_entry_context(
            EntryContextAssemblyRequest(_result(items, budget=budget), budget=budget)
        ).blocks
    )


def _assemble(**overrides: Any) -> AssembledPrompt:
    base: dict[str, Any] = {
        "template_body": "너는 {{char}}이다.",
        "context_window": 8192,
        "max_tokens": 512,
    }
    base.update(overrides)
    return PromptEngine().assemble(AssembleInput(**base))


def _system(prompt: AssembledPrompt) -> str:
    return prompt.system or ""


def _section(trace: dict[str, Any], key: str) -> Any:
    return trace[key]


# --- Entry block contract -------------------------------------------------


def test_entry_block_kind_is_entry_and_never_memory() -> None:
    block = entry_retrieval_item_to_prompt_block(
        _item("entry-1"), policy_version="entry-keyword-v1"
    )

    assert block.kind == "entry"
    assert block.kind != "memory"
    assert block.id == "entry:entry-1"
    assert block.priority == DEFAULT_PRIORITY["entry"]
    # Whole-Entry only: the final BudgetManager must drop, never trim.
    assert block.truncatable is False
    assert block.metadata["source"] == "entry_store"
    assert block.metadata["entry_id"] == "entry-1"


def test_entry_layer_and_priority_sit_between_lore_and_the_identity_blocks() -> None:
    assert "entry" in LAYER_ORDER
    # Grouped with the knowledge layers, without reordering any existing kind.
    assert LAYER_ORDER.index("lore") < LAYER_ORDER.index("entry")
    assert LAYER_ORDER.index("entry") < LAYER_ORDER.index("memory")
    assert [kind for kind in LAYER_ORDER if kind != "entry"] == [
        "system", "character", "persona", "world", "lore",
        "memory", "chapter", "history", "user", "instruction",
    ]

    # Human-gated shared canon outranks chat-private memory and legacy lore ...
    assert DEFAULT_PRIORITY["entry"] > DEFAULT_PRIORITY["memory"]
    assert DEFAULT_PRIORITY["entry"] > DEFAULT_PRIORITY["lore"]
    # ... but stays below the structural identity/continuity blocks, because the
    # legacy path remains authoritative until the approved P1-8 cutover.
    assert DEFAULT_PRIORITY["entry"] < DEFAULT_PRIORITY["world"]
    assert DEFAULT_PRIORITY["entry"] < DEFAULT_PRIORITY["chapter"]
    # And never competes with the protected user/instruction blocks.
    assert DEFAULT_PRIORITY["entry"] < DEFAULT_PRIORITY["user"]
    assert DEFAULT_PRIORITY["entry"] < DEFAULT_PRIORITY["instruction"]


# --- PromptEngine seam ----------------------------------------------------


def test_entry_memory_and_lore_stay_three_separate_blocks() -> None:
    prompt = _assemble(
        lore_entries=[_Lore("l1", "레거시 로어 본문", ["비밀"])],
        memory_long=[_Memory("사용자는 어제 고양이 얘기를 했다.")],
        entry_blocks=_blocks([_item("entry-1")]),
        user_message="비밀 통로에 대해 알려줘",
    )

    kinds = [entry["kind"] for entry in prompt.trace["entries"]]
    assert kinds.count("lore") == 1
    assert kinds.count("memory") == 1
    assert kinds.count("entry") == 1

    entry_traces = [e for e in prompt.trace["entries"] if e["kind"] == "entry"]
    assert entry_traces[0]["block_id"] == "entry:entry-1"
    # Entry content is carried verbatim, not folded into the lore or memory text.
    assert "황궁의 비밀 통로는 북쪽 벽 뒤에 있다." in _system(prompt)
    assert "레거시 로어 본문" in _system(prompt)
    assert "사용자는 어제 고양이 얘기를 했다." in _system(prompt)


def test_entry_blocks_render_after_lore_and_before_memory() -> None:
    prompt = _assemble(
        lore_entries=[_Lore("l1", "로어", ["통로"])],
        memory_long=[_Memory("메모리")],
        entry_blocks=_blocks([_item("entry-1", content="엔트리", title=None)]),
        user_message="통로",
    )

    contents = [m.content for m in prompt.messages]
    assert contents.index("로어") < contents.index("[story.fact]\n엔트리")
    assert contents.index("[story.fact]\n엔트리") < contents.index("메모리")


def test_absent_entry_input_leaves_the_prompt_byte_identical() -> None:
    kwargs: dict[str, Any] = {
        "lore_entries": [_Lore("l1", "로어 본문", ["통로"])],
        "memory_long": [_Memory("메모리 본문")],
        "user_message": "통로 알려줘",
        "prompt_asset_id": "chat.default",
        "prompt_asset_version": "v1",
        "prompt_asset_sha256": "abc",
    }
    none_input = _assemble(**kwargs)
    empty_input = _assemble(entry_blocks=[], entry_context_trace=None, **kwargs)

    assert none_input.messages == empty_input.messages
    assert none_input.system == empty_input.system
    assert none_input.token_count == empty_input.token_count
    assert none_input.trace == empty_input.trace
    # No Entry input means no Entry trace section at all.
    assert "entry_context" not in none_input.trace


def test_entry_context_trace_is_attached_verbatim_when_supplied() -> None:
    disabled = disabled_entry_context_trace()
    prompt = _assemble(entry_context_trace=disabled, user_message="안녕")

    assert prompt.trace["entry_context"] == {
        "feature_enabled": False,
        "retrieval_invoked": False,
    }


def test_entry_content_is_not_variable_resolved() -> None:
    """Stored canon is data, not a template — `{{...}}` must survive verbatim."""

    prompt = _assemble(
        entry_blocks=_blocks([_item("entry-1", content="{{char}}는 검을 쓴다.", title=None)]),
        user_message="무기?",
    )

    assert "{{char}}는 검을 쓴다." in _system(prompt)


# --- Budget -----------------------------------------------------------------


def test_oversized_entry_block_is_dropped_whole_not_trimmed() -> None:
    long_entry = _item("entry-big", content="가" * 4000, title=None)
    blocks = _blocks([long_entry], budget=100_000)
    assert blocks, "fixture must produce a block before budget pressure is applied"
    original = blocks[0].content

    prompt = _assemble(
        entry_blocks=blocks,
        user_message="짧은 질문",
        context_window=1024,
        max_tokens=256,
    )

    dropped = [e for e in prompt.trace["entries"] if e["kind"] == "entry"]
    assert dropped and all(e["status"] == "dropped" for e in dropped)
    assert all(e["trimmed_tokens"] == 0 for e in dropped)
    # The block object itself was never mutated into a partial Entry.
    assert blocks[0].content == original
    assert "가" * 4000 not in (prompt.system or "")


def test_context_window_invariant_holds_with_entry_blocks() -> None:
    items = [_item(f"entry-{i}", content=f"사실 {i} " * 200, title=None) for i in range(12)]
    prompt = _assemble(
        entry_blocks=_blocks(items, budget=100_000),
        memory_long=[_Memory("메모리 " * 100)],
        user_message="질문",
        context_window=2048,
        max_tokens=512,
    )

    assert prompt.token_count <= 2048


def test_entry_selection_and_order_are_deterministic() -> None:
    items = [_item("entry-b", title="B"), _item("entry-a", title="A")]
    first = _assemble(entry_blocks=_blocks(items), user_message="질문")
    second = _assemble(entry_blocks=_blocks(items), user_message="질문")

    assert [m.content for m in first.messages] == [m.content for m in second.messages]
    assert first.token_count == second.token_count


def test_entry_blocks_cannot_displace_the_protected_user_message() -> None:
    items = [_item(f"entry-{i}", content=f"긴 사실 {i} " * 300, title=None) for i in range(8)]
    prompt = _assemble(
        entry_blocks=_blocks(items, budget=100_000),
        user_message="반드시 남아야 하는 사용자 질문",
        context_window=1024,
        max_tokens=256,
    )

    assert any(m.content == "반드시 남아야 하는 사용자 질문" for m in prompt.messages)


# --- Trace ------------------------------------------------------------------


def test_retrieval_and_assembly_exclusions_stay_separately_attributable() -> None:
    small = _item("entry-small", content="짧은 사실", title=None)
    large = _item("entry-large", content="아주 긴 사실 " * 200, title=None)
    result = EntryRetrievalResult(
        items=[small, large],
        total_estimated_tokens=small.estimated_tokens + large.estimated_tokens,
        requested_budget=4096,
        policy_version="entry-keyword-v1",
        trace=EntryRetrievalTrace(
            excluded_orphaned_entry_ids=["orphan-1"],
            budget_rejected_entry_ids=["retrieval-budget-1"],
            limit_rejected_entry_ids=["limit-1"],
        ),
    )
    assembled = assemble_entry_context(
        EntryContextAssemblyRequest(result, budget=small.estimated_tokens + 4)
    )
    request = EntryRetrieveRequest(
        user_id="owner",
        scopes=[EntryScopeSelector(scope_kind=EntryScope.WORK, scope_id="work-1")],
        budget=4096,
    )

    trace = build_entry_context_trace(request=request, result=result, assembled=assembled)

    assert trace["feature_enabled"] is True
    assert trace["retrieval_invoked"] is True
    assert trace["selected_entry_ids"] == ["entry-small", "entry-large"]
    assert trace["blocks_created"] is True
    assert trace["no_eligible_entries"] is False
    assert trace["requested_scopes"] == [{"scope_kind": "work", "scope_id": "work-1"}]
    assert trace["requested_statuses"] == ["canon"]

    retrieval_exclusions = _section(trace, "retrieval_exclusions")
    assert retrieval_exclusions["orphaned_entry_ids"] == ["orphan-1"]
    assert retrieval_exclusions["retrieval_budget_rejected_entry_ids"] == [
        "retrieval-budget-1"
    ]
    assert retrieval_exclusions["limit_rejected_entry_ids"] == ["limit-1"]

    # The rendered-block rejection is recorded on the assembly side only.
    assembly_exclusions = _section(trace, "assembly_exclusions")
    assert [e["entry_id"] for e in assembly_exclusions] == ["entry-large"]
    assert assembly_exclusions[0]["stage"] == "context_assembly"
    assert "entry-large" not in retrieval_exclusions["retrieval_budget_rejected_entry_ids"]


def test_trace_reports_no_eligible_entries_distinctly_from_disabled() -> None:
    empty = _result([])
    assembled = assemble_entry_context(EntryContextAssemblyRequest(empty, budget=512))
    request = EntryRetrieveRequest(
        user_id="owner",
        scopes=[EntryScopeSelector(scope_kind=EntryScope.USER)],
        budget=512,
    )

    trace = build_entry_context_trace(request=request, result=empty, assembled=assembled)

    assert trace["feature_enabled"] is True
    assert trace["retrieval_invoked"] is True
    assert trace["no_eligible_entries"] is True
    assert trace["blocks_created"] is False
    assert disabled_entry_context_trace() == {
        "feature_enabled": False,
        "retrieval_invoked": False,
    }
