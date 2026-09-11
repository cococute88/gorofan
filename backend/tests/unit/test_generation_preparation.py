"""AOS-1 deterministic, provider-neutral generation preparation contract."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from app.adapters.base import ModelCapability, ProviderRequest
from app.adapters.registry import ProviderRegistry
from app.engines.novel.engine import NovelEngine
from app.engines.novel.generation_preparation import (
    ContinueGenerationInput,
    FrozenMap,
    GenerationSectionKind,
    GenerationTarget,
    PreparedChapterContext,
    PreparedCharacterContext,
    PreparedLoreContext,
    PreparedPriorSummary,
    PreparedPromptBlock,
    PreparedWorkContext,
    PreparedWorldContext,
    freeze_mapping,
    prepare_continue_generation,
)
from app.engines.prompt.assets import PromptAssetLoader
from app.engines.prompt.blocks import DEFAULT_PRIORITY, PromptBlock
from app.engines.prompt.engine import AssembleInput, PromptEngine


class _Registry(ProviderRegistry):
    def capabilities(self, provider: str, model: str) -> ModelCapability:  # noqa: ARG002
        return ModelCapability(context_window=8192, max_output_tokens=2048)


def _entry_block(
    entry_id: str,
    entry_type: str,
    content: str,
    *,
    source_index: int | None = None,
    disposition: str = "prior",
    source_chapter_id: str | None = None,
    scope_id: str = "work-1",
    extra_metadata: dict[str, object] | None = None,
) -> PreparedPromptBlock:
    metadata: dict[str, object] = {
        "source": "entry_store",
        "entry_id": entry_id,
        "entry_type": entry_type,
        "scope_kind": "work",
        "scope_id": scope_id,
    }
    if source_index is not None:
        metadata["story_summary_chronology"] = {
            "disposition": disposition,
            "reason": "eligible_prior_summary",
            "source_chapter_id": source_chapter_id or f"chapter-{source_index}",
            "source_chapter_index": source_index,
        }
    metadata.update(extra_metadata or {})
    return PreparedPromptBlock.from_prompt_block(
        PromptBlock(
            id=f"entry:{entry_id}",
            role="system",
            kind="entry",
            content=content,
            priority=DEFAULT_PRIORITY["entry"],
            token_count=5,
            truncatable=False,
            metadata=metadata,
        )
    )


def _input(**updates) -> ContinueGenerationInput:  # noqa: ANN003
    value = ContinueGenerationInput(
        target=GenerationTarget("owner-1", "work-1", "chapter-3"),
        work=PreparedWorkContext(
            "work-1",
            "owner-1",
            "겨울 궁전",
            "몰락한 공녀의 귀환",
            "로맨스 판타지",
            ("회귀", "궁정"),
        ),
        characters=(
            PreparedCharacterContext(
                "character-1", "owner-1", "하린", "침착함", "짧고 단정함"
            ),
        ),
        world=PreparedWorldContext(
            "world-1", "owner-1", "북부 제국", "긴 겨울이 이어진다.", "증기력 412년"
        ),
        lore=(
            PreparedLoreContext(
                "lore-1", "황실 문장은 은빛 매다.", ("황실", "문장"), 50, 4
            ),
        ),
        prior_summaries=(
            PreparedPriorSummary("chapter-1", "work-1", 1, "첫 장 요약"),
        ),
        current_chapter=PreparedChapterContext(
            "chapter-3", "work-1", "owner-1", 3, "귀환", "문이 천천히 열렸다."
        ),
        instruction="하린이 안으로 들어가게 이어 써라.",
        target_words=900,
        context_window=8192,
        entry_blocks=(
            _entry_block("summary-2", "story.summary", "[story.summary]\n둘째 장 요약", source_index=2),
            _entry_block(
                "relationship-1",
                "relationship.state",
                "[relationship.state]\n하린과 준은 서로를 경계한다.",
            ),
            _entry_block("fact-1", "story.fact", "[story.fact]\n열쇠는 하린이 갖고 있다."),
        ),
        entry_context_trace=freeze_mapping(
            {
                "feature_enabled": True,
                "retrieval_invoked": True,
                "retrieval_budget": 1228,
                "assembly_budget": 1228,
                "entry_block_tokens": 15,
                "selected_entry_ids": ["summary-2", "relationship-1", "fact-1"],
                "retrieval_exclusions": {
                    "orphaned_entry_ids": ["orphan-1"],
                    "excluded_entry_types": {
                        "orphan-1": "character.identity",
                        "future-1": "story.summary",
                        "budget-1": "relationship.state",
                    },
                    "story_summary_chronology": [
                        {"entry_id": "future-1", "reason": "future_chapter_summary"}
                    ],
                    "retrieval_budget_rejected_entry_ids": ["budget-1"],
                    "limit_rejected_entry_ids": [],
                },
                "assembly_exclusions": [
                    {
                        "entry_id": "assembly-1",
                        "entry_type": "story.fact",
                        "reason": "rendered_block_budget_exceeded",
                    }
                ],
            }
        ),
    )
    return replace(value, **updates)


def _section(preparation, kind: GenerationSectionKind):  # noqa: ANN001, ANN202
    return next(section for section in preparation.sections if section.kind is kind)


def test_same_typed_input_produces_identical_immutable_preparation() -> None:
    value = _input()

    first = prepare_continue_generation(value)
    second = prepare_continue_generation(value)

    assert first == second
    with pytest.raises(FrozenInstanceError):
        first.instruction = "변조"  # type: ignore[misc]
    with pytest.raises(TypeError):
        first.entry_blocks[0].metadata.items[0] = ("entry_id", "변조")  # type: ignore[index]


def test_target_and_story_metadata_are_explicit_without_latest_fallback() -> None:
    preparation = prepare_continue_generation(_input())

    assert preparation.target == GenerationTarget("owner-1", "work-1", "chapter-3")
    assert preparation.current_chapter.id == "chapter-3"
    story = _section(preparation, GenerationSectionKind.STORY)
    assert len(story.items) == 1
    assert story.items[0].content == (
        "제목: 겨울 궁전\n"
        "시놉시스: 몰락한 공녀의 귀환\n"
        "장르: 로맨스 판타지\n"
        "태그: 회귀, 궁정"
    )
    assert story.items[0].evidence.current_prompt_visible is False

    wrong = _input(
        current_chapter=PreparedChapterContext(
            "latest-chapter", "work-1", "owner-1", 99, "최신", "잘못된 fallback"
        )
    )
    with pytest.raises(ValueError, match="Chapter authority"):
        prepare_continue_generation(wrong)


def test_character_relationship_and_canon_sections_preserve_current_authority() -> None:
    preparation = prepare_continue_generation(_input())

    characters = _section(preparation, GenerationSectionKind.CHARACTERS)
    relationships = _section(preparation, GenerationSectionKind.RELATIONSHIPS)
    canon = _section(preparation, GenerationSectionKind.CANON_CONTEXT)
    assert [item.evidence.source_type for item in characters.items] == ["character"]
    assert "하린: 침착함 / 말투: 짧고 단정함" in characters.items[0].content
    assert [item.evidence.source_type for item in relationships.items] == [
        "entry:relationship.state"
    ]
    assert [item.evidence.source_type for item in canon.items] == [
        "world",
        "lore_entry",
        "entry:story.fact",
    ]


def test_prior_summaries_reuse_resolved_evidence_and_keep_story_order() -> None:
    preparation = prepare_continue_generation(_input())
    summaries = _section(preparation, GenerationSectionKind.PRIOR_CHAPTER_SUMMARIES)

    assert [(item.evidence.selection_order, item.content) for item in summaries.items] == [
        (1, "첫 장 요약"),
        (2, "[story.summary]\n둘째 장 요약"),
    ]
    assert all("future" not in item.content.lower() for item in summaries.items)
    omitted = {(item.source_id, item.reason) for item in preparation.evidence if not item.selected}
    assert ("future-1", "future_chapter_summary") in omitted
    assert ("orphan-1", "orphaned_anchor") in omitted
    assert ("budget-1", "retrieval_budget_exceeded") in omitted
    assert ("assembly-1", "rendered_block_budget_exceeded") in omitted


def test_current_chapter_instruction_constraints_budget_and_section_order_are_explicit() -> None:
    preparation = prepare_continue_generation(_input())

    assert tuple(section.kind for section in preparation.sections) == tuple(GenerationSectionKind)
    current = _section(preparation, GenerationSectionKind.CURRENT_CHAPTER)
    instruction = _section(preparation, GenerationSectionKind.INSTRUCTION)
    constraints = _section(preparation, GenerationSectionKind.CONSTRAINTS)
    assert current.items[0].content == "[현재 챕터 끝부분]\n문이 천천히 열렸다."
    assert instruction.items[0].content == "하린이 안으로 들어가게 이어 써라."
    assert [(item.content) for item in constraints.items] == [
        "target_words: 900",
        "response_language: ko",
        "continuation_mode: continue",
    ]
    assert preparation.budget.context_window == 8192
    assert preparation.budget.retrieval_budget == 1228
    assert preparation.budget.assembly_budget == 1228
    assert preparation.budget.entry_block_tokens == 15


def test_entry_flag_off_preserves_legacy_sections_and_has_no_relationship_entry() -> None:
    trace = freeze_mapping({"feature_enabled": False, "retrieval_invoked": False})
    preparation = prepare_continue_generation(
        _input(entry_blocks=(), entry_context_trace=trace)
    )

    assert preparation.budget.entry_context_enabled is False
    assert preparation.budget.retrieval_invoked is False
    assert _section(preparation, GenerationSectionKind.RELATIONSHIPS).items == ()
    assert _section(preparation, GenerationSectionKind.CHARACTERS).items
    assert _section(preparation, GenerationSectionKind.PRIOR_CHAPTER_SUMMARIES).items


def test_foreign_context_fails_closed_and_chat_memory_has_no_input_seam() -> None:
    foreign = PreparedCharacterContext(
        "foreign-character", "owner-2", "침입자", "PRIVATE CHAT MEMORY", ""
    )
    with pytest.raises(ValueError, match="Foreign Character"):
        prepare_continue_generation(_input(characters=(foreign,)))

    preparation = prepare_continue_generation(_input())
    assert "PRIVATE CHAT MEMORY" not in repr(preparation)
    assert not hasattr(ContinueGenerationInput, "memory")


def test_invalid_summary_order_or_missing_chronology_evidence_fails_closed() -> None:
    with pytest.raises(ValueError, match="resolved story order"):
        prepare_continue_generation(
            _input(
                prior_summaries=(
                    PreparedPriorSummary("chapter-2", "work-1", 2, "둘째"),
                    PreparedPriorSummary("chapter-1", "work-1", 1, "첫째"),
                )
            )
        )
    with pytest.raises(ValueError, match="valid prior source"):
        prepare_continue_generation(
            _input(entry_blocks=(_entry_block("summary", "story.summary", "요약"),))
        )


@pytest.mark.parametrize(
    ("chapter_id", "source_index"),
    [
        ("chapter-99", 99),
        ("chapter-3", 3),
    ],
)
def test_legacy_summary_anchor_invariant_rejects_current_or_future_source(
    chapter_id: str, source_index: int
) -> None:
    sentinel = "FUTURE_LEGACY_SENTINEL"
    with pytest.raises(ValueError, match="target anchor") as error:
        prepare_continue_generation(
            _input(
                prior_summaries=(
                    PreparedPriorSummary(
                        chapter_id, "work-1", source_index, sentinel
                    ),
                )
            )
        )
    assert sentinel not in str(error.value)


@pytest.mark.parametrize(
    ("disposition", "source_index", "source_id"),
    [
        ("current", 3, "chapter-3"),
        ("future", 4, "chapter-4"),
        ("prior", 5, "chapter-5"),
        ("unknown", 2, "chapter-2"),
    ],
)
def test_entry_summary_anchor_invariant_rejects_non_prior_or_invalid_index(
    disposition: str, source_index: int, source_id: str
) -> None:
    with pytest.raises(ValueError, match="valid prior source"):
        prepare_continue_generation(
            _input(
                entry_blocks=(
                    _entry_block(
                        "malformed-summary",
                        "story.summary",
                        "MALFORMED_ENTRY_SUMMARY_SENTINEL",
                        disposition=disposition,
                        source_index=source_index,
                        source_chapter_id=source_id,
                    ),
                )
            )
        )


def test_valid_direct_prior_summary_evidence_is_accepted() -> None:
    preparation = prepare_continue_generation(
        _input(
            entry_blocks=(
                _entry_block(
                    "valid-summary",
                    "story.summary",
                    "VALID_PRIOR_SENTINEL",
                    disposition="prior",
                    source_index=2,
                    source_chapter_id="chapter-2",
                ),
            )
        )
    )
    summaries = _section(preparation, GenerationSectionKind.PRIOR_CHAPTER_SUMMARIES)
    assert any("VALID_PRIOR_SENTINEL" in item.content for item in summaries.items)


def test_caller_owned_sequences_and_nested_mappings_are_defensively_snapshotted() -> None:
    tags = ["회귀"]
    characters = [
        PreparedCharacterContext(
            "mutable-character", "owner-1", "원본", "침착", "단정"
        )
    ]
    lore_keywords = ["열쇠"]
    lore = [
        PreparedLoreContext(
            "mutable-lore", "열쇠는 탁자 위에 있다.", lore_keywords, 50, 4  # type: ignore[arg-type]
        )
    ]
    metadata: dict[str, object] = {
        "source": "entry_store",
        "entry_id": "mutable-entry",
        "entry_type": "story.fact",
        "scope_kind": "work",
        "scope_id": "work-1",
        "provenance": {"private": ["ORIGINAL_PRIVATE_METADATA"]},
    }
    raw_block = PromptBlock(
        id="entry:mutable-entry",
        role="system",
        kind="entry",
        content="공유 사실",
        priority=DEFAULT_PRIORITY["entry"],
        metadata=metadata,
    )
    blocks = [raw_block]
    trace: dict[str, object] = {
        "feature_enabled": True,
        "retrieval_invoked": True,
        "selected_entry_ids": ["mutable-entry"],
        "retrieval_exclusions": {
            "orphaned_entry_ids": [],
            "story_summary_chronology": [],
            "retrieval_budget_rejected_entry_ids": [],
            "limit_rejected_entry_ids": [],
            "excluded_entry_types": {},
        },
        "assembly_exclusions": [],
    }
    value = _input(
        work=PreparedWorkContext(
            "work-1", "owner-1", "가변 작품", "", "", tags  # type: ignore[arg-type]
        ),
        characters=characters,  # type: ignore[arg-type]
        lore=lore,  # type: ignore[arg-type]
        entry_blocks=blocks,  # type: ignore[arg-type]
        entry_context_trace=trace,  # type: ignore[arg-type]
    )
    preparation = prepare_continue_generation(value)
    before = (repr(preparation), preparation.sections, preparation.evidence)

    tags.append("변조")
    characters.clear()
    lore_keywords.append("변조")
    lore.clear()
    blocks.clear()
    cast_metadata = metadata["provenance"]
    assert isinstance(cast_metadata, dict)
    cast_metadata["private"] = ["MUTATED_PRIVATE_METADATA"]
    cast_trace = trace["selected_entry_ids"]
    assert isinstance(cast_trace, list)
    cast_trace.append("mutated-entry")

    assert (repr(preparation), preparation.sections, preparation.evidence) == before
    assert preparation.work.tags == ("회귀",)
    assert [character.id for character in preparation.characters] == [
        "mutable-character"
    ]
    assert preparation.lore[0].keywords == ("열쇠",)
    assert [block.id for block in preparation.entry_blocks] == [
        "entry:mutable-entry"
    ]
    assert len(_section(preparation, GenerationSectionKind.CHARACTERS).items) == len(
        preparation.characters
    )


def test_entry_compatibility_metadata_is_explicitly_whitelisted() -> None:
    sentinel = "ARBITRARY_PRIVATE_METADATA_SENTINEL_73921"
    raw = _entry_block("safe-entry", "story.fact", "안전한 사실").to_prompt_block()
    raw.metadata.update(
        {
            "provenance": {"locator": sentinel},
            "retrieval_score": 999,
            "arbitrary_private": sentinel,
        }
    )

    preparation = prepare_continue_generation(_input(entry_blocks=[raw]))
    metadata = dict(preparation.entry_blocks[0].metadata.items)
    assert set(metadata) == {
        "entry_id",
        "entry_type",
        "scope_id",
        "scope_kind",
        "source",
    }
    assert sentinel not in repr(preparation)


def test_story_summary_chronology_metadata_is_nested_whitelisted() -> None:
    sentinel = "ARBITRARY_PRIVATE_METADATA_SENTINEL_73921"
    raw = _entry_block(
        "safe-summary",
        "story.summary",
        "안전한 이전 요약",
        disposition="prior",
        source_index=2,
        source_chapter_id="chapter-2",
    ).to_prompt_block()
    chronology = raw.metadata["story_summary_chronology"]
    assert isinstance(chronology, dict)
    chronology["private_locator"] = {"secret": sentinel}

    preparation = prepare_continue_generation(_input(entry_blocks=[raw]))
    frozen = preparation.entry_blocks[0].metadata.get("story_summary_chronology")
    assert isinstance(frozen, FrozenMap)
    assert {key for key, _ in frozen.items} == {
        "disposition",
        "source_chapter_id",
        "source_chapter_index",
    }
    assert sentinel not in repr(preparation)


def test_omission_evidence_uses_each_entry_semantic_section() -> None:
    preparation = prepare_continue_generation(_input())
    omitted = {
        item.source_id: item.section for item in preparation.evidence if not item.selected
    }
    assert omitted == {
        "orphan-1": GenerationSectionKind.CHARACTERS,
        "budget-1": GenerationSectionKind.RELATIONSHIPS,
        "future-1": GenerationSectionKind.PRIOR_CHAPTER_SUMMARIES,
        "assembly-1": GenerationSectionKind.CANON_CONTEXT,
    }


def test_legacy_provider_visible_prompt_is_equivalent_after_preparation_wiring() -> None:
    value = _input(
        entry_blocks=(),
        entry_context_trace=freeze_mapping(
            {"feature_enabled": False, "retrieval_invoked": False}
        ),
    )
    preparation = prepare_continue_generation(value)
    request = ProviderRequest(
        provider="fake",
        model_name="fake-1",
        base_url=None,
        api_key=None,
        temperature=0.8,
        max_tokens=512,
        context_window=8192,
    )
    actual = NovelEngine(PromptEngine(), _Registry()).assemble_continue(
        preparation, req=request
    )

    asset = PromptAssetLoader().load("novel.continue")
    character_lines = [
        f"- {character.name}: {character.personality} / 말투: {character.speech_style}"
        for character in value.characters
    ]
    legacy_body = asset.body + "\n\n[등장인물]\n" + "\n".join(character_lines)
    expected = PromptEngine().assemble(
        AssembleInput(
            template_body=legacy_body,
            prompt_asset_id=asset.asset_id,
            prompt_asset_version=asset.version,
            prompt_asset_sha256=asset.sha256,
            world=value.world,
            lore_entries=list(value.lore),
            chapter_prior_summaries=[summary.content for summary in value.prior_summaries],
            chapter_prior_summary_indexes=[
                summary.chapter_index for summary in value.prior_summaries
            ],
            history=[],
            entry_blocks=[],
            entry_context_trace={"feature_enabled": False, "retrieval_invoked": False},
            user_message=f"[현재 챕터 끝부분]\n{value.current_chapter.tail}",
            instruction=value.instruction,
            context_window=request.context_window,
            max_tokens=request.max_tokens,
            safety_ratio=0.08,
        )
    )
    assert actual == expected
    assert "겨울 궁전" not in "\n".join(message.content for message in actual.messages)
