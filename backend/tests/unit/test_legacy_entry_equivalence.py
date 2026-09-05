"""Pure P1-8 projection and coverage contract tests."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.engines.prompt.engine import render_character_block, render_world_block
from app.schemas.equivalence import CoverageState, ProjectionKind
from app.services.legacy_entry_equivalence import (
    EntrySnapshot,
    compare_coverage,
    normalize_comparison_text,
    project_chapter_summaries,
    project_character,
    project_lore,
    project_world,
)


def _candidate(
    projection,
    *,
    entry_id: str,
    content: str | None = None,
    title: str | None = None,
    status: str = "canon",
    live: bool = True,
    data_level: str | None = None,
) -> EntrySnapshot:
    return EntrySnapshot(
        id=entry_id,
        scope_kind=projection.scope_kind,
        scope_id=projection.scope_id,
        subject_type=projection.subject_type,
        subject_id=projection.subject_id,
        entry_type=projection.entry_type,
        status=status,
        title=title if title is not None else projection.title,
        content=content if content is not None else projection.content,
        data_level=data_level,
        priority=50,
        live_anchor=live,
        superseded_by_entry_id=None,
    )


def test_normalization_is_strict_and_utf8_safe() -> None:
    assert normalize_comparison_text(" \r\n한 글  A!\r ") == "한 글  A!"
    assert normalize_comparison_text("Case") != normalize_comparison_text("case")
    assert normalize_comparison_text("한  글") != normalize_comparison_text("한 글")


def test_aggregate_renderers_preserve_prompt_text_and_distinct_source_spans() -> None:
    shared = "동일 원문"
    character = render_character_block(
        SimpleNamespace(name=shared, personality=shared, speech_style=shared)
    )
    assert character.content == (
        f"이름: {shared}\n성격: {shared}\n말투: {shared}"
    )
    assert character.field_spans["name"] != character.field_spans["personality"]
    assert character.field_spans["personality"] != character.field_spans["speech_style"]
    for span in character.field_spans.values():
        assert character.content[slice(*span)] == shared

    world = render_world_block(
        SimpleNamespace(name=shared, description=shared)
    )
    assert world.content == f"세계관: {shared}\n{shared}"
    assert world.content[slice(*world.field_spans["description"])] == shared

    resolved = render_character_block(
        SimpleNamespace(
            name="세라",
            personality="{{world.name}}",
            speech_style="{{world.name}}",
        ),
        transform=lambda value: value.replace("{{world.name}}", "테라"),
    )
    assert resolved.content == "이름: 세라\n성격: 테라\n말투: 테라"
    assert (
        resolved.content[slice(*resolved.field_spans["personality"])]
        == "테라"
    )


def test_character_projects_only_approved_fields_and_stable_keys() -> None:
    character = SimpleNamespace(
        id="char-1",
        name="세라",
        personality=" 침착함 ",
        speech_style="존댓말",
        greeting="투영 금지",
        tags=["금지"],
        avatar_url="secret.png",
    )
    batch = project_character(character)
    assert [item.source_key for item in batch.projections] == [
        "character:char-1:personality:0",
        "character:char-1:speech_style:0",
    ]
    assert [item.entry_type for item in batch.projections] == [
        "character.identity",
        "character.voice",
    ]
    assert {item.content for item in batch.projections} == {"침착함", "존댓말"}
    assert all("투영 금지" not in item.content for item in batch.projections)


def test_blank_character_source_is_traced_not_projected() -> None:
    batch = project_character(
        SimpleNamespace(id="char-2", name="빈", personality=" \r\n ", speech_style="말투")
    )
    assert [item.source_field for item in batch.projections] == ["speech_style"]
    assert batch.blank_source_keys == ("character:char-2:personality:0",)


def test_world_scalar_collection_glossary_mapping_and_order() -> None:
    world = SimpleNamespace(
        id="world-1",
        name="테라",
        description="설명",
        era="중세",
        races=["인간", " ", "엘프"],
        nations=["북국"],
        taboos=["마법 금지"],
    )
    glossary = [SimpleNamespace(id="term-1", term="마나", definition="마력 단위")]
    batch = project_world(world, glossary_terms=glossary)
    payloads = {item.projection_kind: item.comparison_payload for item in batch.projections}
    assert payloads[ProjectionKind.WORLD_DESCRIPTION] == ("설명",)
    assert payloads[ProjectionKind.WORLD_ERA] == ("시대: 중세",)
    assert payloads[ProjectionKind.GLOSSARY_TERM] == ("마나", "마력 단위")
    races = [item for item in batch.projections if item.projection_kind is ProjectionKind.WORLD_RACE]
    assert [(item.source_order, item.content) for item in races] == [
        (0, "종족: 인간"),
        (2, "종족: 엘프"),
    ]
    assert "world:world-1:races:1" in batch.blank_source_keys
    assert all(
        item.runtime_visibility == "not_applicable"
        for item in batch.projections
        if item.projection_kind
        in {
            ProjectionKind.WORLD_ERA,
            ProjectionKind.WORLD_RACE,
            ProjectionKind.WORLD_NATION,
            ProjectionKind.WORLD_TABOO,
            ProjectionKind.GLOSSARY_TERM,
        }
    )


def test_lore_projection_preserves_real_enabled_and_scan_semantics() -> None:
    rows = [
        (
            SimpleNamespace(
                id="lore-b",
                content="둘째",
                keywords=["Key"],
                priority=30,
                enabled=False,
                scan_depth=20,
            ),
            SimpleNamespace(id="book-1", enabled=True),
        ),
        (
            SimpleNamespace(
                id="lore-a",
                content="첫째",
                keywords=["key"],
                priority=30,
                enabled=True,
                scan_depth=9,
            ),
            SimpleNamespace(id="book-2", enabled=False),
        ),
    ]
    batch = project_lore("world-1", rows)
    assert [item.source_id for item in batch.projections] == ["lore-a", "lore-b"]
    first = batch.projections[0]
    assert first.selection_metadata == {
        "keywords": ("key",),
        "entry_enabled": True,
        "lorebook_enabled": False,
        "lorebook_id": "book-2",
        "scan_depth": 9,
        "effective_scan_depth": 9,
        "history_count": 0,
    }


def test_chapter_summary_uses_story_index_not_timestamp() -> None:
    chapters = [
        SimpleNamespace(id="c2", work_id="w", index=2, summary=" 둘 "),
        SimpleNamespace(id="c1", work_id="w", index=1, summary="하나"),
    ]
    rows = project_chapter_summaries(chapters).projections
    assert [(row.source_id, row.story_position, row.content) for row in rows] == [
        ("c1", 1, "하나"),
        ("c2", 2, "둘"),
    ]


@pytest.mark.parametrize(
    ("candidates", "expected", "code"),
    [
        ([], CoverageState.MISSING_ENTRY, None),
        ([{"id": "rejected", "status": "rejected"}], CoverageState.INELIGIBLE_ONLY, "entry_status_excluded"),
        ([{"id": "orphan", "live": False}], CoverageState.INELIGIBLE_ONLY, "entry_orphan_excluded"),
        ([{"id": "different", "content": "다름"}], CoverageState.CONTENT_MISMATCH, None),
        (
            [{"id": "different-old", "content": "다름", "status": "rejected"}],
            CoverageState.CONTENT_MISMATCH,
            "all_structural_candidates_ineligible",
        ),
        ([{"id": "exact"}], CoverageState.EQUIVALENT, None),
        ([{"id": "exact-1"}, {"id": "exact-2"}], CoverageState.AMBIGUOUS_MATCH, None),
    ],
)
def test_coverage_states_and_precedence(candidates, expected, code) -> None:
    projection = project_character(
        SimpleNamespace(id="char", name="주인공", personality="정확", speech_style="")
    ).projections[0]
    rows = [_candidate(projection, entry_id=item.pop("id"), **item) for item in candidates]
    record = compare_coverage([projection], rows)[0]
    assert record.coverage_state is expected
    if code:
        assert code in record.diagnostic_codes


def test_exact_canon_wins_over_mismatched_canon_and_exact_history() -> None:
    projection = project_character(
        SimpleNamespace(id="char", name="주인공", personality="정확", speech_style="")
    ).projections[0]
    record = compare_coverage(
        [projection],
        [
            _candidate(projection, entry_id="canon-exact"),
            _candidate(projection, entry_id="canon-other", content="다름"),
            _candidate(projection, entry_id="captured-exact", status="captured"),
            _candidate(projection, entry_id="proposed-exact", status="proposed"),
            _candidate(projection, entry_id="rejected-exact", status="rejected"),
            _candidate(projection, entry_id="superseded-exact", status="superseded"),
        ],
    )[0]
    assert record.coverage_state is CoverageState.EQUIVALENT
    assert record.eligible_exact_entry_ids == ["canon-exact"]
    assert record.ineligible_exact_entry_ids == [
        "captured-exact",
        "proposed-exact",
        "rejected-exact",
        "superseded-exact",
    ]


def test_title_required_only_for_glossary_and_level_rule_for_summary() -> None:
    world = SimpleNamespace(
        id="world",
        name="세계",
        description="설명",
        era="",
        races=[],
        nations=[],
        taboos=[],
    )
    glossary_projection = next(
        item
        for item in project_world(
            world,
            glossary_terms=[SimpleNamespace(id="term", term="용어", definition="정의")],
        ).projections
        if item.projection_kind is ProjectionKind.GLOSSARY_TERM
    )
    glossary_record = compare_coverage(
        [glossary_projection],
        [_candidate(glossary_projection, entry_id="term-entry", title="다른 용어")],
    )[0]
    assert glossary_record.coverage_state is CoverageState.CONTENT_MISMATCH
    assert glossary_record.candidates[0].differing_fields == ["title"]

    description = project_world(world).projections[0]
    assert compare_coverage(
        [description], [_candidate(description, entry_id="fact", title="무시되는 제목")]
    )[0].coverage_state is CoverageState.EQUIVALENT

    summary = project_chapter_summaries(
        [SimpleNamespace(id="chapter", work_id="work", index=1, summary="요약")]
    ).projections[0]
    assert compare_coverage(
        [summary], [_candidate(summary, entry_id="arc", data_level="arc")]
    )[0].coverage_state is CoverageState.CONTENT_MISMATCH
    assert compare_coverage(
        [summary], [_candidate(summary, entry_id="chapter", data_level="chapter")]
    )[0].coverage_state is CoverageState.EQUIVALENT


def test_duplicate_legacy_payload_reuses_coverage_but_stays_visible() -> None:
    world = SimpleNamespace(
        id="world",
        name="세계",
        description="",
        era="",
        races=["인간", "인간"],
        nations=[],
        taboos=[],
    )
    projections = list(project_world(world).projections)
    canon = _candidate(projections[0], entry_id="one-canon")
    records = compare_coverage(projections, [canon])
    assert [record.coverage_state for record in records] == [
        CoverageState.EQUIVALENT,
        CoverageState.EQUIVALENT,
    ]
    assert all("duplicate_legacy_payload" in record.diagnostic_codes for record in records)

    glossary = [
        SimpleNamespace(id="term-1", term="마나", definition="마력 단위"),
        SimpleNamespace(id="term-2", term="마나", definition="마력 단위"),
    ]
    glossary_projections = [
        item
        for item in project_world(world, glossary_terms=glossary).projections
        if item.projection_kind is ProjectionKind.GLOSSARY_TERM
    ]
    glossary_records = compare_coverage(
        glossary_projections,
        [_candidate(glossary_projections[0], entry_id="one-term")],
    )
    assert all(
        record.coverage_state is CoverageState.EQUIVALENT
        and "duplicate_legacy_payload" in record.diagnostic_codes
        for record in glossary_records
    )

    lore_rows = [
        (
            SimpleNamespace(
                id=f"lore-{index}",
                content="같은 로어",
                keywords=["같은"],
                priority=50,
                enabled=True,
                scan_depth=4,
            ),
            SimpleNamespace(id="book", enabled=True),
        )
        for index in range(2)
    ]
    lore_projections = list(project_lore("world", lore_rows).projections)
    lore_records = compare_coverage(
        lore_projections, [_candidate(lore_projections[0], entry_id="one-lore")]
    )
    assert all(
        record.coverage_state is CoverageState.EQUIVALENT
        and "duplicate_legacy_payload" in record.diagnostic_codes
        for record in lore_records
    )
