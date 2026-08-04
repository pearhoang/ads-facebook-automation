from __future__ import annotations

import hashlib
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    AIProviderConfig,
    AdAccount,
    AdAutomationEvent,
    AdAutomationRequest,
    AgentWorkflowLearning,
    ApprovalRequest,
    CampaignDraft,
    ExecutionArtifact,
    ExecutionJob,
    FacebookAccount,
    MetaResource,
    TenantMembership,
    Worker,
    utc_now,
)
from . import campaigns, execution_jobs


TERMINAL_REQUEST_STATES = {"completed", "failed", "cancelled"}


def _event(
    db: Session,
    request: AdAutomationRequest,
    *,
    event_type: str,
    stage: str,
    message: str,
    actor_type: str,
    payload: dict | None = None,
) -> None:
    db.add(
        AdAutomationEvent(
            tenant_id=request.tenant_id,
            request_id=request.id,
            actor_type=actor_type,
            event_type=event_type,
            stage=stage,
            message=message,
            payload_json=payload or {},
        )
    )


def _worker_context(
    db: Session, worker_id: str
) -> tuple[AIProviderConfig, str, str]:
    config = db.scalar(
        select(AIProviderConfig)
        .where(
            AIProviderConfig.worker_id == worker_id,
            AIProviderConfig.execution_scope == "worker",
            AIProviderConfig.status == "configured",
        )
        .order_by(AIProviderConfig.updated_at.desc())
    )
    if config is None:
        raise HTTPException(status_code=409, detail="Worker chưa có Hermes provider được cấu hình.")
    membership = db.get(
        TenantMembership,
        {"user_id": config.updated_by_user_id, "tenant_id": config.tenant_id},
    )
    if membership is None or membership.role not in {"owner", "admin"}:
        raise HTTPException(
            status_code=409,
            detail="Tài khoản cấu hình Hermes phải có quyền owner hoặc admin.",
        )
    return config, config.updated_by_user_id, membership.role


def _owned_account(
    db: Session, *, worker_id: str, tenant_id: str, ad_account_id: str
) -> tuple[AdAccount, FacebookAccount, Worker]:
    row = db.execute(
        select(AdAccount, FacebookAccount, Worker)
        .join(FacebookAccount, FacebookAccount.id == AdAccount.facebook_account_id)
        .join(Worker, Worker.id == FacebookAccount.assigned_worker_id)
        .where(
            AdAccount.id == ad_account_id,
            AdAccount.tenant_id == tenant_id,
            FacebookAccount.assigned_worker_id == worker_id,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Ad account không thuộc Bot VPS này.")
    return row


def resource_context(db: Session, worker_id: str) -> dict:
    config, _user_id, _role = _worker_context(db, worker_id)
    rows = list(
        db.execute(
            select(AdAccount, FacebookAccount, Worker)
            .join(FacebookAccount, FacebookAccount.id == AdAccount.facebook_account_id)
            .join(Worker, Worker.id == FacebookAccount.assigned_worker_id)
            .where(
                AdAccount.tenant_id == config.tenant_id,
                FacebookAccount.assigned_worker_id == worker_id,
            )
            .order_by(AdAccount.label)
        )
    )
    account_ids = [row.AdAccount.id for row in rows]
    resources = (
        list(
            db.scalars(
                select(MetaResource)
                .where(MetaResource.ad_account_id.in_(account_ids))
                .order_by(MetaResource.kind, MetaResource.label)
            )
        )
        if account_ids
        else []
    )
    resources_by_account: dict[str, list[dict]] = {}
    for item in resources:
        resources_by_account.setdefault(item.ad_account_id, []).append(
            {
                "id": item.id,
                "kind": item.kind,
                "label": item.label,
                "external_id": item.external_id,
                "status": item.status,
                "metadata": item.metadata_json,
            }
        )
    return {
        "worker_id": worker_id,
        "safety": {
            "agent_can_plan_recover_and_use_worker_tools": True,
            "publish_requires_explicit_confirmation": True,
            "novnc_role": "login_2fa_challenge_handoff_only",
        },
        "ad_accounts": [
            {
                "id": row.AdAccount.id,
                "label": row.AdAccount.label,
                "meta_ad_account_id": row.AdAccount.meta_ad_account_id,
                "currency": row.AdAccount.currency,
                "timezone_name": row.AdAccount.timezone_name,
                "status": row.AdAccount.status,
                "facebook_account": {
                    "id": row.FacebookAccount.id,
                    "label": row.FacebookAccount.label,
                    "status": row.FacebookAccount.status,
                    "profile_key": row.FacebookAccount.profile_key,
                },
                "resources": resources_by_account.get(row.AdAccount.id, []),
            }
            for row in rows
        ],
    }


def prepare_campaign_request(
    db: Session,
    worker_id: str,
    *,
    ad_account_id: str,
    request_text: str,
    title: str,
    name: str,
    objective: str,
    daily_budget_minor: int,
    start_at: datetime | None,
    end_at: datetime | None,
    targeting_json: dict,
    creative_json: dict,
    source: str = "telegram",
    source_session_id: str | None = None,
    source_message_id: str | None = None,
) -> dict:
    config, user_id, _role = _worker_context(db, worker_id)
    ad_account, facebook_account, worker = _owned_account(
        db,
        worker_id=worker_id,
        tenant_id=config.tenant_id,
        ad_account_id=ad_account_id,
    )
    campaign = campaigns.create_campaign(
        db,
        tenant_id=config.tenant_id,
        user_id=user_id,
        actor_type="agent",
        ad_account_id=ad_account.id,
        name=name,
        objective=objective,
        daily_budget_minor=daily_budget_minor,
        start_at=start_at,
        end_at=end_at,
        targeting_json=targeting_json,
        creative_json=creative_json,
    )
    approval = campaigns.submit_campaign(
        db,
        tenant_id=config.tenant_id,
        user_id=user_id,
        campaign_id=campaign.id,
        actor_type="agent",
    )
    work = AdAutomationRequest(
        tenant_id=config.tenant_id,
        worker_id=worker.id,
        facebook_account_id=facebook_account.id,
        ad_account_id=ad_account.id,
        campaign_draft_id=campaign.id,
        approval_request_id=approval.id,
        source=source,
        source_session_id=source_session_id,
        source_message_id=source_message_id,
        intent="create_campaign",
        request_text=request_text.strip(),
        title=title.strip()[:240] or name,
        status="awaiting_approval",
        stage="approval",
        progress_message="Đã lập kế hoạch; đang chờ bạn xác nhận trong cuộc trò chuyện.",
        plan_json=approval.snapshot_json,
        resolution_json={
            "worker": {"id": worker.id, "name": worker.display_name},
            "facebook_account": {
                "id": facebook_account.id,
                "label": facebook_account.label,
                "profile_key": facebook_account.profile_key,
            },
            "ad_account": {
                "id": ad_account.id,
                "label": ad_account.label,
                "meta_ad_account_id": ad_account.meta_ad_account_id,
            },
        },
        recovery_json={"max_automatic_retries": 1, "learnings": []},
        requested_by_user_id=user_id,
    )
    db.add(work)
    db.flush()
    _event(
        db,
        work,
        event_type="request.prepared",
        stage="approval",
        message="Hermes đã phân giải account/resource và tạo action preview.",
        actor_type="agent",
        payload={"campaign_draft_id": campaign.id, "approval_request_id": approval.id},
    )
    db.commit()
    db.refresh(work)
    return request_payload(db, work)


def confirm_campaign_request(
    db: Session,
    worker_id: str,
    *,
    request_id: str,
    decision: str,
    note: str | None,
) -> dict:
    config, user_id, role = _worker_context(db, worker_id)
    work = get_request(db, config.tenant_id, request_id, worker_id=worker_id)
    if work.status != "awaiting_approval" or not work.approval_request_id:
        raise HTTPException(status_code=409, detail="Yêu cầu không còn chờ xác nhận.")
    if decision == "cancel":
        campaigns.decide_approval(
            db,
            tenant_id=config.tenant_id,
            user_id=user_id,
            role=role,
            approval_id=work.approval_request_id,
            decision="rejected",
            note=(note or "Người dùng hủy trong cuộc trò chuyện."),
            actor_type="agent",
        )
        work.status = "cancelled"
        work.stage = "cancelled"
        work.progress_message = "Đã hủy theo yêu cầu. Không thao tác trên Meta."
        work.completed_at = utc_now()
        _event(
            db,
            work,
            event_type="request.cancelled",
            stage="cancelled",
            message=work.progress_message,
            actor_type="agent",
        )
        db.commit()
        return request_payload(db, work)
    if decision != "execute_draft":
        raise HTTPException(status_code=422, detail="Decision phải là execute_draft hoặc cancel.")
    campaigns.decide_approval(
        db,
        tenant_id=config.tenant_id,
        user_id=user_id,
        role=role,
        approval_id=work.approval_request_id,
        decision="approved",
        note=note or "Người dùng xác nhận bằng ngôn ngữ tự nhiên trên Hermes/Telegram.",
        actor_type="agent",
    )
    job = execution_jobs.create_preflight_job(
        db,
        tenant_id=config.tenant_id,
        user_id=user_id,
        role=role,
        campaign_id=str(work.campaign_draft_id),
        confirmation=execution_jobs.CONFIRMATION_TEXT,
        actor_type="agent",
    )
    job_payload = dict(job.payload_json or {})
    job_payload["automation_request"] = {
        "id": work.id,
        "title": work.title,
        "source": work.source,
    }
    job.payload_json = job_payload
    work.execution_job_id = job.id
    work.status = "queued"
    work.stage = "preflight"
    work.progress_message = "Đã xác nhận; worker đang chờ chạy preflight trên đúng Chrome profile."
    _event(
        db,
        work,
        event_type="request.approved",
        stage="preflight",
        message=work.progress_message,
        actor_type="agent",
        payload={"execution_job_id": job.id},
    )
    db.commit()
    return request_payload(db, work)


def get_request(
    db: Session,
    tenant_id: str,
    request_id: str,
    *,
    worker_id: str | None = None,
) -> AdAutomationRequest:
    clauses = [
        AdAutomationRequest.id == request_id,
        AdAutomationRequest.tenant_id == tenant_id,
    ]
    if worker_id:
        clauses.append(AdAutomationRequest.worker_id == worker_id)
    work = db.scalar(select(AdAutomationRequest).where(*clauses))
    if work is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy công việc quảng cáo.")
    return work


def list_requests(
    db: Session,
    tenant_id: str,
    *,
    status: str | None = None,
    limit: int = 100,
) -> list[AdAutomationRequest]:
    query = select(AdAutomationRequest).where(AdAutomationRequest.tenant_id == tenant_id)
    if status:
        query = query.where(AdAutomationRequest.status == status)
    return list(db.scalars(query.order_by(AdAutomationRequest.updated_at.desc()).limit(limit)))


def list_events(db: Session, tenant_id: str, request_id: str) -> list[AdAutomationEvent]:
    get_request(db, tenant_id, request_id)
    return list(
        db.scalars(
            select(AdAutomationEvent)
            .where(
                AdAutomationEvent.tenant_id == tenant_id,
                AdAutomationEvent.request_id == request_id,
            )
            .order_by(AdAutomationEvent.created_at)
        )
    )


def request_payload(db: Session, work: AdAutomationRequest) -> dict:
    events = list_events(db, work.tenant_id, work.id)
    artifacts: list[ExecutionArtifact] = []
    if work.campaign_draft_id:
        job_ids = list(
            db.scalars(
                select(ExecutionJob.id).where(
                    ExecutionJob.tenant_id == work.tenant_id,
                    ExecutionJob.campaign_draft_id == work.campaign_draft_id,
                )
            )
        )
        artifacts = list(
            db.scalars(
                select(ExecutionArtifact)
                .where(ExecutionArtifact.execution_job_id.in_(job_ids))
                .order_by(ExecutionArtifact.created_at.desc())
            )
        ) if job_ids else []
    return {
        "id": work.id,
        "tenant_id": work.tenant_id,
        "worker_id": work.worker_id,
        "facebook_account_id": work.facebook_account_id,
        "ad_account_id": work.ad_account_id,
        "campaign_draft_id": work.campaign_draft_id,
        "approval_request_id": work.approval_request_id,
        "execution_job_id": work.execution_job_id,
        "source": work.source,
        "source_session_id": work.source_session_id,
        "source_message_id": work.source_message_id,
        "intent": work.intent,
        "request_text": work.request_text,
        "title": work.title,
        "status": work.status,
        "stage": work.stage,
        "progress_message": work.progress_message,
        "plan_json": work.plan_json,
        "resolution_json": work.resolution_json,
        "recovery_json": work.recovery_json,
        "last_error": work.last_error,
        "attempt_count": work.attempt_count,
        "recovery_count": work.recovery_count,
        "requested_at": work.requested_at,
        "completed_at": work.completed_at,
        "updated_at": work.updated_at,
        "events": [
            {
                "id": item.id,
                "actor_type": item.actor_type,
                "event_type": item.event_type,
                "stage": item.stage,
                "message": item.message,
                "payload_json": item.payload_json,
                "created_at": item.created_at,
            }
            for item in events
        ],
        "artifacts": [
            {
                "id": item.id,
                "kind": item.kind,
                "content_type": item.content_type,
                "byte_size": item.byte_size,
                "created_at": item.created_at,
            }
            for item in artifacts
        ],
        "published": False,
    }


def on_execution_synced(db: Session, job: ExecutionJob) -> None:
    work = db.scalar(
        select(AdAutomationRequest).where(
            AdAutomationRequest.campaign_draft_id == job.campaign_draft_id,
            AdAutomationRequest.tenant_id == job.tenant_id,
        )
    )
    if work is None or work.status in TERMINAL_REQUEST_STATES:
        return
    work.execution_job_id = job.id
    work.attempt_count = job.attempt_count
    work.last_error = job.last_error
    if job.status == "running":
        work.status = "running"
        work.stage = job.job_type
        work.progress_message = (
            "Worker đang kiểm tra profile và quyền Ads Manager."
            if job.job_type == "preflight"
            else "Worker đang điền Campaign → Ad Set → Ad và lưu checkpoint."
        )
        _event(
            db,
            work,
            event_type="execution.running",
            stage=work.stage,
            message=work.progress_message,
            actor_type="worker",
            payload={"execution_job_id": job.id, "attempt": job.attempt_count},
        )
        db.commit()
        return
    if job.status == "succeeded" and job.job_type == "preflight":
        config, user_id, role = _worker_context(db, job.worker_id)
        work.status = "queued"
        work.stage = "draft_build"
        work.progress_message = "Preflight đạt; hệ thống tự chuyển sang dựng Meta draft."
        _event(
            db,
            work,
            event_type="preflight.succeeded",
            stage="draft_build",
            message=work.progress_message,
            actor_type="worker",
            payload={"preflight_job_id": job.id},
        )
        db.commit()
        try:
            draft_job = execution_jobs.create_draft_build_job(
                db,
                tenant_id=config.tenant_id,
                user_id=user_id,
                role=role,
                campaign_id=job.campaign_draft_id,
                confirmation=execution_jobs.BUILD_DRAFT_CONFIRMATION_TEXT,
                actor_type="agent",
            )
        except HTTPException as exc:
            work = get_request(db, config.tenant_id, work.id, worker_id=job.worker_id)
            work.status = "awaiting_user"
            work.stage = "handoff"
            work.last_error = str(exc.detail)
            work.progress_message = "Preflight đạt nhưng kế hoạch còn thiếu resource hoặc field cần xác nhận."
            _event(
                db,
                work,
                event_type="draft_build.blocked",
                stage="handoff",
                message=work.progress_message,
                actor_type="control_plane",
                payload={"blocker": str(exc.detail)},
            )
            db.commit()
            return
        draft_payload = dict(draft_job.payload_json or {})
        draft_payload["automation_request"] = {
            "id": work.id,
            "title": work.title,
            "source": work.source,
        }
        draft_job.payload_json = draft_payload
        work = get_request(db, config.tenant_id, work.id, worker_id=job.worker_id)
        work.execution_job_id = draft_job.id
        _event(
            db,
            work,
            event_type="draft_build.queued",
            stage="draft_build",
            message="Đã xếp hàng Meta draft builder; publish vẫn bị khóa.",
            actor_type="agent",
            payload={"execution_job_id": draft_job.id},
        )
        db.commit()
        return
    if job.status == "succeeded" and job.job_type == "draft_build":
        work.status = "completed"
        work.stage = "review"
        work.progress_message = "Đã điền xong Campaign → Ad Set → Ad và dừng tại Review. Chưa publish."
        work.completed_at = utc_now()
        work.last_error = None
        _event(
            db,
            work,
            event_type="request.completed",
            stage="review",
            message=work.progress_message,
            actor_type="worker",
            payload={"execution_job_id": job.id, "published": False},
        )
        if work.recovery_count:
            attempts = list((work.recovery_json or {}).get("attempts") or [])
            last_attempt = attempts[-1] if attempts else {}
            symptom = str(last_attempt.get("error") or "Worker/browser transient failure")
            learning_key = "checkpoint-retry-" + hashlib.sha256(
                symptom.lower().encode("utf-8")
            ).hexdigest()[:16]
            learning = db.scalar(
                select(AgentWorkflowLearning).where(
                    AgentWorkflowLearning.tenant_id == work.tenant_id,
                    AgentWorkflowLearning.worker_id == work.worker_id,
                    AgentWorkflowLearning.learning_key == learning_key,
                )
            )
            if learning is None:
                learning = AgentWorkflowLearning(
                    tenant_id=work.tenant_id,
                    worker_id=work.worker_id,
                    learning_key=learning_key,
                    symptom=symptom,
                    cause="Lỗi tạm thời đã được giải quyết bằng resume/retry từ checkpoint.",
                    recovery_plan_json={
                        "strategy": "retry_from_checkpoint",
                        "max_automatic_retries": 1,
                        "do_not_publish": True,
                    },
                    status="verified",
                    success_count=1,
                    last_used_at=utc_now(),
                )
                db.add(learning)
            else:
                learning.status = "verified"
                learning.success_count += 1
                learning.last_used_at = utc_now()
            _event(
                db,
                work,
                event_type="workflow_learning.verified",
                stage="review",
                message="Đã lưu recovery thành workflow learning sau khi kiểm chứng thành công.",
                actor_type="control_plane",
                payload={"learning_key": learning_key},
            )
        db.commit()
        return
    if job.status == "failed" and work.recovery_count < 1:
        work.recovery_count += 1
        work.status = "recovering"
        work.stage = "recovery"
        work.progress_message = "Đã gặp lỗi; worker đang tự thử lại một lần từ checkpoint an toàn."
        recovery = dict(work.recovery_json or {})
        recovery.setdefault("attempts", []).append(
            {"at": utc_now().isoformat(), "job_id": job.id, "error": job.last_error}
        )
        work.recovery_json = recovery
        _event(
            db,
            work,
            event_type="recovery.auto_retry",
            stage="recovery",
            message=work.progress_message,
            actor_type="worker",
            payload={"error": job.last_error},
        )
        job.status = "queued"
        job.result_json = {}
        job.last_error = None
        job.lease_expires_at = None
        job.claimed_at = None
        job.started_at = None
        job.completed_at = None
        db.commit()
        return
    if job.status in {"failed", "awaiting_user"}:
        work.status = "awaiting_user" if job.status == "awaiting_user" else "failed"
        work.stage = "handoff" if job.status == "awaiting_user" else "recovery"
        work.progress_message = (
            "Meta yêu cầu đăng nhập, 2FA/challenge hoặc thông tin chưa thể tự xác định."
            if job.status == "awaiting_user"
            else "Tự phục hồi chưa giải quyết được lỗi; Hermes có thể đọc artifact và lập phương án mới."
        )
        if job.status == "failed":
            work.completed_at = utc_now()
        _event(
            db,
            work,
            event_type=f"execution.{job.status}",
            stage=work.stage,
            message=work.progress_message,
            actor_type="worker",
            payload={"error": job.last_error, "execution_job_id": job.id},
        )
        db.commit()


def list_learnings(db: Session, worker_id: str, *, include_proposed: bool = True) -> dict:
    config, _user_id, _role = _worker_context(db, worker_id)
    query = select(AgentWorkflowLearning).where(
        AgentWorkflowLearning.tenant_id == config.tenant_id,
        AgentWorkflowLearning.worker_id == worker_id,
    )
    if not include_proposed:
        query = query.where(AgentWorkflowLearning.status == "verified")
    items = list(db.scalars(query.order_by(AgentWorkflowLearning.updated_at.desc()).limit(100)))
    return {
        "items": [
            {
                "id": item.id,
                "learning_key": item.learning_key,
                "symptom": item.symptom,
                "cause": item.cause,
                "recovery_plan": item.recovery_plan_json,
                "status": item.status,
                "success_count": item.success_count,
                "failure_count": item.failure_count,
            }
            for item in items
        ]
    }


def record_learning(
    db: Session,
    worker_id: str,
    *,
    learning_key: str,
    symptom: str,
    cause: str | None,
    recovery_plan_json: dict,
) -> dict:
    config, _user_id, _role = _worker_context(db, worker_id)
    item = db.scalar(
        select(AgentWorkflowLearning).where(
            AgentWorkflowLearning.tenant_id == config.tenant_id,
            AgentWorkflowLearning.worker_id == worker_id,
            AgentWorkflowLearning.learning_key == learning_key,
        )
    )
    if item is None:
        item = AgentWorkflowLearning(
            tenant_id=config.tenant_id,
            worker_id=worker_id,
            learning_key=learning_key.strip(),
            symptom=symptom.strip(),
            cause=(cause or "").strip() or None,
            recovery_plan_json=recovery_plan_json,
            status="proposed",
        )
        db.add(item)
    else:
        item.symptom = symptom.strip()
        item.cause = (cause or "").strip() or None
        item.recovery_plan_json = recovery_plan_json
        item.status = "proposed"
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "learning_key": item.learning_key,
        "status": item.status,
        "next_step": "Learning chỉ là proposal; chỉ được coi là verified sau một lần chạy thành công có kiểm chứng.",
    }
