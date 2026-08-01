from __future__ import annotations

import secrets
from typing import Any

from .browser_runtime import BrowserRuntimeManager
from .config import WorkerConfig
from .contracts import BrowserSessionAssignment
from .control_plane import ControlPlaneClient


class BrowserSessionSupervisor:
    def __init__(
        self,
        config: WorkerConfig,
        client: ControlPlaneClient,
        runtime: BrowserRuntimeManager | None = None,
    ):
        self.config = config
        self.client = client
        self.runtime = runtime or BrowserRuntimeManager(config.data_dir)
        self.local_sessions: dict[str, dict[str, Any]] = self.runtime.load_persisted_sessions()

    def _slot_for(self, session_id: str) -> int:
        existing = self.local_sessions.get(session_id)
        if existing and existing.get("slot") is not None:
            return int(existing["slot"])
        used = {
            int(record["slot"])
            for record in self.local_sessions.values()
            if record.get("slot") is not None and self.runtime.is_running(record)
        }
        for slot in range(self.config.slot_count):
            if slot not in used:
                return slot
        raise RuntimeError("Worker has no free browser session slot.")

    def _base_record(self, assignment: BrowserSessionAssignment) -> dict[str, Any]:
        slot = self._slot_for(assignment.session_id)
        return {
            "session_id": assignment.session_id,
            "account_id": assignment.account_id,
            "profile_key": assignment.profile_key,
            "slot": slot,
            "display_number": self.config.display_base + slot,
            "vnc_port": self.config.vnc_port_base + slot,
            "web_port": self.config.web_port_base + slot,
            "debug_port": self.config.debug_port_base + slot,
            "access_password": secrets.token_urlsafe(6)[:8],
            "start_url": assignment.launch_url,
        }

    def _stop(self, session_id: str) -> None:
        record = self.local_sessions.pop(session_id, None)
        if record:
            self.runtime.stop(record)

    def _launch(self, assignment: BrowserSessionAssignment) -> None:
        self.client.sync_session(assignment.session_id, status="starting")
        record = self._base_record(assignment)
        try:
            launch_metadata = self.runtime.launch(record)
            record.update(launch_metadata)
            self.local_sessions[assignment.session_id] = record
            self.runtime.save_session_record(record)
            self.client.sync_session(
                assignment.session_id,
                status="awaiting_user",
                novnc_url=str(record["novnc_url"]),
                web_port=int(record["web_port"]),
            )
        except Exception as exc:
            self._stop(assignment.session_id)
            self.client.sync_session(
                assignment.session_id,
                status="failed",
                last_error=str(exc),
            )

    def reconcile(self) -> None:
        assignments = self.client.poll_sessions()
        desired_ids = {item.session_id for item in assignments}

        for session_id in list(self.local_sessions):
            if session_id not in desired_ids:
                self._stop(session_id)

        for assignment in assignments:
            record = self.local_sessions.get(assignment.session_id)
            if assignment.status == "closing":
                self._stop(assignment.session_id)
                self.client.sync_session(assignment.session_id, status="closed")
                continue

            if assignment.status in {"requested", "starting"}:
                if record and self.runtime.is_running(record):
                    self.client.sync_session(
                        assignment.session_id,
                        status="awaiting_user",
                        novnc_url=str(record["novnc_url"]),
                        web_port=int(record["web_port"]),
                    )
                else:
                    self._launch(assignment)
                continue

            if assignment.status in {"awaiting_user", "ready"}:
                if record and self.runtime.is_running(record):
                    self.client.sync_session(
                        assignment.session_id,
                        status=assignment.status,
                        novnc_url=str(record["novnc_url"]),
                        web_port=int(record["web_port"]),
                    )
                else:
                    self.client.sync_session(
                        assignment.session_id,
                        status="failed",
                        last_error="Browser runtime stopped unexpectedly.",
                    )

    def shutdown(self) -> None:
        for session_id in list(self.local_sessions):
            self._stop(session_id)

    def active_profile_keys(self) -> set[str]:
        return {
            str(record.get("profile_key"))
            for record in self.local_sessions.values()
            if record.get("profile_key") and self.runtime.is_running(record)
        }
