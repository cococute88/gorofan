"""Cursor pagination utilities (design 6.1, 8.3.2).

Deterministic ordering by (created_at, id) ensures stable cursors.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class PageParams:
    limit: int = 20
    cursor: str | None = None
    # for chat messages: reverse (newest->oldest) using `before`
    before: str | None = None


@dataclass
class Page(Generic[T]):
    items: list[T]
    next_cursor: str | None = None


def encode_cursor(created_at: str, id_: str) -> str:
    raw = json.dumps({"c": created_at, "i": id_}).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def decode_cursor(cursor: str) -> tuple[str, str] | None:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("utf-8"))
        data = json.loads(raw)
        return data["c"], data["i"]
    except Exception:
        return None
