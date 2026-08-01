from __future__ import annotations

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
