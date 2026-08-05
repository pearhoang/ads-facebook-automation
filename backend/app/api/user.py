from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..config import Settings
from ..dependencies import get_current_tenant_id, get_db, get_settings, require_owner, verify_csrf
from ..schemas import (
    AccountCreateRequest,
    AccountView,
    BrowserSessionCreateRequest,
    BrowserSessionView,
    WorkerView,
)
from ..services import account_sessions, remote_ops, resources, ssh_credentials


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


@router.delete("/accounts/{account_id}", response_model=AccountView)
def remove_account(
    account_id: str,
    principal=Depends(require_owner),
    _csrf: None = Depends(verify_csrf),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    account = account_sessions.prepare_account_removal(
        db,
        tenant_id=principal.tenant_id,
        account_id=account_id,
    )
    if account.status != "removed":
        worker = account.worker
        password = ssh_credentials.decrypt_password(
            settings.resolved_secret_encryption_key(),
            worker.ssh_password_ciphertext if worker else None,
        )
        if not password:
            raise HTTPException(
                status_code=409,
                detail="Bot VPS chưa lưu SSH password nên chưa thể xóa cookie/profile an toàn.",
            )
        try:
            remote_ops.cleanup_browser_profile(worker, password, account.profile_key)
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Không thể dọn browser profile trên Bot VPS: {str(exc)[:600]}",
            ) from exc
    return account_sessions.mark_account_removed(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        account_id=account_id,
    )


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
