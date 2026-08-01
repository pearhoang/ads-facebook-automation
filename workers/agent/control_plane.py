from __future__ import annotations

import hashlib
import os
from pathlib import Path

import httpx

from .config import WorkerConfig
from .contracts import BrowserSessionAssignment, ExecutionJobAssignment, ReportJobAssignment
from .local_state import LocalStateStore, TERMINAL_STATUSES


class ControlPlaneClient:
    def __init__(self, config: WorkerConfig):
        self.config = config
        headers = (
            {"X-Worker-Credential": config.credential}
            if config.credential
            else {"X-Worker-Secret": config.shared_secret}
        )
        self.http = httpx.Client(
            base_url=config.control_plane_url,
            headers=headers,
            timeout=20,
        )
        self.state = LocalStateStore(config.data_dir / "worker-state.sqlite3")
        self.worker_id: str | None = self.state.get_value("worker_id")

    def close(self) -> None:
        self.http.close()

    def register(self) -> str:
        response = self.http.post(
            "/api/workers/register",
            json={
                "worker_key": self.config.worker_key,
                "display_name": self.config.worker_name,
            },
        )
        response.raise_for_status()
        self.worker_id = str(response.json()["id"])
        self.state.set_value("worker_id", self.worker_id)
        return self.worker_id

    def heartbeat(self) -> None:
        worker_id = self._worker_id()
        response = self.http.post(
            f"/api/workers/{worker_id}/heartbeat",
            json={
                "runtime_version": self.config.runtime_version,
                "agent_version": self.config.agent_version,
                "capabilities": {
                    "browser": self.config.browser_enabled,
                    "execution": self.config.execution_enabled,
                    "novnc": self.config.browser_enabled,
                    "hermes": True,
                    "durable_outbox": True,
                    "outbox_depth": self.state.outbox_count(),
                },
                "last_error": None,
            },
        )
        response.raise_for_status()

    def flush_outbox(self) -> int:
        flushed = 0
        for item in self.state.pending_outbox():
            try:
                response = self.http.request(
                    item["method"],
                    item["path"],
                    json=item["payload"],
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                self.state.mark_outbox_failure(item["id"], str(exc))
                break
            self.state.delete_outbox(item["id"])
            if item["terminal"] and item["assignment_kind"] and item["assignment_id"]:
                self.state.delete_assignment(item["assignment_kind"], item["assignment_id"])
            flushed += 1
        return flushed

    def poll_sessions(self) -> list[BrowserSessionAssignment]:
        worker_id = self._worker_id()
        response = self.http.post(f"/api/workers/{worker_id}/browser-sessions/poll")
        response.raise_for_status()
        return [BrowserSessionAssignment.from_payload(item) for item in response.json()]

    def sync_session(
        self,
        session_id: str,
        *,
        status: str,
        novnc_url: str | None = None,
        web_port: int | None = None,
        last_error: str | None = None,
    ) -> None:
        worker_id = self._worker_id()
        self._sync_json(
            f"/api/workers/{worker_id}/browser-sessions/{session_id}/sync",
            {
                "status": status,
                "novnc_url": novnc_url,
                "web_port": web_port,
                "last_error": last_error,
            },
        )

    def poll_execution_job(self) -> ExecutionJobAssignment | None:
        worker_id = self._worker_id()
        try:
            response = self.http.post(f"/api/workers/{worker_id}/execution-jobs/poll")
            response.raise_for_status()
            payload = response.json()
        except (httpx.TransportError, httpx.TimeoutException):
            payload = self.state.resumable_assignment("execution")
        if payload:
            self.state.save_assignment("execution", str(payload["id"]), payload)
        return ExecutionJobAssignment.from_payload(payload) if payload else None

    def sync_execution_job(
        self,
        job_id: str,
        *,
        status: str,
        result_json: dict | None = None,
        last_error: str | None = None,
    ) -> None:
        worker_id = self._worker_id()
        terminal = status in TERMINAL_STATUSES
        self.state.update_assignment_status("execution", job_id, "terminal" if terminal else status)
        self._sync_json(
            f"/api/workers/{worker_id}/execution-jobs/{job_id}/sync",
            {
                "status": status,
                "result_json": result_json or {},
                "last_error": last_error,
            },
            assignment_kind="execution",
            assignment_id=job_id,
            terminal=terminal,
        )

    def poll_report_job(self) -> ReportJobAssignment | None:
        worker_id = self._worker_id()
        try:
            response = self.http.post(f"/api/workers/{worker_id}/report-jobs/poll")
            response.raise_for_status()
            payload = response.json()
        except (httpx.TransportError, httpx.TimeoutException):
            payload = self.state.resumable_assignment("report")
        if payload:
            self.state.save_assignment("report", str(payload["id"]), payload)
        return ReportJobAssignment.from_payload(payload) if payload else None

    def sync_report_job(
        self,
        job_id: str,
        *,
        status: str,
        result_json: dict | None = None,
        last_error: str | None = None,
    ) -> None:
        worker_id = self._worker_id()
        terminal = status in TERMINAL_STATUSES
        self.state.update_assignment_status("report", job_id, "terminal" if terminal else status)
        self._sync_json(
            f"/api/workers/{worker_id}/report-jobs/{job_id}/sync",
            {
                "status": status,
                "result_json": result_json or {},
                "last_error": last_error,
            },
            assignment_kind="report",
            assignment_id=job_id,
            terminal=terminal,
        )

    def get_ai_provider_config(self) -> dict | None:
        worker_id = self._worker_id()
        response = self.http.get(f"/api/workers/{worker_id}/ai-provider")
        response.raise_for_status()
        payload = response.json()
        return dict(payload) if payload else None

    def call_agent_tool(self, path: str, payload: dict | None = None) -> dict:
        worker_id = self._worker_id()
        response = self.http.request(
            "GET" if payload is None else "POST",
            f"/api/workers/{worker_id}/agent-tools/{path.lstrip('/')}",
            json=payload,
        )
        response.raise_for_status()
        return dict(response.json())

    def upload_execution_artifact(self, job_id: str, kind: str, content: bytes) -> None:
        worker_id = self._worker_id()
        response = self.http.post(
            f"/api/workers/{worker_id}/execution-jobs/{job_id}/artifacts",
            params={"kind": kind},
            headers={"Content-Type": "image/png"},
            content=content,
        )
        response.raise_for_status()

    def upload_execution_screenshot(self, job_id: str, content: bytes) -> None:
        self.upload_execution_artifact(job_id, "screenshot", content)

    def download_execution_asset(
        self,
        job_id: str,
        asset_id: str,
        target: Path,
        expected_sha256: str,
    ) -> Path:
        worker_id = self._worker_id()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.download")
        digest = hashlib.sha256()
        try:
            with self.http.stream(
                "GET",
                f"/api/workers/{worker_id}/execution-jobs/{job_id}/assets/{asset_id}",
                timeout=300,
            ) as response:
                response.raise_for_status()
                with temporary.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        if chunk:
                            digest.update(chunk)
                            handle.write(chunk)
            actual_sha256 = digest.hexdigest()
            if actual_sha256 != expected_sha256:
                raise RuntimeError(
                    f"Creative asset digest mismatch: expected={expected_sha256} actual={actual_sha256}"
                )
            os.replace(temporary, target)
            return target
        finally:
            temporary.unlink(missing_ok=True)

    def _worker_id(self) -> str:
        if not self.worker_id:
            raise RuntimeError("Worker is not registered.")
        return self.worker_id

    def _sync_json(
        self,
        path: str,
        payload: dict,
        *,
        assignment_kind: str | None = None,
        assignment_id: str | None = None,
        terminal: bool = False,
    ) -> bool:
        try:
            response = self.http.post(path, json=payload)
            response.raise_for_status()
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            self.state.enqueue(
                method="POST",
                path=path,
                payload=payload,
                assignment_kind=assignment_kind,
                assignment_id=assignment_id,
                terminal=terminal,
            )
            return False
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code < 500:
                raise
            self.state.enqueue(
                method="POST",
                path=path,
                payload=payload,
                assignment_kind=assignment_kind,
                assignment_id=assignment_id,
                terminal=terminal,
            )
            return False
        if terminal and assignment_kind and assignment_id:
            self.state.delete_assignment(assignment_kind, assignment_id)
        return True
