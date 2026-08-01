from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from ..config import Settings
from ..dependencies import get_current_tenant_id, get_db, get_settings, verify_csrf
from ..schemas import (
    AccountCreateRequest,
    AccountView,
    BrowserSessionCreateRequest,
    BrowserSessionView,
    WorkerView,
)
from ..services import account_sessions, resources


router = APIRouter(prefix="/api", tags=["user"])


@router.get("/workers", response_model=list[WorkerView])
def list_workers(
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return account_sessions.list_tenant_workers(db, tenant_id)


@router.post("/accounts", response_model=AccountView, status_code=status.HTTP_201_CREATED)
def create_account(
    payload: AccountCreateRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return account_sessions.create_account(
        db,
        tenant_id,
        payload.label,
        payload.assigned_worker_id,
    )


@router.get("/accounts", response_model=list[AccountView])
def list_accounts(
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return account_sessions.list_accounts(db, tenant_id)


@router.post(
    "/accounts/{account_id}/browser-sessions",
    response_model=BrowserSessionView,
    status_code=status.HTTP_201_CREATED,
)
def create_browser_session(
    account_id: str,
    payload: BrowserSessionCreateRequest | None = None,
    tenant_id: str = Depends(get_current_tenant_id),
    _csrf: None = Depends(verify_csrf),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    return account_sessions.create_browser_session(
        db,
        tenant_id,
        account_id,
        settings.browser_session_ttl_minutes,
        resources.validate_facebook_launch_url(payload.launch_url if payload else None),
    )


@router.get("/browser-sessions/{session_id}", response_model=BrowserSessionView)
def get_browser_session(
    session_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return account_sessions.get_browser_session(db, tenant_id, session_id)


@router.get(
    "/accounts/{account_id}/browser-sessions/latest",
    response_model=BrowserSessionView | None,
)
def get_latest_browser_session(
    account_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return account_sessions.get_latest_browser_session(db, tenant_id, account_id)


@router.post("/browser-sessions/{session_id}/confirm", response_model=BrowserSessionView)
def confirm_browser_session(
    session_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return account_sessions.confirm_browser_session(db, tenant_id, session_id)


@router.delete("/browser-sessions/{session_id}", response_model=BrowserSessionView)
def close_browser_session(
    session_id: str,
    response: Response,
    tenant_id: str = Depends(get_current_tenant_id),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    response.status_code = status.HTTP_202_ACCEPTED
    return account_sessions.request_close_browser_session(db, tenant_id, session_id)
