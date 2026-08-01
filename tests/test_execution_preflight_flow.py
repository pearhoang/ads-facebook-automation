from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.models import FacebookAccount, TenantMembership
from backend.app.services import account_sessions, auth


TENANT_A = "00000000-0000-0000-0000-00000000000a"
TENANT_B = "00000000-0000-0000-0000-00000000000b"
PASSWORD = "Strong-test-password-2026"
WORKER_SECRET = "execution-worker-secret"
CONFIRMATION = "CHẠY PREFLIGHT"
BUILD_CONFIRMATION = "TẠO DRAFT META"


def build_client(tmp_path: Path) -> TestClient:
    return TestClient(
        create_app(
            Settings(
                app_env="test",
                database_url="sqlite://",
                worker_shared_secret=WORKER_SECRET,
                dev_tenant_id=TENANT_A,
                app_origin="http://testserver",
                session_cookie_secure=False,
                artifact_root=str(tmp_path / "artifacts"),
            )
        )
    )


def provision(client: TestClient, tenant_id: str, email: str, role: str = "owner") -> None:
    with client.app.state.database.session_factory() as db:
        user = auth.provision_admin(
            db,
            tenant_id=tenant_id,
            tenant_name=f"Workspace {tenant_id[-1]}",
            email=email,
            display_name=email.split("@", 1)[0],
            password=PASSWORD,
        )
        membership = db.get(TenantMembership, {"user_id": user.id, "tenant_id": tenant_id})
        membership.role = role
        db.commit()


def login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return {"X-CSRF-Token": client.cookies.get("ads_lush_csrf")}


def approved_campaign(client: TestClient, headers: dict[str, str]) -> tuple[dict, dict]:
    worker = client.post(
        "/api/workers/register",
        headers={"X-Worker-Secret": WORKER_SECRET},
        json={"worker_key": "execution-worker", "display_name": "Execution Worker"},
    ).json()
    with client.app.state.database.session_factory() as db:
        account_sessions.assign_worker_to_tenant(db, worker["id"], TENANT_A)
    facebook = client.post(
        "/api/accounts",
        headers=headers,
        json={"label": "Facebook chính", "assigned_worker_id": worker["id"]},
    ).json()
    with client.app.state.database.session_factory() as db:
        model = db.get(FacebookAccount, facebook["id"])
        model.status = "authenticated"
        db.commit()
    ad_account = client.post(
        "/api/ad-accounts",
        headers=headers,
        json={
            "facebook_account_id": facebook["id"],
            "meta_ad_account_id": "act_123456789",
            "label": "Ad account test",
            "currency": "VND",
            "timezone_name": "Asia/Ho_Chi_Minh",
        },
    ).json()
    campaign = client.post(
        "/api/campaign-drafts",
        headers=headers,
        json={
            "ad_account_id": ad_account["id"],
            "name": "Campaign preflight",
            "objective": "sales",
            "daily_budget_minor": 100000,
            "targeting_json": {"note": "Việt Nam"},
            "creative_json": {"note": "Creative test"},
        },
    ).json()
    approval = client.post(
        f"/api/campaign-drafts/{campaign['id']}/submit", headers=headers, json={}
    ).json()
    approved = client.post(
        f"/api/approval-requests/{approval['id']}/approve",
        headers=headers,
        json={"note": "Ready for read-only preflight"},
    )
    assert approved.status_code == 200
    return campaign, worker


def test_preflight_job_worker_flow_artifact_and_tenant_isolation(tmp_path: Path):
    with build_client(tmp_path) as client:
        provision(client, TENANT_A, "owner-a@example.test")
        provision(client, TENANT_A, "member-a@example.test", role="member")
        provision(client, TENANT_B, "owner-b@example.test")
        owner_headers = login(client, "owner-a@example.test")
        campaign, worker = approved_campaign(client, owner_headers)

        preview = client.get(
            f"/api/campaign-drafts/{campaign['id']}/execution-preview"
        )
        assert preview.status_code == 200
        assert preview.json()["can_run_preflight"] is True
        assert preview.json()["blockers"] == []

        wrong_confirmation = client.post(
            "/api/execution-jobs",
            headers=owner_headers,
            json={"campaign_id": campaign["id"], "confirmation": "run"},
        )
        assert wrong_confirmation.status_code == 422
        created = client.post(
            "/api/execution-jobs",
            headers=owner_headers,
            json={"campaign_id": campaign["id"], "confirmation": CONFIRMATION},
        )
        assert created.status_code == 201
        job = created.json()
        assert job["status"] == "queued"
        assert job["payload_json"]["safety"] == {
            "mode": "read_only",
            "allow_click": False,
            "allow_publish": False,
        }

        duplicate = client.post(
            "/api/execution-jobs",
            headers=owner_headers,
            json={"campaign_id": campaign["id"], "confirmation": CONFIRMATION},
        )
        assert duplicate.status_code == 409

        member_headers = login(client, "member-a@example.test")
        forbidden = client.post(
            "/api/execution-jobs",
            headers=member_headers,
            json={"campaign_id": campaign["id"], "confirmation": CONFIRMATION},
        )
        assert forbidden.status_code == 403

        worker_headers = {"X-Worker-Secret": WORKER_SECRET}
        claimed = client.post(
            f"/api/workers/{worker['id']}/execution-jobs/poll",
            headers=worker_headers,
        )
        assert claimed.status_code == 200
        assert claimed.json()["id"] == job["id"]
        assert claimed.json()["profile_key"]
        assert claimed.json()["meta_ad_account_id"] == "act_123456789"

        running = client.post(
            f"/api/workers/{worker['id']}/execution-jobs/{job['id']}/sync",
            headers=worker_headers,
            json={"status": "running", "result_json": {}, "last_error": None},
        )
        assert running.status_code == 200
        png = b"\x89PNG\r\n\x1a\npreflight-test"
        uploaded = client.post(
            f"/api/workers/{worker['id']}/execution-jobs/{job['id']}/artifacts?kind=screenshot",
            headers={**worker_headers, "Content-Type": "image/png"},
            content=png,
        )
        assert uploaded.status_code == 201
        artifact = uploaded.json()
        assert artifact["byte_size"] == len(png)

        result = {
            "readiness": "ready",
            "ready": True,
            "authenticated": True,
            "ads_manager_loaded": True,
            "ad_account_confirmed": True,
            "safety": {"clicked": False, "published": False},
        }
        succeeded = client.post(
            f"/api/workers/{worker['id']}/execution-jobs/{job['id']}/sync",
            headers=worker_headers,
            json={"status": "succeeded", "result_json": result, "last_error": None},
        )
        assert succeeded.status_code == 200
        assert succeeded.json()["status"] == "succeeded"
        assert succeeded.json()["result_json"]["safety"]["published"] is False

        owner_headers = login(client, "owner-a@example.test")
        artifacts = client.get(f"/api/execution-jobs/{job['id']}/artifacts").json()
        assert len(artifacts) == 1
        downloaded = client.get(f"/api/execution-artifacts/{artifact['id']}")
        assert downloaded.status_code == 200
        assert downloaded.content == png

        login(client, "owner-b@example.test")
        assert client.get(f"/api/execution-jobs/{job['id']}").status_code == 404
        assert client.get(f"/api/execution-artifacts/{artifact['id']}").status_code == 404


def test_preflight_requires_approved_campaign_and_blocks_active_browser(tmp_path: Path):
    with build_client(tmp_path) as client:
        provision(client, TENANT_A, "owner-a@example.test")
        headers = login(client, "owner-a@example.test")
        campaign, _worker = approved_campaign(client, headers)
        ad_account = client.get("/api/ad-accounts").json()[0]
        facebook_id = ad_account["facebook_account_id"]
        active = client.post(
            f"/api/accounts/{facebook_id}/browser-sessions",
            headers=headers,
        )
        assert active.status_code == 201
        preview = client.get(
            f"/api/campaign-drafts/{campaign['id']}/execution-preview"
        ).json()
        assert preview["can_run_preflight"] is False
        assert preview["active_browser_session"] is True
        blocked = client.post(
            "/api/execution-jobs",
            headers=headers,
            json={"campaign_id": campaign["id"], "confirmation": CONFIRMATION},
        )
        assert blocked.status_code == 409


def test_draft_build_requires_successful_preflight_and_never_allows_publish(tmp_path: Path):
    with build_client(tmp_path) as client:
        provision(client, TENANT_A, "owner-a@example.test")
        headers = login(client, "owner-a@example.test")
        campaign, worker = approved_campaign(client, headers)

        blocked = client.post(
            "/api/execution-jobs",
            headers=headers,
            json={
                "campaign_id": campaign["id"],
                "job_type": "draft_build",
                "confirmation": BUILD_CONFIRMATION,
            },
        )
        assert blocked.status_code == 409

        preflight = client.post(
            "/api/execution-jobs",
            headers=headers,
            json={"campaign_id": campaign["id"], "confirmation": CONFIRMATION},
        ).json()
        worker_headers = {"X-Worker-Secret": WORKER_SECRET}
        client.post(f"/api/workers/{worker['id']}/execution-jobs/poll", headers=worker_headers)
        client.post(
            f"/api/workers/{worker['id']}/execution-jobs/{preflight['id']}/sync",
            headers=worker_headers,
            json={"status": "running", "result_json": {}, "last_error": None},
        )
        client.post(
            f"/api/workers/{worker['id']}/execution-jobs/{preflight['id']}/sync",
            headers=worker_headers,
            json={
                "status": "succeeded",
                "result_json": {"ready": True, "readiness": "ready"},
                "last_error": None,
            },
        )

        preview = client.get(
            f"/api/campaign-drafts/{campaign['id']}/execution-preview"
        ).json()
        assert preview["can_build_draft"] is True
        assert preview["draft_blockers"] == []
        assert preview["draft_warnings"]

        created = client.post(
            "/api/execution-jobs",
            headers=headers,
            json={
                "campaign_id": campaign["id"],
                "job_type": "draft_build",
                "confirmation": BUILD_CONFIRMATION,
            },
        )
        assert created.status_code == 201
        job = created.json()
        assert job["job_type"] == "draft_build"
        assert job["payload_json"]["safety"] == {
            "mode": "draft_only",
            "allow_click": True,
            "allow_publish": False,
            "stop_before": "publish",
        }
        adapter = job["payload_json"]["objective_adapter"]
        assert adapter["key"] == "sales"
        assert adapter["default_conversion_location"] == "website"
        assert "creative.destination_url" in adapter["required_fields"]

        claimed = client.post(
            f"/api/workers/{worker['id']}/execution-jobs/poll",
            headers=worker_headers,
        ).json()
        assert claimed["id"] == job["id"]
        client.post(
            f"/api/workers/{worker['id']}/execution-jobs/{job['id']}/sync",
            headers=worker_headers,
            json={"status": "running", "result_json": {}, "last_error": None},
        )
        checkpoint = client.post(
            f"/api/workers/{worker['id']}/execution-jobs/{job['id']}/artifacts?kind=campaign_step",
            headers={**worker_headers, "Content-Type": "image/png"},
            content=b"\x89PNG\r\n\x1a\nphase4",
        )
        assert checkpoint.status_code == 201
        result = {
            "readiness": "awaiting_user",
            "ready": False,
            "phase": "adset",
            "blockers": ["Thiếu Page Facebook trong execution spec."],
            "safety": {"clicked": True, "published": False},
        }
        synced = client.post(
            f"/api/workers/{worker['id']}/execution-jobs/{job['id']}/sync",
            headers=worker_headers,
            json={"status": "awaiting_user", "result_json": result, "last_error": "needs user"},
        )
        assert synced.status_code == 200
        assert synced.json()["result_json"]["safety"]["published"] is False
