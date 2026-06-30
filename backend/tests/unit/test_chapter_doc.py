"""Unit tests for chapter text<->doc conversion + word count (design 11.6)."""
from __future__ import annotations

from app.services.novel_service import _text_to_doc, _word_count


def test_text_to_doc_structure():
    doc = _text_to_doc("문단 하나\n\n문단 둘")
    assert doc["type"] == "doc"
    assert len(doc["content"]) == 2
    assert doc["content"][0]["content"][0]["text"] == "문단 하나"


def test_empty_text_yields_single_paragraph():
    doc = _text_to_doc("")
    assert doc["content"] == [{"type": "paragraph"}]


def test_word_count():
    assert _word_count("one two three") == 3
