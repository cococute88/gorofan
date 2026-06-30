"""Crypto + JWT helpers (design 4.5, 8.14, 14.4).

Symmetric encryption (Fernet, key derived from APP_SECRET_KEY) protects provider
API keys and OAuth tokens at rest. JWT issuance/verification backs sessions.
Plaintext secrets never leave the backend (Property 8).
"""
from __future__ import annotations

import base64
import hashlib
import time
import uuid
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt

from app.config import Settings


def _fernet(settings: Settings) -> Fernet:
    raw = settings.APP_SECRET_KEY.get_secret_value().encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
    return Fernet(key)


def encrypt_secret(settings: Settings, plaintext: str) -> str:
    return _fernet(settings).encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(settings: Settings, token: str) -> str:
    try:
        return _fernet(settings).decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:  # pragma: no cover - defensive
        raise ValueError("Unable to decrypt secret (wrong APP_SECRET_KEY?)") from exc


def mask_secret(plaintext: str) -> str:
    """Return masked form like ``sk-...abcd`` (design 4.5 / Property 8)."""
    if not plaintext:
        return ""
    tail = plaintext[-4:] if len(plaintext) >= 4 else plaintext
    prefix = plaintext[:3] if len(plaintext) > 7 else ""
    return f"{prefix}...{tail}"


def create_access_token(settings: Settings, sub: str, email: str | None = None) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": sub,
        "email": email,
        "iat": now,
        "exp": now + settings.JWT_TTL_SECONDS,
        "jti": str(uuid.uuid4()),
        "typ": "access",
    }
    return jwt.encode(
        payload, settings.APP_SECRET_KEY.get_secret_value(), algorithm=settings.JWT_ALG
    )


def create_refresh_token(settings: Settings, sub: str) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "iat": now,
        "exp": now + settings.REFRESH_TTL_SECONDS,
        "jti": str(uuid.uuid4()),
        "typ": "refresh",
    }
    return jwt.encode(
        payload, settings.APP_SECRET_KEY.get_secret_value(), algorithm=settings.JWT_ALG
    )


def decode_token(settings: Settings, token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token, settings.APP_SECRET_KEY.get_secret_value(), algorithms=[settings.JWT_ALG]
        )
    except JWTError as exc:
        raise ValueError("invalid token") from exc
