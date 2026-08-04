from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path

import paramiko
import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.models import AIProviderConfig, Worker, WorkerEnrollment, WorkerOperation
from backend.app.services import auth, remote_ops, ssh_credentials
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
    template = Path("backend/app/templates/hermes_agents.html").read_text(encoding="utf-8")
    assert "DeepSeek V4 Flash 0731" in template
    assert "https://api.deepseek.com" in template
    assert "deepseek-v4-flash" in template
    assert "Đổi mật khẩu Dashboard" in template
    assert "SSH credential đã mã hóa" in template
    assert 'id="dashboard-new-password" type="password" required minlength="4"' in template
    assert "Codex Search &amp; Vision" in template
    assert "Kết nối Codex" in template
    assert "Ngắt kết nối Codex" in template
    assert "Xóa token và ngắt kết nối" in template
    assert "codex login --device-auth" in template


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
                "ssh_password": "saved-decommission-password",
            },
        )
        assert edited.status_code == 200
        assert edited.json()["host"] == "203.0.113.20"
        assert edited.json()["ssh_password_configured"] is True

        drained = client.post(f"/api/bot-nodes/{worker['id']}/drain", headers=headers)
        assert drained.status_code == 200
        assert drained.json()["lifecycle_status"] == "draining"
        assert client.post(
            f"/api/workers/{worker['id']}/execution-jobs/poll",
            headers=credential_headers,
        ).json() is None

        monkeypatch.setattr(remote_ops, "run_decommission", lambda *args: None)
        decommission = client.post(
            f"/api/bot-nodes/{worker['id']}/decommission",
            headers=headers,
        )
        assert decommission.status_code == 202, decommission.text

        revoked = client.delete(f"/api/bot-nodes/{worker['id']}", headers=headers)
        assert revoked.status_code == 200
        assert revoked.json()["lifecycle_status"] == "revoked"
        assert revoked.json()["ssh_password_configured"] is False
        with client.app.state.database.session_factory() as db:
            assert db.get(Worker, worker["id"]).ssh_password_ciphertext is None
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
                "agent_permission_mode": "experimental_full",
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
        assert runtime.json()["agent_permission_mode"] == "experimental_full"

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


def test_remote_install_stores_ssh_password_encrypted(tmp_path: Path, monkeypatch):
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
            "Telegram Bot Token",
            "Telegram user ID được phép",
        ):
            assert copy in page.text
        ssh_password = "temporary-ssh-password"
        provider_api_key = "sk-provider-secret"
        telegram_bot_token = "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcd"
        telegram_allowed_users = "123456789,987654321"
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
                "telegram_bot_token": telegram_bot_token,
                "telegram_allowed_users": telegram_allowed_users,
            },
        )
        assert response.status_code == 202, response.text
        assert ssh_password not in response.text
        assert provider_api_key not in response.text
        assert telegram_bot_token not in response.text
        assert captured["args"][-9] == ssh_password
        assert captured["args"][-3] == provider_api_key
        assert captured["args"][-2] == telegram_bot_token
        assert captured["args"][-1] == telegram_allowed_users

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
            assert telegram_bot_token not in persisted
            assert telegram_allowed_users not in persisted
            assert enrollment.ssh_password_ciphertext
            assert ssh_credentials.decrypt_password(
                FERNET_KEY.encode("ascii"), enrollment.ssh_password_ciphertext
            ) == ssh_password


def test_rotate_dashboard_password_is_transient_and_scoped_to_worker(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}

    def fake_rotate(*args):
        captured["args"] = args

    monkeypatch.setattr(remote_ops, "run_rotate_dashboard_password", fake_rotate)
    with build_client(tmp_path) as client:
        headers = provision_and_login(client)
        _, enrolled = enroll_node(client, headers)
        worker = enrolled["worker"]
        edited = client.patch(
            f"/api/bot-nodes/{worker['id']}",
            headers=headers,
            json={
                "display_name": "Dashboard worker",
                "host": "203.0.113.30",
                "ssh_user": "root",
                "ssh_password": "saved-dashboard-ssh-password",
            },
        )
        assert edited.status_code == 200

        ssh_password = "saved-dashboard-ssh-password"
        new_password = "1234"
        mismatched = client.post(
            f"/api/bot-nodes/{worker['id']}/hermes-dashboard/password",
            headers=headers,
            json={
                "new_password": new_password,
                "new_password_confirmation": "Different-dashboard-password-2026",
            },
        )
        assert mismatched.status_code == 422

        response = client.post(
            f"/api/bot-nodes/{worker['id']}/hermes-dashboard/password",
            headers=headers,
            json={
                "new_password": new_password,
                "new_password_confirmation": new_password,
            },
        )
        assert response.status_code == 202, response.text
        assert response.json()["operation_type"] == "rotate_dashboard_password"
        assert ssh_password not in response.text
        assert new_password not in response.text
        assert captured["args"][-2] == ssh_password
        assert captured["args"][-1] == new_password

        with client.app.state.database.session_factory() as db:
            operation = db.query(WorkerOperation).one()
            persisted = " ".join(str(value) for value in vars(operation).values())
            assert ssh_password not in persisted
            assert new_password not in persisted


def test_codex_device_login_is_transient_and_scoped_to_worker(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}

    def fake_connect(*args):
        captured["args"] = args

    monkeypatch.setattr(remote_ops, "run_codex_device_login", fake_connect)
    with build_client(tmp_path) as client:
        headers = provision_and_login(client)
        _, enrolled = enroll_node(client, headers)
        worker = enrolled["worker"]
        assert client.patch(
            f"/api/bot-nodes/{worker['id']}",
            headers=headers,
            json={
                "display_name": "Codex worker",
                "host": "203.0.113.31",
                "ssh_user": "root",
                "ssh_password": "saved-codex-ssh-password",
            },
        ).status_code == 200

        ssh_password = "saved-codex-ssh-password"
        response = client.post(
            f"/api/bot-nodes/{worker['id']}/codex/device-login",
            headers=headers,
        )
        assert response.status_code == 202, response.text
        assert response.json()["operation_type"] == "codex_device_login"
        assert ssh_password not in response.text
        assert captured["args"][-1] == ssh_password

        with client.app.state.database.session_factory() as db:
            operation = db.query(WorkerOperation).one()
            persisted = " ".join(str(value) for value in vars(operation).values())
            assert ssh_password not in persisted


def test_worker_edit_encrypts_ssh_password_and_api_only_returns_status(tmp_path: Path):
    with build_client(tmp_path) as client:
        headers = provision_and_login(client)
        _, enrolled = enroll_node(client, headers)
        worker = enrolled["worker"]
        ssh_password = "saved-worker-password"

        response = client.patch(
            f"/api/bot-nodes/{worker['id']}",
            headers=headers,
            json={
                "display_name": "Stored credential worker",
                "host": "203.0.113.32",
                "ssh_user": "root",
                "ssh_password": ssh_password,
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["ssh_password_configured"] is True
        assert ssh_password not in response.text

        with client.app.state.database.session_factory() as db:
            stored = db.get(Worker, worker["id"])
            assert stored.ssh_password_ciphertext != ssh_password
            original_ciphertext = stored.ssh_password_ciphertext
            assert ssh_credentials.decrypt_password(
                FERNET_KEY.encode("ascii"), stored.ssh_password_ciphertext
            ) == ssh_password

        unchanged = client.patch(
            f"/api/bot-nodes/{worker['id']}",
            headers=headers,
            json={
                "display_name": "Stored credential worker renamed",
                "host": "203.0.113.32",
                "ssh_user": "root",
            },
        )
        assert unchanged.status_code == 200, unchanged.text
        assert unchanged.json()["ssh_password_configured"] is True
        with client.app.state.database.session_factory() as db:
            assert db.get(Worker, worker["id"]).ssh_password_ciphertext == original_ciphertext


def test_codex_action_without_stored_ssh_rejects_before_operation(tmp_path: Path):
    with build_client(tmp_path) as client:
        headers = provision_and_login(client)
        _, enrolled = enroll_node(client, headers)
        worker = enrolled["worker"]
        assert client.patch(
            f"/api/bot-nodes/{worker['id']}",
            headers=headers,
            json={
                "display_name": "Missing credential worker",
                "host": "203.0.113.33",
                "ssh_user": "root",
            },
        ).status_code == 200

        response = client.post(
            f"/api/bot-nodes/{worker['id']}/codex/device-login",
            headers=headers,
        )
        assert response.status_code == 409
        assert "chưa lưu SSH password" in response.text
        with client.app.state.database.session_factory() as db:
            assert db.query(WorkerOperation).count() == 0


def test_codex_disconnect_is_transient_and_scoped_to_worker(tmp_path: Path, monkeypatch):
    captured: dict[str, object] = {}

    def fake_disconnect(*args):
        captured["args"] = args

    monkeypatch.setattr(remote_ops, "run_codex_disconnect", fake_disconnect)
    with build_client(tmp_path) as client:
        headers = provision_and_login(client)
        _, enrolled = enroll_node(client, headers)
        worker = enrolled["worker"]
        assert client.patch(
            f"/api/bot-nodes/{worker['id']}",
            headers=headers,
            json={
                "display_name": "Codex worker",
                "host": "203.0.113.31",
                "ssh_user": "root",
                "ssh_password": "saved-codex-disconnect-password",
            },
        ).status_code == 200

        ssh_password = "saved-codex-disconnect-password"
        response = client.post(
            f"/api/bot-nodes/{worker['id']}/codex/disconnect",
            headers=headers,
        )
        assert response.status_code == 202, response.text
        assert response.json()["operation_type"] == "codex_disconnect"
        assert ssh_password not in response.text
        assert captured["args"][-1] == ssh_password

        with client.app.state.database.session_factory() as db:
            operation = db.query(WorkerOperation).one()
            persisted = " ".join(str(value) for value in vars(operation).values())
            assert ssh_password not in persisted


def test_codex_disconnect_script_targets_only_worker_credential():
    script = remote_ops._codex_disconnect_script()
    assert "codex logout" in script
    assert "/opt/meta-ads-copilot-runtime/worker-data/codex/auth.json" in script
    assert "/opt/meta-ads-copilot-runtime/worker-data/codex/.credential-disconnected" in script
    assert "rm -rf" not in script


def test_dashboard_password_hash_matches_hermes_scrypt_contract():
    password = "Hash-contract-dashboard-password-2026"
    encoded = remote_ops.hash_dashboard_password(password)
    scheme, n_value, r_value, p_value, salt_value, digest_value = encoded.split("$")
    assert (scheme, n_value, r_value, p_value) == ("scrypt", "16384", "8", "1")
    salt = base64.b64decode(salt_value)
    expected = base64.b64decode(digest_value)
    actual = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=int(n_value),
        r=int(r_value),
        p=int(p_value),
        dklen=len(expected),
        maxmem=0,
    )
    assert actual == expected
    assert password not in encoded


def test_dashboard_rotation_rejects_changed_host_key_before_credentials():
    key = paramiko.RSAKey.generate(1024)
    fingerprint = remote_ops._host_key_fingerprint(key)
    client = paramiko.SSHClient()
    remote_ops._ExpectedHostKeyPolicy(fingerprint).missing_host_key(client, "worker", key)
    with pytest.raises(paramiko.SSHException, match="trước khi gửi credential"):
        remote_ops._ExpectedHostKeyPolicy("SHA256:not-the-worker").missing_host_key(
            client,
            "worker",
            key,
        )


def test_codex_device_prompt_keeps_only_public_url_and_one_time_code():
    prompt = remote_ops._codex_device_prompt(
        "Open https://auth.openai.com/codex/device and enter ABCD-EFGHJ to continue"
    )
    assert prompt == (
        "Xác thực Codex trên trình duyệt của bạn.\n"
        "Mở: https://auth.openai.com/codex/device\n"
        "Mã: ABCD-EFGHJ\n"
        "Đang chờ bạn hoàn tất đăng nhập…"
    )


def test_codex_device_prompt_still_accepts_legacy_eight_character_code():
    prompt = remote_ops._codex_device_prompt(
        "Open https://auth.openai.com/codex/device and enter WXYZ-1234 to continue"
    )
    assert "Mã: WXYZ-1234" in prompt


def test_hermes_config_adds_reasoning_and_typed_mcp_without_terminal_by_default(tmp_path: Path, monkeypatch):
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
    codex_mcp = config["mcp_servers"]["codex_capabilities"]
    assert codex_mcp["args"] == ["-m", "workers.agent.codex_capabilities_mcp"]
    assert codex_mcp["env"] == {
        "CODEX_HOME": "${CODEX_HOME}",
        "WORKER_DATA_DIR": "${WORKER_DATA_DIR}",
    }
    assert codex_mcp["tools"]["include"] == ["codex_search", "codex_vision"]
    assert "sk-test-only" not in manager.config_path.read_text(encoding="utf-8")
    assert "sk-test-only" in manager.env_path.read_text(encoding="utf-8")
    assert "không publish" in manager.soul_path.read_text(encoding="utf-8")
    assert config["gateway"]["api_server"]["host"] == "127.0.0.1"
    assert config["gateway"]["api_server"]["port"] == 8642
    assert config["gateway"]["api_server"]["model_name"] == "ads-copilot"
    assert config["gateway"]["api_server"]["extra"]["model_routes"] == {
        "ads-copilot": {
            "model": "deepseek-v4-flash",
            "provider": "custom:ads-lush",
        }
    }
    assert manager.api_key_path.exists()
    assert config["gateway"]["api_server"]["key"] == manager.api_key_path.read_text(encoding="utf-8")
    service = Path("infra/systemd/meta-ads-copilot-hermes.service").read_text(encoding="utf-8")
    assert "EnvironmentFile=-/opt/meta-ads-copilot-runtime/worker-data/hermes/.env" in service
    dashboard_service = Path(
        "infra/systemd/meta-ads-copilot-hermes-dashboard.service"
    ).read_text(encoding="utf-8")
    assert "HERMES_DASHBOARD_BIND_HOST" in dashboard_service
    assert "--skip-build --no-open" in dashboard_service
    assert "hermes-dashboard.env" in dashboard_service
    caddy = Path("infra/caddy/ads.lushmedia.net.Caddyfile").read_text(encoding="utf-8")
    assert "hermes.ads.lushmedia.net" in caddy
    assert "host.docker.internal:9119" in caddy
    assert "@hermes_websocket header Upgrade websocket" in caddy
    assert "header_up Origin http://172.17.0.1:9119" in caddy


def test_hermes_config_schema_upgrade_rewrites_unchanged_provider(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("workers.agent.hermes_config.subprocess.run", lambda *args, **kwargs: None)
    provider = {
        "provider_name": "deepseek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
        "api_key": "sk-test-only",
    }
    manager = HermesConfigManager(tmp_path / "hermes")
    manager.home.mkdir(parents=True)
    legacy = json.dumps(
        {"schema_version": 7, "provider": provider},
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")
    manager.managed_hash_path.write_text(hashlib.sha256(legacy).hexdigest(), encoding="utf-8")
    manager.api_key_path.write_text("existing-api-key", encoding="utf-8")
    manager.config_path.write_text("mcp_servers: {}\n", encoding="utf-8")

    assert manager.apply(provider) is True
    config = __import__("yaml").safe_load(manager.config_path.read_text(encoding="utf-8"))
    assert "codex_capabilities" in config["mcp_servers"]


def test_hermes_experimental_full_access_removes_managed_toolset_blocks(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("workers.agent.hermes_config.subprocess.run", lambda *args, **kwargs: None)
    manager = HermesConfigManager(tmp_path / "hermes")
    base_provider = {
        "provider_name": "deepseek",
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-flash",
        "thinking_mode": "enabled",
        "reasoning_effort": "high",
        "api_key": "sk-test-only",
    }
    assert manager.apply(base_provider) is True
    full_provider = {**base_provider, "agent_permission_mode": "experimental_full"}
    assert manager.apply(full_provider) is True

    config = __import__("yaml").safe_load(manager.config_path.read_text(encoding="utf-8"))
    managed_toolsets = {
        "terminal",
        "file",
        "browser",
        "code_execution",
        "delegation",
        "computer_use",
    }
    assert managed_toolsets.isdisjoint(config["agent"]["disabled_toolsets"])
    assert "ads_create_campaign_draft" in config["mcp_servers"]["ads_control_plane"]["tools"]["include"]
    soul = manager.soul_path.read_text(encoding="utf-8")
    assert "Experimental Full Access" in soul
    assert "không tự sửa source production" in soul
    assert "Không dùng quyền hệ thống hoặc browser để đi vòng" in soul

    assert manager.apply({**base_provider, "agent_permission_mode": "ads_safe"}) is True
    safe_config = __import__("yaml").safe_load(manager.config_path.read_text(encoding="utf-8"))
    assert managed_toolsets.issubset(set(safe_config["agent"]["disabled_toolsets"]))
    assert "Chế độ `Ads Safe`" in manager.soul_path.read_text(encoding="utf-8")


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
