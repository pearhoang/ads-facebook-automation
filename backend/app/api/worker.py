from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import Settings
from ..dependencies import get_db, get_settings, verify_worker_secret
from ..models import AgentConversation, Worker
from ..schemas import (
    BrowserSessionSyncRequest,
    BrowserSessionView,
    WorkerBrowserSessionItem,
    WorkerRegisterRequest,
    WorkerView,
    ExecutionArtifactView,
    ExecutionJobSyncRequest,
    ExecutionJobView,
    WorkerExecutionJobItem,
    ReportJobSyncRequest,
    ReportJobView,
    WorkerReportJobItem,
    WorkerHeartbeatRequest,
    WorkerAIProviderRuntimeView,
    AgentCampaignQuery,
    AgentCampaignPrepareRequest,
    AgentCampaignConfirmRequest,
    AgentWorkStatusRequest,
    AgentWorkflowLearningRequest,
    AgentKPIQuery,
    AgentReportRequest,
    AgentJobSyncRequest,
    CampaignDraftCreateRequest,
    CreativeAssetView,
    AgentJobView,
    WorkerAgentJobItem,
)
from ..services import account_sessions, agent_chat, agent_tools, ai_settings, automation, execution_jobs, fleet, reporting, resources


router = APIRouter(
    prefix="/api/workers",
    tags=["worker"],
    dependencies=[Depends(verify_worker_secret)],
)


def _require_node_credential(request: Request, worker_id: str) -> None:
    worker_auth = request.state.worker_auth
    if worker_auth.legacy or worker_auth.worker_id != worker_id:
        raise HTTPException(status_code=403, detail="Agent tools require per-node credential.")


@router.post("/register", response_model=WorkerView, status_code=status.HTTP_201_CREATED)
def register_worker(
    payload: WorkerRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    worker_auth = request.state.worker_auth
    if worker_auth.worker_id:
        registered = fleet.reregister_worker(
            db,
            worker_id=worker_auth.worker_id,
            worker_key=payload.worker_key,
            display_name=payload.display_name,
        )
    else:
        registered = account_sessions.register_worker(db, payload.worker_key, payload.display_name)
    if settings.app_env in {"development", "test"} and settings.dev_tenant_id:
        account_sessions.assign_worker_to_tenant(db, registered.id, settings.dev_tenant_id)
    return registered


@router.post("/{worker_id}/heartbeat", response_model=WorkerView)
def heartbeat_worker(
    worker_id: str,
    payload: WorkerHeartbeatRequest | None = None,
    db: Session = Depends(get_db),
):
    return fleet.update_heartbeat(
        db,
        worker_id=worker_id,
        runtime_version=payload.runtime_version if payload else None,
        agent_version=payload.agent_version if payload else None,
        capabilities=payload.capabilities if payload else None,
        last_error=payload.last_error if payload else None,
    )


@router.post("/{worker_id}/browser-sessions/poll", response_model=list[WorkerBrowserSessionItem])
def poll_browser_sessions(worker_id: str, db: Session = Depends(get_db)):
    node = db.get(Worker, worker_id)
    if node is None or node.lifecycle_status != "active":
        return []
    sessions = account_sessions.poll_worker_sessions(db, worker_id)
    return [
        WorkerBrowserSessionItem(
            **BrowserSessionView.model_validate(browser_session).model_dump(),
            profile_key=browser_session.account.profile_key,
        )
        for browser_session in sessions
    ]


@router.post(
    "/{worker_id}/browser-sessions/{session_id}/sync",
    response_model=BrowserSessionView,
)
def sync_browser_session(
    worker_id: str,
    session_id: str,
    payload: BrowserSessionSyncRequest,
    db: Session = Depends(get_db),
):
    return account_sessions.sync_worker_session(
        db,
        worker_id,
        session_id,
        payload.status,
        payload.novnc_url,
        payload.web_port,
        payload.last_error,
        payload.facebook_user_id,
    )


@router.post(
    "/{worker_id}/execution-jobs/poll",
    response_model=WorkerExecutionJobItem | None,
)
def poll_execution_job(worker_id: str, db: Session = Depends(get_db)):
    node = db.get(Worker, worker_id)
    if node is None or node.lifecycle_status != "active":
        return None
    job = execution_jobs.poll_worker_job(db, worker_id)
    if job is None:
        return None
    return WorkerExecutionJobItem(
        **ExecutionJobView.model_validate(job).model_dump(),
        profile_key=job.facebook_account.profile_key if hasattr(job, "facebook_account") else "",
        meta_ad_account_id=job.payload_json["ad_account"]["meta_ad_account_id"],
    )


@router.post(
    "/{worker_id}/execution-jobs/{job_id}/sync",
    response_model=ExecutionJobView,
)
def sync_execution_job(
    worker_id: str,
    job_id: str,
    payload: ExecutionJobSyncRequest,
    db: Session = Depends(get_db),
):
    return execution_jobs.sync_worker_job(
        db,
        worker_id=worker_id,
        job_id=job_id,
        next_status=payload.status,
        result_json=payload.result_json,
        last_error=payload.last_error,
    )


@router.post(
    "/{worker_id}/execution-jobs/{job_id}/artifacts",
    response_model=ExecutionArtifactView,
    status_code=status.HTTP_201_CREATED,
)
async def upload_execution_artifact(
    worker_id: str,
    job_id: str,
    request: Request,
    kind: str = Query(default="screenshot"),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    content = await request.body()
    return execution_jobs.store_artifact(
        db,
        worker_id=worker_id,
        job_id=job_id,
        kind=kind,
        content_type=request.headers.get("content-type", ""),
        content=content,
        artifact_root=settings.artifact_root,
        max_bytes=settings.artifact_max_bytes,
    )


@router.get("/{worker_id}/execution-jobs/{job_id}/assets/{asset_id}")
def download_execution_asset(
    worker_id: str,
    job_id: str,
    asset_id: str,
    db: Session = Depends(get_db),
):
    asset = resources.get_worker_job_asset(
        db,
        worker_id=worker_id,
        job_id=job_id,
        asset_id=asset_id,
    )
    return FileResponse(
        asset.storage_path,
        media_type=asset.content_type,
        filename=asset.file_name,
        headers={"X-Content-SHA256": asset.sha256},
    )


@router.post(
    "/{worker_id}/report-jobs/poll",
    response_model=WorkerReportJobItem | None,
)
def poll_report_job(worker_id: str, db: Session = Depends(get_db)):
    node = db.get(Worker, worker_id)
    if node is None or node.lifecycle_status != "active":
        return None
    job = reporting.poll_worker_job(db, worker_id)
    if job is None:
        return None
    ad_account = job.payload_json["ad_account"]
    return WorkerReportJobItem(
        **ReportJobView.model_validate(job).model_dump(),
        profile_key=job.facebook_account.profile_key,
        meta_ad_account_id=ad_account["meta_ad_account_id"],
        ad_account_label=ad_account["label"],
        currency=ad_account["currency"],
    )


@router.post(
    "/{worker_id}/report-jobs/{job_id}/sync",
    response_model=ReportJobView,
)
def sync_report_job(
    worker_id: str,
    job_id: str,
    payload: ReportJobSyncRequest,
    db: Session = Depends(get_db),
):
    return reporting.sync_worker_job(
        db,
        worker_id=worker_id,
        job_id=job_id,
        next_status=payload.status,
        result_json=payload.result_json,
        last_error=payload.last_error,
    )


@router.get(
    "/{worker_id}/ai-provider",
    response_model=WorkerAIProviderRuntimeView | None,
)
def get_worker_ai_provider(
    worker_id: str,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    return ai_settings.runtime_config_for_worker(
        db,
        worker_id=worker_id,
        encryption_key=settings.resolved_secret_encryption_key(),
    )


@router.post(
    "/{worker_id}/agent-jobs/poll",
    response_model=WorkerAgentJobItem | None,
)
def poll_agent_job(
    worker_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_node_credential(request, worker_id)
    node = db.get(Worker, worker_id)
    if node is None or node.lifecycle_status != "active":
        return None
    job = agent_chat.poll_worker_job(db, worker_id)
    if job is None:
        return None
    hermes_session_id = None
    if job.conversation_id:
        conversation = db.get(AgentConversation, job.conversation_id)
        hermes_session_id = conversation.hermes_session_id if conversation else None
    return WorkerAgentJobItem(
        **AgentJobView.model_validate(job).model_dump(),
        hermes_session_id=hermes_session_id,
        payload_json=job.payload_json,
    )


@router.post(
    "/{worker_id}/agent-jobs/{job_id}/sync",
    response_model=AgentJobView,
)
def sync_agent_job(
    worker_id: str,
    job_id: str,
    payload: AgentJobSyncRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_node_credential(request, worker_id)
    return agent_chat.sync_worker_job(
        db,
        worker_id=worker_id,
        job_id=job_id,
        next_status=payload.status,
        result_json=payload.result_json,
        last_error=payload.last_error,
    )


@router.get("/{worker_id}/agent-tools/context")
def get_agent_workspace_context(
    worker_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_node_credential(request, worker_id)
    return agent_tools.workspace_context(db, worker_id)


@router.get("/{worker_id}/agent-tools/resource-context")
def get_agent_resource_context(
    worker_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_node_credential(request, worker_id)
    return automation.resource_context(db, worker_id)


@router.post("/{worker_id}/agent-tools/media", response_model=CreativeAssetView)
async def upload_agent_media(
    worker_id: str,
    request: Request,
    ad_account_id: str = Query(min_length=1, max_length=36),
    label: str = Query(min_length=1, max_length=200),
    file_name: str = Query(min_length=1, max_length=255),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    _require_node_credential(request, worker_id)
    config, user_id, _role = automation._worker_context(db, worker_id)
    automation._owned_account(
        db,
        worker_id=worker_id,
        tenant_id=config.tenant_id,
        ad_account_id=ad_account_id,
    )
    return await resources.store_asset(
        db,
        tenant_id=config.tenant_id,
        user_id=user_id,
        ad_account_id=ad_account_id,
        label=label,
        file_name=file_name,
        content_type=request.headers.get("content-type", ""),
        chunks=request.stream(),
        storage_root=settings.creative_asset_root,
        max_bytes=settings.creative_asset_max_bytes,
        allow_existing=True,
        metadata_json={"source": "telegram_or_hermes", "managed_by": "agent"},
    )


@router.post("/{worker_id}/agent-tools/ad-work/prepare")
def prepare_agent_ad_work(
    worker_id: str,
    payload: AgentCampaignPrepareRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_node_credential(request, worker_id)
    return automation.prepare_campaign_request(db, worker_id, **payload.model_dump())


@router.post("/{worker_id}/agent-tools/ad-work/confirm")
def confirm_agent_ad_work(
    worker_id: str,
    payload: AgentCampaignConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_node_credential(request, worker_id)
    return automation.confirm_campaign_request(db, worker_id, **payload.model_dump())


@router.post("/{worker_id}/agent-tools/ad-work/status")
def get_agent_ad_work_status(
    worker_id: str,
    payload: AgentWorkStatusRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_node_credential(request, worker_id)
    config, _user_id, _role = automation._worker_context(db, worker_id)
    work = automation.get_request(db, config.tenant_id, payload.request_id, worker_id=worker_id)
    return automation.request_payload(db, work)


@router.get("/{worker_id}/agent-tools/workflow-learnings")
def list_agent_workflow_learnings(
    worker_id: str,
    request: Request,
    include_proposed: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    _require_node_credential(request, worker_id)
    return automation.list_learnings(db, worker_id, include_proposed=include_proposed)


@router.post("/{worker_id}/agent-tools/workflow-learnings")
def record_agent_workflow_learning(
    worker_id: str,
    payload: AgentWorkflowLearningRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_node_credential(request, worker_id)
    return automation.record_learning(db, worker_id, **payload.model_dump())


@router.post("/{worker_id}/agent-tools/latest-kpi")
def get_agent_latest_kpi(
    worker_id: str,
    payload: AgentKPIQuery,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_node_credential(request, worker_id)
    return agent_tools.latest_kpi(db, worker_id, payload.ad_account_id)


@router.post("/{worker_id}/agent-tools/campaign-drafts/query")
def query_agent_campaign_drafts(
    worker_id: str,
    payload: AgentCampaignQuery,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_node_credential(request, worker_id)
    return agent_tools.list_campaign_drafts(db, worker_id, **payload.model_dump())


@router.post("/{worker_id}/agent-tools/campaign-drafts")
def create_agent_campaign_draft(
    worker_id: str,
    payload: CampaignDraftCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_node_credential(request, worker_id)
    return agent_tools.create_campaign_draft(db, worker_id, payload.model_dump())


@router.post("/{worker_id}/agent-tools/report-jobs")
def create_agent_report_job(
    worker_id: str,
    payload: AgentReportRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    _require_node_credential(request, worker_id)
    return agent_tools.request_kpi_collection(db, worker_id, **payload.model_dump())
