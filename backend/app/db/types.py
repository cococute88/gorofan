"""Portable column types (design 4.4).

JSON columns map to JSONB on PostgreSQL and JSON on SQLite via a dialect variant.
This keeps array/flexible fields (tags, races, keywords, meta) dialect-agnostic
without raw SQL (CON-2).
"""
from __future__ import annotations

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

# JSONB on PostgreSQL, JSON elsewhere (SQLite).
PortableJSON = JSON().with_variant(JSONB(), "postgresql")

# Semantic aliases used by models.
JSONList = PortableJSON
JSONDict = PortableJSON
