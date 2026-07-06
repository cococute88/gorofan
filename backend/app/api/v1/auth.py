"""Auth router (design 6.2, 14)."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import RedirectResponse

from app.core.deps import get_current_user, get_state
from app.core.errors import AppError
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
    frontend = state.settings.FRONTEND_BASE_URL.rstrip("/")
    if state.auth_service is None:
        return RedirectResponse(url=f"{frontend}/login?error=auth_disabled", status_code=302)
    try:
        pair = await state.auth_service.complete(provider, code, state_param)
    except AppError as exc:
        # Bounce back to the login screen with a machine-readable reason.
        return RedirectResponse(
            url=f"{frontend}/login?error={quote(exc.code)}", status_code=302
        )

    # Hand the access token to the SPA via the URL fragment (never sent to a
    # server / not logged), and set the refresh token as an HttpOnly cookie.
    resp = Response(status_code=302)
    resp.headers["Location"] = f"{frontend}/auth/callback#access_token={quote(pair.access_token)}"
    resp.set_cookie(
        "refresh_token",
        pair.refresh_token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=state.settings.REFRESH_TTL_SECONDS,
    )
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
