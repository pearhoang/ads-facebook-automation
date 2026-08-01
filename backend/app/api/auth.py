from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from ..config import Settings
from ..dependencies import get_current_principal, get_db, get_settings, verify_csrf
from ..schemas import AuthLoginRequest, AuthView
from ..services import auth


router = APIRouter(prefix="/api/auth", tags=["auth"])


def _auth_view(principal: auth.AuthPrincipal) -> AuthView:
    return AuthView(
        user_id=principal.user_id,
        email=principal.email,
        display_name=principal.display_name,
        tenant_id=principal.tenant_id,
        tenant_name=principal.tenant_name,
        role=principal.role,
    )


def _require_same_origin(request: Request, settings: Settings) -> None:
    if settings.app_env != "production":
        return
    origin = request.headers.get("origin")
    if origin != settings.app_origin:
        raise HTTPException(status_code=403, detail="Origin không hợp lệ.")


@router.post("/login", response_model=AuthView)
def login(
    payload: AuthLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    _require_same_origin(request, settings)
    issued = auth.authenticate(
        db,
        email=payload.email,
        password=payload.password,
        ttl_hours=settings.session_ttl_hours,
        tenant_id=payload.tenant_id,
    )
    max_age = settings.session_ttl_hours * 60 * 60
    response.set_cookie(
        settings.session_cookie_name,
        issued.session_token,
        max_age=max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        issued.csrf_token,
        max_age=max_age,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return _auth_view(issued.principal)


@router.get("/me", response_model=AuthView)
def me(principal: auth.AuthPrincipal = Depends(get_current_principal)):
    return _auth_view(principal)


@router.post("/logout", status_code=204, dependencies=[Depends(verify_csrf)])
def logout(
    response: Response,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    auth.revoke_session(db, principal.session_id)
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        settings.csrf_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=False,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
