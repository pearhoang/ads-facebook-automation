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
            email="admin",
            display_name="Quản trị viên",
            password=PASSWORD,
        )


def test_ads_meta_master_branding_is_consistent_across_rendered_pages():
    with build_production_client() as client:
        provision(client)

        login_page = client.get("/login")
        assert login_page.status_code == 200
        assert "Ads Meta Master" in login_page.text
        assert "Meta Ads Automation" in login_page.text
        assert (
            'rel="icon" type="image/svg+xml" href="/static/ads-meta-master.svg?v=meta-light-focus-2"'
            in login_page.text
        )
        assert "Ads Lush" not in login_page.text
        assert "Automation workspace" not in login_page.text

        logged_in = client.post(
            "/api/auth/login",
            headers={"Origin": "https://testserver"},
            json={"email": "admin", "password": PASSWORD},
        )
        assert logged_in.status_code == 200

        for path in ("/", "/campaigns", "/reports", "/bot-nodes", "/hermes-agents"):
            page = client.get(path)
            assert page.status_code == 200
            assert "Ads Meta Master" in page.text, path
            assert "Meta Ads Automation" in page.text, path
            assert "<strong>Admin</strong>" in page.text, path
            assert (
                'rel="icon" type="image/svg+xml" href="/static/ads-meta-master.svg?v=meta-light-focus-2"'
                in page.text
            ), path
            assert "Ads Lush" not in page.text, path
            assert "Automation workspace" not in page.text, path
            assert "Lush Media" not in page.text, path

        asset = client.get("/static/ads-meta-master.svg")
        assert asset.status_code == 200
        assert asset.headers["content-type"].startswith("image/svg+xml")
        assert 'viewBox="0 0 32 32"' in asset.text
        assert "<script" not in asset.text
        assert "xlink:href" not in asset.text
        assert "data:" not in asset.text


def test_meta_light_focus_theme_css_contract_is_served():
    with build_production_client() as client:
        response = client.get("/static/workspace.css")
        assert response.status_code == 200
        css = response.text.lower()

        for token in (
            "--background: #f1f4f8;",
            "--surface-subtle: #f5f7fa;",
            "--border: #cfd7e3;",
            "--border-strong: #b9c5d6;",
            "--text: #172033;",
            "--muted: #475467;",
            "--meta-blue: #0866ff;",
            "--accent: #4f46e5;",
            "--accent-hover: #4338ca;",
            "--success: #16865f;",
            "--warning: #a76513;",
            "--danger: #b83a3a;",
        ):
            assert token in css

        for retired in (
            "#d85c36",
            "#bd4827",
            "rgba(216,92,54,.12)",
            "#fff1dc",
            "#edcf9f",
            "#fff8ed",
            "#fff6e9",
            "#714813",
        ):
            assert retired not in css

        assert "radial-gradient(ellipse 820px 390px at 0 0" in css
        assert ".nav-item.is-active," in css
        assert "background: var(--accent);" in css
        assert ".summary > div::after" in css
        assert ".ui-select-menu" in css
        assert "border-radius: 10px" in css
        assert ".button-danger" in css
        assert "color: var(--danger);" in css


def test_login_cookie_csrf_logout_and_workspace_guard():
    with build_production_client() as client:
        provision(client)

        unauthenticated_page = client.get("/", follow_redirects=False)
        assert unauthenticated_page.status_code == 303
        assert unauthenticated_page.headers["location"] == "/login"
        login_page = client.get("/login")
        assert login_page.status_code == 200
        assert '<label for="email">Tài khoản</label>' in login_page.text
        assert 'type="text"' in login_page.text
        unauthenticated_hermes = client.get("/ai-copilot", follow_redirects=False)
        assert unauthenticated_hermes.status_code == 303
        assert unauthenticated_hermes.headers["location"] == "/login"
        assert client.get("/api/accounts").status_code == 401

        wrong_origin = client.post(
            "/api/auth/login",
            headers={"Origin": "https://evil.example"},
            json={"email": "admin", "password": PASSWORD},
        )
        assert wrong_origin.status_code == 403

        wrong_password = client.post(
            "/api/auth/login",
            headers={"Origin": "https://testserver"},
            json={"email": "admin", "password": "incorrect"},
        )
        assert wrong_password.status_code == 401
        assert wrong_password.json()["detail"] == "Tài khoản hoặc mật khẩu không đúng."

        logged_in = client.post(
            "/api/auth/login",
            headers={"Origin": "https://testserver"},
            json={"email": "ADMIN", "password": PASSWORD},
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
        assert "Ads Meta Master" in workspace.text
        assert "Meta Ads Automation" in workspace.text
        assert "<strong>Admin</strong>" in workspace.text
        assert "Lush Media" not in workspace.text
        assert "Hermes Dashboard" in workspace.text
        assert "data-open-password-dialog" in workspace.text
        assert 'id="password-dialog"' in workspace.text
        assert '/static/account_settings.js' in workspace.text
        for page_path in ("/campaigns", "/reports", "/bot-nodes", "/hermes-agents"):
            page = client.get(page_path)
            assert page.status_code == 200
            assert "data-open-password-dialog" in page.text
            assert 'id="password-dialog"' in page.text
            assert '/static/account_settings.js' in page.text
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


def test_change_password_requires_csrf_keeps_current_session_and_revokes_others():
    new_password = "1234"
    with build_production_client() as client:
        provision(client)
        secondary = TestClient(client.app, base_url="https://testserver")
        try:
            for session_client in (client, secondary):
                logged_in = session_client.post(
                    "/api/auth/login",
                    headers={"Origin": "https://testserver"},
                    json={"email": "admin", "password": PASSWORD},
                )
                assert logged_in.status_code == 200

            payload = {
                "current_password": PASSWORD,
                "new_password": new_password,
                "new_password_confirmation": new_password,
            }
            assert client.post("/api/auth/password", json=payload).status_code == 403

            csrf_token = client.cookies.get("ads_lush_csrf")
            wrong_current = client.post(
                "/api/auth/password",
                headers={"X-CSRF-Token": csrf_token},
                json={**payload, "current_password": "not-the-current-password"},
            )
            assert wrong_current.status_code == 400
            assert wrong_current.json()["detail"] == "Mật khẩu hiện tại không đúng."

            mismatched = client.post(
                "/api/auth/password",
                headers={"X-CSRF-Token": csrf_token},
                json={**payload, "new_password_confirmation": "Another-password-confirmation-2026"},
            )
            assert mismatched.status_code == 422

            unchanged = client.post(
                "/api/auth/password",
                headers={"X-CSRF-Token": csrf_token},
                json={
                    "current_password": PASSWORD,
                    "new_password": PASSWORD,
                    "new_password_confirmation": PASSWORD,
                },
            )
            assert unchanged.status_code == 400
            assert unchanged.json()["detail"] == "Mật khẩu mới phải khác mật khẩu hiện tại."

            changed = client.post(
                "/api/auth/password",
                headers={"X-CSRF-Token": csrf_token},
                json=payload,
            )
            assert changed.status_code == 204
            assert client.get("/api/auth/me").status_code == 200
            assert secondary.get("/api/auth/me").status_code == 401

            secondary.cookies.clear()
            old_login = secondary.post(
                "/api/auth/login",
                headers={"Origin": "https://testserver"},
                json={"email": "admin", "password": PASSWORD},
            )
            assert old_login.status_code == 401
            new_login = secondary.post(
                "/api/auth/login",
                headers={"Origin": "https://testserver"},
                json={"email": "admin", "password": new_password},
            )
            assert new_login.status_code == 200
        finally:
            secondary.close()
