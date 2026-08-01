"""Add execution preflight jobs and artifacts.

Revision ID: 20260731_0003
Revises: 20260731_0002
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260731_0003"
down_revision: Union[str, Sequence[str], None] = "20260731_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "execution_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("campaign_draft_id", sa.String(length=36), nullable=False),
        sa.Column("approval_request_id", sa.String(length=36), nullable=False),
        sa.Column("ad_account_id", sa.String(length=36), nullable=False),
        sa.Column("facebook_account_id", sa.String(length=36), nullable=False),
        sa.Column("worker_id", sa.String(length=36), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ad_account_id"], ["ad_accounts.id"]),
        sa.ForeignKeyConstraint(["approval_request_id"], ["approval_requests.id"]),
        sa.ForeignKeyConstraint(["campaign_draft_id"], ["campaign_drafts.id"]),
        sa.ForeignKeyConstraint(["facebook_account_id"], ["facebook_accounts.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_execution_jobs_ad_account_id", "execution_jobs", ["ad_account_id"])
    op.create_index("ix_execution_jobs_campaign_draft_id", "execution_jobs", ["campaign_draft_id"])
    op.create_index("ix_execution_jobs_facebook_account_id", "execution_jobs", ["facebook_account_id"])
    op.create_index("ix_execution_jobs_status", "execution_jobs", ["status"])
    op.create_index("ix_execution_jobs_tenant_id", "execution_jobs", ["tenant_id"])
    op.create_index("ix_execution_jobs_tenant_status", "execution_jobs", ["tenant_id", "status"])
    op.create_index("ix_execution_jobs_worker_id", "execution_jobs", ["worker_id"])
    op.create_index("ix_execution_jobs_worker_status", "execution_jobs", ["worker_id", "status"])
    active = sa.text("status IN ('queued','claimed','running')")
    op.create_index(
        "uq_execution_jobs_one_active_preflight",
        "execution_jobs",
        ["campaign_draft_id", "job_type"],
        unique=True,
        sqlite_where=active,
        postgresql_where=active,
    )

    op.create_table(
        "execution_artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("execution_job_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["execution_job_id"], ["execution_jobs.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_job_id", "kind", name="uq_execution_artifacts_job_kind"),
    )
    op.create_index("ix_execution_artifacts_execution_job_id", "execution_artifacts", ["execution_job_id"])
    op.create_index("ix_execution_artifacts_tenant_id", "execution_artifacts", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_execution_artifacts_tenant_id", table_name="execution_artifacts")
    op.drop_index("ix_execution_artifacts_execution_job_id", table_name="execution_artifacts")
    op.drop_table("execution_artifacts")
    op.drop_index("uq_execution_jobs_one_active_preflight", table_name="execution_jobs")
    op.drop_index("ix_execution_jobs_worker_status", table_name="execution_jobs")
    op.drop_index("ix_execution_jobs_worker_id", table_name="execution_jobs")
    op.drop_index("ix_execution_jobs_tenant_status", table_name="execution_jobs")
    op.drop_index("ix_execution_jobs_tenant_id", table_name="execution_jobs")
    op.drop_index("ix_execution_jobs_status", table_name="execution_jobs")
    op.drop_index("ix_execution_jobs_facebook_account_id", table_name="execution_jobs")
    op.drop_index("ix_execution_jobs_campaign_draft_id", table_name="execution_jobs")
    op.drop_index("ix_execution_jobs_ad_account_id", table_name="execution_jobs")
    op.drop_table("execution_jobs")
