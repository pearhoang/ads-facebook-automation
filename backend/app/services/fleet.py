from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import (
    AuditEvent,
    Worker,
    WorkerCredential,
    WorkerEnrollment,
    WorkerOperation,
    WorkerTenantAssignment,
    utc_now,
)


@dataclass(frozen=True, slots=True)
class WorkerAuthContext:
    worker_id: str | None
    legacy: bool = False


@dataclass(frozen=True, slots=True)
class IssuedEnrollment:
    enrollment: WorkerEnrollment
    raw_token: str


@dataclass(frozen=True, slots=True)
class EnrolledWorker:
    worker: Worker
    raw_credential: str


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _audit(
    db: Session,
    *,
    tenant_id: str,
    user_id: str | None,
    actor_type: str,
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


def issue_enrollment(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    worker_key: str,
    display_name: str,
    repo_url: str,
    repo_branch: str,
    ttl_minutes: int,
) -> IssuedEnrollment:
    normalized_key = worker_key.strip()
    if db.scalar(select(Worker).where(Worker.worker_key == normalized_key)) is not None:
        raise HTTPException(status_code=409, detail="Worker key đã tồn tại.")
    existing = db.scalar(
        select(WorkerEnrollment).where(
            WorkerEnrollment.worker_key == normalized_key,
            WorkerEnrollment.status == "pending",
        )
    )
    if existing is not None:
        existing.status = "cancelled"
    raw_token = secrets.token_urlsafe(48)
    enrollment = WorkerEnrollment(
        tenant_id=tenant_id,
        token_hash=_digest(raw_token),
        worker_key=normalized_key,
        display_name=display_name.strip(),
        repo_url=repo_url.strip(),
        repo_branch=repo_branch.strip() or "main",
        status="pending",
        created_by_user_id=user_id,
        expires_at=utc_now() + timedelta(minutes=ttl_minutes),
    )
    db.add(enrollment)
    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        actor_type="user",
        action="Đã tạo enrollment Bot VPS",
        entity_type="worker_enrollment",
        entity_id=enrollment.id,
        payload={"worker_key": normalized_key, "display_name": display_name.strip()},
    )
    db.commit()
    db.refresh(enrollment)
    return IssuedEnrollment(enrollment=enrollment, raw_token=raw_token)


def enroll_worker(
    db: Session,
    *,
    raw_token: str,
    runtime_version: str | None,
    agent_version: str | None,
    capabilities: dict,
) -> EnrolledWorker:
    enrollment = db.scalar(
        select(WorkerEnrollment).where(WorkerEnrollment.token_hash == _digest(raw_token))
    )
    if enrollment is None:
        raise HTTPException(status_code=401, detail="Enrollment token không hợp lệ.")
    if enrollment.status != "pending" or enrollment.used_at is not None:
        raise HTTPException(status_code=409, detail="Enrollment token đã được sử dụng.")
    if _aware(enrollment.expires_at) <= utc_now():
        enrollment.status = "expired"
        db.commit()
        raise HTTPException(status_code=410, detail="Enrollment token đã hết hạn.")
    if db.scalar(select(Worker).where(Worker.worker_key == enrollment.worker_key)) is not None:
        raise HTTPException(status_code=409, detail="Worker key đã tồn tại.")

    worker = Worker(
        worker_key=enrollment.worker_key,
        display_name=enrollment.display_name,
        status="online",
        lifecycle_status="active",
        runtime_version=runtime_version,
        agent_version=agent_version,
        capabilities_json=capabilities,
    )
    db.add(worker)
    db.flush()
    db.add(WorkerTenantAssignment(worker_id=worker.id, tenant_id=enrollment.tenant_id))
    raw_credential = secrets.token_urlsafe(64)
    db.add(
        WorkerCredential(
            worker_id=worker.id,
            token_hash=_digest(raw_credential),
            status="active",
        )
    )
    enrollment.status = "used"
    enrollment.used_at = utc_now()
    enrollment.worker_id = worker.id
    _audit(
        db,
        tenant_id=enrollment.tenant_id,
        user_id=None,
        actor_type="worker",
        action="Bot VPS đã enrollment",
        entity_type="worker",
        entity_id=worker.id,
        payload={"worker_key": worker.worker_key},
    )
    db.commit()
    db.refresh(worker)
    return EnrolledWorker(worker=worker, raw_credential=raw_credential)


def authenticate_worker(db: Session, raw_credential: str) -> WorkerAuthContext:
    credential = db.scalar(
        select(WorkerCredential).where(
            WorkerCredential.token_hash == _digest(raw_credential),
            WorkerCredential.status == "active",
        )
    )
    if credential is None:
        raise HTTPException(status_code=401, detail="Invalid worker credential.")
    worker = db.get(Worker, credential.worker_id)
    if worker is None or worker.lifecycle_status in {"revoked", "decommissioned"}:
        raise HTTPException(status_code=401, detail="Worker credential has been revoked.")
    credential.last_used_at = utc_now()
    db.commit()
    return WorkerAuthContext(worker_id=credential.worker_id, legacy=False)


def list_nodes(db: Session, tenant_id: str) -> list[Worker]:
    return list(
        db.scalars(
            select(Worker)
            .join(WorkerTenantAssignment, WorkerTenantAssignment.worker_id == Worker.id)
            .where(WorkerTenantAssignment.tenant_id == tenant_id)
            .order_by(Worker.created_at.desc())
        )
    )


def create_operation(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    operation_type: str,
    host: str,
    ssh_user: str,
    worker_id: str | None = None,
    enrollment_id: str | None = None,
) -> WorkerOperation:
    operation = WorkerOperation(
        tenant_id=tenant_id,
        worker_id=worker_id,
        enrollment_id=enrollment_id,
        operation_type=operation_type,
        status="queued",
        host=host,
        ssh_user=ssh_user,
        created_by_user_id=user_id,
    )
    db.add(operation)
    db.flush()
    _audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        actor_type="user",
        action=f"Đã tạo thao tác {operation_type} Bot VPS",
        entity_type="worker_operation",
        entity_id=operation.id,
        payload={"host": host, "ssh_user": ssh_user, "worker_id": worker_id},
    )
    db.commit()
    db.refresh(operation)
    return operation


def get_operation(db: Session, tenant_id: str, operation_id: str) -> WorkerOperation:
    operation = db.scalar(
        select(WorkerOperation).where(
            WorkerOperation.id == operation_id,
            WorkerOperation.tenant_id == tenant_id,
        )
    )
    if operation is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy thao tác worker.")
    return operation


def list_operations(db: Session, tenant_id: str, limit: int = 30) -> list[WorkerOperation]:
    return list(
        db.scalars(
            select(WorkerOperation)
            .where(WorkerOperation.tenant_id == tenant_id)
            .order_by(WorkerOperation.created_at.desc())
            .limit(limit)
        )
    )


def edit_node(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    worker_id: str,
    display_name: str,
    host: str,
    ssh_user: str,
) -> Worker:
    worker = get_tenant_node(db, tenant_id, worker_id)
    if worker.host and worker.host != host.strip():
        worker.ssh_host_fingerprint = None
    worker.display_name = display_name.strip()
    worker.host = host.strip()
    worker.ssh_user = ssh_user.strip()
    _audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        actor_type="user",
        action="Đã sửa thiết lập Bot VPS",
        entity_type="worker",
        entity_id=worker.id,
        payload={"display_name": worker.display_name, "host": worker.host, "ssh_user": worker.ssh_user},
    )
    db.commit()
    db.refresh(worker)
    return worker


def get_tenant_node(db: Session, tenant_id: str, worker_id: str) -> Worker:
    worker = db.scalar(
        select(Worker)
        .join(WorkerTenantAssignment, WorkerTenantAssignment.worker_id == Worker.id)
        .where(
            Worker.id == worker_id,
            WorkerTenantAssignment.tenant_id == tenant_id,
        )
    )
    if worker is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy Bot VPS.")
    return worker


def set_lifecycle(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
    worker_id: str,
    lifecycle_status: str,
) -> Worker:
    worker = get_tenant_node(db, tenant_id, worker_id)
    if lifecycle_status == "draining":
        worker.lifecycle_status = "draining"
        worker.drained_at = utc_now()
        worker.status = "draining"
        action = "Đã drain Bot VPS"
    elif lifecycle_status == "active":
        if worker.revoked_at is not None:
            raise HTTPException(status_code=409, detail="Bot VPS đã revoke, cần enrollment lại.")
        worker.lifecycle_status = "active"
        worker.drained_at = None
        action = "Đã kích hoạt lại Bot VPS"
    elif lifecycle_status == "revoked":
        worker.lifecycle_status = "revoked"
        worker.status = "revoked"
        worker.revoked_at = utc_now()
        db.execute(
            update(WorkerCredential)
            .where(WorkerCredential.worker_id == worker.id)
            .values(status="revoked", revoked_at=utc_now())
        )
        action = "Đã revoke Bot VPS"
    else:
        raise HTTPException(status_code=422, detail="Lifecycle status không hợp lệ.")
    _audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        actor_type="user",
        action=action,
        entity_type="worker",
        entity_id=worker.id,
        payload={"lifecycle_status": worker.lifecycle_status},
    )
    db.commit()
    db.refresh(worker)
    return worker


def update_heartbeat(
    db: Session,
    *,
    worker_id: str,
    runtime_version: str | None,
    agent_version: str | None,
    capabilities: dict | None,
    last_error: str | None,
) -> Worker:
    worker = db.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found.")
    if worker.lifecycle_status in {"revoked", "decommissioned"}:
        raise HTTPException(status_code=410, detail="Worker has been revoked.")
    worker.status = "draining" if worker.lifecycle_status == "draining" else "online"
    worker.last_seen_at = utc_now()
    if runtime_version:
        worker.runtime_version = runtime_version
    if agent_version:
        worker.agent_version = agent_version
    if capabilities is not None:
        worker.capabilities_json = capabilities
    worker.last_error = last_error
    db.commit()
    db.refresh(worker)
    return worker


def reregister_worker(
    db: Session,
    *,
    worker_id: str,
    worker_key: str,
    display_name: str,
) -> Worker:
    worker = db.get(Worker, worker_id)
    if worker is None or worker.worker_key != worker_key:
        raise HTTPException(status_code=403, detail="Worker identity mismatch.")
    worker.display_name = display_name.strip()
    return update_heartbeat(
        db,
        worker_id=worker.id,
        runtime_version=None,
        agent_version=None,
        capabilities=None,
        last_error=None,
    )
