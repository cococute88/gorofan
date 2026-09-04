"""Golden logical snapshots for both P1-8 generation surfaces."""
from __future__ import annotations

from app.services.legacy_entry_equivalence import compare_coverage
from tests.golden.legacy_entry_equivalence_fixture import chat_golden, novel_golden


def _logical_snapshot(records) -> list[dict]:  # noqa: ANN001
    return [
        {
            "source_key": record.projection.source_key,
            "kind": record.projection.projection_kind.value,
            "coverage": record.coverage_state.value,
            "eligible": record.eligible_exact_entry_ids,
            "ineligible": record.ineligible_exact_entry_ids,
            "codes": record.diagnostic_codes,
            "visibility": record.projection.runtime_visibility,
        }
        for record in records
    ]


def test_chat_coverage_golden() -> None:
    projections, candidates = chat_golden()
    assert _logical_snapshot(compare_coverage(projections, candidates)) == [
        {
            "source_key": "character:chat-character:personality:0",
            "kind": "character_personality",
            "coverage": "equivalent",
            "eligible": ["chat-identity"],
            "ineligible": [],
            "codes": [],
            "visibility": "visible",
        },
        {
            "source_key": "character:chat-character:speech_style:0",
            "kind": "character_speech_style",
            "coverage": "equivalent",
            "eligible": ["chat-voice"],
            "ineligible": [],
            "codes": [],
            "visibility": "visible",
        },
        {
            "source_key": "lore_entry:chat-lore:content:0",
            "kind": "lore",
            "coverage": "content_mismatch",
            "eligible": [],
            "ineligible": ["chat-lore-history"],
            "codes": ["entry_status_excluded"],
            "visibility": "visible",
        },
        {
            "source_key": "world:chat-world:description:0",
            "kind": "world_description",
            "coverage": "content_mismatch",
            "eligible": [],
            "ineligible": [],
            "codes": ["entry_status_excluded"],
            "visibility": "visible",
        },
        {
            "source_key": "world:chat-world:era:0",
            "kind": "world_era",
            "coverage": "content_mismatch",
            "eligible": [],
            "ineligible": [],
            "codes": ["entry_status_excluded"],
            "visibility": "not_applicable",
        },
        {
            "source_key": "world:chat-world:races:0",
            "kind": "world_race",
            "coverage": "content_mismatch",
            "eligible": [],
            "ineligible": [],
            "codes": ["entry_status_excluded"],
            "visibility": "not_applicable",
        },
    ]


def test_novel_summary_chronology_golden() -> None:
    projections, candidates = novel_golden()
    assert _logical_snapshot(compare_coverage(projections, candidates)) == [
        {
            "source_key": "chapter:chapter-1:summary:0",
            "kind": "chapter_summary",
            "coverage": "equivalent",
            "eligible": ["summary-prior"],
            "ineligible": [],
            "codes": [],
            "visibility": "visible",
        },
        {
            "source_key": "chapter:chapter-3:summary:0",
            "kind": "chapter_summary",
            "coverage": "ambiguous_match",
            "eligible": ["summary-future-a", "summary-future-b"],
            "ineligible": [],
            "codes": [],
            "visibility": "visible",
        },
    ]
