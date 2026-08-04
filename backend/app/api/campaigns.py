from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..config import Settings
from ..dependencies import (
    get_current_principal,
    get_current_tenant_id,
    get_db,
    get_settings,
    verify_csrf,
)
from ..schemas import (
    AdAccountCreateRequest,
    AdAccountUpdateRequest,
    AdAccountView,
    AdAutomationEventView,
    AdAutomationRequestSummaryView,
    ApprovalDecisionRequest,
    ApprovalRequestView,
    AuditEventView,
    CampaignDraftCreateRequest,
    CampaignDraftUpdateRequest,
    CampaignDraftView,
    CreativeAssetView,
    MetaResourceCreateRequest,
    MetaResourceVerifyRequest,
    MetaResourceView,
    ObjectiveSpecView,
)
from ..services import auth, automation, campaigns, objective_specs, resources


router = APIRouter(prefix="/api", tags=["campaigns"])


@router.get("/objective-specs", response_model=list[ObjectiveSpecView])
def list_objective_specs(
    _tenant_id: str = Depends(get_current_tenant_id),
):
    return objective_specs.list_specs()


@router.get("/ad-accounts", response_model=list[AdAccountView])
def list_ad_accounts(
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return campaigns.list_ad_accounts(db, tenant_id)


@router.post("/ad-accounts", response_model=AdAccountView, status_code=status.HTTP_201_CREATED)
def create_ad_account(
    payload: AdAccountCreateRequest,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return campaigns.create_ad_account(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        **payload.model_dump(),
    )


@router.patch("/ad-accounts/{ad_account_id}", response_model=AdAccountView)
def update_ad_account(
    ad_account_id: str,
    payload: AdAccountUpdateRequest,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return campaigns.update_ad_account(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        ad_account_id=ad_account_id,
        changes=payload.model_dump(exclude_unset=True),
    )


@router.get("/meta-resources", response_model=list[MetaResourceView])
def list_meta_resources(
    ad_account_id: str | None = Query(default=None, max_length=36),
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return resources.list_resources(db, tenant_id, ad_account_id)


@router.post(
    "/meta-resources",
    response_model=MetaResourceView,
    status_code=status.HTTP_201_CREATED,
)
def create_meta_resource(
    payload: MetaResourceCreateRequest,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return resources.create_resource(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        **payload.model_dump(),
    )


@router.post(
    "/meta-resources/{resource_id}/verify",
    response_model=MetaResourceView,
)
def verify_meta_resource(
    resource_id: str,
    payload: MetaResourceVerifyRequest,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return resources.verify_resource(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        resource_id=resource_id,
        confirmation=payload.confirmation,
    )


@router.get("/creative-assets", response_model=list[CreativeAssetView])
def list_creative_assets(
    ad_account_id: str | None = Query(default=None, max_length=36),
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return resources.list_assets(db, tenant_id, ad_account_id)


@router.get(
    "/ad-automation-requests",
    response_model=list[AdAutomationRequestSummaryView],
)
def list_ad_automation_requests(
    status_filter: str | None = Query(default=None, alias="status", max_length=32),
    limit: int = Query(default=100, ge=1, le=200),
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return automation.list_requests(db, tenant_id, status=status_filter, limit=limit)


@router.get("/ad-automation-requests/{request_id}")
def get_ad_automation_request(
    request_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    work = automation.get_request(db, tenant_id, request_id)
    return automation.request_payload(db, work)


@router.get(
    "/ad-automation-requests/{request_id}/events",
    response_model=list[AdAutomationEventView],
)
def list_ad_automation_events(
    request_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return automation.list_events(db, tenant_id, request_id)


@router.post(
    "/creative-assets",
    response_model=CreativeAssetView,
    status_code=status.HTTP_201_CREATED,
)
async def upload_creative_asset(
    request: Request,
    ad_account_id: str = Query(min_length=1, max_length=36),
    label: str = Query(min_length=1, max_length=200),
    file_name: str = Query(min_length=1, max_length=255),
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    _csrf: None = Depends(verify_csrf),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    if not label.strip():
        raise HTTPException(status_code=422, detail="Tên gợi nhớ asset không được để trống.")
    return await resources.store_asset(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        ad_account_id=ad_account_id,
        label=label,
        file_name=file_name,
        content_type=request.headers.get("content-type", ""),
        chunks=request.stream(),
        storage_root=settings.creative_asset_root,
        max_bytes=settings.creative_asset_max_bytes,
    )


@router.get("/campaign-drafts", response_model=list[CampaignDraftView])
def list_campaign_drafts(
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return campaigns.list_campaigns(db, tenant_id)


@router.get("/campaign-drafts/{campaign_id}", response_model=CampaignDraftView)
def get_campaign_draft(
    campaign_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return campaigns.get_campaign(db, tenant_id, campaign_id)


@router.post("/campaign-drafts", response_model=CampaignDraftView, status_code=status.HTTP_201_CREATED)
def create_campaign_draft(
    payload: CampaignDraftCreateRequest,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return campaigns.create_campaign(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        **payload.model_dump(),
    )


@router.patch("/campaign-drafts/{campaign_id}", response_model=CampaignDraftView)
def update_campaign_draft(
    campaign_id: str,
    payload: CampaignDraftUpdateRequest,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return campaigns.update_campaign(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        campaign_id=campaign_id,
        changes=payload.model_dump(exclude_unset=True),
    )


@router.post("/campaign-drafts/{campaign_id}/submit", response_model=ApprovalRequestView)
def submit_campaign_draft(
    campaign_id: str,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return campaigns.submit_campaign(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        campaign_id=campaign_id,
    )


@router.get("/approval-requests", response_model=list[ApprovalRequestView])
def list_approval_requests(
    status_filter: str | None = Query(default=None, alias="status"),
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return campaigns.list_approvals(db, tenant_id, status_filter)


@router.post("/approval-requests/{approval_id}/approve", response_model=ApprovalRequestView)
def approve_request(
    approval_id: str,
    payload: ApprovalDecisionRequest,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return campaigns.decide_approval(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        role=principal.role,
        approval_id=approval_id,
        decision="approved",
        note=payload.note,
    )


@router.post("/approval-requests/{approval_id}/reject", response_model=ApprovalRequestView)
def reject_request(
    approval_id: str,
    payload: ApprovalDecisionRequest,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return campaigns.decide_approval(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        role=principal.role,
        approval_id=approval_id,
        decision="rejected",
        note=payload.note,
    )


@router.get("/audit-events", response_model=list[AuditEventView])
def list_audit_events(
    limit: int = Query(default=50, ge=1, le=200),
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return campaigns.list_audit_events(db, tenant_id, limit)
