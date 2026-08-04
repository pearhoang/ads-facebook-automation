from __future__ import annotations

import shlex
from math import ceil

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import Settings
from ..dependencies import get_current_tenant_id, get_db, get_settings, require_owner, verify_csrf
from ..schemas import (
    BotNodeEnrollRequest,
    BotNodeEnrollResponse,
    BotNodeEnrollmentCreateRequest,
    BotNodeEnrollmentView,
    BotNodeRemoteInstallRequest,
    BotNodeEditRequest,
    HermesDashboardPasswordRotateRequest,
    WorkerView,
    WorkerOperationPage,
    WorkerOperationPageDeletion,
    WorkerOperationView,
)
from ..services import auth, fleet, remote_ops, ssh_credentials


router = APIRouter(prefix="/api/bot-nodes", tags=["bot-nodes"])


def _stored_ssh_password(worker, settings: Settings) -> str:
    password = ssh_credentials.decrypt_password(
        settings.resolved_secret_encryption_key(),
        worker.ssh_password_ciphertext,
    )
    if not password:
        raise HTTPException(
            status_code=409,
            detail="Bot VPS chưa lưu SSH password. Hãy mở Sửa thiết lập và lưu password một lần.",
        )
    return password


@router.get("/bootstrap.sh", include_in_schema=False)
def bootstrap_script():
    return FileResponse(
        "infra/bootstrap/install_bot_node.sh",
        media_type="text/x-shellscript; charset=utf-8",
        filename="install_bot_node.sh",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/decommission.sh", include_in_schema=False)
def decommission_script():
    return FileResponse(
        "infra/bootstrap/decommission_bot_node.sh",
        media_type="text/x-shellscript; charset=utf-8",
        filename="decommission_bot_node.sh",
        headers={"Cache-Control": "no-store"},
    )


@router.post("/enroll", response_model=BotNodeEnrollResponse, status_code=status.HTTP_201_CREATED)
def enroll_node(payload: BotNodeEnrollRequest, db: Session = Depends(get_db)):
    issued = fleet.enroll_worker(
        db,
        raw_token=payload.enrollment_token,
        runtime_version=payload.runtime_version,
        agent_version=payload.agent_version,
        capabilities=payload.capabilities,
    )
    return BotNodeEnrollResponse(
        worker=WorkerView.model_validate(issued.worker),
        worker_credential=issued.raw_credential,
    )


@router.get("", response_model=list[WorkerView])
def list_nodes(
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return fleet.list_nodes(db, tenant_id)


@router.get("/operations", response_model=list[WorkerOperationView])
def list_operations(
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return fleet.list_operations(db, tenant_id)


@router.get("/operations/page", response_model=WorkerOperationPage)
def list_operations_page(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=5, le=50),
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    operations, total, deletable_count = fleet.list_operations_page(
        db,
        tenant_id,
        page=page,
        page_size=page_size,
    )
    return WorkerOperationPage(
        items=operations,
        page=page,
        page_size=page_size,
        total=total,
        total_pages=ceil(total / page_size) if total else 0,
        deletable_count=deletable_count,
    )


@router.delete("/operations/page", response_model=WorkerOperationPageDeletion)
def delete_operations_page(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=5, le=50),
    principal: auth.AuthPrincipal = Depends(require_owner),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    deleted_count, protected_count = fleet.delete_terminal_operations_page(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        page=page,
        page_size=page_size,
    )
    return WorkerOperationPageDeletion(
        deleted_count=deleted_count,
        protected_count=protected_count,
    )


@router.get("/operations/{operation_id}", response_model=WorkerOperationView)
def get_operation(
    operation_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    db: Session = Depends(get_db),
):
    return fleet.get_operation(db, tenant_id, operation_id)


@router.post("/install", response_model=WorkerOperationView, status_code=status.HTTP_202_ACCEPTED)
def install_node(
    payload: BotNodeRemoteInstallRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    principal: auth.AuthPrincipal = Depends(require_owner),
    _csrf: None = Depends(verify_csrf),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    repo_url = (payload.repo_url or settings.worker_bootstrap_repo_url).strip()
    if not repo_url:
        raise HTTPException(
            status_code=422,
            detail="Hãy nhập GitHub repository URL hoặc cấu hình WORKER_BOOTSTRAP_REPO_URL.",
        )
    repo_branch = (payload.repo_branch or settings.worker_bootstrap_repo_branch).strip() or "main"
    issued = fleet.issue_enrollment(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        worker_key=payload.worker_key,
        display_name=payload.display_name,
        repo_url=repo_url,
        repo_branch=repo_branch,
        ttl_minutes=settings.worker_enrollment_ttl_minutes,
        ssh_password_ciphertext=ssh_credentials.encrypt_password(
            settings.resolved_secret_encryption_key(),
            payload.ssh_password.get_secret_value(),
        ),
    )
    operation = fleet.create_operation(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        operation_type="install",
        host=payload.host,
        ssh_user=payload.ssh_user,
        enrollment_id=issued.enrollment.id,
    )
    background_tasks.add_task(
        remote_ops.run_install,
        request.app.state.database.session_factory,
        settings,
        operation.id,
        issued.raw_token,
        repo_url,
        repo_branch,
        payload.ssh_password.get_secret_value(),
        payload.provider_name,
        payload.provider_base_url,
        payload.provider_model,
        payload.provider_thinking_mode,
        payload.provider_reasoning_effort,
        payload.provider_api_key.get_secret_value() if payload.provider_api_key else None,
        payload.telegram_bot_token.get_secret_value(),
        payload.telegram_allowed_users,
    )
    return operation


@router.post(
    "/enrollments",
    response_model=BotNodeEnrollmentView,
    status_code=status.HTTP_201_CREATED,
)
def create_enrollment(
    payload: BotNodeEnrollmentCreateRequest,
    request: Request,
    principal: auth.AuthPrincipal = Depends(require_owner),
    _csrf: None = Depends(verify_csrf),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    repo_url = (payload.repo_url or settings.worker_bootstrap_repo_url).strip()
    if not repo_url:
        raise HTTPException(
            status_code=422,
            detail="Hãy nhập GitHub repository URL hoặc cấu hình WORKER_BOOTSTRAP_REPO_URL.",
        )
    repo_branch = (payload.repo_branch or settings.worker_bootstrap_repo_branch).strip() or "main"
    issued = fleet.issue_enrollment(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        worker_key=payload.worker_key,
        display_name=payload.display_name,
        repo_url=repo_url,
        repo_branch=repo_branch,
        ttl_minutes=settings.worker_enrollment_ttl_minutes,
    )
    script_url = f"{settings.app_origin}/api/bot-nodes/bootstrap.sh"
    install_command = " ".join(
        [
            "curl -fsSL",
            shlex.quote(script_url),
            "-o /tmp/ads-lush-bot-bootstrap.sh && sudo bash /tmp/ads-lush-bot-bootstrap.sh",
            "--control-plane",
            shlex.quote(settings.app_origin),
            "--token",
            shlex.quote(issued.raw_token),
            "--repo",
            shlex.quote(repo_url),
            "--branch",
            shlex.quote(repo_branch),
        ]
    )
    return BotNodeEnrollmentView(
        id=issued.enrollment.id,
        worker_key=issued.enrollment.worker_key,
        display_name=issued.enrollment.display_name,
        expires_at=issued.enrollment.expires_at,
        enrollment_token=issued.raw_token,
        install_command=install_command,
    )


@router.patch("/{worker_id}", response_model=WorkerView)
def edit_node(
    worker_id: str,
    payload: BotNodeEditRequest,
    principal: auth.AuthPrincipal = Depends(require_owner),
    _csrf: None = Depends(verify_csrf),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    return fleet.edit_node(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        worker_id=worker_id,
        display_name=payload.display_name,
        host=payload.host,
        ssh_user=payload.ssh_user,
        ssh_password_ciphertext=(
            ssh_credentials.encrypt_password(
                settings.resolved_secret_encryption_key(),
                payload.ssh_password.get_secret_value(),
            )
            if payload.ssh_password
            else None
        ),
    )


@router.post(
    "/{worker_id}/decommission",
    response_model=WorkerOperationView,
    status_code=status.HTTP_202_ACCEPTED,
)
def decommission_node(
    worker_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    principal: auth.AuthPrincipal = Depends(require_owner),
    _csrf: None = Depends(verify_csrf),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    worker = fleet.get_tenant_node(db, principal.tenant_id, worker_id)
    if not worker.host or not worker.ssh_user:
        raise HTTPException(status_code=409, detail="Worker chưa có host/SSH user để gỡ từ xa.")
    if worker.lifecycle_status != "draining":
        raise HTTPException(status_code=409, detail="Hãy Drain worker trước khi gỡ khỏi VPS.")
    ssh_password = _stored_ssh_password(worker, settings)
    operation = fleet.create_operation(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        operation_type="decommission",
        host=worker.host,
        ssh_user=worker.ssh_user,
        worker_id=worker.id,
    )
    background_tasks.add_task(
        remote_ops.run_decommission,
        request.app.state.database.session_factory,
        settings,
        operation.id,
        ssh_password,
    )
    return operation


@router.post(
    "/{worker_id}/hermes-dashboard/password",
    response_model=WorkerOperationView,
    status_code=status.HTTP_202_ACCEPTED,
)
def rotate_hermes_dashboard_password(
    worker_id: str,
    payload: HermesDashboardPasswordRotateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    principal: auth.AuthPrincipal = Depends(require_owner),
    _csrf: None = Depends(verify_csrf),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    worker = fleet.get_tenant_node(db, principal.tenant_id, worker_id)
    if not worker.host or not worker.ssh_user:
        raise HTTPException(
            status_code=409,
            detail="Worker chưa có host/SSH user để đổi mật khẩu Dashboard từ xa.",
        )
    ssh_password = _stored_ssh_password(worker, settings)
    operation = fleet.create_operation(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        operation_type="rotate_dashboard_password",
        host=worker.host,
        ssh_user=worker.ssh_user,
        worker_id=worker.id,
    )
    background_tasks.add_task(
        remote_ops.run_rotate_dashboard_password,
        request.app.state.database.session_factory,
        operation.id,
        ssh_password,
        payload.new_password.get_secret_value(),
    )
    return operation


@router.post(
    "/{worker_id}/codex/device-login",
    response_model=WorkerOperationView,
    status_code=status.HTTP_202_ACCEPTED,
)
def connect_codex_device_login(
    worker_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    principal: auth.AuthPrincipal = Depends(require_owner),
    _csrf: None = Depends(verify_csrf),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    worker = fleet.get_tenant_node(db, principal.tenant_id, worker_id)
    if not worker.host or not worker.ssh_user:
        raise HTTPException(
            status_code=409,
            detail="Worker chưa có host/SSH user để kết nối Codex từ xa.",
        )
    ssh_password = _stored_ssh_password(worker, settings)
    operation = fleet.create_operation(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        operation_type="codex_device_login",
        host=worker.host,
        ssh_user=worker.ssh_user,
        worker_id=worker.id,
    )
    background_tasks.add_task(
        remote_ops.run_codex_device_login,
        request.app.state.database.session_factory,
        operation.id,
        ssh_password,
    )
    return operation


@router.post(
    "/{worker_id}/codex/disconnect",
    response_model=WorkerOperationView,
    status_code=status.HTTP_202_ACCEPTED,
)
def disconnect_codex(
    worker_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    principal: auth.AuthPrincipal = Depends(require_owner),
    _csrf: None = Depends(verify_csrf),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    worker = fleet.get_tenant_node(db, principal.tenant_id, worker_id)
    if not worker.host or not worker.ssh_user:
        raise HTTPException(
            status_code=409,
            detail="Worker chưa có host/SSH user để ngắt kết nối Codex từ xa.",
        )
    ssh_password = _stored_ssh_password(worker, settings)
    operation = fleet.create_operation(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        operation_type="codex_disconnect",
        host=worker.host,
        ssh_user=worker.ssh_user,
        worker_id=worker.id,
    )
    background_tasks.add_task(
        remote_ops.run_codex_disconnect,
        request.app.state.database.session_factory,
        operation.id,
        ssh_password,
    )
    return operation


@router.post("/{worker_id}/drain", response_model=WorkerView)
def drain_node(
    worker_id: str,
    principal: auth.AuthPrincipal = Depends(require_owner),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return fleet.set_lifecycle(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        worker_id=worker_id,
        lifecycle_status="draining",
    )


@router.post("/{worker_id}/activate", response_model=WorkerView)
def activate_node(
    worker_id: str,
    principal: auth.AuthPrincipal = Depends(require_owner),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return fleet.set_lifecycle(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        worker_id=worker_id,
        lifecycle_status="active",
    )


@router.delete("/{worker_id}", response_model=WorkerView)
def revoke_node(
    worker_id: str,
    principal: auth.AuthPrincipal = Depends(require_owner),
    _csrf: None = Depends(verify_csrf),
    db: Session = Depends(get_db),
):
    return fleet.set_lifecycle(
        db,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        worker_id=worker_id,
        lifecycle_status="revoked",
    )
