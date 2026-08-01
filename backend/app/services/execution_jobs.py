from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    AdAccount,
    ApprovalRequest,
    AuditEvent,
    BrowserSession,
    CampaignDraft,
    ExecutionArtifact,
    ExecutionJob,
    FacebookAccount,
    Worker,
    new_id,
    utc_now,
)
from . import objective_specs, resources


APPROVER_ROLES = {"owner", "admin"}
ACTIVE_BROWSER_STATES = {"requested", "starting", "awaiting_user", "ready", "closing"}
ACTIVE_JOB_STATES = {"queued", "claimed", "running"}
CONFIRMATION_TEXT = "CHẠY PREFLIGHT"
BUILD_DRAFT_CONFIRMATION_TEXT = "TẠO DRAFT META"
LEASE_MINUTES = 3
ARTIFACT_KINDS = {
    "screenshot",
    "campaign_step",
    "adset_step",
    "ad_step",
    "review_step",
    "failure",
}


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


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
            entity_type="execution_job",
            entity_id=entity_id,
            payload_json=payload or {},
        )
    )


def _campaign_graph(
    db: Session, tenant_id: str, campaign_id: str
) -> tuple[CampaignDraft, ApprovalRequest, AdAccount, FacebookAccount, Worker]:
    row = db.execute(
        select(CampaignDraft, ApprovalRequest, AdAccount, FacebookAccount, Worker)
        .join(AdAccount, AdAccount.id == CampaignDraft.ad_account_id)
        .join(FacebookAccount, FacebookAccount.id == AdAccount.facebook_account_id)
        .join(Worker, Worker.id == FacebookAccount.assigned_worker_id)
        .join(
            ApprovalRequest,
            (ApprovalRequest.campaign_draft_id == CampaignDraft.id)
            & (ApprovalRequest.status == "approved"),
        )
        .where(
            CampaignDraft.id == campaign_id,
            CampaignDraft.tenant_id == tenant_id,
        )
        .order_by(ApprovalRequest.decided_at.desc())
        .limit(1)
    ).one_or_none()
    if row is None:
        raise HTTPException(
            status_code=409,
            detail="Campaign phải được duyệt nội bộ trước khi chạy preflight.",
        )
    return row


def build_preview(db: Session, tenant_id: str, campaign_id: str) -> dict:
    campaign, approval, ad_account, facebook_account, worker = _campaign_graph(
        db, tenant_id, campaign_id
    )
    blockers: list[str] = []
    if campaign.status != "approved":
        blockers.append("Campaign không còn ở trạng thái đã duyệt nội bộ.")
    if approval.snapshot_json.get("version") != campaign.version:
        blockers.append("Version campaign không khớp snapshot đã duyệt.")
    if facebook_account.status != "authenticated":
        blockers.append("Tài khoản Facebook chưa được xác nhận đăng nhập.")
    if worker.status != "online" or (utc_now() - _aware(worker.last_seen_at)).total_seconds() > 90:
        blockers.append("Worker đang offline hoặc heartbeat đã cũ.")
    active_browser = db.scalar(
        select(BrowserSession.id).where(
            BrowserSession.account_id == facebook_account.id,
            BrowserSession.status.in_(ACTIVE_BROWSER_STATES),
        )
    )
    if active_browser is not None:
        blockers.append("Chrome profile đang có browser session hoạt động.")
    successful_preflight = db.scalar(
        select(ExecutionJob)
        .where(
            ExecutionJob.tenant_id == tenant_id,
            ExecutionJob.campaign_draft_id == campaign.id,
            ExecutionJob.job_type == "preflight",
            ExecutionJob.status == "succeeded",
        )
        .order_by(ExecutionJob.completed_at.desc())
        .limit(1)
    )
    draft_blockers = list(blockers)
    if successful_preflight is None or not successful_preflight.result_json.get("ready"):
        draft_blockers.append("Campaign chưa có preflight đạt trên Chrome profile hiện tại.")
    elif (
        successful_preflight.payload_json.get("campaign_snapshot", {}).get("version")
        != campaign.version
    ):
        draft_blockers.append("Preflight đạt không cùng version với campaign đã duyệt.")
    targeting = approval.snapshot_json.get("targeting_json") or {}
    creative = approval.snapshot_json.get("creative_json") or {}
    objective_blockers, draft_warnings = objective_specs.build_spec_warnings(
        str(approval.snapshot_json.get("objective") or ""),
        targeting,
        creative,
    )
    draft_blockers.extend(objective_blockers)
    resource_blockers, resource_warnings = resources.execution_resource_findings(
        db,
        tenant_id=tenant_id,
        ad_account_id=ad_account.id,
        targeting=targeting,
        creative=creative,
    )
    draft_blockers.extend(resource_blockers)
    draft_warnings.extend(resource_warnings)
    return {
        "campaign_id": campaign.id,
        "campaign_name": campaign.name,
        "campaign_version": campaign.version,
        "ad_account_label": ad_account.label,
        "meta_ad_account_id": ad_account.meta_ad_account_id,
        "facebook_account_label": facebook_account.label,
        "facebook_account_status": facebook_account.status,
        "worker_name": worker.display_name,
        "worker_status": worker.status,
        "active_browser_session": active_browser is not None,
        "can_run_preflight": not blockers,
        "can_build_draft": not draft_blockers,
        "blockers": blockers,
        "draft_blockers": draft_blockers,
        "draft_warnings": draft_warnings,
        "approved_snapshot": approval.snapshot_json,
    }


def create_execution_job(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    role: str,
    campaign_id: str,
    job_type: str,
    confirmation: str,
) -> ExecutionJob:
    if job_type == "preflight":
        return create_preflight_job(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            campaign_id=campaign_id,
            confirmation=confirmation,
        )
    if job_type == "draft_build":
        return create_draft_build_job(
            db,
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            campaign_id=campaign_id,
            confirmation=confirmation,
        )
    raise HTTPException(status_code=422, detail="Execution job type không được hỗ trợ.")


def create_preflight_job(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    role: str,
    campaign_id: str,
    confirmation: str,
) -> ExecutionJob:
    if role not in APPROVER_ROLES:
        raise HTTPException(status_code=403, detail="Bạn không có quyền tạo execution job.")
    if confirmation.strip() != CONFIRMATION_TEXT:
        raise HTTPException(
            status_code=422,
            detail=f"Hãy nhập chính xác: {CONFIRMATION_TEXT}",
        )
    preview = build_preview(db, tenant_id, campaign_id)
    if preview["blockers"]:
        raise HTTPException(status_code=409, detail=" ".join(preview["blockers"]))
    campaign, approval, ad_account, facebook_account, worker = _campaign_graph(
        db, tenant_id, campaign_id
    )
    active = db.scalar(
        select(ExecutionJob.id).where(
            ExecutionJob.campaign_draft_id == campaign.id,
            ExecutionJob.job_type == "preflight",
            ExecutionJob.status.in_(ACTIVE_JOB_STATES),
        )
    )
    if active is not None:
        raise HTTPException(status_code=409, detail="Campaign đã có preflight job đang chạy.")
    job = ExecutionJob(
        tenant_id=tenant_id,
        campaign_draft_id=campaign.id,
        approval_request_id=approval.id,
        ad_account_id=ad_account.id,
        facebook_account_id=facebook_account.id,
        worker_id=worker.id,
        job_type="preflight",
        status="queued",
        payload_json={
            "campaign_snapshot": approval.snapshot_json,
            "ad_account": {
                "id": ad_account.id,
                "label": ad_account.label,
                "meta_ad_account_id": ad_account.meta_ad_account_id,
                "currency": ad_account.currency,
                "timezone_name": ad_account.timezone_name,
            },
            "safety": {
                "mode": "read_only",
                "allow_click": False,
                "allow_publish": False,
            },
        },
        requested_by_user_id=user_id,
    )
    db.add(job)
    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=user_id,
        actor_type="user",
        action="execution_job.queued",
        entity_id=job.id,
        payload={"campaign_id": campaign.id, "job_type": "preflight"},
    )
    db.commit()
    db.refresh(job)
    return job


def create_draft_build_job(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    role: str,
    campaign_id: str,
    confirmation: str,
) -> ExecutionJob:
    if role not in APPROVER_ROLES:
        raise HTTPException(status_code=403, detail="Bạn không có quyền tạo Meta draft job.")
    if confirmation.strip() != BUILD_DRAFT_CONFIRMATION_TEXT:
        raise HTTPException(
            status_code=422,
            detail=f"Hãy nhập chính xác: {BUILD_DRAFT_CONFIRMATION_TEXT}",
        )
    preview = build_preview(db, tenant_id, campaign_id)
    if preview["draft_blockers"]:
        raise HTTPException(status_code=409, detail=" ".join(preview["draft_blockers"]))
    campaign, approval, ad_account, facebook_account, worker = _campaign_graph(
        db, tenant_id, campaign_id
    )
    active = db.scalar(
        select(ExecutionJob.id).where(
            ExecutionJob.campaign_draft_id == campaign.id,
            ExecutionJob.job_type == "draft_build",
            ExecutionJob.status.in_(ACTIVE_JOB_STATES),
        )
    )
    if active is not None:
        raise HTTPException(status_code=409, detail="Campaign đã có Meta draft job đang chạy.")
    snapshot = approval.snapshot_json
    objective_spec = objective_specs.get_spec(str(snapshot.get("objective") or ""))
    if objective_spec is None:
        raise HTTPException(status_code=409, detail="Objective chưa có adapter đã khảo sát.")
    job = ExecutionJob(
        tenant_id=tenant_id,
        campaign_draft_id=campaign.id,
        approval_request_id=approval.id,
        ad_account_id=ad_account.id,
        facebook_account_id=facebook_account.id,
        worker_id=worker.id,
        job_type="draft_build",
        status="queued",
        payload_json={
            "campaign_snapshot": snapshot,
            "ad_account": {
                "id": ad_account.id,
                "label": ad_account.label,
                "meta_ad_account_id": ad_account.meta_ad_account_id,
                "currency": ad_account.currency,
                "timezone_name": ad_account.timezone_name,
            },
            "draft_spec": {
                "campaign_name": snapshot["name"],
                "adset_name": f"{snapshot['name']} — Ad Set",
                "ad_name": f"{snapshot['name']} — Ad",
                "objective": snapshot["objective"],
                "daily_budget_minor": snapshot["daily_budget_minor"],
                "start_at": snapshot.get("start_at"),
                "end_at": snapshot.get("end_at"),
                "targeting": snapshot.get("targeting_json") or {},
                "creative": snapshot.get("creative_json") or {},
            },
            "objective_adapter": objective_spec.as_payload(),
            "safety": {
                "mode": "draft_only",
                "allow_click": True,
                "allow_publish": False,
                "stop_before": "publish",
            },
        },
        requested_by_user_id=user_id,
    )
    db.add(job)
    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=user_id,
        actor_type="user",
        action="execution_job.queued",
        entity_id=job.id,
        payload={"campaign_id": campaign.id, "job_type": "draft_build"},
    )
    db.commit()
    db.refresh(job)
    return job


def list_jobs(db: Session, tenant_id: str, limit: int = 100) -> list[ExecutionJob]:
    return list(
        db.scalars(
            select(ExecutionJob)
            .where(ExecutionJob.tenant_id == tenant_id)
            .order_by(ExecutionJob.requested_at.desc())
            .limit(limit)
        )
    )


def get_job(db: Session, tenant_id: str, job_id: str) -> ExecutionJob:
    job = db.scalar(
        select(ExecutionJob).where(
            ExecutionJob.id == job_id,
            ExecutionJob.tenant_id == tenant_id,
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy execution job.")
    return job


def retry_job(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    role: str,
    job_id: str,
    confirmation: str,
) -> ExecutionJob:
    if role not in APPROVER_ROLES:
        raise HTTPException(status_code=403, detail="Bạn không có quyền retry execution job.")
    job = get_job(db, tenant_id, job_id)
    expected_confirmation = (
        BUILD_DRAFT_CONFIRMATION_TEXT if job.job_type == "draft_build" else CONFIRMATION_TEXT
    )
    if confirmation.strip() != expected_confirmation:
        raise HTTPException(status_code=422, detail=f"Hãy nhập chính xác: {expected_confirmation}")
    if job.status not in {"failed", "awaiting_user"}:
        raise HTTPException(status_code=409, detail="Chỉ job failed hoặc awaiting_user mới có thể retry.")
    preview = build_preview(db, tenant_id, job.campaign_draft_id)
    blocker_key = "draft_blockers" if job.job_type == "draft_build" else "blockers"
    blockers = [item for item in preview[blocker_key] if "đăng nhập" not in item.lower()]
    if blockers:
        raise HTTPException(status_code=409, detail=" ".join(blockers))
    job.status = "queued"
    job.result_json = {}
    job.last_error = None
    job.lease_expires_at = None
    job.claimed_at = None
    job.started_at = None
    job.completed_at = None
    _audit(
        db,
        tenant_id=tenant_id,
        actor_user_id=user_id,
        actor_type="user",
        action="execution_job.retried",
        entity_id=job.id,
        payload={"attempt_count": job.attempt_count},
    )
    db.commit()
    db.refresh(job)
    return job


def poll_worker_job(db: Session, worker_id: str) -> ExecutionJob | None:
    now = utc_now()
    expired = list(
        db.scalars(
            select(ExecutionJob).where(
                ExecutionJob.worker_id == worker_id,
                ExecutionJob.status.in_({"claimed", "running"}),
                ExecutionJob.lease_expires_at < now,
            )
        )
    )
    for job in expired:
        job.status = "queued"
        job.last_error = "Worker lease expired; job returned to queue."
        job.lease_expires_at = None
    current = db.scalar(
        select(ExecutionJob)
        .where(
            ExecutionJob.worker_id == worker_id,
            ExecutionJob.status.in_({"claimed", "running"}),
        )
        .order_by(ExecutionJob.claimed_at)
        .limit(1)
    )
    if current is not None:
        db.commit()
        db.refresh(current)
        return current
    candidates = list(
        db.scalars(
            select(ExecutionJob)
            .where(
                ExecutionJob.worker_id == worker_id,
                ExecutionJob.status == "queued",
            )
            .order_by(ExecutionJob.requested_at)
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
        if busy is not None:
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
) -> ExecutionJob:
    job = db.scalar(
        select(ExecutionJob).where(
            ExecutionJob.id == job_id,
            ExecutionJob.worker_id == worker_id,
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Execution job not found for worker.")
    transitions = {
        "claimed": {"running", "failed", "awaiting_user"},
        "running": {"succeeded", "failed", "awaiting_user"},
    }
    if next_status != job.status and next_status not in transitions.get(job.status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Invalid execution transition: {job.status} -> {next_status}.",
        )
    now = utc_now()
    job.status = next_status
    job.result_json = result_json
    job.last_error = last_error
    if next_status == "running":
        job.started_at = job.started_at or now
        job.lease_expires_at = now + timedelta(minutes=LEASE_MINUTES)
    if next_status in {"succeeded", "failed", "awaiting_user"}:
        job.completed_at = now
        job.lease_expires_at = None
        _audit(
            db,
            tenant_id=job.tenant_id,
            actor_user_id=None,
            actor_type="worker",
            action=f"execution_job.{next_status}",
            entity_id=job.id,
            payload={"attempt_count": job.attempt_count, "readiness": result_json.get("readiness")},
        )
    db.commit()
    db.refresh(job)
    return job


def store_artifact(
    db: Session,
    *,
    worker_id: str,
    job_id: str,
    kind: str,
    content_type: str,
    content: bytes,
    artifact_root: str,
    max_bytes: int,
) -> ExecutionArtifact:
    if kind not in ARTIFACT_KINDS or content_type != "image/png":
        raise HTTPException(status_code=415, detail="Unsupported execution artifact kind or content type.")
    if not content or len(content) > max_bytes:
        raise HTTPException(status_code=413, detail="Execution artifact size is invalid.")
    job = db.scalar(
        select(ExecutionJob).where(
            ExecutionJob.id == job_id,
            ExecutionJob.worker_id == worker_id,
            ExecutionJob.status.in_({"claimed", "running"}),
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Active execution job not found for worker.")
    root = Path(artifact_root).resolve()
    target_dir = root / job.tenant_id / job.id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = (target_dir / f"{kind}.png").resolve()
    target.relative_to(root)
    temporary = target.with_name(f".{new_id()}.tmp")
    temporary.write_bytes(content)
    os.replace(temporary, target)
    digest = hashlib.sha256(content).hexdigest()
    artifact = db.scalar(
        select(ExecutionArtifact).where(
            ExecutionArtifact.execution_job_id == job.id,
            ExecutionArtifact.kind == kind,
        )
    )
    if artifact is None:
        artifact = ExecutionArtifact(
            tenant_id=job.tenant_id,
            execution_job_id=job.id,
            kind=kind,
            storage_path=str(target),
            content_type=content_type,
            byte_size=len(content),
            sha256=digest,
            metadata_json={"source": "worker_cdp"},
        )
        db.add(artifact)
    else:
        artifact.storage_path = str(target)
        artifact.content_type = content_type
        artifact.byte_size = len(content)
        artifact.sha256 = digest
        artifact.created_at = utc_now()
    db.commit()
    db.refresh(artifact)
    return artifact


def list_artifacts(db: Session, tenant_id: str, job_id: str) -> list[ExecutionArtifact]:
    get_job(db, tenant_id, job_id)
    return list(
        db.scalars(
            select(ExecutionArtifact)
            .where(
                ExecutionArtifact.tenant_id == tenant_id,
                ExecutionArtifact.execution_job_id == job_id,
            )
            .order_by(ExecutionArtifact.created_at.desc())
        )
    )


def get_artifact(db: Session, tenant_id: str, artifact_id: str) -> ExecutionArtifact:
    artifact = db.scalar(
        select(ExecutionArtifact).where(
            ExecutionArtifact.id == artifact_id,
            ExecutionArtifact.tenant_id == tenant_id,
        )
    )
    if artifact is None or not Path(artifact.storage_path).is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy execution artifact.")
    return artifact
