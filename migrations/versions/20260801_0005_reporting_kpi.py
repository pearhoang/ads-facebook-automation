"""Add reporting schedules, jobs and immutable KPI snapshots.

Revision ID: 20260801_0005
Revises: 20260731_0004
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260801_0005"
down_revision: Union[str, Sequence[str], None] = "20260731_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "report_schedules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("ad_account_id", sa.String(length=36), nullable=False),
        sa.Column("worker_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("cadence", sa.String(length=24), nullable=False),
        sa.Column("local_time", sa.String(length=5), nullable=False),
        sa.Column("timezone_name", sa.String(length=80), nullable=False),
        sa.Column("lookback_days", sa.Integer(), nullable=False),
        sa.Column("telegram_chat_id", sa.String(length=80), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_enqueued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "lookback_days BETWEEN 1 AND 90",
            name="ck_report_schedules_lookback",
        ),
        sa.ForeignKeyConstraint(["ad_account_id"], ["ad_accounts.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_schedules_ad_account_id", "report_schedules", ["ad_account_id"])
    op.create_index("ix_report_schedules_next_run_at", "report_schedules", ["next_run_at"])
    op.create_index("ix_report_schedules_status", "report_schedules", ["status"])
    op.create_index("ix_report_schedules_tenant_id", "report_schedules", ["tenant_id"])
    op.create_index(
        "ix_report_schedules_tenant_status",
        "report_schedules",
        ["tenant_id", "status"],
    )
    op.create_index("ix_report_schedules_worker_id", "report_schedules", ["worker_id"])
    op.create_index(
        "ix_report_schedules_worker_due",
        "report_schedules",
        ["worker_id", "status", "next_run_at"],
    )

    op.create_table(
        "report_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("ad_account_id", sa.String(length=36), nullable=False),
        sa.Column("facebook_account_id", sa.String(length=36), nullable=False),
        sa.Column("worker_id", sa.String(length=36), nullable=False),
        sa.Column("schedule_id", sa.String(length=36), nullable=True),
        sa.Column("trigger", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("range_start", sa.Date(), nullable=False),
        sa.Column("range_end", sa.Date(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("delivery_status", sa.String(length=32), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ad_account_id"], ["ad_accounts.id"]),
        sa.ForeignKeyConstraint(["facebook_account_id"], ["facebook_accounts.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["schedule_id"], ["report_schedules.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_jobs_ad_account_id", "report_jobs", ["ad_account_id"])
    op.create_index("ix_report_jobs_delivery_status", "report_jobs", ["delivery_status"])
    op.create_index("ix_report_jobs_facebook_account_id", "report_jobs", ["facebook_account_id"])
    op.create_index("ix_report_jobs_schedule_id", "report_jobs", ["schedule_id"])
    op.create_index("ix_report_jobs_status", "report_jobs", ["status"])
    op.create_index("ix_report_jobs_tenant_id", "report_jobs", ["tenant_id"])
    op.create_index("ix_report_jobs_tenant_status", "report_jobs", ["tenant_id", "status"])
    op.create_index("ix_report_jobs_worker_id", "report_jobs", ["worker_id"])
    op.create_index("ix_report_jobs_worker_status", "report_jobs", ["worker_id", "status"])
    op.create_index(
        "uq_report_jobs_one_active_per_account",
        "report_jobs",
        ["ad_account_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued','claimed','running')"),
        sqlite_where=sa.text("status IN ('queued','claimed','running')"),
    )

    op.create_table(
        "report_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("report_job_id", sa.String(length=36), nullable=False),
        sa.Column("ad_account_id", sa.String(length=36), nullable=False),
        sa.Column("range_start", sa.Date(), nullable=False),
        sa.Column("range_end", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("totals_json", sa.JSON(), nullable=False),
        sa.Column("campaigns_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ad_account_id"], ["ad_accounts.id"]),
        sa.ForeignKeyConstraint(["report_job_id"], ["report_jobs.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_job_id", name="uq_report_snapshots_job"),
    )
    op.create_index("ix_report_snapshots_ad_account_id", "report_snapshots", ["ad_account_id"])
    op.create_index(
        "ix_report_snapshots_account_collected",
        "report_snapshots",
        ["ad_account_id", "collected_at"],
    )
    op.create_index("ix_report_snapshots_collected_at", "report_snapshots", ["collected_at"])
    op.create_index("ix_report_snapshots_report_job_id", "report_snapshots", ["report_job_id"])
    op.create_index("ix_report_snapshots_tenant_id", "report_snapshots", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_report_snapshots_tenant_id", table_name="report_snapshots")
    op.drop_index("ix_report_snapshots_report_job_id", table_name="report_snapshots")
    op.drop_index("ix_report_snapshots_collected_at", table_name="report_snapshots")
    op.drop_index("ix_report_snapshots_account_collected", table_name="report_snapshots")
    op.drop_index("ix_report_snapshots_ad_account_id", table_name="report_snapshots")
    op.drop_table("report_snapshots")
    op.drop_index("uq_report_jobs_one_active_per_account", table_name="report_jobs")
    op.drop_index("ix_report_jobs_worker_status", table_name="report_jobs")
    op.drop_index("ix_report_jobs_worker_id", table_name="report_jobs")
    op.drop_index("ix_report_jobs_tenant_status", table_name="report_jobs")
    op.drop_index("ix_report_jobs_tenant_id", table_name="report_jobs")
    op.drop_index("ix_report_jobs_status", table_name="report_jobs")
    op.drop_index("ix_report_jobs_schedule_id", table_name="report_jobs")
    op.drop_index("ix_report_jobs_facebook_account_id", table_name="report_jobs")
    op.drop_index("ix_report_jobs_delivery_status", table_name="report_jobs")
    op.drop_index("ix_report_jobs_ad_account_id", table_name="report_jobs")
    op.drop_table("report_jobs")
    op.drop_index("ix_report_schedules_worker_due", table_name="report_schedules")
    op.drop_index("ix_report_schedules_worker_id", table_name="report_schedules")
    op.drop_index("ix_report_schedules_tenant_status", table_name="report_schedules")
    op.drop_index("ix_report_schedules_tenant_id", table_name="report_schedules")
    op.drop_index("ix_report_schedules_status", table_name="report_schedules")
    op.drop_index("ix_report_schedules_next_run_at", table_name="report_schedules")
    op.drop_index("ix_report_schedules_ad_account_id", table_name="report_schedules")
    op.drop_table("report_schedules")

