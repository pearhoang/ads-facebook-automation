from __future__ import annotations

import base64
import hashlib
import json
import shlex
import secrets
import time
import re
from collections.abc import Callable

import paramiko
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import Worker, WorkerEnrollment, WorkerOperation, utc_now
from . import ai_settings, fleet


_DASHBOARD_ENV_UPDATE_CODE = r'''
import os
import secrets
import sys
import tempfile
from pathlib import Path

path = Path("/etc/meta-ads-copilot/hermes-dashboard.env")
if not path.is_file():
    raise SystemExit("Không tìm thấy /etc/meta-ads-copilot/hermes-dashboard.env")
password_hash = sys.stdin.readline().rstrip("\n")
if not password_hash.startswith("scrypt$"):
    raise SystemExit("Dashboard password hash không hợp lệ")

replacements = {
    "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH": password_hash,
    "HERMES_DASHBOARD_BASIC_AUTH_SECRET": secrets.token_urlsafe(48),
}
output = []
seen = set()
for line in path.read_text(encoding="utf-8").splitlines():
    key = line.split("=", 1)[0].strip() if "=" in line else ""
    if key == "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD":
        continue
    if key in replacements:
        output.append(f"{key}={replacements[key]}")
        seen.add(key)
    else:
        output.append(line)
for key, value in replacements.items():
    if key not in seen:
        output.append(f"{key}={value}")

stat = path.stat()
fd, temporary = tempfile.mkstemp(prefix=".hermes-dashboard.env.", dir=str(path.parent))
try:
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(output) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o600)
    os.chown(temporary, stat.st_uid, stat.st_gid)
    os.replace(temporary, path)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
'''.strip()


def hash_dashboard_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
        maxmem=0,
    )
    return (
        "scrypt$16384$8$1$"
        f"{base64.b64encode(salt).decode('ascii')}$"
        f"{base64.b64encode(derived_key).decode('ascii')}"
    )


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


def _host_key_fingerprint(key: paramiko.PKey) -> str:
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


class _ExpectedHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    def __init__(self, expected_fingerprint: str | None):
        self.expected_fingerprint = expected_fingerprint

    def missing_host_key(
        self,
        client: paramiko.SSHClient,
        hostname: str,
        key: paramiko.PKey,
    ) -> None:
        fingerprint = _host_key_fingerprint(key)
        if self.expected_fingerprint and fingerprint != self.expected_fingerprint:
            raise paramiko.SSHException(
                "SSH host fingerprint đã thay đổi; dừng trước khi gửi credential."
            )


def _connect(
    host: str,
    ssh_user: str,
    password: str,
    expected_fingerprint: str | None = None,
) -> tuple[paramiko.SSHClient, str]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(_ExpectedHostKeyPolicy(expected_fingerprint))
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
    fingerprint = _host_key_fingerprint(transport.get_remote_server_key())
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


_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_DEVICE_URL = re.compile(r"https://[^\s]+", re.IGNORECASE)
_DEVICE_CODE = re.compile(r"\b[A-Z0-9]{4}(?:-[A-Z0-9]{4})+\b")


def _codex_device_prompt(output: str) -> str | None:
    clean = _ANSI_ESCAPE.sub("", output)
    urls = [item.rstrip(".,);]") for item in _DEVICE_URL.findall(clean)]
    url = next((item for item in urls if "openai.com" in item or "chatgpt.com" in item), None)
    code_match = _DEVICE_CODE.search(clean.upper())
    if not url and not code_match:
        return None
    parts = ["Xác thực Codex trên trình duyệt của bạn."]
    if url:
        parts.append(f"Mở: {url}")
    if code_match:
        parts.append(f"Mã: {code_match.group(0)}")
    parts.append("Đang chờ bạn hoàn tất đăng nhập…")
    return "\n".join(parts)


def run_codex_device_login(
    session_factory: Callable[[], Session],
    operation_id: str,
    ssh_password: str,
) -> None:
    operation = _set_operation(session_factory, operation_id, status="running", started=True)
    client: paramiko.SSHClient | None = None
    try:
        with session_factory() as db:
            expected_worker = db.get(Worker, operation.worker_id) if operation.worker_id else None
            expected_fingerprint = expected_worker.ssh_host_fingerprint if expected_worker else None
        client, fingerprint = _connect(
            operation.host,
            operation.ssh_user,
            ssh_password,
            expected_fingerprint,
        )
        codex_home = "/opt/meta-ads-copilot-runtime/worker-data/codex"
        script = " && ".join(
            [
                f"install -d -m 700 {shlex.quote(codex_home)}",
                "(command -v npm >/dev/null 2>&1 || (apt-get update && apt-get install -y nodejs npm))",
                "(command -v codex >/dev/null 2>&1 || npm install -g @openai/codex@latest)",
                f"CODEX_HOME={shlex.quote(codex_home)} codex login --device-auth",
                f"test -s {shlex.quote(codex_home + '/auth.json')}",
                f"chmod 600 {shlex.quote(codex_home + '/auth.json')}",
                f"CODEX_HOME={shlex.quote(codex_home)} codex login status",
            ]
        )
        operator_script, sudo_stdin = _operator_command(operation.ssh_user, ssh_password, script)
        stdin, stdout, _stderr = client.exec_command(operator_script, get_pty=True)
        if sudo_stdin:
            stdin.write(sudo_stdin)
            stdin.flush()
        channel = stdout.channel
        deadline = time.monotonic() + 900
        captured = ""
        last_prompt: str | None = None
        while not channel.exit_status_ready():
            if time.monotonic() >= deadline:
                channel.close()
                raise RuntimeError("Codex device login hết hạn sau 15 phút. Hãy thử kết nối lại.")
            if channel.recv_ready():
                captured += channel.recv(4096).decode("utf-8", errors="replace")
                captured = captured[-12000:]
                prompt = _codex_device_prompt(captured)
                if prompt and prompt != last_prompt:
                    _set_operation(
                        session_factory,
                        operation_id,
                        status="waiting_user",
                        message=prompt,
                    )
                    last_prompt = prompt
            time.sleep(0.2)
        while channel.recv_ready():
            captured += channel.recv(4096).decode("utf-8", errors="replace")
        exit_code = channel.recv_exit_status()
        if exit_code != 0:
            clean = _ANSI_ESCAPE.sub("", captured)
            raise RuntimeError("\n".join(clean.strip().splitlines()[-20:])[-2400:] or "Codex login thất bại.")
        with session_factory() as db:
            current = db.get(WorkerOperation, operation_id)
            worker = db.get(Worker, current.worker_id) if current and current.worker_id else None
            if worker is not None:
                worker.ssh_host_fingerprint = fingerprint
                db.commit()
        _set_operation(
            session_factory,
            operation_id,
            status="succeeded",
            message="Đã kết nối Codex Search & Vision. Worker sẽ báo trạng thái mới trong tối đa 15 giây.",
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
                agent_permission_mode="ads_safe",
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
        with session_factory() as db:
            expected_worker = db.get(Worker, operation.worker_id) if operation.worker_id else None
            expected_fingerprint = expected_worker.ssh_host_fingerprint if expected_worker else None
        client, fingerprint = _connect(
            operation.host,
            operation.ssh_user,
            ssh_password,
            expected_fingerprint,
        )
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


def run_rotate_dashboard_password(
    session_factory: Callable[[], Session],
    operation_id: str,
    ssh_password: str,
    new_password: str,
) -> None:
    operation = _set_operation(session_factory, operation_id, status="running", started=True)
    client: paramiko.SSHClient | None = None
    try:
        with session_factory() as db:
            expected_worker = db.get(Worker, operation.worker_id) if operation.worker_id else None
            expected_fingerprint = expected_worker.ssh_host_fingerprint if expected_worker else None
        client, fingerprint = _connect(
            operation.host,
            operation.ssh_user,
            ssh_password,
            expected_fingerprint,
        )

        password_digest = hash_dashboard_password(new_password)
        script = " && ".join(
            [
                f"python3 -c {shlex.quote(_DASHBOARD_ENV_UPDATE_CODE)}",
                "systemctl restart meta-ads-copilot-hermes-dashboard.service",
                "systemctl is-active --quiet meta-ads-copilot-hermes-dashboard.service",
            ]
        )
        operator_script, sudo_stdin = _operator_command(
            operation.ssh_user,
            ssh_password,
            script,
        )
        _run_command(
            client,
            operator_script,
            stdin_text=f"{sudo_stdin or ''}{password_digest}\n",
            timeout_seconds=120,
        )
        with session_factory() as db:
            current = db.get(WorkerOperation, operation_id)
            worker = db.get(Worker, current.worker_id) if current and current.worker_id else None
            if worker is not None:
                worker.ssh_host_fingerprint = fingerprint
                db.commit()
        _set_operation(
            session_factory,
            operation_id,
            status="succeeded",
            message="Đã đổi mật khẩu và đăng xuất các phiên Hermes Dashboard cũ.",
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
