from __future__ import annotations

from datetime import timedelta

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select

from backend.app.db import Database
from backend.app.models import (
    BrowserSession,
    FacebookAccount,
    Tenant,
    TenantMembership,
    User,
    UserSession,
    Worker,
    WorkerTenantAssignment,
    new_id,
    utc_now,
)
from scripts.migrate_sqlite_to_postgres import migrate


EXPECTED_TABLES = {
    "ad_accounts",
    "ad_automation_events",
    "ad_automation_requests",
    "ai_provider_configs",
    "agent_conversations",
    "agent_jobs",
    "agent_messages",
    "agent_workflow_learnings",
    "alembic_version",
    "approval_requests",
    "audit_events",
    "browser_sessions",
    "campaign_drafts",
    "creative_assets",
    "execution_artifacts",
    "execution_jobs",
    "facebook_accounts",
    "meta_resources",
    "report_jobs",
    "report_schedules",
    "report_snapshots",
    "tenant_memberships",
    "tenants",
    "user_sessions",
    "users",
    "worker_tenant_assignments",
    "workers",
    "worker_credentials",
    "worker_enrollments",
    "worker_operations",
}


def alembic_config() -> Config:
    return Config("alembic.ini")


def test_alembic_baseline_matches_models(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'schema.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    command.upgrade(alembic_config(), "head")

    engine = create_engine(database_url)
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES
    engine.dispose()
    command.check(alembic_config())


def test_copy_existing_sqlite_data_into_migrated_schema(tmp_path, monkeypatch):
    source_url = f"sqlite:///{tmp_path / 'source.db'}"
    target_url = f"sqlite:///{tmp_path / 'target.db'}"
    source = Database(source_url)
    source.create_schema()
    now = utc_now()
    tenant_id = new_id()
    user_id = new_id()
    worker_id = new_id()
    account_id = new_id()
    browser_session_id = new_id()

    with source.session_factory() as db:
        db.add_all(
            [
                Tenant(id=tenant_id, name="Lush Media"),
                User(
                    id=user_id,
                    email="admin@example.test",
                    normalized_email="admin@example.test",
                    display_name="Admin",
                    password_hash="argon2-placeholder",
                    status="active",
                ),
                Worker(id=worker_id, worker_key="worker-01", display_name="Worker 01"),
            ]
        )
        db.flush()
        db.add_all(
            [
                TenantMembership(user_id=user_id, tenant_id=tenant_id, role="owner"),
                WorkerTenantAssignment(worker_id=worker_id, tenant_id=tenant_id),
                UserSession(
                    token_hash="a" * 64,
                    csrf_token_hash="b" * 64,
                    user_id=user_id,
                    tenant_id=tenant_id,
                    expires_at=now + timedelta(hours=1),
                ),
                FacebookAccount(
                    id=account_id,
                    tenant_id=tenant_id,
                    assigned_worker_id=worker_id,
                    label="Facebook chính",
                    profile_key="profile-01",
                ),
            ]
        )
        db.flush()
        db.add(
            BrowserSession(
                id=browser_session_id,
                tenant_id=tenant_id,
                account_id=account_id,
                worker_id=worker_id,
                status="closed",
                expires_at=now + timedelta(minutes=20),
                closed_at=now,
            )
        )
        db.commit()
    source.engine.dispose()

    monkeypatch.setenv("DATABASE_URL", target_url)
    command.upgrade(alembic_config(), "head")
    counts = migrate(source_url, target_url)
    assert counts == {
        "tenants": 1,
        "users": 1,
        "workers": 1,
        "ai_provider_configs": 0,
        "agent_conversations": 0,
        "agent_jobs": 0,
        "agent_messages": 0,
        "agent_workflow_learnings": 0,
        "ad_accounts": 0,
        "ad_automation_events": 0,
        "ad_automation_requests": 0,
        "audit_events": 0,
        "campaign_drafts": 0,
        "creative_assets": 0,
        "approval_requests": 0,
        "execution_artifacts": 0,
        "execution_jobs": 0,
        "tenant_memberships": 1,
        "user_sessions": 1,
        "worker_tenant_assignments": 1,
        "worker_credentials": 0,
        "worker_enrollments": 0,
        "worker_operations": 0,
        "facebook_accounts": 1,
        "meta_resources": 0,
        "report_schedules": 0,
        "report_jobs": 0,
        "report_snapshots": 0,
        "browser_sessions": 1,
    }

    target = create_engine(target_url)
    with target.connect() as connection:
        assert connection.scalar(select(Tenant.name).where(Tenant.id == tenant_id)) == "Lush Media"
        assert connection.scalar(select(FacebookAccount.profile_key)) == "profile-01"
        assert connection.scalar(select(BrowserSession.status)) == "closed"
    target.dispose()
