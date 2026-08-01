from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.models import TenantMembership
from backend.app.services import account_sessions, auth


TENANT_A = "00000000-0000-0000-0000-00000000000a"
TENANT_B = "00000000-0000-0000-0000-00000000000b"
PASSWORD = "Strong-test-password-2026"
WORKER_SECRET = "campaign-worker-secret"


def build_client() -> TestClient:
    return TestClient(
        create_app(
            Settings(
                app_env="test",
                database_url="sqlite://",
                worker_shared_secret=WORKER_SECRET,
                dev_tenant_id=TENANT_A,
                app_origin="http://testserver",
                session_cookie_secure=False,
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


def create_facebook_account(client: TestClient, headers: dict[str, str]) -> dict:
    worker = client.post(
        "/api/workers/register",
        headers={"X-Worker-Secret": WORKER_SECRET},
        json={"worker_key": "campaign-worker", "display_name": "Campaign Worker"},
    ).json()
    with client.app.state.database.session_factory() as db:
        account_sessions.assign_worker_to_tenant(db, worker["id"], TENANT_A)
    response = client.post(
        "/api/accounts",
        headers=headers,
        json={"label": "Facebook chính", "assigned_worker_id": worker["id"]},
    )
    assert response.status_code == 201
    return response.json()


def create_ad_account(client: TestClient, headers: dict[str, str], facebook_account_id: str) -> dict:
    response = client.post(
        "/api/ad-accounts",
        headers=headers,
        json={
            "facebook_account_id": facebook_account_id,
            "meta_ad_account_id": "act_123456789",
            "label": "Bán hàng Việt Nam",
            "currency": "vnd",
            "timezone_name": "Asia/Ho_Chi_Minh",
        },
    )
    assert response.status_code == 201
    assert response.json()["currency"] == "VND"
    return response.json()


def create_campaign(client: TestClient, headers: dict[str, str], ad_account_id: str) -> dict:
    response = client.post(
        "/api/campaign-drafts",
        headers=headers,
        json={
            "ad_account_id": ad_account_id,
            "name": "Lead form tháng 8",
            "objective": "leads",
            "daily_budget_minor": 250000,
            "targeting_json": {"note": "Việt Nam, 25–45"},
            "creative_json": {"note": "Video UGC"},
        },
    )
    assert response.status_code == 201
    return response.json()


def test_campaign_approval_state_machine_and_audit_log():
    with build_client() as client:
        provision(client, TENANT_A, "owner-a@example.test")
        owner_headers = login(client, "owner-a@example.test")
        facebook_account = create_facebook_account(client, owner_headers)

        assert client.post(
            "/api/ad-accounts",
            json={
                "facebook_account_id": facebook_account["id"],
                "meta_ad_account_id": "act_no_csrf",
                "label": "No CSRF",
                "currency": "VND",
                "timezone_name": "Asia/Ho_Chi_Minh",
            },
        ).status_code == 403

        ad_account = create_ad_account(client, owner_headers, facebook_account["id"])
        campaign = create_campaign(client, owner_headers, ad_account["id"])
        assert campaign["status"] == "draft"
        assert campaign["version"] == 1

        submitted = client.post(
            f"/api/campaign-drafts/{campaign['id']}/submit",
            headers=owner_headers,
            json={},
        )
        assert submitted.status_code == 200
        approval = submitted.json()
        assert approval["status"] == "pending"
        assert approval["snapshot_json"]["daily_budget_minor"] == 250000
        assert approval["snapshot_json"]["version"] == 1

        locked = client.patch(
            f"/api/campaign-drafts/{campaign['id']}",
            headers=owner_headers,
            json={"daily_budget_minor": 500000},
        )
        assert locked.status_code == 409

        approved = client.post(
            f"/api/approval-requests/{approval['id']}/approve",
            headers=owner_headers,
            json={"note": "Ngân sách và targeting hợp lệ"},
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        current = client.get(f"/api/campaign-drafts/{campaign['id']}").json()
        assert current["status"] == "approved"
        assert current["approved_at"] is not None

        events = client.get("/api/audit-events").json()
        actions = [event["action"] for event in events]
        assert actions[:4] == [
            "campaign_draft.approved",
            "campaign_draft.submitted",
            "campaign_draft.created",
            "ad_account.created",
        ]
        assert not any("publish" in action for action in actions)


def test_member_cannot_approve_and_tenant_cannot_see_foreign_campaign():
    with build_client() as client:
        provision(client, TENANT_A, "owner-a@example.test")
        provision(client, TENANT_A, "member-a@example.test", role="member")
        provision(client, TENANT_B, "owner-b@example.test")
        owner_headers = login(client, "owner-a@example.test")
        facebook_account = create_facebook_account(client, owner_headers)
        ad_account = create_ad_account(client, owner_headers, facebook_account["id"])
        campaign = create_campaign(client, owner_headers, ad_account["id"])
        approval = client.post(
            f"/api/campaign-drafts/{campaign['id']}/submit",
            headers=owner_headers,
            json={},
        ).json()

        member_headers = login(client, "member-a@example.test")
        forbidden = client.post(
            f"/api/approval-requests/{approval['id']}/approve",
            headers=member_headers,
            json={"note": None},
        )
        assert forbidden.status_code == 403

        login(client, "owner-b@example.test")
        assert client.get(f"/api/campaign-drafts/{campaign['id']}").status_code == 404
        assert client.get("/api/campaign-drafts").json() == []
        assert client.get("/api/approval-requests").json() == []


def test_rejected_campaign_requires_note_then_can_be_revised_and_resubmitted():
    with build_client() as client:
        provision(client, TENANT_A, "owner-a@example.test")
        headers = login(client, "owner-a@example.test")
        facebook_account = create_facebook_account(client, headers)
        ad_account = create_ad_account(client, headers, facebook_account["id"])
        campaign = create_campaign(client, headers, ad_account["id"])
        approval = client.post(
            f"/api/campaign-drafts/{campaign['id']}/submit", headers=headers, json={}
        ).json()

        missing_note = client.post(
            f"/api/approval-requests/{approval['id']}/reject",
            headers=headers,
            json={"note": ""},
        )
        assert missing_note.status_code == 422
        rejected = client.post(
            f"/api/approval-requests/{approval['id']}/reject",
            headers=headers,
            json={"note": "Giảm ngân sách thử nghiệm"},
        )
        assert rejected.status_code == 200

        revised = client.patch(
            f"/api/campaign-drafts/{campaign['id']}",
            headers=headers,
            json={"daily_budget_minor": 100000},
        )
        assert revised.status_code == 200
        assert revised.json()["status"] == "draft"
        assert revised.json()["version"] == 2
        resubmitted = client.post(
            f"/api/campaign-drafts/{campaign['id']}/submit", headers=headers, json={}
        )
        assert resubmitted.status_code == 200
        assert resubmitted.json()["id"] != approval["id"]
        assert resubmitted.json()["snapshot_json"]["daily_budget_minor"] == 100000


def test_ad_account_can_be_renamed_but_linkage_is_locked_after_dependencies_exist():
    with build_client() as client:
        provision(client, TENANT_A, "owner-a@example.test")
        headers = login(client, "owner-a@example.test")
        facebook_account = create_facebook_account(client, headers)
        ad_account = create_ad_account(client, headers, facebook_account["id"])

        assert client.patch(
            f"/api/ad-accounts/{ad_account['id']}",
            json={"label": "Thiếu CSRF"},
        ).status_code == 403

        updated = client.patch(
            f"/api/ad-accounts/{ad_account['id']}",
            headers=headers,
            json={"label": "Lê Hoàng", "currency": "vnd"},
        )
        assert updated.status_code == 200
        assert updated.json()["label"] == "Lê Hoàng"
        assert updated.json()["currency"] == "VND"

        create_campaign(client, headers, ad_account["id"])
        locked = client.patch(
            f"/api/ad-accounts/{ad_account['id']}",
            headers=headers,
            json={"timezone_name": "UTC"},
        )
        assert locked.status_code == 409
        assert "Chỉ có thể đổi tên gợi nhớ" in locked.json()["detail"]

        renamed = client.patch(
            f"/api/ad-accounts/{ad_account['id']}",
            headers=headers,
            json={"label": "Lê Hoàng Ads"},
        )
        assert renamed.status_code == 200
        assert renamed.json()["label"] == "Lê Hoàng Ads"

        events = client.get("/api/audit-events").json()
        update_events = [event for event in events if event["action"] == "ad_account.updated"]
        assert len(update_events) == 2
        assert update_events[0]["payload_json"]["changes"]["label"]["to"] == "Lê Hoàng Ads"
