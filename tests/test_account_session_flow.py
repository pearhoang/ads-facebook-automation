from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.services import account_sessions, auth


WORKER_SECRET = "test-worker-secret"
TENANT_A = "00000000-0000-0000-0000-00000000000a"
TENANT_B = "00000000-0000-0000-0000-00000000000b"
PASSWORD = "Strong-test-password-2026"


def build_client() -> TestClient:
    settings = Settings(
        app_env="test",
        database_url="sqlite://",
        worker_shared_secret=WORKER_SECRET,
        dev_tenant_id=TENANT_A,
        browser_session_ttl_minutes=20,
        app_origin="http://testserver",
        session_cookie_secure=False,
    )
    return TestClient(create_app(settings))


def worker_headers() -> dict[str, str]:
    return {"X-Worker-Secret": WORKER_SECRET}


def provision_user(client: TestClient, tenant_id: str, email: str) -> None:
    with client.app.state.database.session_factory() as db:
        auth.provision_admin(
            db,
            tenant_id=tenant_id,
            tenant_name=f"Workspace {tenant_id[-1]}",
            email=email,
            display_name=email.split("@", 1)[0],
            password=PASSWORD,
        )


def login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return {"X-CSRF-Token": client.cookies.get("ads_lush_csrf")}


def test_account_session_vertical_slice_and_tenant_isolation():
    with build_client() as client:
        assert client.get("/health").json() == {"status": "ok"}
        provision_user(client, TENANT_A, "owner-a@example.test")
        provision_user(client, TENANT_B, "owner-b@example.test")
        csrf_headers = login(client, "owner-a@example.test")

        worker_response = client.post(
            "/api/workers/register",
            headers=worker_headers(),
            json={"worker_key": "worker-local-01", "display_name": "Local Worker"},
        )
        assert worker_response.status_code == 201
        worker_id = worker_response.json()["id"]
        with client.app.state.database.session_factory() as db:
            account_sessions.assign_worker_to_tenant(db, worker_id, TENANT_A)

        account_response = client.post(
            "/api/accounts",
            headers=csrf_headers,
            json={"label": "Facebook chính", "assigned_worker_id": worker_id},
        )
        assert account_response.status_code == 201
        account_id = account_response.json()["id"]

        csrf_headers_b = login(client, "owner-b@example.test")
        unassigned_worker_response = client.post(
            "/api/accounts",
            headers=csrf_headers_b,
            json={"label": "Không được phép", "assigned_worker_id": worker_id},
        )
        assert unassigned_worker_response.status_code == 403

        invalid_handoff = client.post(
            f"/api/accounts/{account_id}/browser-sessions",
            headers=login(client, "owner-a@example.test"),
            json={"launch_url": "https://example.com/not-facebook"},
        )
        assert invalid_handoff.status_code == 422

        launch_url = "https://adsmanager.facebook.com/adsmanager/manage/ads/edit/standalone?act=123"
        session_response = client.post(
            f"/api/accounts/{account_id}/browser-sessions",
            headers=login(client, "owner-a@example.test"),
            json={"launch_url": launch_url},
        )
        assert session_response.status_code == 201
        browser_session = session_response.json()
        session_id = browser_session["id"]
        assert browser_session["status"] == "requested"
        assert browser_session["launch_url"] == launch_url

        duplicate_response = client.post(
            f"/api/accounts/{account_id}/browser-sessions",
            headers={"X-CSRF-Token": client.cookies.get("ads_lush_csrf")},
        )
        assert duplicate_response.status_code == 409

        login(client, "owner-b@example.test")
        hidden_response = client.get(
            f"/api/browser-sessions/{session_id}",
        )
        assert hidden_response.status_code == 404
        csrf_headers = login(client, "owner-a@example.test")

        poll_response = client.post(
            f"/api/workers/{worker_id}/browser-sessions/poll",
            headers=worker_headers(),
        )
        assert poll_response.status_code == 200
        assignments = poll_response.json()
        assert len(assignments) == 1
        assert assignments[0]["id"] == session_id
        assert assignments[0]["profile_key"] == account_response.json()["profile_key"]
        assert assignments[0]["launch_url"] == launch_url

        starting_response = client.post(
            f"/api/workers/{worker_id}/browser-sessions/{session_id}/sync",
            headers=worker_headers(),
            json={"status": "starting"},
        )
        assert starting_response.status_code == 200

        ready_for_user_response = client.post(
            f"/api/workers/{worker_id}/browser-sessions/{session_id}/sync",
            headers=worker_headers(),
            json={
                "status": "awaiting_user",
                "novnc_url": "https://example.test/browser/session-token",
                "web_port": 16080,
                "facebook_user_id": "fb-user-123",
            },
        )
        assert ready_for_user_response.status_code == 200
        assert ready_for_user_response.json()["novnc_url"] is not None

        confirm_response = client.post(
            f"/api/browser-sessions/{session_id}/confirm",
            headers=csrf_headers,
        )
        assert confirm_response.status_code == 200
        assert confirm_response.json()["status"] == "ready"

        close_response = client.delete(
            f"/api/browser-sessions/{session_id}",
            headers=csrf_headers,
        )
        assert close_response.status_code == 202
        assert close_response.json()["status"] == "closing"

        closed_response = client.post(
            f"/api/workers/{worker_id}/browser-sessions/{session_id}/sync",
            headers=worker_headers(),
            json={"status": "closed"},
        )
        assert closed_response.status_code == 200
        assert closed_response.json()["status"] == "closed"
        assert closed_response.json()["novnc_url"] is None


def test_worker_rejects_invalid_transition_and_secret():
    with build_client() as client:
        provision_user(client, TENANT_A, "owner-a@example.test")
        csrf_headers = login(client, "owner-a@example.test")
        unauthorized = client.post(
            "/api/workers/register",
            json={"worker_key": "worker-local-01", "display_name": "Local Worker"},
        )
        assert unauthorized.status_code == 401

        worker = client.post(
            "/api/workers/register",
            headers=worker_headers(),
            json={"worker_key": "worker-local-01", "display_name": "Local Worker"},
        ).json()
        with client.app.state.database.session_factory() as db:
            account_sessions.assign_worker_to_tenant(db, worker["id"], TENANT_A)
        account = client.post(
            "/api/accounts",
            headers=csrf_headers,
            json={"label": "Facebook chính", "assigned_worker_id": worker["id"]},
        ).json()
        session = client.post(
            f"/api/accounts/{account['id']}/browser-sessions",
            headers=csrf_headers,
        ).json()

        invalid = client.post(
            f"/api/workers/{worker['id']}/browser-sessions/{session['id']}/sync",
            headers=worker_headers(),
            json={"status": "ready"},
        )
        assert invalid.status_code == 409
