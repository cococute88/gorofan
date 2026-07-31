# Entry authoring and audit read API — Phase 1 implementation note

This note documents the authenticated HTTP boundary added after the Entry Review
Card API. It conforms to RFC-002 (Entry ownership, provenance, lifecycle, and
supersession), RFC-003 (default canonical status and retrieval separation), and
RFC-011 (the human gate).

## Boundary

All endpoints derive the owner from the existing current-user dependency. A
caller cannot provide `user_id`, `status`, `provenance`, `producer`, or
`confidence` to the direct-authoring endpoint.

### `POST /api/v1/entries`

Creates an explicitly human-authored canonical Entry. The intentional,
authenticated authoring action is the RFC-002 §7.2 human gate. The service,
not the client, writes this provenance:

```json
{
  "source_kind": "user",
  "source_id": "<authenticated-user-id>",
  "capture_method": "human-authored",
  "producer": "user-authoring-api"
}
```

The request may contain only the governed scope, optional typed subject, closed
Entry type, prose content, bounded data, priority, optional chapter origin, and
optional `supersedes_entry_id`. `EntryType` remains the RFC-002 closed
vocabulary; `note` is the only low-structure escape hatch. Invalid scope,
subject, owner, missing/soft-deleted anchor, cross-owner reference, and type
combinations use the existing validation error contract.

Without `supersedes_entry_id`, the server creates one canonical Entry with an
`accepted_at` timestamp after rechecking active anchors. For the two
single-current identities (`relationship.state` and `story.summary`), an
existing matching canon is rejected rather than overwritten.

With `supersedes_entry_id`, the server persists the new Entry only inside the
open transaction as a proposed replacement, then delegates to the established
`EntryService.supersede()` transaction. The old owned canon becomes
`superseded`, links to the new Entry, and the new Entry becomes `canon` in the
same commit. The endpoint has no generic update operation: canonical prose,
owner, lifecycle, and terminal history are never updated in place. Existing AI
producers remain bound to `EntryCreate` plus the Review Card path, where
AI-extracted Entries must begin as `proposed`.

### `GET /api/v1/entries`

Returns `PageOut[EntryRead]` ordered deterministically by `(created_at, id)`.
It uses the repository cursor convention (`limit` defaults to 20 and is capped
at 100) and is a CRUD/audit query, not `EntryService.retrieve()`.

The default result is only active, owned `status=canon` Entries. Canonical rows
whose required scope or subject anchor has been soft-deleted or orphaned are
excluded from this normal view before page selection. The owner root is applied
before every filter and before pagination.

Supported filters:

- `scope` and its required `scope_id` for `collection`, `work`, `character`,
  or `world`; `user` accepts no anchor;
- `type` from the governed Entry type vocabulary;
- `subject_type` plus `subject_id`, or exactly two repeated
  `subject_character_id` parameters for the normalized `character-pair`;
- `status`, only as an explicit audit filter;
- `limit` and `cursor`.

`include_history=false` is the default. A non-canonical `status` requires
`include_history=true`; otherwise it is rejected. `include_history=true` with
no status returns all lifecycle states (`captured`, `proposed`, `canon`,
`rejected`, and `superseded`) and intentionally retains orphaned records for
history/recovery. Every item carries its actual `status` so historical records
cannot be mistaken for current truth. Malformed cursors and incomplete scope or
subject selectors are rejected rather than silently broadening or restarting a
query.

### `GET /api/v1/entries/{entry_id}`

Returns a complete owned `EntryRead`, including the persisted lifecycle status
and timestamps. An unknown ID and a foreign owner ID both use the existing
`Entry not found` response, avoiding cross-owner existence disclosure.

## Relationship to Review Card and retrieval

The six `/api/v1/entries/review/*` endpoints are unchanged. They remain the
only route for AI-proposed Entry review, edit, accept, reject, and supersede.
The direct human-authoring DTO cannot carry AI provenance or a client-selected
lifecycle status, so it is not an AI direct-to-canon back door.

`GET /entries` does not call `EntryService.retrieve()`, rank Entries, choose a
knowledge budget, or assemble prompt context. Store-wide `retrieve()` remains
the separate RFC-003 generation-context seam for P1-6.

## Deliberate deferrals

This API does not add an Entry `PATCH`, a new lifecycle mutation API, a review
event table, a migration, a new type, ranking behavior, Analyst, Writer, or
frontend work. Dedicated review actor/action/diff persistence remains the
separate P1-9 design decision.
