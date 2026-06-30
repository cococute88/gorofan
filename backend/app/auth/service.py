"""AuthService (design 14). OAuth begin/complete + JWT issuance + default-user.

In-memory PKCE/state store is adequate for single-instance MVP; a shared store
would be used at scale. Tokens are encrypted at rest (Property 8).
"""
from __future__ import annotations

import base64
import hashlib
import os
import time
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.providers.base import PKCE, OAuthProvider
from app.config import Settings
from app.core.errors import Unauthenticated
from app.core.security import (
    create_access_token,
    create_refresh_token,
    encrypt_secret,
)
from app.models.user import OAuthAccount, User


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str


class AuthService:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        settings: Settings,
        providers: dict[str, OAuthProvider],
    ) -> None:
        self.sm = sessionmaker
        self.settings = settings
        self.providers = providers
        self._pending: dict[str, tuple[PKCE, float]] = {}

    def _redirect_uri(self, provider: str) -> str:
        return f"{self.settings.OAUTH_REDIRECT_BASE}/api/v1/auth/{provider}/callback"

    def begin(self, provider: str) -> str:
        prov = self._provider(provider)
        verifier = base64.urlsafe_b64encode(os.urandom(48)).decode().rstrip("=")
        challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .decode()
            .rstrip("=")
        )
        state = base64.urlsafe_b64encode(os.urandom(24)).decode().rstrip("=")
        self._pending[state] = (PKCE(verifier=verifier, challenge=challenge), time.time() + 600)
        return prov.authorize_url(state, PKCE(verifier, challenge), self._redirect_uri(provider))

    async def complete(self, provider: str, code: str, state: str) -> TokenPair:
        prov = self._provider(provider)
        entry = self._pending.pop(state, None)
        if entry is None or entry[1] < time.time():
            raise Unauthenticated("Invalid or expired OAuth state")
        pkce = entry[0]
        tokens = await prov.exchange_code(code, pkce, self._redirect_uri(provider))
        identity = await prov.fetch_identity(tokens)
        async with self.sm() as s:
            user = await self._upsert_user(s, identity, tokens)
            await s.commit()
            return TokenPair(
                access_token=create_access_token(self.settings, user.id, user.email),
                refresh_token=create_refresh_token(self.settings, user.id),
            )

    async def _upsert_user(self, s: AsyncSession, identity, tokens) -> User:  # noqa: ANN001
        acc_stmt = select(OAuthAccount).where(
            OAuthAccount.provider == identity.provider,
            OAuthAccount.provider_account_id == identity.provider_account_id,
        )
        account = (await s.execute(acc_stmt)).scalars().first()
        if account is not None:
            user = await s.get(User, account.user_id)
        else:
            user_stmt = select(User).where(User.email == identity.email)
            user = (await s.execute(user_stmt)).scalars().first()
            if user is None:
                user = User(
                    email=identity.email,
                    display_name=identity.display_name,
                    avatar_url=identity.avatar_url,
                )
                s.add(user)
                await s.flush()
            account = OAuthAccount(
                user_id=user.id,
                provider=identity.provider,
                provider_account_id=identity.provider_account_id,
            )
            s.add(account)
        # encrypt tokens at rest (Property 8)
        if tokens.access_token:
            account.access_token_enc = encrypt_secret(self.settings, tokens.access_token)
        if tokens.refresh_token:
            account.refresh_token_enc = encrypt_secret(self.settings, tokens.refresh_token)
        return user

    def _provider(self, provider: str) -> OAuthProvider:
        prov = self.providers.get(provider)
        if prov is None:
            raise Unauthenticated(f"Unsupported OAuth provider: {provider}")
        return prov


async def ensure_default_user(sessionmaker: async_sessionmaker[AsyncSession], user_id: str) -> None:
    """Idempotently seed the local-mode default user (design 14.2)."""
    async with sessionmaker() as s:
        existing = await s.get(User, user_id)
        if existing is None:
            s.add(
                User(
                    id=user_id,
                    email="local@localhost",
                    display_name="창작자",
                    is_active=True,
                )
            )
            await s.commit()
