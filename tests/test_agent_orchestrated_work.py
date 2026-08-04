from __future__ import annotations

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.models import (
    AIProviderConfig,
    AdAccount,
    CreativeAsset,
    FacebookAccount,
    MetaResource,
    TenantMembership,
    Worker,
    WorkerTenantAssignment,
    new_id,
)
from backend.app.services import auth, automation, execution_jobs


TENANT_ID = "00000000-0000-0000-0000-0000000000c1"
PASSWORD = "test-password"


def setup_graph(db, asset_path):
    user = auth.provision_admin(
        db,
        tenant_id=TENANT_ID,
        tenant_name="Agent Ads",
        email="owner@example.test",
        display_name="Owner",
        password=PASSWORD,
    )
    membership = db.get(TenantMembership, {"user_id": user.id, "tenant_id": TENANT_ID})
    membership.role = "owner"
    worker = Worker(id=new_id(), worker_key="agent-worker", display_name="Agent Worker")
    db.add(worker)
    db.flush()
    db.add(WorkerTenantAssignment(worker_id=worker.id, tenant_id=TENANT_ID))
    facebook = FacebookAccount(
        id=new_id(),
        tenant_id=TENANT_ID,
        assigned_worker_id=worker.id,
        label="Facebook bán hàng",
        profile_key="agent-profile",
        status="authenticated",
    )
    db.add(facebook)
    db.flush()
    ad_account = AdAccount(
        id=new_id(),
        tenant_id=TENANT_ID,
        facebook_account_id=facebook.id,
        meta_ad_account_id="123456789",
        label="Bán hàng Việt Nam",
        currency="VND",
        timezone_name="Asia/Ho_Chi_Minh",
        status="active",
        created_by_user_id=user.id,
    )
    db.add(ad_account)
    db.flush()
    page = MetaResource(
        id=new_id(),
        tenant_id=TENANT_ID,
        ad_account_id=ad_account.id,
        kind="page",
        label="Page bán hàng",
        external_id="page-123",
        status="verified",
        metadata_json={},
        created_by_user_id=user.id,
        verified_by_user_id=user.id,
    )
    asset = CreativeAsset(
        id=new_id(),
        tenant_id=TENANT_ID,
        ad_account_id=ad_account.id,
        label="Ảnh Telegram",
        file_name="telegram.png",
        content_type="image/png",
        byte_size=128,
        sha256="a" * 64,
        storage_path=str(asset_path),
        status="ready",
        metadata_json={"source": "telegram"},
        created_by_user_id=user.id,
    )
    db.add_all(
        [
            page,
            asset,
            AIProviderConfig(
                tenant_id=TENANT_ID,
                provider_type="openai_compatible",
                provider_name="deepseek",
                base_url="https://api.deepseek.com",
                model="deepseek-v4-flash",
                execution_scope="worker",
                worker_id=worker.id,
                status="configured",
                updated_by_user_id=user.id,
            ),
        ]
    )
    db.commit()
    return user, worker, facebook, ad_account, page, asset


def prepare(db, worker, ad_account, page, asset):
    return automation.prepare_campaign_request(
        db,
        worker.id,
        ad_account_id=ad_account.id,
        request_text="Tạo camp nhận biết dùng ảnh vừa gửi, ngân sách 100k/ngày.",
        title="Camp nhận biết từ Telegram",
        name="Awareness Telegram",
        objective="awareness",
        daily_budget_minor=100000,
        start_at=None,
        end_at=None,
        targeting_json={
            "page_resource_id": page.id,
            "countries": ["VN"],
            "age_min": 18,
            "age_max": 65,
        },
        creative_json={
            "asset_id": asset.id,
            "primary_text": "Nội dung quảng cáo",
            "headline": "Sản phẩm mới",
        },
        source="telegram",
        source_session_id="telegram-session-1",
    )


def test_agent_request_advances_preflight_to_draft_builder_and_review(tmp_path):
    app = create_app(Settings(app_env="test", database_url="sqlite://"))
    app.state.database.create_schema()
    asset_path = tmp_path / "telegram.png"
    asset_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 120)
    with app.state.database.session_factory() as db:
        _user, worker, _facebook, ad_account, page, asset = setup_graph(db, asset_path)
        prepared = prepare(db, worker, ad_account, page, asset)
        assert prepared["status"] == "awaiting_approval"
        assert prepared["plan_json"]["creative_json"]["asset_snapshot"]["sha256"] == "a" * 64

        confirmed = automation.confirm_campaign_request(
            db,
            worker.id,
            request_id=prepared["id"],
            decision="execute_draft",
            note="Người dùng nói: đúng rồi, làm đi.",
        )
        assert confirmed["status"] == "queued"
        assert confirmed["stage"] == "preflight"

        preflight = execution_jobs.poll_worker_job(db, worker.id)
        execution_jobs.sync_worker_job(
            db,
            worker_id=worker.id,
            job_id=preflight.id,
            next_status="running",
            result_json={},
            last_error=None,
        )
        execution_jobs.sync_worker_job(
            db,
            worker_id=worker.id,
            job_id=preflight.id,
            next_status="succeeded",
            result_json={"ready": True},
            last_error=None,
        )
        work = automation.get_request(db, TENANT_ID, prepared["id"])
        assert work.stage == "draft_build"
        assert work.execution_job_id != preflight.id

        draft_job = execution_jobs.poll_worker_job(db, worker.id)
        assert draft_job.job_type == "draft_build"
        assert draft_job.payload_json["safety"]["allow_publish"] is False
        execution_jobs.sync_worker_job(
            db,
            worker_id=worker.id,
            job_id=draft_job.id,
            next_status="running",
            result_json={},
            last_error=None,
        )
        execution_jobs.sync_worker_job(
            db,
            worker_id=worker.id,
            job_id=draft_job.id,
            next_status="succeeded",
            result_json={"ready": True, "phase": "review", "safety": {"published": False}},
            last_error=None,
        )
        completed = automation.request_payload(
            db, automation.get_request(db, TENANT_ID, prepared["id"])
        )
        assert completed["status"] == "completed"
        assert completed["stage"] == "review"
        assert completed["published"] is False
        assert any(event["event_type"] == "request.completed" for event in completed["events"])


def test_first_worker_failure_is_requeued_from_checkpoint_once(tmp_path):
    app = create_app(Settings(app_env="test", database_url="sqlite://"))
    app.state.database.create_schema()
    asset_path = tmp_path / "telegram.png"
    asset_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 120)
    with app.state.database.session_factory() as db:
        _user, worker, _facebook, ad_account, page, asset = setup_graph(db, asset_path)
        prepared = prepare(db, worker, ad_account, page, asset)
        automation.confirm_campaign_request(
            db,
            worker.id,
            request_id=prepared["id"],
            decision="execute_draft",
            note="Xác nhận.",
        )
        job = execution_jobs.poll_worker_job(db, worker.id)
        execution_jobs.sync_worker_job(
            db,
            worker_id=worker.id,
            job_id=job.id,
            next_status="running",
            result_json={},
            last_error=None,
        )
        synced = execution_jobs.sync_worker_job(
            db,
            worker_id=worker.id,
            job_id=job.id,
            next_status="failed",
            result_json={},
            last_error="Transient CDP navigation error",
        )
        assert synced.status == "queued"
        work = automation.get_request(db, TENANT_ID, prepared["id"])
        assert work.status == "recovering"
        assert work.recovery_count == 1
        assert automation.list_events(db, TENANT_ID, work.id)[-1].event_type == "recovery.auto_retry"

        retried = execution_jobs.poll_worker_job(db, worker.id)
        execution_jobs.sync_worker_job(
            db, worker_id=worker.id, job_id=retried.id, next_status="running", result_json={}, last_error=None
        )
        execution_jobs.sync_worker_job(
            db, worker_id=worker.id, job_id=retried.id, next_status="succeeded", result_json={"ready": True}, last_error=None
        )
        draft_job = execution_jobs.poll_worker_job(db, worker.id)
        execution_jobs.sync_worker_job(
            db, worker_id=worker.id, job_id=draft_job.id, next_status="running", result_json={}, last_error=None
        )
        execution_jobs.sync_worker_job(
            db, worker_id=worker.id, job_id=draft_job.id, next_status="succeeded", result_json={"ready": True}, last_error=None
        )
        learnings = automation.list_learnings(db, worker.id, include_proposed=False)["items"]
        assert len(learnings) == 1
        assert learnings[0]["status"] == "verified"
        assert learnings[0]["recovery_plan"]["strategy"] == "retry_from_checkpoint"
