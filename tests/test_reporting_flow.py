from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.models import FacebookAccount, ReportSchedule, TenantMembership, utc_now
from backend.app.services import account_sessions, auth


TENANT_A = "00000000-0000-0000-0000-00000000000a"
TENANT_B = "00000000-0000-0000-0000-00000000000b"
PASSWORD = "Strong-test-password-2026"
WORKER_SECRET = "report-worker-secret"


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


def reporting_account(client: TestClient, headers: dict[str, str]) -> tuple[dict, dict]:
    worker = client.post(
        "/api/workers/register",
        headers={"X-Worker-Secret": WORKER_SECRET},
        json={"worker_key": "report-worker", "display_name": "Report Worker"},
    ).json()
    with client.app.state.database.session_factory() as db:
        account_sessions.assign_worker_to_tenant(db, worker["id"], TENANT_A)
    facebook = client.post(
        "/api/accounts",
        headers=headers,
        json={"label": "Facebook reporting", "assigned_worker_id": worker["id"]},
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
            "meta_ad_account_id": "act_987654321",
            "label": "Ad account reporting",
            "currency": "VND",
            "timezone_name": "Asia/Ho_Chi_Minh",
        },
    ).json()
    return ad_account, worker


def test_manual_report_worker_snapshot_and_tenant_isolation(tmp_path: Path):
    with build_client(tmp_path) as client:
        provision(client, TENANT_A, "owner-a@example.test")
        provision(client, TENANT_B, "owner-b@example.test")
        headers = login(client, "owner-a@example.test")
        account, worker = reporting_account(client, headers)

        wrong = client.post(
            "/api/report-jobs",
            headers=headers,
            json={
                "ad_account_id": account["id"],
                "lookback_days": 7,
                "confirmation": "run",
            },
        )
        assert wrong.status_code == 422

        created = client.post(
            "/api/report-jobs",
            headers=headers,
            json={
                "ad_account_id": account["id"],
                "lookback_days": 7,
                "telegram_chat_id": "-1001234567890",
                "confirmation": "THU THẬP KPI",
            },
        )
        assert created.status_code == 201
        job = created.json()
        assert job["status"] == "queued"
        assert job["payload_json"]["safety"] == {
            "mode": "report_read_only",
            "allow_filter_click": False,
            "allow_ad_mutation": False,
            "allow_publish": False,
        }
        assert (job["range_end"][:10] > job["range_start"][:10]) is True

        worker_headers = {"X-Worker-Secret": WORKER_SECRET}
        claimed = client.post(
            f"/api/workers/{worker['id']}/report-jobs/poll",
            headers=worker_headers,
        )
        assert claimed.status_code == 200
        assignment = claimed.json()
        assert assignment["id"] == job["id"]
        assert assignment["profile_key"]
        assert assignment["meta_ad_account_id"] == "act_987654321"

        running = client.post(
            f"/api/workers/{worker['id']}/report-jobs/{job['id']}/sync",
            headers=worker_headers,
            json={"status": "running", "result_json": {}, "last_error": None},
        )
        assert running.status_code == 200
        result = {
            "ready": True,
            "data_state": "ready",
            "source": "meta_ads_manager_dom",
            "collected_at": utc_now().isoformat(),
            "body_sha256": "a" * 64,
            "metrics": {
                "headers": ["Chiến dịch", "Kết quả", "Số tiền đã chi tiêu"],
                "totals": {
                    "results": 12,
                    "amount_spent": 240000,
                    "cost_per_result": 20000,
                    "campaigns": 1,
                    "currency": "VND",
                },
                "campaigns": [{"campaign_name": "Campaign A", "results": 12}],
            },
            "delivery": {"status": "not_configured", "error": "Missing token"},
            "safety": {"clicked": False, "ad_mutated": False, "published": False},
        }
        succeeded = client.post(
            f"/api/workers/{worker['id']}/report-jobs/{job['id']}/sync",
            headers=worker_headers,
            json={"status": "succeeded", "result_json": result, "last_error": None},
        )
        assert succeeded.status_code == 200
        assert succeeded.json()["delivery_status"] == "not_configured"

        snapshots = client.get(f"/api/report-snapshots?ad_account_id={account['id']}").json()
        assert len(snapshots) == 1
        assert snapshots[0]["totals_json"]["amount_spent"] == 240000
        assert snapshots[0]["metadata_json"]["safety"]["published"] is False

        login(client, "owner-b@example.test")
        assert client.get("/api/report-jobs").json() == []
        assert client.get("/api/report-snapshots").json() == []


def test_daily_schedule_materializes_once_and_can_pause(tmp_path: Path):
    with build_client(tmp_path) as client:
        provision(client, TENANT_A, "owner-a@example.test")
        headers = login(client, "owner-a@example.test")
        account, worker = reporting_account(client, headers)

        created = client.post(
            "/api/report-schedules",
            headers=headers,
            json={
                "ad_account_id": account["id"],
                "local_time": "08:00",
                "lookback_days": 7,
                "telegram_chat_id": None,
            },
        )
        assert created.status_code == 201
        schedule = created.json()
        assert schedule["status"] == "enabled"
        with client.app.state.database.session_factory() as db:
            model = db.get(ReportSchedule, schedule["id"])
            model.next_run_at = utc_now() - timedelta(minutes=1)
            db.commit()

        worker_headers = {"X-Worker-Secret": WORKER_SECRET}
        first = client.post(
            f"/api/workers/{worker['id']}/report-jobs/poll",
            headers=worker_headers,
        ).json()
        assert first["trigger"] == "scheduled"
        assert first["schedule_id"] == schedule["id"]
        jobs = client.get("/api/report-jobs").json()
        assert len(jobs) == 1

        paused = client.patch(
            f"/api/report-schedules/{schedule['id']}",
            headers=headers,
            json={"status": "paused"},
        )
        assert paused.status_code == 200
        assert paused.json()["status"] == "paused"

