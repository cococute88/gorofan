"""Google OAuth provider (design 14.3, 14.7).

Authorization Code + PKCE. id_token is verified (iss/aud/exp) via Google's tokeninfo
endpoint for simplicity; production may verify the JWT signature against JWKS.
"""
from __future__ import annotations

import httpx

from app.auth.providers.base import PKCE, OAuthIdentity, OAuthProvider, OAuthTokens
from app.core.errors import Unauthenticated

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
TOKENINFO_ENDPOINT = "https://oauth2.googleapis.com/tokeninfo"


class GoogleOAuthProvider(OAuthProvider):
    name = "google"

    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret

    def authorize_url(self, state: str, pkce: PKCE, redirect_uri: str) -> str:
        from urllib.parse import urlencode

        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "code_challenge": pkce.challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{AUTH_ENDPOINT}?{urlencode(params)}"

    async def exchange_code(self, code: str, pkce: PKCE, redirect_uri: str) -> OAuthTokens:
        data = {
            "code": code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": pkce.verifier,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(TOKEN_ENDPOINT, data=data)
        if resp.status_code >= 400:
            raise Unauthenticated("OAuth code exchange failed")
        body = resp.json()
        return OAuthTokens(
            access_token=body.get("access_token", ""),
            refresh_token=body.get("refresh_token"),
            id_token=body.get("id_token"),
            expires_in=body.get("expires_in"),
        )

    async def fetch_identity(self, tokens: OAuthTokens) -> OAuthIdentity:
        if not tokens.id_token:
            raise Unauthenticated("Missing id_token")
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(TOKENINFO_ENDPOINT, params={"id_token": tokens.id_token})
        if resp.status_code >= 400:
            raise Unauthenticated("id_token verification failed")
        claims = resp.json()
        # verify audience (design 14.7)
        if claims.get("aud") != self.client_id:
            raise Unauthenticated("id_token aud mismatch")
        return OAuthIdentity(
            provider="google",
            provider_account_id=claims["sub"],
            email=claims.get("email", ""),
            display_name=claims.get("name", claims.get("email", "사용자")),
            avatar_url=claims.get("picture"),
        )
