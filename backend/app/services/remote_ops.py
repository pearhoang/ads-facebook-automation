from __future__ import annotations

import base64
import hashlib
import json
import shlex
import time
from collections.abc import Callable

import paramiko
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Worker, WorkerEnrollment, WorkerOperation, utc_now
from . import ai_settings, fleet


def _set_operation(
    session_factory: Callable[[], Session],
    operation_id: str,
    *,
    status: str,
    message: str | None = None,
    started: bool = False,
    completed: bool = False,
) -> WorkerOperation:
    with session_factory() as db:
        operation = db.get(WorkerOperation, operation_id)
        if operation is None:
            raise RuntimeError("Worker operation disappeared.")
        operation.status = status
        operation.message = message
        if started:
            operation.started_at = utc_now()
        if completed:
            operation.completed_at = utc_now()
        db.commit()
        db.refresh(operation)
        db.expunge(operation)
        return operation


def _connect(host: str, ssh_user: str, password: str) -> tuple[paramiko.SSHClient, str]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=host,
        username=ssh_user,
        password=password,
        timeout=20,
        banner_timeout=20,
        auth_timeout=20,
        look_for_keys=False,
        allow_agent=False,
    )
    transport = client.get_transport()
    if transport is None or transport.get_remote_server_key() is None:
        client.close()
        raise RuntimeError("Không đọc được SSH host key.")
    digest = hashlib.sha256(transport.get_remote_server_key().asbytes()).digest()
    fingerprint = "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")
    return client, fingerprint


def _run_command(
    client: paramiko.SSHClient,
    command: str,
    *,
    stdin_text: str | None = None,
    timeout_seconds: int = 2400,
) -> str:
    stdin, stdout, stderr = client.exec_command(command)
    if stdin_text:
        stdin.write(stdin_text)
        stdin.flush()
    channel = stdout.channel
    deadline = time.monotonic() + timeout_seconds
    while not channel.exit_status_ready():
        if time.monotonic() >= deadline:
            channel.close()
            raise RuntimeError(f"Remote command timeout after {timeout_seconds}s.")
        time.sleep(0.25)
    exit_code = channel.recv_exit_status()
    output = stdout.read().decode("utf-8", errors="replace")
    error = stderr.read().decode("utf-8", errors="replace")
    if exit_code != 0:
        tail = (error or output).strip().splitlines()[-20:]
        raise RuntimeError("\n".join(tail)[-2400:] or f"Remote command failed ({exit_code}).")
    return output[-2400:]


def _operator_command(ssh_user: str, password: str, script_command: str) -> tuple[str, str | None]:
    if ssh_user == "root":
        return script_command, None
    return f"sudo -S -p '' {script_command}", f"{password}\n"


def run_install(
    session_factory: Callable[[], Session],
    settings: Settings,
    operation_id: str,
    enrollment_token: str,
    repo_url: str,
    repo_branch: str,
    ssh_password: str,
    provider_name: str,
    provider_base_url: str,
    provider_model: str,
    provider_thinking_mode: str,
    provider_reasoning_effort: str,
    provider_api_key: str | None,
    telegram_bot_token: str,
    telegram_allowed_users: str,
) -> None:
    operation = _set_operation(session_factory, operation_id, status="running", started=True)
    client: paramiko.SSHClient | None = None
    remote_secrets_path = f"/tmp/ads-lush-install-secrets-{operation_id}.json"
    try:
        client, fingerprint = _connect(operation.host, operation.ssh_user, ssh_password)
        with client.open_sftp() as sftp:
            with sftp.file(remote_secrets_path, "w") as secret_file:
                secret_file.write(
                    json.dumps(
                        {
                            "telegram_bot_token": telegram_bot_token,
                            "telegram_allowed_users": telegram_allowed_users,
                        }
                    )
                )
            sftp.chmod(remote_secrets_path, 0o600)
        script_url = f"{settings.app_origin}/api/bot-nodes/bootstrap.sh"
        script = " ".join(
            [
                "bash /tmp/ads-lush-bot-bootstrap.sh",
                "--control-plane",
                shlex.quote(settings.app_origin),
                "--token",
                shlex.quote(enrollment_token),
                "--repo",
                shlex.quote(repo_url),
                "--branch",
                shlex.quote(repo_branch),
                "--secrets-file",
                shlex.quote(remote_secrets_path),
            ]
        )
        operator_script, stdin_text = _operator_command(operation.ssh_user, ssh_password, script)
        command = f"curl -fsSL {shlex.quote(script_url)} -o /tmp/ads-lush-bot-bootstrap.sh && {operator_script}"
        output = _run_command(client, command, stdin_text=stdin_text)

        with session_factory() as db:
            current = db.get(WorkerOperation, operation_id)
            enrollment = db.get(WorkerEnrollment, current.enrollment_id) if current else None
            if current is None or enrollment is None or not enrollment.worker_id:
                raise RuntimeError("Installer kết thúc nhưng worker chưa enrollment về control-plane.")
            worker = db.get(Worker, enrollment.worker_id)
            if worker is None:
                raise RuntimeError("Worker enrollment không còn tồn tại.")
            worker.host = current.host
            worker.ssh_user = current.ssh_user
            worker.ssh_host_fingerprint = fingerprint
            worker.install_status = "installed"
            worker.installed_at = utc_now()
            current.worker_id = worker.id
            ai_settings.upsert_config(
                db,
                tenant_id=current.tenant_id,
                user_id=current.created_by_user_id,
                provider_type="openai_compatible",
                provider_name=provider_name,
                base_url=provider_base_url,
                model=provider_model,
                thinking_mode=provider_thinking_mode,
                reasoning_effort=provider_reasoning_effort,
                api_key=provider_api_key,
                execution_scope="worker",
                worker_id=worker.id,
                encryption_key=settings.resolved_secret_encryption_key(),
            )
        _set_operation(
            session_factory,
            operation_id,
            status="succeeded",
            message=(output.strip().splitlines()[-1] if output.strip() else "Cài đặt hoàn tất."),
            completed=True,
        )
    except Exception as exc:
        _set_operation(
            session_factory,
            operation_id,
            status="failed",
            message=str(exc)[:2400],
            completed=True,
        )
    finally:
        if client is not None:
            try:
                with client.open_sftp() as sftp:
                    sftp.remove(remote_secrets_path)
            except OSError:
                pass
            client.close()


def run_decommission(
    session_factory: Callable[[], Session],
    settings: Settings,
    operation_id: str,
    ssh_password: str,
) -> None:
    operation = _set_operation(session_factory, operation_id, status="running", started=True)
    client: paramiko.SSHClient | None = None
    try:
        client, fingerprint = _connect(operation.host, operation.ssh_user, ssh_password)
        with session_factory() as db:
            expected_worker = db.get(Worker, operation.worker_id) if operation.worker_id else None
            expected_fingerprint = expected_worker.ssh_host_fingerprint if expected_worker else None
        if expected_fingerprint and expected_fingerprint != fingerprint:
            raise RuntimeError("SSH host fingerprint đã thay đổi; dừng gỡ để tránh thao tác nhầm VPS.")
        script_url = f"{settings.app_origin}/api/bot-nodes/decommission.sh"
        script = "bash /tmp/ads-lush-bot-decommission.sh"
        operator_script, stdin_text = _operator_command(operation.ssh_user, ssh_password, script)
        command = f"curl -fsSL {shlex.quote(script_url)} -o /tmp/ads-lush-bot-decommission.sh && {operator_script}"
        output = _run_command(client, command, stdin_text=stdin_text, timeout_seconds=900)
        with session_factory() as db:
            current = db.get(WorkerOperation, operation_id)
            if current is None or current.worker_id is None:
                raise RuntimeError("Không tìm thấy worker cần gỡ.")
            worker = fleet.get_tenant_node(db, current.tenant_id, current.worker_id)
            worker.ssh_host_fingerprint = fingerprint
            worker.install_status = "decommissioned"
            fleet.set_lifecycle(
                db,
                tenant_id=current.tenant_id,
                user_id=current.created_by_user_id,
                worker_id=worker.id,
                lifecycle_status="revoked",
            )
        _set_operation(
            session_factory,
            operation_id,
            status="succeeded",
            message=(output.strip().splitlines()[-1] if output.strip() else "Đã gỡ service."),
            completed=True,
        )
    except Exception as exc:
        _set_operation(
            session_factory,
            operation_id,
            status="failed",
            message=str(exc)[:2400],
            completed=True,
        )
    finally:
        if client is not None:
            client.close()
