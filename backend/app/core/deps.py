"""FastAPI dependencies (design 8.4).

Single DI mechanism via Depends. App-lifetime singletons live on app.state;
per-request session and current_user are resolved here.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.core.errors import Unauthenticated
from app.core.security import decode_token
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_state(request: Request):
    return request.app.state


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    sm = request.app.state.sessionmaker
    session: AsyncSession = sm()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not settings.AUTH_ENABLED:
        # local single-user mode: inject default-user (design 14.9)
        user = await db.get(User, settings.DEFAULT_USER_ID)
        if user is None:
            raise Unauthenticated("default-user not seeded")
        return user
    if creds is None:
        raise Unauthenticated("Missing bearer token")
    try:
        payload = decode_token(settings, creds.credentials)
    except ValueError as exc:
        raise Unauthenticated("Invalid token") from exc
    if payload.get("typ") != "access":
        raise Unauthenticated("Wrong token type")
    user = await db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise Unauthenticated("User not found")
    return user
