from __future__ import annotations

from pathlib import Path
import sys

import httpx

from .config import WorkerConfig
from .contracts import AgentJobAssignment
from .control_plane import ControlPlaneClient


class HermesApiError(RuntimeError):
    def __init__(self, public_message: str, diagnostic: str):
        super().__init__(public_message)
        self.public_message = public_message
        self.diagnostic = diagnostic


class HermesApiClient:
    def __init__(self, home: Path, port: int):
        key_path = home / ".ads-lush-api-server.key"
        if not key_path.exists():
            raise RuntimeError(f"Hermes API key chưa sẵn sàng: {key_path}")
        key = key_path.read_text(encoding="utf-8").strip()
        if not key:
            raise RuntimeError("Hermes API key đang trống.")
        self.http = httpx.Client(
            base_url=f"http://127.0.0.1:{port}",
            headers={"Authorization": f"Bearer {key}"},
            timeout=httpx.Timeout(600, connect=10),
        )

    def close(self) -> None:
        self.http.close()

    @staticmethod
    def _ensure_success(response: httpx.Response, operation: str) -> None:
        if response.is_success:
            return
        diagnostic = (
            f"Hermes API {operation} failed with HTTP {response.status_code}: "
            f"{response.text[:1200]}"
        )
        if response.status_code == 429:
            public = "Provider AI đang giới hạn tần suất. Hãy chờ một lát rồi thử lại."
        elif response.status_code in {401, 403}:
            public = "Hermes chưa xác thực được provider AI. Hãy kiểm tra Hermes Agents."
        elif response.status_code >= 500:
            public = "Hermes chưa thể xử lý yêu cầu. Hãy kiểm tra cấu hình provider trong Hermes Agents rồi thử lại."
        else:
            public = "Hermes từ chối yêu cầu này. Hãy kiểm tra nội dung rồi thử lại."
        raise HermesApiError(public, diagnostic)

    def sessions(self, *, session_limit: int, message_limit: int) -> list[dict]:
        response = self.http.get("/api/sessions", params={"limit": session_limit})
        self._ensure_success(response, "list sessions")
        payload = response.json()
        sessions = payload.get("data") if isinstance(payload, dict) else payload
        output: list[dict] = []
        for item in (sessions or [])[:session_limit]:
            if not isinstance(item, dict):
                continue
            session_id = str(item.get("id") or item.get("session_id") or "")
            if not session_id:
                continue
            messages_response = self.http.get(
                f"/api/sessions/{session_id}/messages",
                params={"limit": message_limit},
            )
            self._ensure_success(messages_response, "list messages")
            messages_payload = messages_response.json()
            messages = (
                messages_payload.get("data")
                if isinstance(messages_payload, dict)
                else messages_payload
            )
            source = item.get("platform") or item.get("source")
            if not source:
                lowered = session_id.lower()
                source = "telegram" if "telegram" in lowered else "hermes"
            output.append(
                {
                    "id": session_id,
                    "title": item.get("title") or item.get("name") or "Cuộc trò chuyện Hermes",
                    "source": source,
                    "metadata": {
                        key: value
                        for key, value in item.items()
                        if key not in {"id", "session_id", "title", "name"}
                    },
                    "messages": messages or [],
                }
            )
        return output

    def create_session(self, title: str) -> str:
        response = self.http.post("/api/sessions", json={"title": title})
        self._ensure_success(response, "create session")
        payload = response.json()
        session = payload.get("session") if isinstance(payload, dict) else None
        session = session if isinstance(session, dict) else payload
        session_id = session.get("id") or session.get("session_id")
        if not session_id:
            raise RuntimeError("Hermes không trả về session_id khi tạo phiên.")
        return str(session_id)

    def chat(self, session_id: str, message: str) -> dict:
        response = self.http.post(
            f"/api/sessions/{session_id}/chat",
            json={"message": message},
        )
        self._ensure_success(response, "chat")
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Hermes trả về chat payload không hợp lệ.")
        payload.setdefault("session_id", session_id)
        return payload


class AgentJobSupervisor:
    def __init__(self, config: WorkerConfig, control_plane: ControlPlaneClient):
        self.config = config
        self.control_plane = control_plane

    def _profile_runtime(self, profile: str) -> tuple[Path, int]:
        root = self.config.hermes_home or (self.config.data_dir / "hermes")
        if profile == "ads":
            return root, self.config.hermes_ads_api_port
        raise RuntimeError(f"Unknown Hermes profile: {profile}")

    def reconcile(self) -> None:
        assignment = self.control_plane.poll_agent_job()
        if assignment is None:
            return
        self.control_plane.sync_agent_job(assignment.job_id, status="running")
        client: HermesApiClient | None = None
        try:
            home, port = self._profile_runtime(assignment.profile)
            client = HermesApiClient(home, port)
            result = self._execute(client, assignment)
            self.control_plane.sync_agent_job(
                assignment.job_id,
                status="succeeded",
                result_json=result,
            )
        except HermesApiError as exc:
            print(
                f"[worker] agent job {assignment.job_id} failed: {exc.diagnostic}",
                file=sys.stderr,
            )
            self.control_plane.sync_agent_job(
                assignment.job_id,
                status="failed",
                last_error=exc.public_message,
            )
        except (httpx.HTTPError, OSError, RuntimeError, ValueError) as exc:
            print(
                f"[worker] agent job {assignment.job_id} failed: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            self.control_plane.sync_agent_job(
                assignment.job_id,
                status="failed",
                last_error=str(exc),
            )
        finally:
            if client is not None:
                client.close()

    @staticmethod
    def _execute(client: HermesApiClient, assignment: AgentJobAssignment) -> dict:
        if assignment.job_type == "sync_sessions":
            return {
                "sessions": client.sessions(
                    session_limit=int(assignment.payload.get("session_limit") or 100),
                    message_limit=int(assignment.payload.get("message_limit") or 200),
                )
            }
        if assignment.job_type == "chat_turn":
            session_id = assignment.hermes_session_id or client.create_session(
                str(assignment.payload.get("title") or "Cuộc trò chuyện Ads Lush")
            )
            return client.chat(session_id, str(assignment.payload["message"]))
        raise RuntimeError(f"Unsupported agent job type: {assignment.job_type}")
