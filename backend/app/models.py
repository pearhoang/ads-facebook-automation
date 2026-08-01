from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid4())


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320))
    normalized_email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class TenantMembership(Base):
    __tablename__ = "tenant_memberships"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token_hash: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Worker(Base):
    __tablename__ = "workers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    worker_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(32), default="online", index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    lifecycle_status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    runtime_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    agent_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    capabilities_json: Mapped[dict] = mapped_column(JSON, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ssh_user: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ssh_host_fingerprint: Mapped[str | None] = mapped_column(String(128), nullable=True)
    install_status: Mapped[str] = mapped_column(String(32), default="registered", index=True)
    installed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    drained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class WorkerTenantAssignment(Base):
    __tablename__ = "worker_tenant_assignments"

    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.id"), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WorkerEnrollment(Base):
    __tablename__ = "worker_enrollments"
    __table_args__ = (
        Index("ix_worker_enrollments_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    worker_key: Mapped[str] = mapped_column(String(120), index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    repo_url: Mapped[str] = mapped_column(Text)
    repo_branch: Mapped[str] = mapped_column(String(120), default="main")
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    worker_id: Mapped[str | None] = mapped_column(ForeignKey("workers.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WorkerCredential(Base):
    __tablename__ = "worker_credentials"
    __table_args__ = (
        Index("ix_worker_credentials_worker_status", "worker_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkerOperation(Base):
    __tablename__ = "worker_operations"
    __table_args__ = (
        Index("ix_worker_operations_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    worker_id: Mapped[str | None] = mapped_column(ForeignKey("workers.id"), nullable=True, index=True)
    enrollment_id: Mapped[str | None] = mapped_column(
        ForeignKey("worker_enrollments.id"), nullable=True
    )
    operation_type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    host: Mapped[str] = mapped_column(String(255))
    ssh_user: Mapped[str] = mapped_column(String(80))
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AIProviderConfig(Base):
    __tablename__ = "ai_provider_configs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "worker_id", name="uq_ai_provider_configs_tenant_worker"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    provider_type: Mapped[str] = mapped_column(String(40), default="openai_compatible")
    provider_name: Mapped[str] = mapped_column(String(80), default="custom")
    base_url: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(160))
    api_key_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_key_hint: Mapped[str | None] = mapped_column(String(24), nullable=True)
    execution_scope: Mapped[str] = mapped_column(String(24), default="worker")
    worker_id: Mapped[str | None] = mapped_column(ForeignKey("workers.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="configured", index=True)
    last_test_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    last_test_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class FacebookAccount(Base):
    __tablename__ = "facebook_accounts"
    __table_args__ = (
        Index("ix_facebook_accounts_tenant_worker", "tenant_id", "assigned_worker_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    assigned_worker_id: Mapped[str] = mapped_column(ForeignKey("workers.id"), index=True)
    label: Mapped[str] = mapped_column(String(160))
    profile_key: Mapped[str] = mapped_column(String(120), unique=True, default=new_id)
    status: Mapped[str] = mapped_column(String(32), default="not_authenticated", index=True)
    facebook_user_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    worker: Mapped[Worker] = relationship()
    sessions: Mapped[list[BrowserSession]] = relationship(back_populates="account")


class BrowserSession(Base):
    __tablename__ = "browser_sessions"
    __table_args__ = (
        Index("ix_browser_sessions_worker_status", "worker_id", "status"),
        Index("ix_browser_sessions_account_status", "account_id", "status"),
        Index(
            "uq_browser_sessions_one_active_per_account",
            "account_id",
            unique=True,
            sqlite_where=text(
                "status IN ('requested','starting','awaiting_user','ready','closing')"
            ),
            postgresql_where=text(
                "status IN ('requested','starting','awaiting_user','ready','closing')"
            ),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("facebook_accounts.id"), index=True)
    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="requested", index=True)
    launch_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    novnc_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    web_port: Mapped[int | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped[FacebookAccount] = relationship(back_populates="sessions")
    worker: Mapped[Worker] = relationship()


class AdAccount(Base):
    __tablename__ = "ad_accounts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "meta_ad_account_id", name="uq_ad_accounts_tenant_meta_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    facebook_account_id: Mapped[str] = mapped_column(ForeignKey("facebook_accounts.id"), index=True)
    meta_ad_account_id: Mapped[str] = mapped_column(String(80))
    label: Mapped[str] = mapped_column(String(160))
    currency: Mapped[str] = mapped_column(String(3))
    timezone_name: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class MetaResource(Base):
    __tablename__ = "meta_resources"
    __table_args__ = (
        UniqueConstraint(
            "ad_account_id",
            "kind",
            "label",
            name="uq_meta_resources_account_kind_label",
        ),
        Index("ix_meta_resources_tenant_kind", "tenant_id", "kind"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    ad_account_id: Mapped[str] = mapped_column(ForeignKey("ad_accounts.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    label: Mapped[str] = mapped_column(String(200))
    external_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="unverified", index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    verified_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CreativeAsset(Base):
    __tablename__ = "creative_assets"
    __table_args__ = (
        UniqueConstraint(
            "ad_account_id",
            "sha256",
            name="uq_creative_assets_account_sha256",
        ),
        Index("ix_creative_assets_tenant_status", "tenant_id", "status"),
        CheckConstraint("byte_size > 0", name="ck_creative_assets_positive_size"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    ad_account_id: Mapped[str] = mapped_column(ForeignKey("ad_accounts.id"), index=True)
    label: Mapped[str] = mapped_column(String(200))
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    byte_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    storage_path: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="ready", index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CampaignDraft(Base):
    __tablename__ = "campaign_drafts"
    __table_args__ = (
        CheckConstraint("daily_budget_minor > 0", name="ck_campaign_drafts_positive_budget"),
        Index("ix_campaign_drafts_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    ad_account_id: Mapped[str] = mapped_column(ForeignKey("ad_accounts.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    objective: Mapped[str] = mapped_column(String(40))
    daily_budget_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    targeting_json: Mapped[dict] = mapped_column(JSON, default=dict)
    creative_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    updated_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        Index("ix_approval_requests_tenant_status", "tenant_id", "status"),
        Index(
            "uq_approval_requests_one_pending_per_campaign",
            "campaign_draft_id",
            unique=True,
            sqlite_where=text("status = 'pending'"),
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    campaign_draft_id: Mapped[str] = mapped_column(ForeignKey("campaign_drafts.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    requested_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decided_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    snapshot_json: Mapped[dict] = mapped_column(JSON)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(24), default="user")
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ExecutionJob(Base):
    __tablename__ = "execution_jobs"
    __table_args__ = (
        Index("ix_execution_jobs_worker_status", "worker_id", "status"),
        Index("ix_execution_jobs_tenant_status", "tenant_id", "status"),
        Index(
            "uq_execution_jobs_one_active_preflight",
            "campaign_draft_id",
            "job_type",
            unique=True,
            sqlite_where=text("status IN ('queued','claimed','running')"),
            postgresql_where=text("status IN ('queued','claimed','running')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    campaign_draft_id: Mapped[str] = mapped_column(ForeignKey("campaign_drafts.id"), index=True)
    approval_request_id: Mapped[str] = mapped_column(ForeignKey("approval_requests.id"))
    ad_account_id: Mapped[str] = mapped_column(ForeignKey("ad_accounts.id"), index=True)
    facebook_account_id: Mapped[str] = mapped_column(ForeignKey("facebook_accounts.id"), index=True)
    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.id"), index=True)
    job_type: Mapped[str] = mapped_column(String(32), default="preflight")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    payload_json: Mapped[dict] = mapped_column(JSON)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    facebook_account: Mapped[FacebookAccount] = relationship()


class ExecutionArtifact(Base):
    __tablename__ = "execution_artifacts"
    __table_args__ = (
        UniqueConstraint("execution_job_id", "kind", name="uq_execution_artifacts_job_kind"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    execution_job_id: Mapped[str] = mapped_column(ForeignKey("execution_jobs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    storage_path: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(120))
    byte_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ReportSchedule(Base):
    __tablename__ = "report_schedules"
    __table_args__ = (
        Index("ix_report_schedules_tenant_status", "tenant_id", "status"),
        Index("ix_report_schedules_worker_due", "worker_id", "status", "next_run_at"),
        CheckConstraint("lookback_days BETWEEN 1 AND 90", name="ck_report_schedules_lookback"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    ad_account_id: Mapped[str] = mapped_column(ForeignKey("ad_accounts.id"), index=True)
    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="enabled", index=True)
    cadence: Mapped[str] = mapped_column(String(24), default="daily")
    local_time: Mapped[str] = mapped_column(String(5))
    timezone_name: Mapped[str] = mapped_column(String(80))
    lookback_days: Mapped[int] = mapped_column(Integer, default=7)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    next_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    last_enqueued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class ReportJob(Base):
    __tablename__ = "report_jobs"
    __table_args__ = (
        Index("ix_report_jobs_worker_status", "worker_id", "status"),
        Index("ix_report_jobs_tenant_status", "tenant_id", "status"),
        Index(
            "uq_report_jobs_one_active_per_account",
            "ad_account_id",
            unique=True,
            sqlite_where=text("status IN ('queued','claimed','running')"),
            postgresql_where=text("status IN ('queued','claimed','running')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    ad_account_id: Mapped[str] = mapped_column(ForeignKey("ad_accounts.id"), index=True)
    facebook_account_id: Mapped[str] = mapped_column(ForeignKey("facebook_accounts.id"), index=True)
    worker_id: Mapped[str] = mapped_column(ForeignKey("workers.id"), index=True)
    schedule_id: Mapped[str | None] = mapped_column(
        ForeignKey("report_schedules.id"), nullable=True, index=True
    )
    trigger: Mapped[str] = mapped_column(String(24), default="manual")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    range_start: Mapped[date] = mapped_column()
    range_end: Mapped[date] = mapped_column()
    payload_json: Mapped[dict] = mapped_column(JSON)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    delivery_status: Mapped[str] = mapped_column(String(32), default="not_requested", index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    facebook_account: Mapped[FacebookAccount] = relationship()


class ReportSnapshot(Base):
    __tablename__ = "report_snapshots"
    __table_args__ = (
        UniqueConstraint("report_job_id", name="uq_report_snapshots_job"),
        Index("ix_report_snapshots_account_collected", "ad_account_id", "collected_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    report_job_id: Mapped[str] = mapped_column(ForeignKey("report_jobs.id"), index=True)
    ad_account_id: Mapped[str] = mapped_column(ForeignKey("ad_accounts.id"), index=True)
    range_start: Mapped[date] = mapped_column()
    range_end: Mapped[date] = mapped_column()
    source: Mapped[str] = mapped_column(String(64), default="meta_ads_manager_dom")
    currency: Mapped[str] = mapped_column(String(3))
    totals_json: Mapped[dict] = mapped_column(JSON, default=dict)
    campaigns_json: Mapped[list] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
