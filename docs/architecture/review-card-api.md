# Entry Review Card API — Phase 1 implementation note

This note records the deliberately small backend boundary that operationalizes
RFC-001, RFC-002, and RFC-011 without defining or implementing Review Card UI.

## Phase 1 boundary

All endpoints are authenticated and derive `user_id` from the existing current-user
dependency. Request bodies cannot select an owner or lifecycle status.

- `GET /api/v1/entries/review` lists the current owner's `proposed` Entries.
- `GET /api/v1/entries/review/{entry_id}` reads one owned `proposed` Entry.
- `POST /api/v1/entries/review/{entry_id}/accept` applies the existing
  `proposed -> canon` transition after rechecking owned, live scope, subject, and
  persisted internal provenance anchors.
- `POST /api/v1/entries/review/{entry_id}/reject` applies only the
  `proposed -> rejected` transition.
- `POST /api/v1/entries/review/{entry_id}/edit` changes only `title`, `content`,
  and `data` while leaving the Entry `proposed`. The service records the
  provenance capture method as `human-edited`.

The response reuses `EntryRead`, including identity, type, status, scope, subject,
content, provenance, confidence, priority, lifecycle timestamps, and ordinary
created/updated timestamps. Owner-invisible Entries use the existing not-found
behavior. Repeated or otherwise non-proposed accept, reject, edit, or detail actions
return an explicit lifecycle validation error rather than silent success.

## Preserved invariants

- There is no API that accepts `status=canon` or lets an AI producer write canon
  directly.
- `relationship.state` and `story.summary` keep the existing single-current rule;
  direct acceptance fails when matching canon exists and directs callers to the
  atomic `EntryService.supersede()` path.
- A proposed Entry whose persisted scope/subject anchor, internal provenance
  source, or chapter-origin anchor is missing, owner-invisible, or soft-deleted
  cannot be accepted.
- No migration, Entry table/schema change, retrieval ranking change, Context
  Assembly change, Analyst, Writer, Bench extension, frontend, or UI is included.

## Intentional deferrals

The Review API does not yet expose a supersede action. A follow-up may add an
authenticated review endpoint that names the current canon and delegates to the
existing atomic `supersede()` service path after the same anchor checks.

The current Entry persistence shape can record `human-edited` provenance and the
ordinary `updated_at`/accept/reject timestamps, but it has no dedicated review-event
or actor field. Persisting an explicit review actor, action history, edit diff, and
reversal metadata remains an open audit-contract decision and requires a separately
approved persistence design; this minimum API does not invent an unversioned JSON
audit schema.
