"""Direct human-authoring request boundary tests."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.entry import (
    EntryAuthoringCreate,
    EntryScope,
    EntrySubjectType,
    EntryType,
)


def _authoring_note(**overrides) -> dict:
    return {
        "scope_kind": EntryScope.USER,
        "type": EntryType.NOTE,
        "content": "An explicitly authored note.",
        **overrides,
    }


def test_authoring_dto_accepts_only_user_content_and_closed_vocabulary() -> None:
    dto = EntryAuthoringCreate(**_authoring_note(content="  Canon note.  "))
    assert dto.content == "Canon note."
    assert dto.priority == 50

    with pytest.raises(ValidationError):
        EntryAuthoringCreate(**_authoring_note(type="misc"))


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "canon"),
        ("user_id", "00000000-0000-0000-0000-000000000099"),
        ("provenance", {"capture_method": "ai-extracted"}),
        ("producer", "analyst"),
        ("confidence", 1.0),
    ],
)
def test_authoring_dto_rejects_lifecycle_owner_and_ai_producer_controls(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        EntryAuthoringCreate(**_authoring_note(**{field: value}))


def test_authoring_dto_reuses_subject_contract() -> None:
    with pytest.raises(ValidationError, match="character subject"):
        EntryAuthoringCreate(
            **_authoring_note(
                scope_kind=EntryScope.WORK,
                scope_id="work-id",
                type=EntryType.CHARACTER_VOICE,
                subject_type=EntrySubjectType.WORK,
                subject_id="work-id",
            )
        )

    with pytest.raises(ValidationError, match="chat-private"):
        EntryAuthoringCreate(
            **_authoring_note(
                scope_kind=EntryScope.CHAT_PRIVATE,
                scope_id="chat-id",
            )
        )
