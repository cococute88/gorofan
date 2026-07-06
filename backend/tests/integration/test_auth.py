"""AuthService integration: fake OAuth begin→complete→JWT + token encryption (R8, Property 8)."""
from __future__ import annotations

import pytest

from app.auth.providers.base import PKCE, OAuthIdentity, OAuthTokens
from app.auth.service import AuthService
from app.config import get_settings
from app.core.errors import Unauthenticated
from app.core.security import decode_token
from app.db.session import create_engine, create_sessionmaker


class FakeGoogle:
    """Minimal OAuthProvider stand-in (design 14.6) — no network."""

    name = "google"

    def authorize_url(self, state: str, pkce: PKCE, redirect_uri: str) -> str:
        return f"https://fake/auth?state={state}&challenge={pkce.challenge}"

    async def exchange_code(self, code: str, pkce: PKCE, redirect_uri: str) -> OAuthTokens:
        assert code == "auth-code"
        return OAuthTokens(
            access_token="provider-access",
            refresh_token="provider-refresh",
            id_token="fake-id-token",
            expires_in=3600,
        )

    async def fetch_identity(self, tokens: OAuthTokens) -> OAuthIdentity:
        return OAuthIdentity(
            provider="google",
            provider_account_id="sub-123",
            email="creator@example.com",
            display_name="창작자",
        )


def _service() -> AuthService:
    settings = get_settings()
    sm = create_sessionmaker(create_engine(settings))
    return AuthService(sm, settings, {"google": FakeGoogle()})


@pytest.mark.asyncio
async def test_begin_returns_state_and_complete_issues_jwt():
    svc = _service()
    url = svc.begin("google")
    assert "state=" in url
    state = next(iter(svc._pending))  # white-box: the pending PKCE state

    pair = await svc.complete("google", "auth-code", state)
    payload = decode_token(get_settings(), pair.access_token)
    assert payload["typ"] == "access"
    assert payload["email"] == "creator@example.com"
    assert pair.refresh_token  # HttpOnly cookie value

    # state is single-use
    with pytest.raises(Unauthenticated):
        await svc.complete("google", "auth-code", state)


@pytest.mark.asyncio
async def test_provider_tokens_stored_encrypted():
    from sqlalchemy import select

    from app.models.user import OAuthAccount

    svc = _service()
    svc.begin("google")
    state = next(iter(svc._pending))
    await svc.complete("google", "auth-code", state)

    sm = create_sessionmaker(create_engine(get_settings()))
    async with sm() as s:
        acc = (
            await s.execute(
                select(OAuthAccount).where(OAuthAccount.provider_account_id == "sub-123")
            )
        ).scalars().first()
    assert acc is not None
    # Plaintext provider secrets must never be persisted (Property 8).
    assert acc.access_token_enc and "provider-access" not in acc.access_token_enc
    assert acc.refresh_token_enc and "provider-refresh" not in acc.refresh_token_enc


@pytest.mark.asyncio
async def test_unsupported_provider_rejected():
    svc = _service()
    with pytest.raises(Unauthenticated):
        svc.begin("facebook")
