from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.services import account_sessions, auth


TENANT_ID = "00000000-0000-0000-0000-00000000000a"
PASSWORD = "Strong-test-password-2026"
WORKER_SECRET = "resource-worker-secret"


def build_client(tmp_path) -> TestClient:
    return TestClient(
        create_app(
            Settings(
                app_env="test",
                database_url="sqlite://",
                worker_shared_secret=WORKER_SECRET,
                dev_tenant_id=TENANT_ID,
                app_origin="http://testserver",
                session_cookie_secure=False,
                creative_asset_root=str(tmp_path / "creative-assets"),
            )
        )
    )


def provision(client: TestClient) -> dict[str, str]:
    with client.app.state.database.session_factory() as db:
        auth.provision_admin(
            db,
            tenant_id=TENANT_ID,
            tenant_name="Lush Media",
            email="owner@example.test",
            display_name="Owner",
            password=PASSWORD,
        )
    login = client.post(
        "/api/auth/login",
        json={"email": "owner@example.test", "password": PASSWORD},
    )
    assert login.status_code == 200
    return {"X-CSRF-Token": client.cookies.get("ads_lush_csrf")}


def create_account_graph(client: TestClient, headers: dict[str, str]) -> tuple[dict, dict]:
    worker = client.post(
        "/api/workers/register",
        headers={"X-Worker-Secret": WORKER_SECRET},
        json={"worker_key": "resource-worker", "display_name": "Resource Worker"},
    ).json()
    with client.app.state.database.session_factory() as db:
        account_sessions.assign_worker_to_tenant(db, worker["id"], TENANT_ID)
    facebook_account = client.post(
        "/api/accounts",
        headers=headers,
        json={"label": "Facebook test", "assigned_worker_id": worker["id"]},
    ).json()
    ad_account = client.post(
        "/api/ad-accounts",
        headers=headers,
        json={
            "facebook_account_id": facebook_account["id"],
            "meta_ad_account_id": "act_resource_test",
            "label": "Ad account test",
            "currency": "VND",
            "timezone_name": "Asia/Ho_Chi_Minh",
        },
    ).json()
    return facebook_account, ad_account


def test_resource_asset_snapshot_and_manual_verification(tmp_path):
    with build_client(tmp_path) as client:
        headers = provision(client)
        _facebook_account, ad_account = create_account_graph(client, headers)

        resource_response = client.post(
            "/api/meta-resources",
            headers=headers,
            json={
                "ad_account_id": ad_account["id"],
                "kind": "page",
                "label": "Lush Test Page",
                "external_id": "page-123",
                "metadata_json": {},
            },
        )
        assert resource_response.status_code == 201
        resource = resource_response.json()
        assert resource["status"] == "unverified"

        png = b"\x89PNG\r\n\x1a\n" + b"phase-7-test"
        asset_response = client.post(
            "/api/creative-assets",
            params={
                "ad_account_id": ad_account["id"],
                "label": "Ảnh test Phase 7",
                "file_name": "creative.png",
            },
            headers={**headers, "Content-Type": "image/png"},
            content=png,
        )
        assert asset_response.status_code == 201
        asset = asset_response.json()
        assert asset["status"] == "ready"
        assert asset["byte_size"] == len(png)
        assert len(asset["sha256"]) == 64
        assert "storage_path" not in asset

        duplicate = client.post(
            "/api/creative-assets",
            params={
                "ad_account_id": ad_account["id"],
                "label": "Ảnh trùng",
                "file_name": "duplicate.png",
            },
            headers={**headers, "Content-Type": "image/png"},
            content=png,
        )
        assert duplicate.status_code == 409

        campaign_response = client.post(
            "/api/campaign-drafts",
            headers=headers,
            json={
                "ad_account_id": ad_account["id"],
                "name": "Phase 7 test draft",
                "objective": "sales",
                "daily_budget_minor": 100000,
                "targeting_json": {
                    "page_resource_id": resource["id"],
                    "countries": ["VN"],
                    "conversion_location": "website",
                },
                "creative_json": {
                    "asset_id": asset["id"],
                    "primary_text": "Nội dung test",
                    "destination_url": "https://example.com",
                    "cta": "SHOP_NOW",
                },
            },
        )
        assert campaign_response.status_code == 201
        campaign = campaign_response.json()
        assert campaign["targeting_json"]["page_name"] == "Lush Test Page"
        assert campaign["targeting_json"]["page_external_id"] == "page-123"
        assert campaign["creative_json"]["asset_snapshot"]["sha256"] == asset["sha256"]

        approval = client.post(
            f"/api/campaign-drafts/{campaign['id']}/submit",
            headers=headers,
            json={},
        ).json()
        approved = client.post(
            f"/api/approval-requests/{approval['id']}/approve",
            headers=headers,
            json={"note": "Test registry"},
        )
        assert approved.status_code == 200
        preview = client.get(
            f"/api/campaign-drafts/{campaign['id']}/execution-preview"
        ).json()
        assert any("chưa được xác minh" in item for item in preview["draft_blockers"])

        wrong_confirmation = client.post(
            f"/api/meta-resources/{resource['id']}/verify",
            headers=headers,
            json={"confirmation": "Xác minh"},
        )
        assert wrong_confirmation.status_code == 422
        verified = client.post(
            f"/api/meta-resources/{resource['id']}/verify",
            headers=headers,
            json={"confirmation": "ĐÃ XÁC MINH TRÊN META"},
        )
        assert verified.status_code == 200
        assert verified.json()["status"] == "verified"
        refreshed_preview = client.get(
            f"/api/campaign-drafts/{campaign['id']}/execution-preview"
        ).json()
        assert not any(
            "Lush Test Page" in item and "chưa được xác minh" in item
            for item in refreshed_preview["draft_blockers"]
        )


def test_asset_rejects_mime_spoof_and_worker_cannot_download_unreferenced_file(tmp_path):
    with build_client(tmp_path) as client:
        headers = provision(client)
        _facebook_account, ad_account = create_account_graph(client, headers)
        spoofed = client.post(
            "/api/creative-assets",
            params={
                "ad_account_id": ad_account["id"],
                "label": "File giả PNG",
                "file_name": "fake.png",
            },
            headers={**headers, "Content-Type": "image/png"},
            content=b"not-a-png",
        )
        assert spoofed.status_code == 415
        unauthorized_download = client.get(
            "/api/workers/missing/execution-jobs/missing/assets/missing",
            headers={"X-Worker-Secret": WORKER_SECRET},
        )
        assert unauthorized_download.status_code == 404
