from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.models import AIProviderConfig, WorkerEnrollment, WorkerOperation
from backend.app.services import auth, remote_ops
from workers.agent.hermes_config import HermesConfigManager
from workers.agent import control_plane_mcp


TENANT_ID = "00000000-0000-0000-0000-0000000000f8"
PASSWORD = "Strong-fleet-password-2026"
WORKER_SECRET = "fleet-legacy-secret"
FERNET_KEY = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="


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
                secret_encryption_key=FERNET_KEY,
                worker_bootstrap_repo_url="https://github.com/example/meta-ads-copilot.git",
                artifact_root=str(tmp_path / "artifacts"),
            )
        )
    )


def test_default_worker_repo_and_deepseek_flash_preset():
    settings = Settings()
    assert settings.worker_bootstrap_repo_url == (
        "https://github.com/pearhoang/ads-facebook-automation.git"
    )
    template = Path("backend/app/templates/ai_copilot.html").read_text(encoding="utf-8")
    assert "DeepSeek V4 Flash 0731" in template
    assert "https://api.deepseek.com" in template
    assert "deepseek-v4-flash" in template


def provision_and_login(client: TestClient) -> dict[str, str]:
    with client.app.state.database.session_factory() as db:
        auth.provision_admin(
            db,
            tenant_id=TENANT_ID,
            tenant_name="Fleet workspace",
            email="owner@example.test",
            display_name="Owner",
            password=PASSWORD,
        )
    response = client.post(
        "/api/auth/login",
        json={"email": "owner@example.test", "password": PASSWORD},
    )
    assert response.status_code == 200
    return {"X-CSRF-Token": client.cookies.get("ads_lush_csrf")}


def enroll_node(client: TestClient, headers: dict[str, str], key: str = "ads-node-01"):
    issued = client.post(
        "/api/bot-nodes/enrollments",
        headers=headers,
        json={"worker_key": key, "display_name": "Ads Node 01"},
    )
    assert issued.status_code == 201, issued.text
    payload = issued.json()
    assert payload["enrollment_token"] in payload["install_command"]
    enrolled = client.post(
        "/api/bot-nodes/enroll",
        json={
            "enrollment_token": payload["enrollment_token"],
            "runtime_version": "0.2.0",
            "agent_version": "managed",
            "capabilities": {"browser": True, "durable_outbox": True},
        },
    )
    assert enrolled.status_code == 201, enrolled.text
    return payload, enrolled.json()


def test_enrollment_per_node_auth_lifecycle_and_reuse_guard(tmp_path: Path, monkeypatch):
    with build_client(tmp_path) as client:
        headers = provision_and_login(client)
        issued, enrolled = enroll_node(client, headers)
        worker = enrolled["worker"]
        credential_headers = {"X-Worker-Credential": enrolled["worker_credential"]}

        reused = client.post(
            "/api/bot-nodes/enroll",
            json={"enrollment_token": issued["enrollment_token"]},
        )
        assert reused.status_code == 409

        heartbeat = client.post(
            f"/api/workers/{worker['id']}/heartbeat",
            headers=credential_headers,
            json={"runtime_version": "0.2.1", "capabilities": {"browser": True}},
        )
        assert heartbeat.status_code == 200
        assert heartbeat.json()["runtime_version"] == "0.2.1"

        other = client.post(
            "/api/workers/register",
            headers={"X-Worker-Secret": WORKER_SECRET},
            json={"worker_key": "legacy-other", "display_name": "Other"},
        ).json()
        cross_node = client.post(
            f"/api/workers/{other['id']}/heartbeat",
            headers=credential_headers,
        )
        assert cross_node.status_code == 403

        edited = client.patch(
            f"/api/bot-nodes/{worker['id']}",
            headers=headers,
            json={
                "display_name": "Ads Node Edited",
                "host": "203.0.113.20",
                "ssh_user": "deploy",
            },
        )
        assert edited.status_code == 200
        assert edited.json()["host"] == "203.0.113.20"

        drained = client.post(f"/api/bot-nodes/{worker['id']}/drain", headers=headers)
        assert drained.status_code == 200
        assert drained.json()["lifecycle_status"] == "draining"
        assert client.post(
            f"/api/workers/{worker['id']}/execution-jobs/poll",
            headers=credential_headers,
        ).json() is None

        monkeypatch.setattr(remote_ops, "run_decommission", lambda *args: None)
        decommission_password = "one-use-decommission-password"
        decommission = client.post(
            f"/api/bot-nodes/{worker['id']}/decommission",
            headers=headers,
            json={"ssh_password": decommission_password},
        )
        assert decommission.status_code == 202, decommission.text
        assert decommission_password not in decommission.text

        revoked = client.delete(f"/api/bot-nodes/{worker['id']}", headers=headers)
        assert revoked.status_code == 200
        assert revoked.json()["lifecycle_status"] == "revoked"
        assert client.post(
            f"/api/workers/{worker['id']}/heartbeat",
            headers=credential_headers,
        ).status_code == 401


def test_ai_key_is_masked_encrypted_and_scoped_to_selected_worker(tmp_path: Path):
    with build_client(tmp_path) as client:
        headers = provision_and_login(client)
        _, enrolled = enroll_node(client, headers)
        worker = enrolled["worker"]
        raw_key = "sk-test-super-secret-value"
        saved = client.put(
            "/api/ai-provider",
            headers=headers,
            json={
                "provider_type": "openai_compatible",
                "provider_name": "9router",
                "base_url": "https://router.example.test/v1",
                "model": "test-model",
                "api_key": raw_key,
                "thinking_mode": "enabled",
                "reasoning_effort": "high",
                "execution_scope": "worker",
                "worker_id": worker["id"],
            },
        )
        assert saved.status_code == 200, saved.text
        assert raw_key not in saved.text
        assert saved.json()["api_key_masked"].endswith("-value")

        runtime = client.get(
            f"/api/workers/{worker['id']}/ai-provider",
            headers={"X-Worker-Credential": enrolled["worker_credential"]},
        )
        assert runtime.status_code == 200
        assert runtime.json()["api_key"] == raw_key
        assert runtime.json()["thinking_mode"] == "enabled"
        assert runtime.json()["reasoning_effort"] == "high"

        context = client.get(
            f"/api/workers/{worker['id']}/agent-tools/context",
            headers={"X-Worker-Credential": enrolled["worker_credential"]},
        )
        assert context.status_code == 200
        assert context.json()["safety"]["publish_allowed"] is False
        assert client.get(
            f"/api/workers/{worker['id']}/agent-tools/context",
            headers={"X-Worker-Secret": WORKER_SECRET},
        ).status_code == 403
        latest = client.post(
            f"/api/workers/{worker['id']}/agent-tools/latest-kpi",
            headers={"X-Worker-Credential": enrolled["worker_credential"]},
            json={"ad_account_id": None},
        )
        assert latest.status_code == 200
        assert latest.json() == {"items": []}

        with client.app.state.database.session_factory() as db:
            config = db.query(AIProviderConfig).one()
            assert config.api_key_ciphertext != raw_key
            assert raw_key not in config.api_key_ciphertext


def test_remote_install_keeps_ssh_password_transient(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}

    def fake_install(*args):
        captured["args"] = args

    monkeypatch.setattr(remote_ops, "run_install", fake_install)
    with build_client(tmp_path) as client:
        headers = provision_and_login(client)
        page = client.get("/bot-nodes")
        assert page.status_code == 200
        for copy in (
            "Thêm Bot VPS",
            "SSH password",
            "Hermes Agent",
            "Gỡ worker khỏi VPS",
            "DeepSeek V4 Flash 0731",
            "deepseek-v4-flash",
        ):
            assert copy in page.text
        ssh_password = "temporary-ssh-password"
        provider_api_key = "sk-provider-secret"
        response = client.post(
            "/api/bot-nodes/install",
            headers=headers,
            json={
                "worker_key": "remote-ads-node",
                "display_name": "Remote Ads Node",
                "host": "203.0.113.10",
                "ssh_user": "root",
                "ssh_password": ssh_password,
                "repo_url": "https://github.com/example/meta-ads-copilot.git",
                "repo_branch": "main",
                "provider_name": "9router",
                "provider_base_url": "https://router.example.test/v1",
                "provider_model": "test-model",
                "provider_api_key": provider_api_key,
            },
        )
        assert response.status_code == 202, response.text
        assert ssh_password not in response.text
        assert provider_api_key not in response.text
        assert captured["args"][-7] == ssh_password
        assert captured["args"][-1] == provider_api_key

        with client.app.state.database.session_factory() as db:
            operation = db.query(WorkerOperation).one()
            enrollment = db.query(WorkerEnrollment).one()
            persisted = " ".join(
                str(value)
                for record in (operation, enrollment)
                for value in vars(record).values()
            )
            assert ssh_password not in persisted
            assert provider_api_key not in persisted


def test_hermes_config_adds_reasoning_and_typed_mcp_without_terminal(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("workers.agent.hermes_config.subprocess.run", lambda *args, **kwargs: None)
    manager = HermesConfigManager(tmp_path / "hermes")
    changed = manager.apply(
        {
            "provider_name": "deepseek",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
            "thinking_mode": "enabled",
            "reasoning_effort": "high",
            "api_key": "sk-test-only",
        }
    )
    assert changed is True
    config = __import__("yaml").safe_load(manager.config_path.read_text(encoding="utf-8"))
    assert config["model"]["provider"] == "custom:ads-lush"
    assert config["agent"]["reasoning_effort"] == "high"
    assert "terminal" in config["agent"]["disabled_toolsets"]
    assert config["providers"]["ads-lush"]["extra_body"]["thinking"]["type"] == "enabled"
    mcp_config = config["mcp_servers"]["ads_control_plane"]
    assert "ads_create_campaign_draft" in mcp_config["tools"]["include"]
    assert mcp_config["env"] == {
        "CONTROL_PLANE_URL": "${CONTROL_PLANE_URL}",
        "WORKER_DATA_DIR": "${WORKER_DATA_DIR}",
        "WORKER_CREDENTIAL_FILE": "${WORKER_CREDENTIAL_FILE}",
    }
    assert "sk-test-only" not in manager.config_path.read_text(encoding="utf-8")
    assert "sk-test-only" in manager.env_path.read_text(encoding="utf-8")
    assert "không publish" in manager.soul_path.read_text(encoding="utf-8")


def test_mcp_bridge_lists_only_ads_typed_tools():
    class FakeClient:
        def call_agent_tool(self, path, payload=None):
            return {"path": path, "payload": payload}

    listed = control_plane_mcp._handle(
        FakeClient(),
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    names = {tool["name"] for tool in listed["result"]["tools"]}
    assert names == {
        "ads_workspace_context",
        "ads_latest_kpi",
        "ads_list_campaign_drafts",
        "ads_request_kpi_collection",
        "ads_create_campaign_draft",
    }
    called = control_plane_mcp._handle(
        FakeClient(),
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "ads_latest_kpi", "arguments": {}},
        },
    )
    assert called["result"]["isError"] is False
    assert '"path":"latest-kpi"' in called["result"]["content"][0]["text"]
