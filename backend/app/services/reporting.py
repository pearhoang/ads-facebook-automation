from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import (
    AdAccount,
    AuditEvent,
    BrowserSession,
    ExecutionJob,
    FacebookAccount,
    ReportJob,
    ReportSchedule,
    ReportSnapshot,
    Worker,
    utc_now,
)


MANUAL_CONFIRMATION = "THU THẬP KPI"
ACTIVE_STATES = {"queued", "claimed", "running"}
ACTIVE_BROWSER_STATES = {"requested", "starting", "awaiting_user", "ready", "closing"}
LEASE_MINUTES = 10
SCHEDULE_ROLES = {"owner", "admin"}
TERMINAL_JOB_STATES = {"succeeded", "failed", "cancelled"}


def _audit(
    db: Session,
    *,
    tenant_id: str,
    actor_user_id: str | None,
    actor_type: str,
    action: str,
    entity_id: str,
    payload: dict | None = None,
) -> None:
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            actor_type=actor_type,
            action=action,
            entity_type="report_job" if "job" in action else "report_schedule",
            entity_id=entity_id,
            payload_json=payload or {},
        )
    )


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(status_code=422, detail="Múi giờ của ad account không hợp lệ.") from exc


def _next_run(local_time: str, timezone_name: str, now: datetime | None = None) -> datetime:
    zone = _timezone(timezone_name)
    current = (now or utc_now()).astimezone(zone)
    hour, minute = (int(part) for part in local_time.split(":"))
    candidate = datetime.combine(current.date(), time(hour, minute), tzinfo=zone)
    if candidate <= current:
        candidate += timedelta(days=1)
    return candidate.astimezone(timezone.utc)


def _report_range(timezone_name: str, lookback_days: int, now: datetime | None = None) -> tuple[date, date]:
    local_today = (now or utc_now()).astimezone(_timezone(timezone_name)).date()
    range_end = local_today - timedelta(days=1)
    return range_end - timedelta(days=lookback_days - 1), range_end


def _account_context(
    db: Session,
    tenant_id: str,
    ad_account_id: str,
) -> tuple[AdAccount, FacebookAccount, Worker]:
    account = db.scalar(
        select(AdAccount).where(
            AdAccount.id == ad_account_id,
            AdAccount.tenant_id == tenant_id,
            AdAccount.status == "active",
        )
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ad account.")
    facebook = db.scalar(
        select(FacebookAccount).where(
            FacebookAccount.id == account.facebook_account_id,
            FacebookAccount.tenant_id == tenant_id,
        )
    )
    if facebook is None:
        raise HTTPException(status_code=409, detail="Ad account chưa có Facebook profile hợp lệ.")
    if facebook.status == "removed":
        raise HTTPException(status_code=409, detail="Facebook profile đã được gỡ khỏi workspace.")
    worker = db.get(Worker, facebook.assigned_worker_id)
    if worker is None:
        raise HTTPException(status_code=409, detail="Facebook profile chưa được gán worker.")
    return account, facebook, worker


def _job_payload(
    account: AdAccount,
    range_start: date,
    range_end: date,
    telegram_chat_id: str | None,
) -> dict:
    return {
        "ad_account": {
            "id": account.id,
            "label": account.label,
            "meta_ad_account_id": account.meta_ad_account_id,
            "currency": account.currency,
            "timezone_name": account.timezone_name,
        },
        "report": {
            "range_start": range_start.isoformat(),
            "range_end": range_end.isoformat(),
        },
        "delivery": {
            "channel": "telegram" if telegram_chat_id else "web_only",
            "telegram_chat_id": telegram_chat_id,
        },
        "safety": {
            "mode": "report_read_only",
            "allow_filter_click": False,
            "allow_ad_mutation": False,
            "allow_publish": False,
        },
    }


def _ensure_no_active_job(db: Session, ad_account_id: str) -> None:
    active = db.scalar(
        select(ReportJob.id).where(
            ReportJob.ad_account_id == ad_account_id,
            ReportJob.status.in_(ACTIVE_STATES),
        )
    )
    if active is not None:
        raise HTTPException(status_code=409, detail="Ad account đã có report job đang chờ hoặc đang chạy.")


def create_manual_job(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    ad_account_id: str,
    lookback_days: int,
    telegram_chat_id: str | None,
    confirmation: str,
) -> ReportJob:
    if confirmation.strip() != MANUAL_CONFIRMATION:
        raise HTTPException(status_code=422, detail=f"Hãy nhập đúng `{MANUAL_CONFIRMATION}`.")
    account, facebook, worker = _account_context(db, tenant_id, ad_account_id)
    if facebook.status != "authenticated":
        raise HTTPException(status_code=409, detail="Facebook profile chưa được xác nhận đăng nhập.")
    _ensure_no_active_job(db, account.id)
    browser_busy = db.scalar(
        select(BrowserSession.id).where(
            BrowserSession.account_id == facebook.id,
            BrowserSession.status.in_(ACTIVE_BROWSER_STATES),
        )
    )
    if browser_busy is not None:
        raise HTTPException(status_code=409, detail="Hãy đóng browser session trước khi thu thập KPI.")
    execution_busy = db.scalar(
        select(ExecutionJob.id).where(
            ExecutionJob.facebook_account_id == facebook.id,
            ExecutionJob.status.in_(ACTIVE_STATES),
        )
    )
    if execution_busy is not None:
        raise HTTPException(status_code=409, detail="Chrome profile đang có execution job.")
    range_start, range_end = _report_range(account.timezone_name, lookback_days)
    job = ReportJob(
        tenant_id=tenant_id,
        ad_account_id=account.id,
        facebook_account_id=facebook.id,
        worker_id=worker.id,
        trigger="manual",
        status="queued",
        range_start=range_start,
        range_end=range_end,
        payload_json=_job_payload(account, range_start, range_end, telegram_chat_id),
        delivery_status="pending" if telegram_chat_id else "not_requested",
        requested_by_user_id=user_id,
    )
    db.add(job)
    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=user_id,
        actor_type="user",
        action="report_job.created",
        entity_id=job.id,
        payload={"trigger": "manual", "range_start": str(range_start), "range_end": str(range_end)},
    )
    db.commit()
    db.refresh(job)
    return job


def list_jobs(db: Session, tenant_id: str, limit: int = 100) -> list[ReportJob]:
    return list(
        db.scalars(
            select(ReportJob)
            .where(ReportJob.tenant_id == tenant_id)
            .order_by(ReportJob.requested_at.desc())
            .limit(limit)
        )
    )


def _jobs_query(tenant_id: str, ad_account_id: str | None = None):
    query = select(ReportJob).where(ReportJob.tenant_id == tenant_id)
    if ad_account_id:
        query = query.where(ReportJob.ad_account_id == ad_account_id)
    return query


def list_jobs_page(
    db: Session,
    *,
    tenant_id: str,
    page: int,
    page_size: int,
    ad_account_id: str | None,
) -> dict:
    query = _jobs_query(tenant_id, ad_account_id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)
    items = list(
        db.scalars(
            query.order_by(ReportJob.requested_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }


def delete_jobs_page(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    role: str,
    page: int,
    page_size: int,
    ad_account_id: str | None,
) -> dict:
    if role not in SCHEDULE_ROLES:
        raise HTTPException(status_code=403, detail="Bạn không có quyền xóa lịch sử báo cáo.")
    page_data = list_jobs_page(
        db,
        tenant_id=tenant_id,
        page=page,
        page_size=page_size,
        ad_account_id=ad_account_id,
    )
    items = page_data["items"]
    account_ids = {item.ad_account_id for item in items}
    retained_job_ids: set[str] = set()
    for account_id in account_ids:
        latest_snapshot = db.scalar(
            select(ReportSnapshot)
            .where(
                ReportSnapshot.tenant_id == tenant_id,
                ReportSnapshot.ad_account_id == account_id,
            )
            .order_by(ReportSnapshot.collected_at.desc())
            .limit(1)
        )
        if latest_snapshot is not None:
            retained_job_ids.add(latest_snapshot.report_job_id)

    deleted = 0
    retained_latest = 0
    skipped_active = 0
    deleted_ids: list[str] = []
    for job in items:
        if job.id in retained_job_ids:
            retained_latest += 1
            continue
        if job.status not in TERMINAL_JOB_STATES:
            skipped_active += 1
            continue
        snapshots = list(
            db.scalars(
                select(ReportSnapshot).where(
                    ReportSnapshot.tenant_id == tenant_id,
                    ReportSnapshot.report_job_id == job.id,
                )
            )
        )
        for snapshot in snapshots:
            db.delete(snapshot)
        deleted_ids.append(job.id)
        db.delete(job)
        deleted += 1

    if deleted_ids:
        _audit(
            db,
            tenant_id=tenant_id,
            actor_user_id=user_id,
            actor_type="user",
            action="report_job.history_deleted",
            entity_id=deleted_ids[0],
            payload={"deleted_ids": deleted_ids, "page": page, "page_size": page_size},
        )
    db.commit()
    remaining = db.scalar(
        select(func.count()).select_from(_jobs_query(tenant_id, ad_account_id).subquery())
    ) or 0
    return {
        "deleted": deleted,
        "retained_latest": retained_latest,
        "skipped_active": skipped_active,
        "remaining": remaining,
    }


def list_snapshots(
    db: Session,
    tenant_id: str,
    ad_account_id: str | None,
    limit: int,
) -> list[ReportSnapshot]:
    query = select(ReportSnapshot).where(ReportSnapshot.tenant_id == tenant_id)
    if ad_account_id:
        query = query.where(ReportSnapshot.ad_account_id == ad_account_id)
    return list(db.scalars(query.order_by(ReportSnapshot.collected_at.desc()).limit(limit)))


def create_schedule(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    role: str,
    ad_account_id: str,
    local_time: str,
    lookback_days: int,
    telegram_chat_id: str | None,
) -> ReportSchedule:
    if role not in SCHEDULE_ROLES:
        raise HTTPException(status_code=403, detail="Bạn không có quyền tạo lịch báo cáo.")
    account, _facebook, worker = _account_context(db, tenant_id, ad_account_id)
    schedule = ReportSchedule(
        tenant_id=tenant_id,
        ad_account_id=account.id,
        worker_id=worker.id,
        status="enabled",
        cadence="daily",
        local_time=local_time,
        timezone_name=account.timezone_name,
        lookback_days=lookback_days,
        telegram_chat_id=telegram_chat_id,
        next_run_at=_next_run(local_time, account.timezone_name),
        created_by_user_id=user_id,
    )
    db.add(schedule)
    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=user_id,
        actor_type="user",
        action="report_schedule.created",
        entity_id=schedule.id,
        payload={"local_time": local_time, "lookback_days": lookback_days},
    )
    db.commit()
    db.refresh(schedule)
    return schedule


def list_schedules(db: Session, tenant_id: str) -> list[ReportSchedule]:
    return list(
        db.scalars(
            select(ReportSchedule)
            .where(ReportSchedule.tenant_id == tenant_id)
            .order_by(ReportSchedule.created_at.desc())
        )
    )


def update_schedule(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    role: str,
    schedule_id: str,
    changes: dict,
) -> ReportSchedule:
    if role not in SCHEDULE_ROLES:
        raise HTTPException(status_code=403, detail="Bạn không có quyền sửa lịch báo cáo.")
    schedule = db.scalar(
        select(ReportSchedule).where(
            ReportSchedule.id == schedule_id,
            ReportSchedule.tenant_id == tenant_id,
        )
    )
    if schedule is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy lịch báo cáo.")
    for field, value in changes.items():
        setattr(schedule, field, value)
    if {"status", "local_time"} & changes.keys():
        schedule.next_run_at = _next_run(schedule.local_time, schedule.timezone_name)
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=user_id,
        actor_type="user",
        action="report_schedule.updated",
        entity_id=schedule.id,
        payload={"changed_fields": sorted(changes)},
    )
    db.commit()
    db.refresh(schedule)
    return schedule


def _materialize_due_schedules(db: Session, worker_id: str, now: datetime) -> None:
    due = list(
        db.scalars(
            select(ReportSchedule)
            .where(
                ReportSchedule.worker_id == worker_id,
                ReportSchedule.status == "enabled",
                ReportSchedule.next_run_at <= now,
            )
            .order_by(ReportSchedule.next_run_at)
            .with_for_update(skip_locked=True)
            .limit(10)
        )
    )
    for schedule in due:
        active = db.scalar(
            select(ReportJob.id).where(
                ReportJob.ad_account_id == schedule.ad_account_id,
                ReportJob.status.in_(ACTIVE_STATES),
            )
        )
        if active is not None:
            continue
        account, facebook, worker = _account_context(db, schedule.tenant_id, schedule.ad_account_id)
        range_start, range_end = _report_range(
            schedule.timezone_name,
            schedule.lookback_days,
            now,
        )
        job = ReportJob(
            tenant_id=schedule.tenant_id,
            ad_account_id=account.id,
            facebook_account_id=facebook.id,
            worker_id=worker.id,
            schedule_id=schedule.id,
            trigger="scheduled",
            status="queued",
            range_start=range_start,
            range_end=range_end,
            payload_json=_job_payload(
                account,
                range_start,
                range_end,
                schedule.telegram_chat_id,
            ),
            delivery_status="pending" if schedule.telegram_chat_id else "not_requested",
        )
        db.add(job)
        schedule.last_enqueued_at = now
        schedule.next_run_at = _next_run(schedule.local_time, schedule.timezone_name, now)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            continue
        _audit(
            db,
            tenant_id=schedule.tenant_id,
            actor_user_id=None,
            actor_type="system",
            action="report_job.scheduled",
            entity_id=job.id,
            payload={"schedule_id": schedule.id},
        )


def poll_worker_job(db: Session, worker_id: str) -> ReportJob | None:
    now = utc_now()
    expired = list(
        db.scalars(
            select(ReportJob).where(
                ReportJob.worker_id == worker_id,
                ReportJob.status.in_({"claimed", "running"}),
                ReportJob.lease_expires_at < now,
            )
        )
    )
    for job in expired:
        job.status = "queued"
        job.last_error = "Worker lease expired; report job returned to queue."
        job.lease_expires_at = None
    _materialize_due_schedules(db, worker_id, now)
    current = db.scalar(
        select(ReportJob)
        .where(
            ReportJob.worker_id == worker_id,
            ReportJob.status.in_({"claimed", "running"}),
        )
        .order_by(ReportJob.claimed_at)
        .limit(1)
    )
    if current is not None:
        db.commit()
        db.refresh(current)
        return current
    candidates = list(
        db.scalars(
            select(ReportJob)
            .where(ReportJob.worker_id == worker_id, ReportJob.status == "queued")
            .order_by(ReportJob.requested_at)
            .with_for_update(skip_locked=True)
            .limit(10)
        )
    )
    for job in candidates:
        busy = db.scalar(
            select(BrowserSession.id).where(
                BrowserSession.account_id == job.facebook_account_id,
                BrowserSession.status.in_(ACTIVE_BROWSER_STATES),
            )
        )
        execution_busy = db.scalar(
            select(ExecutionJob.id).where(
                ExecutionJob.facebook_account_id == job.facebook_account_id,
                ExecutionJob.status.in_(ACTIVE_STATES),
            )
        )
        if busy is not None or execution_busy is not None:
            continue
        job.status = "claimed"
        job.claimed_at = now
        job.lease_expires_at = now + timedelta(minutes=LEASE_MINUTES)
        job.attempt_count += 1
        db.commit()
        db.refresh(job)
        return job
    db.commit()
    return None


def sync_worker_job(
    db: Session,
    *,
    worker_id: str,
    job_id: str,
    next_status: str,
    result_json: dict,
    last_error: str | None,
) -> ReportJob:
    job = db.scalar(
        select(ReportJob).where(ReportJob.id == job_id, ReportJob.worker_id == worker_id)
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Report job not found for worker.")
    transitions = {"claimed": {"running", "failed"}, "running": {"succeeded", "failed"}}
    if next_status != job.status and next_status not in transitions.get(job.status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Invalid report transition: {job.status} -> {next_status}.",
        )
    now = utc_now()
    job.status = next_status
    job.result_json = result_json
    job.last_error = last_error
    if next_status == "running":
        job.started_at = job.started_at or now
        job.lease_expires_at = now + timedelta(minutes=LEASE_MINUTES)
    if next_status in {"succeeded", "failed"}:
        job.completed_at = now
        job.lease_expires_at = None
        delivery = result_json.get("delivery") or {}
        if job.delivery_status != "not_requested":
            job.delivery_status = str(delivery.get("status") or "failed")
        if next_status == "succeeded":
            safety = result_json.get("safety") or {}
            if safety.get("published") is not False or safety.get("ad_mutated") is not False:
                raise HTTPException(status_code=422, detail="Report result is missing read-only safety proof.")
            metrics = result_json.get("metrics") or {}
            snapshot = db.scalar(
                select(ReportSnapshot).where(ReportSnapshot.report_job_id == job.id)
            )
            if snapshot is None:
                collected_raw = result_json.get("collected_at")
                try:
                    collected_at = datetime.fromisoformat(str(collected_raw).replace("Z", "+00:00"))
                except (TypeError, ValueError):
                    collected_at = now
                account = db.get(AdAccount, job.ad_account_id)
                snapshot = ReportSnapshot(
                    tenant_id=job.tenant_id,
                    report_job_id=job.id,
                    ad_account_id=job.ad_account_id,
                    range_start=job.range_start,
                    range_end=job.range_end,
                    source=str(result_json.get("source") or "meta_ads_manager_dom"),
                    currency=account.currency if account else "VND",
                    totals_json=dict(metrics.get("totals") or {}),
                    campaigns_json=list(metrics.get("campaigns") or []),
                    metadata_json={
                        "data_state": result_json.get("data_state"),
                        "headers": metrics.get("headers") or [],
                        "body_sha256": result_json.get("body_sha256"),
                        "safety": safety,
                    },
                    collected_at=collected_at,
                )
                db.add(snapshot)
        _audit(
            db,
            tenant_id=job.tenant_id,
            actor_user_id=None,
            actor_type="worker",
            action=f"report_job.{next_status}",
            entity_id=job.id,
            payload={"attempt_count": job.attempt_count, "delivery_status": job.delivery_status},
        )
    db.commit()
    db.refresh(job)
    return job
