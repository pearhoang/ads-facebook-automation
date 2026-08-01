from __future__ import annotations

import signal
import time
from threading import Event

import httpx

from .config import WorkerConfig
from .control_plane import ControlPlaneClient
from .sessions import BrowserSessionSupervisor
from .execution import ExecutionJobSupervisor
from .hermes_config import HermesConfigManager
from .reporting import ReportJobSupervisor
from .agent_bridge import AgentJobSupervisor


def run() -> None:
    config = WorkerConfig.from_env()
    client = ControlPlaneClient(config)
    stop_event = Event()

    def request_stop(_signum, _frame) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    supervisor = BrowserSessionSupervisor(config, client)
    execution_supervisor = ExecutionJobSupervisor(config, client)
    report_supervisor = ReportJobSupervisor(config, client)
    agent_supervisor = AgentJobSupervisor(config, client)
    hermes_manager = HermesConfigManager(config.hermes_home or (config.data_dir / "hermes"))
    last_heartbeat_at = 0.0
    last_ai_sync_at = 0.0
    try:
        while not stop_event.is_set():
            if not client.worker_id:
                try:
                    worker_id = client.register()
                    print(f"[worker] registered id={worker_id}", flush=True)
                except (httpx.HTTPError, RuntimeError) as exc:
                    print(f"[worker] register unavailable: {exc}", flush=True)
                    stop_event.wait(config.poll_seconds)
                    continue

            try:
                flushed = client.flush_outbox()
                if flushed:
                    print(f"[worker] replayed outbox={flushed}", flush=True)
            except (httpx.HTTPError, RuntimeError) as exc:
                print(f"[worker] outbox replay deferred: {exc}", flush=True)

            now = time.monotonic()
            if now - last_heartbeat_at >= config.heartbeat_seconds:
                try:
                    client.heartbeat()
                    last_heartbeat_at = now
                except (httpx.HTTPError, RuntimeError) as exc:
                    print(f"[worker] heartbeat unavailable: {exc}", flush=True)

            if now - last_ai_sync_at >= 60:
                try:
                    if hermes_manager.apply(client.get_ai_provider_config()):
                        print("[worker] Hermes provider config updated", flush=True)
                    last_ai_sync_at = now
                except (httpx.HTTPError, RuntimeError, OSError) as exc:
                    print(f"[worker] AI config sync deferred: {exc}", flush=True)

            if config.browser_enabled:
                try:
                    supervisor.reconcile()
                except (httpx.HTTPError, RuntimeError) as exc:
                    print(f"[worker] browser reconcile deferred: {exc}", flush=True)
            if config.execution_enabled:
                try:
                    execution_supervisor.reconcile(supervisor.active_profile_keys())
                except (httpx.HTTPError, RuntimeError) as exc:
                    print(f"[worker] execution reconcile deferred: {exc}", flush=True)
                try:
                    report_supervisor.reconcile(supervisor.active_profile_keys())
                except (httpx.HTTPError, RuntimeError) as exc:
                    print(f"[worker] report reconcile deferred: {exc}", flush=True)
            try:
                agent_supervisor.reconcile()
            except (httpx.HTTPError, RuntimeError) as exc:
                print(f"[worker] agent reconcile deferred: {exc}", flush=True)
            stop_event.wait(config.poll_seconds)
    finally:
        supervisor.shutdown()
        client.close()


if __name__ == "__main__":
    run()
