from __future__ import annotations

import base64
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.models import AgentMessage
from backend.app.services import auth


TENANT_ID = "00000000-0000-0000-0000-0000000000c1"
PASSWORD = "Strong-copilot-password-2026"
WORKER_SECRET = "copilot-legacy-secret"


def build_client(tmp_path: Path) -> TestClient:
    return TestClient(
        create_app(
            Settings(
                app_env="test",
                database_url="sqlite://",
                worker_shared_secret=WORKER_SECRET,
                dev_tenant_id=TENANT_ID,
                app_origin="http://testserver",
                session_cookie_secure=False,
                artifact_root=str(tmp_path / "artifacts"),
            )
        )
    )


def provision(client: TestClient) -> tuple[dict[str, str], dict[str, str], dict]:
    with client.app.state.database.session_factory() as db:
        auth.provision_admin(
            db,
            tenant_id=TENANT_ID,
            tenant_name="Copilot workspace",
            email="owner@example.test",
            display_name="Owner",
            password=PASSWORD,
        )
    login = client.post(
        "/api/auth/login",
        json={"email": "owner@example.test", "password": PASSWORD},
    )
    assert login.status_code == 200
    csrf = {"X-CSRF-Token": client.cookies.get("ads_lush_csrf")}
    enrollment = client.post(
        "/api/bot-nodes/enrollments",
        headers=csrf,
        json={"worker_key": "copilot-node", "display_name": "Copilot Node"},
    ).json()
    enrolled = client.post(
        "/api/bot-nodes/enroll",
        json={"enrollment_token": enrollment["enrollment_token"]},
    ).json()
    worker_headers = {"X-Worker-Credential": enrolled["worker_credential"]}
    return csrf, worker_headers, enrolled["worker"]


def test_web_chat_uses_outbound_worker_job_and_mirrors_hermes_reply(tmp_path: Path):
    with build_client(tmp_path) as client:
        csrf, worker_headers, worker = provision(client)
        page = client.get("/ai-copilot")
        assert page.status_code == 200
        assert "Bạn cứ nói theo cách tự nhiên" in page.text
        assert "VPS Copilot" not in page.text

        created = client.post(
            "/api/ai-copilot/conversations",
            headers=csrf,
            json={"worker_id": worker["id"], "profile": "ads", "title": "Camp mùa hè"},
        )
        assert created.status_code == 201, created.text
        conversation = created.json()

        rejected_profile = client.post(
            "/api/ai-copilot/conversations",
            headers=csrf,
            json={"worker_id": worker["id"], "profile": "vps", "title": "Không hợp lệ"},
        )
        assert rejected_profile.status_code == 422

        queued = client.post(
            f"/api/ai-copilot/conversations/{conversation['id']}/messages",
            headers=csrf,
            json={"content": "Báo cáo quảng cáo hôm qua"},
        )
        assert queued.status_code == 202, queued.text
        job = queued.json()

        polled = client.post(
            f"/api/workers/{worker['id']}/agent-jobs/poll",
            headers=worker_headers,
        )
        assert polled.status_code == 200, polled.text
        assert polled.json()["id"] == job["id"]
        assert polled.json()["payload_json"]["message"] == "Báo cáo quảng cáo hôm qua"

        running = client.post(
            f"/api/workers/{worker['id']}/agent-jobs/{job['id']}/sync",
            headers=worker_headers,
            json={"status": "running"},
        )
        assert running.status_code == 200
        succeeded = client.post(
            f"/api/workers/{worker['id']}/agent-jobs/{job['id']}/sync",
            headers=worker_headers,
            json={
                "status": "succeeded",
                "result_json": {
                    "session_id": "telegram:12345",
                    "message": {"role": "assistant", "content": "Tôi đã lấy báo cáo hôm qua."},
                    "usage": {"total_tokens": 42},
                },
            },
        )
        assert succeeded.status_code == 200, succeeded.text

        messages = client.get(
            f"/api/ai-copilot/conversations/{conversation['id']}/messages"
        ).json()
        assert [item["role"] for item in messages] == ["user", "assistant"]
        assert messages[-1]["content"] == "Tôi đã lấy báo cáo hôm qua."
        conversations = client.get(
            f"/api/ai-copilot/conversations?worker_id={worker['id']}&profile=ads"
        ).json()
        assert conversations[0]["hermes_session_id"] == "telegram:12345"


def test_sync_imports_existing_telegram_session(tmp_path: Path):
    with build_client(tmp_path) as client:
        csrf, worker_headers, worker = provision(client)
        sync = client.post(
            "/api/ai-copilot/sync",
            headers=csrf,
            json={"worker_id": worker["id"], "profile": "ads"},
        )
        assert sync.status_code == 202
        job_id = sync.json()["id"]
        assert client.post(
            f"/api/workers/{worker['id']}/agent-jobs/poll", headers=worker_headers
        ).json()["id"] == job_id
        result = client.post(
            f"/api/workers/{worker['id']}/agent-jobs/{job_id}/sync",
            headers=worker_headers,
            json={
                "status": "succeeded",
                "result_json": {
                    "sessions": [
                        {
                            "id": "telegram:98765",
                            "title": "Tối ưu camp bán hàng",
                            "source": "telegram",
                            "messages": [
                                {"id": "m1", "role": "user", "content": "Camp nào CPA cao?"},
                                {"id": "m-tool-1", "role": "tool", "content": "{\"name\":\"mcp__ads_control_plane__ads_latest_kpi\"}"},
                                {"id": "m-tool-2", "role": "tool", "content": "<untrusted_tool_result>raw KPI</untrusted_tool_result>"},
                                {"id": "m-meta", "role": "session_meta", "content": "internal"},
                                {"id": "m2", "role": "assistant", "content": "Tôi sẽ kiểm tra KPI."},
                            ],
                        }
                    ]
                },
            },
        )
        assert result.status_code == 200, result.text
        conversations = client.get(
            f"/api/ai-copilot/conversations?worker_id={worker['id']}&profile=ads"
        ).json()
        assert conversations[0]["source"] == "telegram"
        with client.app.state.database.session_factory() as db:
            db.add(
                AgentMessage(
                    tenant_id=TENANT_ID,
                    conversation_id=conversations[0]["id"],
                    role="tool",
                    source="telegram",
                    content="legacy raw tool result",
                )
            )
            db.commit()
        messages = client.get(
            f"/api/ai-copilot/conversations/{conversations[0]['id']}/messages"
        ).json()
        assert [item["content"] for item in messages] == [
            "Camp nào CPA cao?",
            "Tôi sẽ kiểm tra KPI.",
        ]


def test_web_chat_accepts_utf8_data_attachment_and_preserves_clean_transcript(tmp_path: Path):
    with build_client(tmp_path) as client:
        csrf, worker_headers, worker = provision(client)
        conversation = client.post(
            "/api/ai-copilot/conversations",
            headers=csrf,
            json={"worker_id": worker["id"], "profile": "ads", "title": "Đọc báo cáo"},
        ).json()
        csv_bytes = "campaign,spend\nCamp A,125000\n".encode("utf-8")
        queued = client.post(
            f"/api/ai-copilot/conversations/{conversation['id']}/messages",
            headers=csrf,
            json={
                "content": "Phân tích chi phí trong tệp này",
                "attachments": [
                    {
                        "name": "bao-cao.csv",
                        "media_type": "text/csv",
                        "content_base64": base64.b64encode(csv_bytes).decode("ascii"),
                    }
                ],
            },
        )
        assert queued.status_code == 202, queued.text
        job_id = queued.json()["id"]
        assignment = client.post(
            f"/api/workers/{worker['id']}/agent-jobs/poll",
            headers=worker_headers,
        ).json()
        hermes_message = assignment["payload_json"]["message"]
        assert f"ads-lush-message:{job_id}" in hermes_message
        assert "<user_attachment" in hermes_message
        assert "Camp A,125000" in hermes_message
        assert assignment["payload_json"]["attachments"][0]["name"] == "bao-cao.csv"

        messages = client.get(
            f"/api/ai-copilot/conversations/{conversation['id']}/messages"
        ).json()
        assert len(messages) == 1
        assert messages[0]["content"] == "Phân tích chi phí trong tệp này"
        assert messages[0]["metadata_json"]["attachments"][0]["size_bytes"] == len(csv_bytes)

        client.post(
            f"/api/workers/{worker['id']}/agent-jobs/{job_id}/sync",
            headers=worker_headers,
            json={
                "status": "succeeded",
                "result_json": {
                    "session_id": "api_attachment_session",
                    "message": {"role": "assistant", "content": "Đã đọc báo cáo."},
                },
            },
        )
        sync = client.post(
            "/api/ai-copilot/sync",
            headers=csrf,
            json={"worker_id": worker["id"], "profile": "ads"},
        ).json()
        client.post(f"/api/workers/{worker['id']}/agent-jobs/poll", headers=worker_headers)
        synced = client.post(
            f"/api/workers/{worker['id']}/agent-jobs/{sync['id']}/sync",
            headers=worker_headers,
            json={
                "status": "succeeded",
                "result_json": {
                    "sessions": [
                        {
                            "id": "api_attachment_session",
                            "title": "Đọc báo cáo",
                            "source": "api_server",
                            "messages": [
                                {"id": "hm1", "role": "user", "content": hermes_message},
                                {"id": "hm2", "role": "assistant", "content": "Đã đọc báo cáo."},
                            ],
                        }
                    ]
                },
            },
        )
        assert synced.status_code == 200, synced.text
        messages = client.get(
            f"/api/ai-copilot/conversations/{conversation['id']}/messages"
        ).json()
        assert [item["content"] for item in messages] == [
            "Phân tích chi phí trong tệp này",
            "Đã đọc báo cáo.",
        ]


def test_web_chat_rejects_unsupported_or_invalid_attachment(tmp_path: Path):
    with build_client(tmp_path) as client:
        csrf, _worker_headers, worker = provision(client)
        conversation = client.post(
            "/api/ai-copilot/conversations",
            headers=csrf,
            json={"worker_id": worker["id"], "profile": "ads", "title": "Tệp lỗi"},
        ).json()
        unsupported = client.post(
            f"/api/ai-copilot/conversations/{conversation['id']}/messages",
            headers=csrf,
            json={
                "content": "Đọc tệp",
                "attachments": [
                    {"name": "report.pdf", "media_type": "application/pdf", "content_base64": "eA=="}
                ],
            },
        )
        assert unsupported.status_code == 422
        assert "TXT" in unsupported.json()["detail"]

        invalid = client.post(
            f"/api/ai-copilot/conversations/{conversation['id']}/messages",
            headers=csrf,
            json={
                "content": "Đọc tệp",
                "attachments": [
                    {"name": "report.csv", "media_type": "text/csv", "content_base64": "not-base64"}
                ],
            },
        )
        assert invalid.status_code == 422
        assert "không có dữ liệu hợp lệ" in invalid.json()["detail"]


def test_agent_job_view_never_exposes_local_hermes_url(tmp_path: Path):
    with build_client(tmp_path) as client:
        csrf, worker_headers, worker = provision(client)
        conversation = client.post(
            "/api/ai-copilot/conversations",
            headers=csrf,
            json={"worker_id": worker["id"], "profile": "ads", "title": "Lỗi Hermes"},
        ).json()
        queued = client.post(
            f"/api/ai-copilot/conversations/{conversation['id']}/messages",
            headers=csrf,
            json={"content": "Xin chào"},
        ).json()
        client.post(f"/api/workers/{worker['id']}/agent-jobs/poll", headers=worker_headers)
        client.post(
            f"/api/workers/{worker['id']}/agent-jobs/{queued['id']}/sync",
            headers=worker_headers,
            json={
                "status": "failed",
                "last_error": "Server error '500 Internal Server Error' for url 'http://127.0.0.1:8642/api/sessions/test/chat'",
            },
        )
        public_job = client.get(f"/api/ai-copilot/jobs/{queued['id']}")
        assert public_job.status_code == 200
        assert "127.0.0.1" not in public_job.text
        assert "Hermes Agents" in public_job.json()["last_error"]
