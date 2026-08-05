from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..dependencies import get_current_principal, get_current_tenant_id, get_db, verify_csrf
from ..schemas import (
    ExecutionArtifactView,
    ExecutionJobCreateRequest,
    ExecutionJobRetryRequest,
    ExecutionJobView,
    ExecutionPreviewView,
)
from ..services import auth, execution_jobs


router = APIRouter(prefix="/api", tags=["execution"])


@router.get(
    "/campaign-drafts/{campaign_id}/execution-preview",
    response_model=ExecutionPreviewView,
)
def execution_preview(
    campaign_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return execution_jobs.build_preview(db, tenant_id, campaign_id)


@router.post("/execution-jobs", response_model=ExecutionJobView, status_code=201)
def create_execution_job(
    payload: ExecutionJobCreateRequest,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return execution_jobs.create_execution_job(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        role=principal.role,
        campaign_id=payload.campaign_id,
        job_type=payload.job_type,
        confirmation=payload.confirmation,
    )


@router.get("/execution-jobs", response_model=list[ExecutionJobView])
def list_execution_jobs(
    limit: int = Query(default=100, ge=1, le=200),
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return execution_jobs.list_jobs(db, tenant_id, limit)


@router.get("/execution-jobs/{job_id}", response_model=ExecutionJobView)
def get_execution_job(
    job_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return execution_jobs.get_job(db, tenant_id, job_id)


@router.post("/execution-jobs/{job_id}/retry", response_model=ExecutionJobView)
def retry_execution_job(
    job_id: str,
    payload: ExecutionJobRetryRequest,
    principal: auth.AuthPrincipal = Depends(get_current_principal),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return execution_jobs.retry_job(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        role=principal.role,
        job_id=job_id,
        confirmation=payload.confirmation,
    )


@router.get(
    "/execution-jobs/{job_id}/artifacts",
    response_model=list[ExecutionArtifactView],
)
def list_execution_artifacts(
    job_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return execution_jobs.list_artifacts(db, tenant_id, job_id)


@router.get("/execution-artifacts/{artifact_id}")
def download_execution_artifact(
    artifact_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    artifact = execution_jobs.get_artifact(db, tenant_id, artifact_id)
    return FileResponse(
        artifact.storage_path,
        media_type=artifact.content_type,
        filename=f"{artifact.kind}.png",
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store"},
    )
