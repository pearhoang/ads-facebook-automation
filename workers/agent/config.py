from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required env: {name}")
    return value


def _truthy(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class WorkerConfig:
    control_plane_url: str
    shared_secret: str
    worker_key: str
    worker_name: str
    poll_seconds: float
    heartbeat_seconds: float
    data_dir: Path
    browser_enabled: bool
    display_base: int
    vnc_port_base: int
    web_port_base: int
    debug_port_base: int
    slot_count: int
    credential: str | None = None
    runtime_version: str = "0.2.0"
    agent_version: str = "hermes-managed"
    execution_enabled: bool = True
    execution_debug_port: int = 19350
    execution_timeout_seconds: int = 45
    telegram_bot_token: str | None = None
    hermes_home: Path | None = None

    @classmethod
    def from_env(cls) -> "WorkerConfig":
        hostname = socket.gethostname().split(".")[0]
        data_dir = Path(os.getenv("WORKER_DATA_DIR", "/opt/meta-ads-copilot-runtime/worker-data"))
        data_dir.mkdir(parents=True, exist_ok=True)
        credential_file = Path(
            os.getenv("WORKER_CREDENTIAL_FILE", str(data_dir / "worker.credential"))
        )
        credential = (os.getenv("WORKER_CREDENTIAL") or "").strip()
        if not credential and credential_file.exists():
            credential = credential_file.read_text(encoding="utf-8").strip()
        shared_secret = (os.getenv("WORKER_SHARED_SECRET") or "").strip()
        if not credential and not shared_secret:
            raise RuntimeError("Missing WORKER_CREDENTIAL or WORKER_SHARED_SECRET.")
        return cls(
            control_plane_url=_required("CONTROL_PLANE_URL").rstrip("/"),
            shared_secret=shared_secret,
            worker_key=os.getenv("WORKER_KEY", hostname).strip() or hostname,
            worker_name=os.getenv("WORKER_NAME", hostname).strip() or hostname,
            poll_seconds=max(1.0, float(os.getenv("WORKER_POLL_SECONDS", "3"))),
            heartbeat_seconds=max(5.0, float(os.getenv("WORKER_HEARTBEAT_SECONDS", "15"))),
            data_dir=data_dir,
            browser_enabled=_truthy("BROWSER_SESSION_ENABLED"),
            display_base=int(os.getenv("BROWSER_SESSION_DISPLAY_BASE", "190")),
            vnc_port_base=int(os.getenv("BROWSER_SESSION_VNC_PORT_BASE", "15900")),
            web_port_base=int(os.getenv("BROWSER_SESSION_WEB_PORT_BASE", "16080")),
            debug_port_base=int(os.getenv("BROWSER_SESSION_DEBUG_PORT_BASE", "19220")),
            slot_count=max(1, int(os.getenv("BROWSER_SESSION_SLOT_COUNT", "10"))),
            credential=credential or None,
            runtime_version=os.getenv("WORKER_RUNTIME_VERSION", "0.2.0").strip() or "0.2.0",
            agent_version=os.getenv("HERMES_AGENT_VERSION", "managed").strip() or "managed",
            execution_enabled=_truthy("EXECUTION_PREFLIGHT_ENABLED", "true"),
            execution_debug_port=int(os.getenv("EXECUTION_PREFLIGHT_DEBUG_PORT", "19350")),
            execution_timeout_seconds=max(
                10,
                int(os.getenv("EXECUTION_PREFLIGHT_TIMEOUT_SECONDS", "45")),
            ),
            telegram_bot_token=(os.getenv("TELEGRAM_BOT_TOKEN") or "").strip() or None,
            hermes_home=Path(os.getenv("HERMES_HOME", str(data_dir / "hermes"))),
        )
