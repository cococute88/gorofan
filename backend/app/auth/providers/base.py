"""OAuthProvider Protocol (design 14.6). New providers register without core changes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class PKCE:
    verifier: str
    challenge: str


@dataclass
class OAuthTokens:
    access_token: str
    refresh_token: str | None
    id_token: str | None
    expires_in: int | None


@dataclass
class OAuthIdentity:
    provider: str
    provider_account_id: str
    email: str
    display_name: str
    avatar_url: str | None = None


class OAuthProvider(Protocol):
    name: str

    def authorize_url(self, state: str, pkce: PKCE, redirect_uri: str) -> str: ...
    async def exchange_code(self, code: str, pkce: PKCE, redirect_uri: str) -> OAuthTokens: ...
    async def fetch_identity(self, tokens: OAuthTokens) -> OAuthIdentity: ...
