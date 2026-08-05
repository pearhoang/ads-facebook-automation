from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    AIProviderConfig,
    AdAccount,
    CampaignDraft,
    FacebookAccount,
    ReportSnapshot,
    Tenant,
)
from . import campaigns, reporting


def _context(db: Session, worker_id: str) -> tuple[AIProviderConfig, Tenant]:
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
    tenant = db.get(Tenant, config.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=409, detail="Workspace của Hermes không còn tồn tại.")
    return config, tenant


def _owned_accounts(db: Session, worker_id: str, tenant_id: str) -> list[AdAccount]:
    return list(
        db.scalars(
            select(AdAccount)
            .join(FacebookAccount, FacebookAccount.id == AdAccount.facebook_account_id)
            .where(
                AdAccount.tenant_id == tenant_id,
                AdAccount.status == "active",
                FacebookAccount.assigned_worker_id == worker_id,
                FacebookAccount.status != "removed",
            )
            .order_by(AdAccount.created_at.desc())
        )
    )


def _owned_account(db: Session, worker_id: str, tenant_id: str, ad_account_id: str) -> AdAccount:
    account = next(
        (item for item in _owned_accounts(db, worker_id, tenant_id) if item.id == ad_account_id),
        None,
    )
    if account is None:
        raise HTTPException(status_code=404, detail="Ad account không thuộc Bot VPS này.")
    return account


def workspace_context(db: Session, worker_id: str) -> dict:
    config, tenant = _context(db, worker_id)
    accounts = _owned_accounts(db, worker_id, tenant.id)
    return {
        "workspace": {"id": tenant.id, "name": tenant.name},
        "worker_id": worker_id,
        "configured_by_user_id": config.updated_by_user_id,
        "safety": {
            "campaign_mutation": "control_plane_draft_only",
            "approval_required": True,
            "publish_allowed": False,
        },
        "ad_accounts": [
            {
                "id": item.id,
                "label": item.label,
                "meta_ad_account_id": item.meta_ad_account_id,
                "currency": item.currency,
                "timezone_name": item.timezone_name,
                "status": item.status,
            }
            for item in accounts
        ],
    }


def latest_kpi(db: Session, worker_id: str, ad_account_id: str | None) -> dict:
    config, _tenant = _context(db, worker_id)
    accounts = _owned_accounts(db, worker_id, config.tenant_id)
    if ad_account_id:
        accounts = [_owned_account(db, worker_id, config.tenant_id, ad_account_id)]
    results: list[dict] = []
    for account in accounts:
        snapshot = db.scalar(
            select(ReportSnapshot)
            .where(
                ReportSnapshot.tenant_id == config.tenant_id,
                ReportSnapshot.ad_account_id == account.id,
            )
            .order_by(ReportSnapshot.collected_at.desc())
        )
        results.append(
            {
                "ad_account": {
                    "id": account.id,
                    "label": account.label,
                    "currency": account.currency,
                },
                "snapshot": None
                if snapshot is None
                else {
                    "id": snapshot.id,
                    "range_start": snapshot.range_start.isoformat(),
                    "range_end": snapshot.range_end.isoformat(),
                    "totals": snapshot.totals_json,
                    "campaigns": snapshot.campaigns_json,
                    "collected_at": snapshot.collected_at.isoformat(),
                },
            }
        )
    return {"items": results}


def list_campaign_drafts(
    db: Session,
    worker_id: str,
    *,
    ad_account_id: str | None,
    status: str | None,
    limit: int,
) -> dict:
    config, _tenant = _context(db, worker_id)
    account_ids = {item.id for item in _owned_accounts(db, worker_id, config.tenant_id)}
    if ad_account_id:
        _owned_account(db, worker_id, config.tenant_id, ad_account_id)
        account_ids = {ad_account_id}
    if not account_ids:
        return {"items": []}
    query = select(CampaignDraft).where(
        CampaignDraft.tenant_id == config.tenant_id,
        CampaignDraft.ad_account_id.in_(account_ids),
    )
    if status:
        query = query.where(CampaignDraft.status == status)
    items = list(db.scalars(query.order_by(CampaignDraft.updated_at.desc()).limit(limit)))
    return {
        "items": [
            {
                "id": item.id,
                "ad_account_id": item.ad_account_id,
                "name": item.name,
                "objective": item.objective,
                "daily_budget_minor": item.daily_budget_minor,
                "currency": item.currency,
                "status": item.status,
                "version": item.version,
                "updated_at": item.updated_at.isoformat(),
            }
            for item in items
        ]
    }


def create_campaign_draft(db: Session, worker_id: str, payload: dict) -> dict:
    config, _tenant = _context(db, worker_id)
    _owned_account(db, worker_id, config.tenant_id, str(payload["ad_account_id"]))
    campaign = campaigns.create_campaign(
        db,
        tenant_id=config.tenant_id,
        user_id=config.updated_by_user_id,
        actor_type="agent",
        **payload,
    )
    return {
        "id": campaign.id,
        "name": campaign.name,
        "status": campaign.status,
        "version": campaign.version,
        "daily_budget_minor": campaign.daily_budget_minor,
        "currency": campaign.currency,
        "next_step": "Mở control-plane để kiểm tra và gửi duyệt nội bộ.",
        "published": False,
    }


def request_kpi_collection(
    db: Session,
    worker_id: str,
    *,
    ad_account_id: str,
    lookback_days: int,
) -> dict:
    config, _tenant = _context(db, worker_id)
    _owned_account(db, worker_id, config.tenant_id, ad_account_id)
    job = reporting.create_manual_job(
        db,
        tenant_id=config.tenant_id,
        user_id=config.updated_by_user_id,
        ad_account_id=ad_account_id,
        lookback_days=lookback_days,
        telegram_chat_id=None,
        confirmation=reporting.MANUAL_CONFIRMATION,
    )
    return {
        "id": job.id,
        "status": job.status,
        "range_start": job.range_start.isoformat(),
        "range_end": job.range_end.isoformat(),
        "mode": "report_read_only",
        "ad_mutation_allowed": False,
    }
