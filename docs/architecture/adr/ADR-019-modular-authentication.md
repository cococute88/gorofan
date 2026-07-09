# ADR-019: Modular Authentication (Optional Auth)

- **Status:** Accepted — *auth as an env-toggled module; local default is no-login single-user*
- **Date:** 2026-07-09
- **Deciders:** Architecture Review Board
- **Related:** ADR-001, ADR-015, ADR-017

## 1. Context

The product is personal/local-first but designed to *allow* shared/multi-user deployment later. `design.md` §14 specifies auth as an independent module: local mode runs with `AUTH_ENABLED=false` injecting a seeded `default-user` (no login), while exposed deployments set `AUTH_ENABLED=true` for Google OAuth (Authorization Code + PKCE), short-lived access JWT + rotating HttpOnly refresh cookie, and standard OAuth validations. Because every aggregate already carries `user_id` (ADR-017), enabling multi-user is a toggle, not a rewrite (FUT-1).

The decision is to ratify this modularity and lock the security-relevant defaults — especially that the *convenient* local default must never accidentally become an *insecure* exposed default.

## 2. Decision

**Adopt authentication as an independent, env-toggled module with a secure-by-requirement exposed mode.**

1. **Single switch:** `AUTH_ENABLED` turns auth on/off with **zero core changes** (AC-AUTH-3). Off → seeded `default-user`, no login (local single-user). On → OAuth login required.
2. **OAuth via PKCE** (Google first) with `state`/CSRF, redirect-URI allowlist, and id_token signature/`iss`/`aud`/`exp` validation (AC-AUTH-1/5, SEC-4).
3. **Session tokens:** short-lived access JWT + rotating HttpOnly, Secure refresh cookie; logout revokes refresh (AC-AUTH-4).
4. **Everything is already user-scoped** (ADR-017 / Property 1), so flipping auth on yields correct isolation without data-model changes (FUT-1).
5. **Secure-by-requirement when exposed:** any network-exposed deployment **requires** `AUTH_ENABLED=true` and TLS (SEC-6). The insecure local default is only legitimate on a trusted local host.
6. **Provider extensibility via an `AuthProvider` seam** (ADR-015): GitHub/Discord/Apple add as registered providers, not core edits (FUT-4). Second providers are deferred until needed.

## 3. Alternatives Considered

- **A. Always-on auth** (login required even locally).
- **B. No auth at all / never multi-user.**
- **C. Roll-your-own password auth** instead of OAuth.
- **D. Third-party auth SaaS** (Auth0/Clerk/Firebase Auth).

## 4. Why Rejected

- **A — Always-on:** Adds friction and an OAuth dependency to the primary personal/local use case for no benefit; offline local use would need a login flow. Rejected — local default is no-login.
- **B — Never multi-user:** Forecloses the documented Phase 3 future (sharing, collaboration) that the `user_id`-everywhere design cheaply preserves. Removing the seam saves almost nothing. Rejected.
- **C — Custom password auth:** Owning password storage/reset/breach handling is security liability with no upside over delegated OAuth; contradicts "boring, safe plumbing." Rejected.
- **D — Auth SaaS:** External dependency and cost, breaks Local-First/Zero-Cost/offline, and adds vendor lock-in of identity. Rejected (self-hosted OAuth client is fine; a managed identity platform is not).

## 5. Consequences

**Positive**
- Frictionless local personal use (no login) with a real, standards-based path to secure multi-user — by a toggle, not a rewrite.
- Security-sensitive logic is quarantined in one module; the core is auth-agnostic.
- Additional OAuth providers are cheap to add later.

**Negative**
- The convenient insecure local default is a foot-gun if someone exposes the app without setting `AUTH_ENABLED=true` + TLS; this must be loudly documented and, ideally, guarded (refuse to bind non-locally without auth).
- OAuth + JWT + refresh rotation is non-trivial to implement correctly even as a module.

**Future risks**
- Misconfiguration (exposed without auth) is the primary risk; mitigation is a startup guard/warning and clear docs.
- Multi-user activation surfaces authorization concerns beyond authentication (sharing, roles) not covered here — a Phase 3 design task.

## 6. Future Revisit Conditions

- Before any exposed/multi-user launch, revisit for authorization (roles/sharing), rate limiting, and a startup guard preventing non-local binding without `AUTH_ENABLED`.
- Add `AuthProvider` implementations (GitHub/Discord/Apple) when a concrete need arises (ADR-015 trigger).
- Revisit token/session strategy if security review or a real deployment surfaces gaps.
