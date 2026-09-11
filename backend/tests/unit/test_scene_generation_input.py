"""AOS-2 minimum ephemeral Scene generation input contract."""
from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest
from pydantic import ValidationError

from app.adapters.base import ModelCapability, ProviderRequest
from app.adapters.registry import ProviderRegistry
from app.engines.novel.engine import NovelEngine
from app.engines.novel.generation_preparation import (
    ContinueGenerationInput,
    GenerationSectionKind,
    GenerationTarget,
    PreparedChapterContext,
    PreparedWorkContext,
    SceneGenerationInput,
    freeze_mapping,
    prepare_continue_generation,
)
from app.engines.prompt.engine import PromptEngine
from app.schemas.novel import (
    SCENE_GOAL_MAX_LENGTH,
    SCENE_ITEM_MAX_LENGTH,
    SCENE_ITEMS_MAX_COUNT,
    SCENE_TOTAL_MAX_LENGTH,
    ContinueRequest,
    SceneGenerationRequest,
)


class _Registry(ProviderRegistry):
    def capabilities(self, provider: str, model: str) -> ModelCapability:  # noqa: ARG002
        return ModelCapability(context_window=8192, max_output_tokens=2048)


def _input(**updates) -> ContinueGenerationInput:  # noqa: ANN003
    value = ContinueGenerationInput(
        target=GenerationTarget("owner-1", "work-1", "chapter-1"),
        work=PreparedWorkContext("work-1", "owner-1", "작품", "", "", ()),
        characters=(),
        world=None,
        lore=(),
        prior_summaries=(),
        current_chapter=PreparedChapterContext(
            "chapter-1", "work-1", "owner-1", 1, "", "현재 본문"
        ),
        instruction="감정선을 천천히 진행해줘.",
        target_words=800,
        context_window=8192,
        entry_context_trace=freeze_mapping(
            {"feature_enabled": False, "retrieval_invoked": False}
        ),
    )
    return replace(value, **updates)


def _request(
    *, provider: str = "fake", context_window: int = 8192, max_tokens: int = 256
) -> ProviderRequest:
    return ProviderRequest(
        provider=provider,
        model_name="fake-1",
        base_url=None,
        api_key=None,
        temperature=0.8,
        max_tokens=max_tokens,
        context_window=context_window,
    )


def _assemble(value: ContinueGenerationInput, *, request: ProviderRequest | None = None):  # noqa: ANN202
    preparation = prepare_continue_generation(value)
    prompt = NovelEngine(PromptEngine(), _Registry()).assemble_continue(
        preparation, req=request or _request()
    )
    return preparation, prompt


def _prompt_text(prompt) -> str:  # noqa: ANN001
    return "\n".join(message.content for message in prompt.messages)


def test_legacy_and_empty_scene_have_exactly_equivalent_preparation_and_prompt() -> None:
    legacy_preparation, legacy_prompt = _assemble(_input())
    empty_preparation, empty_prompt = _assemble(
        _input(
            scene=SceneGenerationInput(
                goal=None,
                beats=cast(tuple[str, ...], []),
                must_include=cast(tuple[str, ...], []),
                must_avoid=cast(tuple[str, ...], []),
            )
        )
    )

    assert empty_preparation == legacy_preparation
    assert empty_preparation.scene is None
    assert empty_prompt == legacy_prompt
    assert "[장면 목표]" not in _prompt_text(empty_prompt)


def test_goal_only_is_canonical_and_rendered_exactly_once() -> None:
    goal = "라니가 결계 이상을 눈치챈다."
    preparation, prompt = _assemble(_input(scene=SceneGenerationInput(goal=goal)))

    assert preparation.scene == SceneGenerationInput(goal=goal)
    instruction = preparation.section(GenerationSectionKind.INSTRUCTION)
    assert [item.evidence.source_type for item in instruction.items] == [
        "generation_request",
        "scene_generation_input",
    ]
    assert sum(item.content.count(goal) for item in instruction.items) == 1
    assert _prompt_text(prompt).count(goal) == 1


def test_combined_scene_preserves_order_duplicates_unicode_and_internal_newlines() -> None:
    scene = SceneGenerationInput(
        goal="결계를 확인한다.",
        beats=("B — 먼저", "A\n두 줄 사건", "B — 먼저", "C <끝> & 확인"),
        must_include=("은빛 표식", "손목을 붙잡는 행동", "은빛 표식"),
        must_avoid=("새로운 악역", "코믹한 분위기"),
    )
    preparation, prompt = _assemble(_input(scene=scene))
    assert preparation.scene is not None
    assert preparation.scene.beats == tuple(scene.beats)
    assert preparation.scene.must_include == tuple(scene.must_include)
    assert preparation.scene.must_avoid == tuple(scene.must_avoid)

    text = _prompt_text(prompt)
    assert text.count("감정선을 천천히 진행해줘.") == 1
    assert text.index("1. B — 먼저") < text.index("2. A\n두 줄 사건")
    assert text.index("2. A\n두 줄 사건") < text.index("3. B — 먼저")
    assert text.index("- 은빛 표식") < text.index("- 손목을 붙잡는 행동")
    assert text.count("은빛 표식") == 2
    assert "C <끝> & 확인" in text


def test_scene_sequences_are_defensively_snapshotted_and_stable() -> None:
    beats = ["첫 사건", "둘째 사건"]
    must_include = ["열쇠"]
    scene = SceneGenerationInput(
        beats=cast(tuple[str, ...], beats),
        must_include=cast(tuple[str, ...], must_include),
    )

    first = prepare_continue_generation(_input(scene=scene))
    repeated = prepare_continue_generation(_input(scene=scene))
    before = (repr(first), first.sections)

    beats.reverse()
    beats.append("변조")
    must_include.clear()

    assert first == repeated
    assert (repr(first), first.sections) == before
    assert first.scene is not None
    assert first.scene.beats == ("첫 사건", "둘째 사건")
    assert first.scene.must_include == ("열쇠",)


def test_scene_request_trims_edges_without_rewriting_internal_text_or_order() -> None:
    dto = SceneGenerationRequest(
        goal="  장면 목표\n둘째 줄  ",
        beats=["  B  ", " A\n둘째 줄 "],
        must_include=None,
        must_avoid=["  피할 것  "],
    )

    assert dto.goal == "장면 목표\n둘째 줄"
    assert dto.beats == ["B", "A\n둘째 줄"]
    assert dto.must_include == []
    assert dto.must_avoid == ["피할 것"]
    assert ContinueRequest(scene={}).scene == SceneGenerationRequest()
    assert ContinueRequest(scene={"goal": "   "}).scene == SceneGenerationRequest()


@pytest.mark.parametrize(
    "scene",
    [
        {"beats": ["정상", "   "]},
        {"must_include": ["\n\t"]},
        {"must_avoid": [" "]},
        {"unknown": "arbitrary metadata"},
        {"beats": "ordered text, not a list"},
        {"goal": 123},
    ],
)
def test_scene_request_rejects_blank_items_unknown_fields_and_malformed_types(
    scene: object,
) -> None:
    with pytest.raises(ValidationError):
        ContinueRequest(scene=scene)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "scene",
    [
        {"goal": "가" * (SCENE_GOAL_MAX_LENGTH + 1)},
        {"beats": ["가" * (SCENE_ITEM_MAX_LENGTH + 1)]},
        {"beats": ["사건"] * (SCENE_ITEMS_MAX_COUNT + 1)},
        {
            "beats": ["가" * SCENE_ITEM_MAX_LENGTH] * SCENE_ITEMS_MAX_COUNT,
            "must_include": ["나" * SCENE_ITEM_MAX_LENGTH] * SCENE_ITEMS_MAX_COUNT,
            "must_avoid": ["다" * SCENE_ITEM_MAX_LENGTH] * SCENE_ITEMS_MAX_COUNT,
        },
    ],
)
def test_scene_request_rejects_oversize_fields_counts_and_total(scene: object) -> None:
    with pytest.raises(ValidationError):
        ContinueRequest(scene=scene)  # type: ignore[arg-type]

    assert SCENE_TOTAL_MAX_LENGTH < 3 * SCENE_ITEMS_MAX_COUNT * SCENE_ITEM_MAX_LENGTH


def test_scene_uses_existing_protected_instruction_budget_without_bypass() -> None:
    directive = SceneGenerationInput(
        goal="목표를 반드시 유지한다.",
        beats=tuple(f"사건 {index}: " + ("가" * 30) for index in range(1, 5)),
        must_include=("은빛 표식",),
        must_avoid=("새로운 악역",),
    )
    value = _input(
        current_chapter=PreparedChapterContext(
            "chapter-1", "work-1", "owner-1", 1, "", "이전 " * 1000
        ),
        scene=directive,
        context_window=512,
    )
    _, prompt = _assemble(value, request=_request(context_window=512, max_tokens=64))

    instruction_entries = [
        entry for entry in prompt.trace["entries"] if entry["kind"] == "instruction"
    ]
    assert len(instruction_entries) == 1
    assert instruction_entries[0]["priority"] == 1000
    assert "목표를 반드시 유지한다." in _prompt_text(prompt)
    assert prompt.token_count <= 512


def test_scene_preparation_and_rendering_are_provider_neutral() -> None:
    value = _input(
        scene=SceneGenerationInput(
            goal="같은 목표",
            beats=("같은 첫 사건", "같은 둘째 사건"),
            must_include=("같은 요소",),
            must_avoid=("같은 금지",),
        )
    )
    preparation = prepare_continue_generation(value)
    engine = NovelEngine(PromptEngine(), _Registry())

    first = engine.assemble_continue(preparation, req=_request(provider="provider-a"))
    second = engine.assemble_continue(preparation, req=_request(provider="provider-b"))

    assert first == second
    assert "provider-a" not in repr(preparation)
    assert "provider-b" not in repr(preparation)
