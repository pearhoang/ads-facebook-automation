from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.services import account_sessions, auth


TENANT_ID = "00000000-0000-0000-0000-0000000000aa"
PASSWORD = "Strong-production-test-password-2026"


def build_production_client() -> TestClient:
    settings = Settings(
        app_env="production",
        database_url="sqlite://",
        worker_shared_secret="production-worker-test-secret",
        dev_tenant_id=None,
        app_origin="https://testserver",
        session_cookie_secure=True,
        browser_session_ttl_minutes=20,
        secret_encryption_key="MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
    )
    app = create_app(settings)
    app.state.database.create_schema()
    return TestClient(app, base_url="https://testserver")


def provision(client: TestClient) -> None:
    with client.app.state.database.session_factory() as db:
        auth.provision_admin(
            db,
            tenant_id=TENANT_ID,
            tenant_name="Lush Media",
            email="admin@lushmedia.test",
            display_name="Quản trị viên",
            password=PASSWORD,
        )


def test_login_cookie_csrf_logout_and_workspace_guard():
    with build_production_client() as client:
        provision(client)

        unauthenticated_page = client.get("/", follow_redirects=False)
        assert unauthenticated_page.status_code == 303
        assert unauthenticated_page.headers["location"] == "/login"
        unauthenticated_hermes = client.get("/ai-copilot", follow_redirects=False)
        assert unauthenticated_hermes.status_code == 303
        assert unauthenticated_hermes.headers["location"] == "/login"
        assert client.get("/api/accounts").status_code == 401

        wrong_origin = client.post(
            "/api/auth/login",
            headers={"Origin": "https://evil.example"},
            json={"email": "admin@lushmedia.test", "password": PASSWORD},
        )
        assert wrong_origin.status_code == 403

        wrong_password = client.post(
            "/api/auth/login",
            headers={"Origin": "https://testserver"},
            json={"email": "admin@lushmedia.test", "password": "incorrect"},
        )
        assert wrong_password.status_code == 401
        assert wrong_password.json()["detail"] == "Email hoặc mật khẩu không đúng."

        logged_in = client.post(
            "/api/auth/login",
            headers={"Origin": "https://testserver"},
            json={"email": "ADMIN@LUSHMEDIA.TEST", "password": PASSWORD},
        )
        assert logged_in.status_code == 200
        assert logged_in.json()["tenant_id"] == TENANT_ID
        cookie_headers = logged_in.headers.get_list("set-cookie")
        session_cookie = next(item for item in cookie_headers if item.startswith("ads_lush_session="))
        assert "HttpOnly" in session_cookie
        assert "Secure" in session_cookie
        assert "SameSite=lax" in session_cookie

        workspace = client.get("/")
        assert workspace.status_code == 200
        assert "Quản trị viên" in workspace.text
        assert "Lush Media" in workspace.text
        assert "Hermes Dashboard" in workspace.text
        dashboard = client.get("/ai-copilot", follow_redirects=False)
        assert dashboard.status_code == 303
        assert dashboard.headers["location"] == "https://hermes.ads.lushmedia.net"
        assert client.get("/api/auth/me").status_code == 200
        assert client.get("/docs").status_code == 404

        worker = client.post(
            "/api/workers/register",
            headers={"X-Worker-Secret": "production-worker-test-secret"},
            json={"worker_key": "worker-auth-test", "display_name": "Auth Worker"},
        ).json()
        with client.app.state.database.session_factory() as db:
            account_sessions.assign_worker_to_tenant(db, worker["id"], TENANT_ID)

        missing_csrf = client.post(
            "/api/accounts",
            json={"label": "Không được tạo", "assigned_worker_id": worker["id"]},
        )
        assert missing_csrf.status_code == 403

        csrf_token = client.cookies.get("ads_lush_csrf")
        created = client.post(
            "/api/accounts",
            headers={"X-CSRF-Token": csrf_token},
            json={"label": "Facebook chính", "assigned_worker_id": worker["id"]},
        )
        assert created.status_code == 201

        logged_out = client.post(
            "/api/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )
        assert logged_out.status_code == 204
        assert client.get("/api/auth/me").status_code == 401
