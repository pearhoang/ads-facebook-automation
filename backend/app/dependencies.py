from __future__ import annotations

import secrets
from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from .config import Settings
from .services import auth, fleet


def get_db(request: Request) -> Iterator[Session]:
    yield from request.app.state.database.session()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_optional_principal(
    request: Request,
    db: Session = Depends(get_db),
) -> auth.AuthPrincipal | None:
    return resolve_optional_principal(request, db)


def resolve_optional_principal(request: Request, db: Session) -> auth.AuthPrincipal | None:
    settings: Settings = request.app.state.settings
    return auth.load_principal(db, request.cookies.get(settings.session_cookie_name))


def get_current_principal(
    principal: auth.AuthPrincipal | None = Depends(get_optional_principal),
) -> auth.AuthPrincipal:
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bạn chưa đăng nhập.")
    return principal


def get_current_tenant_id(
    principal: auth.AuthPrincipal = Depends(get_current_principal),
) -> str:
    return principal.tenant_id


def verify_csrf(
    request: Request,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    x_csrf_token: str | None = Header(default=None),
) -> None:
    settings: Settings = request.app.state.settings
    auth.verify_csrf_token(
        principal,
        request.cookies.get(settings.csrf_cookie_name),
        x_csrf_token,
    )


def require_owner(
    principal: auth.AuthPrincipal = Depends(get_current_principal),
) -> auth.AuthPrincipal:
    if principal.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Chỉ owner/admin được thực hiện thao tác này.")
    return principal


def verify_worker_credential(
    request: Request,
    db: Session = Depends(get_db),
    x_worker_secret: str | None = Header(default=None),
    x_worker_credential: str | None = Header(default=None),
) -> fleet.WorkerAuthContext:
    expected = request.app.state.settings.worker_shared_secret
    if x_worker_secret and secrets.compare_digest(x_worker_secret, expected):
        context = fleet.WorkerAuthContext(worker_id=None, legacy=True)
        request.state.worker_auth = context
        return context
    if not x_worker_credential:
        raise HTTPException(status_code=401, detail="Invalid worker credential.")
    context = fleet.authenticate_worker(db, x_worker_credential)
    route_worker_id = request.path_params.get("worker_id")
    if route_worker_id and context.worker_id != route_worker_id:
        raise HTTPException(status_code=403, detail="Worker credential does not match route.")
    request.state.worker_auth = context
    return context


verify_worker_secret = verify_worker_credential
