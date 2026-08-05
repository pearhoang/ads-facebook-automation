from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    AdAccount,
    AdAutomationRequest,
    ApprovalRequest,
    AuditEvent,
    CampaignDraft,
    CreativeAsset,
    ExecutionJob,
    FacebookAccount,
    MetaResource,
    ReportJob,
    ReportSchedule,
    utc_now,
)
from . import resources


APPROVER_ROLES = {"owner", "admin"}
ACTIVE_RUNTIME_STATUSES = {"queued", "claimed", "running", "planning", "awaiting_approval", "awaiting_user", "recovering"}


def _audit(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    actor_type: str = "user",
    action: str,
    entity_type: str,
    entity_id: str,
    payload: dict | None = None,
) -> None:
    db.add(
        AuditEvent(
            tenant_id=tenant_id,
            actor_user_id=user_id,
            actor_type=actor_type,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload_json=payload or {},
        )
    )


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _validate_schedule(start_at: datetime | None, end_at: datetime | None) -> None:
    if start_at and end_at and _normalize_datetime(end_at) <= _normalize_datetime(start_at):
        raise HTTPException(status_code=422, detail="Thời gian kết thúc phải sau thời gian bắt đầu.")


def get_ad_account(db: Session, tenant_id: str, ad_account_id: str) -> AdAccount:
    account = db.scalar(
        select(AdAccount).where(
            AdAccount.id == ad_account_id,
            AdAccount.tenant_id == tenant_id,
        )
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy ad account.")
    return account


def create_ad_account(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    facebook_account_id: str,
    meta_ad_account_id: str,
    label: str,
    currency: str,
    timezone_name: str,
) -> AdAccount:
    facebook_account = db.scalar(
        select(FacebookAccount).where(
            FacebookAccount.id == facebook_account_id,
            FacebookAccount.tenant_id == tenant_id,
        )
    )
    if facebook_account is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản Facebook trong workspace.")
    duplicate = db.scalar(
        select(AdAccount).where(
            AdAccount.tenant_id == tenant_id,
            AdAccount.meta_ad_account_id == meta_ad_account_id,
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Ad account này đã tồn tại trong workspace.")
    account = AdAccount(
        tenant_id=tenant_id,
        facebook_account_id=facebook_account_id,
        meta_ad_account_id=meta_ad_account_id,
        label=label,
        currency=currency,
        timezone_name=timezone_name,
        created_by_user_id=user_id,
    )
    db.add(account)
    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="ad_account.created",
        entity_type="ad_account",
        entity_id=account.id,
        payload={"meta_ad_account_id": meta_ad_account_id, "label": label},
    )
    db.commit()
    db.refresh(account)
    return account


def list_ad_accounts(db: Session, tenant_id: str) -> list[AdAccount]:
    return list(
        db.scalars(
            select(AdAccount)
            .where(
                AdAccount.tenant_id == tenant_id,
                AdAccount.status == "active",
            )
            .order_by(AdAccount.created_at.desc())
        )
    )


def remove_ad_account(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    ad_account_id: str,
) -> AdAccount:
    """Remove an account from active routing without deleting immutable history."""
    account = get_ad_account(db, tenant_id, ad_account_id)
    if account.status == "removed":
        return account

    active_execution = db.scalar(
        select(ExecutionJob.id)
        .where(
            ExecutionJob.ad_account_id == account.id,
            ExecutionJob.status.in_(ACTIVE_RUNTIME_STATUSES),
        )
        .limit(1)
    )
    active_report = db.scalar(
        select(ReportJob.id)
        .where(
            ReportJob.ad_account_id == account.id,
            ReportJob.status.in_(ACTIVE_RUNTIME_STATUSES),
        )
        .limit(1)
    )
    active_request = db.scalar(
        select(AdAutomationRequest.id)
        .where(
            AdAutomationRequest.ad_account_id == account.id,
            AdAutomationRequest.status.in_(ACTIVE_RUNTIME_STATUSES),
        )
        .limit(1)
    )
    if active_execution or active_report or active_request:
        raise HTTPException(
            status_code=409,
            detail="Ad account đang có công việc chạy. Hãy chờ hoàn tất hoặc dừng công việc trước khi gỡ.",
        )

    disabled_schedules = list(
        db.scalars(
            select(ReportSchedule).where(
                ReportSchedule.ad_account_id == account.id,
                ReportSchedule.status == "enabled",
            )
        )
    )
    for schedule in disabled_schedules:
        schedule.status = "disabled"
    account.status = "removed"
    _audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="ad_account.removed",
        entity_type="ad_account",
        entity_id=account.id,
        payload={
            "label": account.label,
            "meta_ad_account_id": account.meta_ad_account_id,
            "disabled_schedule_count": len(disabled_schedules),
        },
    )
    db.commit()
    db.refresh(account)
    return account


def update_ad_account(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    ad_account_id: str,
    changes: dict,
) -> AdAccount:
    account = get_ad_account(db, tenant_id, ad_account_id)
    if "facebook_account_id" in changes:
        facebook_account = db.scalar(
            select(FacebookAccount).where(
                FacebookAccount.id == changes["facebook_account_id"],
                FacebookAccount.tenant_id == tenant_id,
            )
        )
        if facebook_account is None:
            raise HTTPException(
                status_code=404,
                detail="Không tìm thấy tài khoản Facebook trong workspace.",
            )
    if "meta_ad_account_id" in changes and changes["meta_ad_account_id"] != account.meta_ad_account_id:
        duplicate = db.scalar(
            select(AdAccount).where(
                AdAccount.tenant_id == tenant_id,
                AdAccount.meta_ad_account_id == changes["meta_ad_account_id"],
                AdAccount.id != account.id,
            )
        )
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="Ad account này đã tồn tại trong workspace.")

    protected_fields = {"facebook_account_id", "meta_ad_account_id", "currency", "timezone_name"}
    structural_changes = {
        field for field in protected_fields
        if field in changes and changes[field] != getattr(account, field)
    }
    if structural_changes:
        has_dependencies = any(
            db.scalar(select(model.id).where(model.ad_account_id == account.id).limit(1)) is not None
            for model in (CampaignDraft, MetaResource, CreativeAsset)
        )
        if has_dependencies:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Ad account đã có campaign/resource/asset. Chỉ có thể đổi tên gợi nhớ; "
                    "không thể đổi liên kết Facebook, mã account, tiền tệ hoặc múi giờ."
                ),
            )

    changed_values: dict[str, dict[str, str]] = {}
    for field, value in changes.items():
        old_value = getattr(account, field)
        if value == old_value:
            continue
        changed_values[field] = {"from": old_value, "to": value}
        setattr(account, field, value)
    if not changed_values:
        return account

    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="ad_account.updated",
        entity_type="ad_account",
        entity_id=account.id,
        payload={"label": account.label, "changes": changed_values},
    )
    db.commit()
    db.refresh(account)
    return account


def get_campaign(db: Session, tenant_id: str, campaign_id: str) -> CampaignDraft:
    campaign = db.scalar(
        select(CampaignDraft).where(
            CampaignDraft.id == campaign_id,
            CampaignDraft.tenant_id == tenant_id,
        )
    )
    if campaign is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy campaign draft.")
    return campaign


def create_campaign(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    ad_account_id: str,
    name: str,
    objective: str,
    daily_budget_minor: int,
    start_at: datetime | None,
    end_at: datetime | None,
    targeting_json: dict,
    creative_json: dict,
    actor_type: str = "user",
) -> CampaignDraft:
    ad_account = get_ad_account(db, tenant_id, ad_account_id)
    if ad_account.status != "active":
        raise HTTPException(status_code=409, detail="Ad account đã được gỡ khỏi định tuyến.")
    _validate_schedule(start_at, end_at)
    targeting_json, creative_json = resources.resolve_campaign_inputs(
        db,
        tenant_id=tenant_id,
        ad_account_id=ad_account.id,
        targeting_json=targeting_json,
        creative_json=creative_json,
    )
    campaign = CampaignDraft(
        tenant_id=tenant_id,
        ad_account_id=ad_account.id,
        name=name,
        objective=objective,
        daily_budget_minor=daily_budget_minor,
        currency=ad_account.currency,
        start_at=start_at,
        end_at=end_at,
        targeting_json=targeting_json,
        creative_json=creative_json,
        status="draft",
        created_by_user_id=user_id,
        updated_by_user_id=user_id,
    )
    db.add(campaign)
    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        actor_type=actor_type,
        action="campaign_draft.created",
        entity_type="campaign_draft",
        entity_id=campaign.id,
        payload={"name": name, "daily_budget_minor": daily_budget_minor, "currency": ad_account.currency},
    )
    db.commit()
    db.refresh(campaign)
    return campaign


def list_campaigns(db: Session, tenant_id: str) -> list[CampaignDraft]:
    return list(
        db.scalars(
            select(CampaignDraft)
            .where(CampaignDraft.tenant_id == tenant_id)
            .order_by(CampaignDraft.created_at.desc())
        )
    )


def update_campaign(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    campaign_id: str,
    changes: dict,
) -> CampaignDraft:
    campaign = get_campaign(db, tenant_id, campaign_id)
    if campaign.status not in {"draft", "rejected"}:
        raise HTTPException(status_code=409, detail="Chỉ có thể sửa campaign ở trạng thái draft hoặc rejected.")
    start_at = changes.get("start_at", campaign.start_at)
    end_at = changes.get("end_at", campaign.end_at)
    _validate_schedule(start_at, end_at)
    if "targeting_json" in changes or "creative_json" in changes:
        targeting_json, creative_json = resources.resolve_campaign_inputs(
            db,
            tenant_id=tenant_id,
            ad_account_id=campaign.ad_account_id,
            targeting_json=changes.get("targeting_json", campaign.targeting_json),
            creative_json=changes.get("creative_json", campaign.creative_json),
        )
        changes["targeting_json"] = targeting_json
        changes["creative_json"] = creative_json
    for key, value in changes.items():
        setattr(campaign, key, value)
    campaign.status = "draft"
    campaign.version += 1
    campaign.updated_by_user_id = user_id
    campaign.submitted_at = None
    campaign.approved_at = None
    _audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action="campaign_draft.updated",
        entity_type="campaign_draft",
        entity_id=campaign.id,
        payload={"changed_fields": sorted(changes), "version": campaign.version},
    )
    db.commit()
    db.refresh(campaign)
    return campaign


def _snapshot(campaign: CampaignDraft) -> dict:
    return {
        "campaign_id": campaign.id,
        "version": campaign.version,
        "ad_account_id": campaign.ad_account_id,
        "name": campaign.name,
        "objective": campaign.objective,
        "daily_budget_minor": campaign.daily_budget_minor,
        "currency": campaign.currency,
        "start_at": campaign.start_at.isoformat() if campaign.start_at else None,
        "end_at": campaign.end_at.isoformat() if campaign.end_at else None,
        "targeting_json": campaign.targeting_json,
        "creative_json": campaign.creative_json,
    }


def submit_campaign(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    campaign_id: str,
    actor_type: str = "user",
) -> ApprovalRequest:
    campaign = get_campaign(db, tenant_id, campaign_id)
    if campaign.status != "draft":
        raise HTTPException(status_code=409, detail="Chỉ campaign draft mới có thể gửi duyệt.")
    approval = ApprovalRequest(
        tenant_id=tenant_id,
        campaign_draft_id=campaign.id,
        status="pending",
        requested_by_user_id=user_id,
        snapshot_json=_snapshot(campaign),
    )
    campaign.status = "pending_approval"
    campaign.submitted_at = utc_now()
    campaign.updated_by_user_id = user_id
    db.add(approval)
    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        actor_type=actor_type,
        action="campaign_draft.submitted",
        entity_type="campaign_draft",
        entity_id=campaign.id,
        payload={"approval_request_id": approval.id, "version": campaign.version},
    )
    db.commit()
    db.refresh(approval)
    return approval


def list_approvals(db: Session, tenant_id: str, status_filter: str | None = None) -> list[ApprovalRequest]:
    query = select(ApprovalRequest).where(ApprovalRequest.tenant_id == tenant_id)
    if status_filter:
        query = query.where(ApprovalRequest.status == status_filter)
    return list(db.scalars(query.order_by(ApprovalRequest.requested_at.desc())))


def _get_pending_approval(db: Session, tenant_id: str, approval_id: str) -> ApprovalRequest:
    approval = db.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.tenant_id == tenant_id,
        )
    )
    if approval is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy yêu cầu duyệt.")
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail="Yêu cầu duyệt này đã được xử lý.")
    return approval


def decide_approval(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    role: str,
    approval_id: str,
    decision: str,
    note: str | None,
    actor_type: str = "user",
) -> ApprovalRequest:
    if role not in APPROVER_ROLES:
        raise HTTPException(status_code=403, detail="Bạn không có quyền duyệt campaign.")
    if decision not in {"approved", "rejected"}:
        raise ValueError("Unsupported approval decision.")
    approval = _get_pending_approval(db, tenant_id, approval_id)
    campaign = get_campaign(db, tenant_id, approval.campaign_draft_id)
    if campaign.status != "pending_approval":
        raise HTTPException(status_code=409, detail="Campaign không còn ở trạng thái chờ duyệt.")
    if decision == "rejected" and not (note or "").strip():
        raise HTTPException(status_code=422, detail="Hãy nhập lý do từ chối.")
    now = utc_now()
    approval.status = decision
    approval.decided_by_user_id = user_id
    approval.decision_note = (note or "").strip() or None
    approval.decided_at = now
    campaign.status = decision
    campaign.updated_by_user_id = user_id
    campaign.approved_at = now if decision == "approved" else None
    _audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        actor_type=actor_type,
        action=f"campaign_draft.{decision}",
        entity_type="campaign_draft",
        entity_id=campaign.id,
        payload={"approval_request_id": approval.id, "note": approval.decision_note},
    )
    db.commit()
    db.refresh(approval)
    return approval


def list_audit_events(db: Session, tenant_id: str, limit: int = 50) -> list[AuditEvent]:
    return list(
        db.scalars(
            select(AuditEvent)
            .where(AuditEvent.tenant_id == tenant_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
        )
    )
