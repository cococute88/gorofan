"""Auth router (design 6.2, 14)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, get_state
from app.models.user import User

router = APIRouter()


@router.get("/{provider}/login")
async def login(provider: str, state=Depends(get_state)):
    if state.auth_service is None:
        return {"detail": "AUTH disabled (local mode). Use the app directly."}
    url = state.auth_service.begin(provider)
    return RedirectResponse(url=url, status_code=302)


@router.get("/{provider}/callback")
async def callback(
    provider: str,
    code: str = Query(...),
    state_param: str = Query(..., alias="state"),
    state=Depends(get_state),
):
    pair = await state.auth_service.complete(provider, code, state_param)
    resp = Response(status_code=302)
    resp.headers["Location"] = "/"
    # refresh token as HttpOnly cookie (design 14.4)
    resp.set_cookie(
        "refresh_token",
        pair.refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=state.settings.REFRESH_TTL_SECONDS,
    )
    resp.headers["X-Access-Token"] = pair.access_token
    return resp


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
    }


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("refresh_token")
    return {"status": "logged_out"}
