from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from ..dependencies import get_current_principal, get_current_tenant_id, get_db, verify_csrf
from ..schemas import (
    ReportJobCreateRequest,
    ReportJobView,
    ReportScheduleCreateRequest,
    ReportScheduleUpdateRequest,
    ReportScheduleView,
    ReportSnapshotView,
)
from ..services import auth, reporting


router = APIRouter(prefix="/api", tags=["reports"])


@router.get("/report-jobs", response_model=list[ReportJobView])
def list_report_jobs(
    limit: int = Query(default=100, ge=1, le=200),
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return reporting.list_jobs(db, tenant_id, limit)


@router.post("/report-jobs", response_model=ReportJobView, status_code=status.HTTP_201_CREATED)
def create_report_job(
    payload: ReportJobCreateRequest,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return reporting.create_manual_job(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        **payload.model_dump(),
    )


@router.get("/report-snapshots", response_model=list[ReportSnapshotView])
def list_report_snapshots(
    ad_account_id: str | None = Query(default=None, max_length=36),
    limit: int = Query(default=100, ge=1, le=200),
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return reporting.list_snapshots(db, tenant_id, ad_account_id, limit)


@router.get("/report-schedules", response_model=list[ReportScheduleView])
def list_report_schedules(
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return reporting.list_schedules(db, tenant_id)


@router.post(
    "/report-schedules",
    response_model=ReportScheduleView,
    status_code=status.HTTP_201_CREATED,
)
def create_report_schedule(
    payload: ReportScheduleCreateRequest,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return reporting.create_schedule(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        role=principal.role,
        **payload.model_dump(),
    )


@router.patch("/report-schedules/{schedule_id}", response_model=ReportScheduleView)
def update_report_schedule(
    schedule_id: str,
    payload: ReportScheduleUpdateRequest,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return reporting.update_schedule(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        role=principal.role,
        schedule_id=schedule_id,
        changes=payload.model_dump(exclude_unset=True),
    )

