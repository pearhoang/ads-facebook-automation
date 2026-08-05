from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    AdAccount,
    AuditEvent,
    BrowserSession,
    FacebookAccount,
    Tenant,
    Worker,
    WorkerTenantAssignment,
    utc_now,
)


ACTIVE_SESSION_STATES = {"requested", "starting", "awaiting_user", "ready", "closing"}
WORKER_VISIBLE_STATES = {"requested", "starting", "awaiting_user", "ready", "closing"}
WORKER_TRANSITIONS = {
    "requested": {"starting", "failed", "closed"},
    "starting": {"awaiting_user", "ready", "failed", "closed"},
    "awaiting_user": {"ready", "failed", "closed"},
    "ready": {"failed", "closed"},
    "closing": {"closed", "failed"},
}


def _is_expired(expires_at: datetime, now: datetime) -> bool:
    """Compare timestamps consistently when SQLite drops timezone metadata."""
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return expires_at <= now


def ensure_tenant(db: Session, tenant_id: str) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        tenant = Tenant(id=tenant_id, name="Development tenant")
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
    return tenant


def register_worker(db: Session, worker_key: str, display_name: str) -> Worker:
    worker = db.scalar(select(Worker).where(Worker.worker_key == worker_key))
    if worker is None:
        worker = Worker(worker_key=worker_key, display_name=display_name)
        db.add(worker)
    else:
        worker.display_name = display_name
        worker.status = "online"
        worker.last_seen_at = utc_now()
    db.commit()
    db.refresh(worker)
    return worker


def assign_worker_to_tenant(db: Session, worker_id: str, tenant_id: str) -> None:
    """Provisioning boundary; a future admin API will call this service."""
    ensure_tenant(db, tenant_id)
    if db.get(Worker, worker_id) is None:
        raise HTTPException(status_code=404, detail="Worker not found.")
    assignment = db.get(
        WorkerTenantAssignment,
        {"worker_id": worker_id, "tenant_id": tenant_id},
    )
    if assignment is None:
        db.add(WorkerTenantAssignment(worker_id=worker_id, tenant_id=tenant_id))
        db.commit()


def heartbeat_worker(db: Session, worker_id: str) -> Worker:
    worker = db.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found.")
    worker.status = "online"
    worker.last_seen_at = utc_now()
    db.commit()
    db.refresh(worker)
    return worker


def list_tenant_workers(db: Session, tenant_id: str) -> list[Worker]:
    return list(
        db.scalars(
            select(Worker)
            .join(WorkerTenantAssignment, WorkerTenantAssignment.worker_id == Worker.id)
            .where(
                WorkerTenantAssignment.tenant_id == tenant_id,
                Worker.lifecycle_status == "active",
            )
            .order_by(Worker.display_name)
        )
    )


def create_account(
    db: Session,
    tenant_id: str,
    label: str,
    assigned_worker_id: str,
) -> FacebookAccount:
    ensure_tenant(db, tenant_id)
    worker = db.get(Worker, assigned_worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="Assigned worker not found.")
    assignment = db.get(
        WorkerTenantAssignment,
        {"worker_id": assigned_worker_id, "tenant_id": tenant_id},
    )
    if assignment is None:
        raise HTTPException(status_code=403, detail="Worker is not assigned to this tenant.")
    account = FacebookAccount(
        tenant_id=tenant_id,
        assigned_worker_id=assigned_worker_id,
        label=label,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def get_account(db: Session, tenant_id: str, account_id: str) -> FacebookAccount:
    account = db.scalar(
        select(FacebookAccount).where(
            FacebookAccount.id == account_id,
            FacebookAccount.tenant_id == tenant_id,
        )
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Facebook account not found.")
    return account


def list_accounts(db: Session, tenant_id: str) -> list[FacebookAccount]:
    return list(
        db.scalars(
            select(FacebookAccount)
            .where(
                FacebookAccount.tenant_id == tenant_id,
                FacebookAccount.status != "removed",
            )
            .order_by(FacebookAccount.created_at.desc())
        )
    )


def prepare_account_removal(
    db: Session,
    *,
    tenant_id: str,
    account_id: str,
) -> FacebookAccount:
    account = get_account(db, tenant_id, account_id)
    if account.status == "removed":
        return account
    active_session = db.scalar(
        select(BrowserSession.id)
        .where(
            BrowserSession.account_id == account.id,
            BrowserSession.status.in_(ACTIVE_SESSION_STATES),
        )
        .limit(1)
    )
    if active_session:
        raise HTTPException(
            status_code=409,
            detail="Facebook profile đang có browser session. Hãy đóng phiên trước khi gỡ.",
        )
    active_ad_account = db.scalar(
        select(AdAccount.id)
        .where(
            AdAccount.facebook_account_id == account.id,
            AdAccount.status == "active",
        )
        .limit(1)
    )
    if active_ad_account:
        raise HTTPException(
            status_code=409,
            detail="Hãy gỡ các ad account đang dùng Facebook profile này trước.",
        )
    return account


def mark_account_removed(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    account_id: str,
) -> FacebookAccount:
    account = prepare_account_removal(db, tenant_id=tenant_id, account_id=account_id)
    if account.status == "removed":
        return account
    account.status = "removed"
    account.last_error = None
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=user_id,
            actor_type="user",
            action="facebook_account.removed",
            entity_type="facebook_account",
            entity_id=account.id,
            payload_json={"label": account.label, "profile_key": account.profile_key},
        )
    )
    db.commit()
    db.refresh(account)
    return account


def create_browser_session(
    db: Session,
    tenant_id: str,
    account_id: str,
    ttl_minutes: int,
    launch_url: str | None = None,
) -> BrowserSession:
    account = get_account(db, tenant_id, account_id)
    if account.status == "removed":
        raise HTTPException(status_code=409, detail="Facebook profile đã được gỡ khỏi workspace.")
    active = db.scalar(
        select(BrowserSession).where(
            BrowserSession.account_id == account.id,
            BrowserSession.status.in_(ACTIVE_SESSION_STATES),
        )
    )
    if active is not None:
        raise HTTPException(status_code=409, detail="Account already has an active browser session.")

    now = utc_now()
    browser_session = BrowserSession(
        tenant_id=tenant_id,
        account_id=account.id,
        worker_id=account.assigned_worker_id,
        status="requested",
        launch_url=launch_url,
        expires_at=now + timedelta(minutes=ttl_minutes),
    )
    db.add(browser_session)
    db.commit()
    db.refresh(browser_session)
    return browser_session


def get_browser_session(db: Session, tenant_id: str, session_id: str) -> BrowserSession:
    browser_session = db.scalar(
        select(BrowserSession).where(
            BrowserSession.id == session_id,
            BrowserSession.tenant_id == tenant_id,
        )
    )
    if browser_session is None:
        raise HTTPException(status_code=404, detail="Browser session not found.")
    return browser_session


def get_latest_browser_session(
    db: Session,
    tenant_id: str,
    account_id: str,
) -> BrowserSession | None:
    get_account(db, tenant_id, account_id)
    return db.scalar(
        select(BrowserSession)
        .where(
            BrowserSession.account_id == account_id,
            BrowserSession.tenant_id == tenant_id,
        )
        .order_by(BrowserSession.requested_at.desc())
        .limit(1)
    )


def confirm_browser_session(db: Session, tenant_id: str, session_id: str) -> BrowserSession:
    browser_session = get_browser_session(db, tenant_id, session_id)
    if browser_session.status not in {"awaiting_user", "ready"}:
        raise HTTPException(status_code=409, detail="Browser session is not ready for confirmation.")
    browser_session.status = "ready"
    browser_session.account.status = "authenticated"
    browser_session.account.last_error = None
    db.commit()
    db.refresh(browser_session)
    return browser_session


def request_close_browser_session(db: Session, tenant_id: str, session_id: str) -> BrowserSession:
    browser_session = get_browser_session(db, tenant_id, session_id)
    if browser_session.status in {"closed", "expired"}:
        return browser_session
    if browser_session.status == "failed":
        browser_session.status = "closed"
        browser_session.closed_at = utc_now()
    else:
        browser_session.status = "closing"
    db.commit()
    db.refresh(browser_session)
    return browser_session


def poll_worker_sessions(db: Session, worker_id: str) -> list[BrowserSession]:
    heartbeat_worker(db, worker_id)
    now = utc_now()
    sessions = list(
        db.scalars(
            select(BrowserSession).where(
                BrowserSession.worker_id == worker_id,
                BrowserSession.status.in_(WORKER_VISIBLE_STATES),
            )
        )
    )
    changed = False
    for browser_session in sessions:
        if _is_expired(browser_session.expires_at, now) and browser_session.status != "closing":
            browser_session.status = "closing"
            changed = True
    if changed:
        db.commit()
    return sessions


def sync_worker_session(
    db: Session,
    worker_id: str,
    session_id: str,
    next_status: str,
    novnc_url: str | None,
    web_port: int | None,
    last_error: str | None,
    facebook_user_id: str | None,
) -> BrowserSession:
    browser_session = db.scalar(
        select(BrowserSession).where(
            BrowserSession.id == session_id,
            BrowserSession.worker_id == worker_id,
        )
    )
    if browser_session is None:
        raise HTTPException(status_code=404, detail="Browser session not found for worker.")

    allowed = WORKER_TRANSITIONS.get(browser_session.status, set())
    if next_status != browser_session.status and next_status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Invalid browser session transition: {browser_session.status} -> {next_status}.",
        )

    browser_session.status = next_status
    browser_session.novnc_url = novnc_url
    browser_session.web_port = web_port
    browser_session.last_error = last_error
    if next_status == "closed":
        browser_session.closed_at = utc_now()
        browser_session.novnc_url = None
        browser_session.web_port = None
    if next_status == "failed":
        browser_session.account.status = "error"
        browser_session.account.last_error = last_error
    if facebook_user_id:
        browser_session.account.facebook_user_id = facebook_user_id
    db.commit()
    db.refresh(browser_session)
    return browser_session
