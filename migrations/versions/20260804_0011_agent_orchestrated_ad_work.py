"""Add agent-orchestrated ad work requests and recovery memory.

Revision ID: 20260804_0011
Revises: 20260804_0010
Create Date: 2026-08-04
"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "20260804_0011"
down_revision: Union[str, Sequence[str], None] = "20260804_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ad_automation_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("worker_id", sa.String(length=36), nullable=False),
        sa.Column("facebook_account_id", sa.String(length=36), nullable=False),
        sa.Column("ad_account_id", sa.String(length=36), nullable=False),
        sa.Column("campaign_draft_id", sa.String(length=36), nullable=True),
        sa.Column("approval_request_id", sa.String(length=36), nullable=True),
        sa.Column("execution_job_id", sa.String(length=36), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="telegram"),
        sa.Column("source_session_id", sa.String(length=255), nullable=True),
        sa.Column("source_message_id", sa.String(length=160), nullable=True),
        sa.Column("intent", sa.String(length=64), nullable=False, server_default="create_campaign"),
        sa.Column("request_text", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="planning"),
        sa.Column("stage", sa.String(length=48), nullable=False, server_default="intent"),
        sa.Column("progress_message", sa.Text(), nullable=False, server_default="Đang phân tích yêu cầu."),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("resolution_json", sa.JSON(), nullable=False),
        sa.Column("recovery_json", sa.JSON(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recovery_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.ForeignKeyConstraint(["facebook_account_id"], ["facebook_accounts.id"]),
        sa.ForeignKeyConstraint(["ad_account_id"], ["ad_accounts.id"]),
        sa.ForeignKeyConstraint(["campaign_draft_id"], ["campaign_drafts.id"]),
        sa.ForeignKeyConstraint(["approval_request_id"], ["approval_requests.id"]),
        sa.ForeignKeyConstraint(["execution_job_id"], ["execution_jobs.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ad_automation_requests_tenant_id", "ad_automation_requests", ["tenant_id"])
    op.create_index("ix_ad_automation_requests_worker_id", "ad_automation_requests", ["worker_id"])
    op.create_index("ix_ad_automation_requests_facebook_account_id", "ad_automation_requests", ["facebook_account_id"])
    op.create_index("ix_ad_automation_requests_ad_account_id", "ad_automation_requests", ["ad_account_id"])
    op.create_index("ix_ad_automation_requests_campaign_draft_id", "ad_automation_requests", ["campaign_draft_id"])
    op.create_index("ix_ad_automation_requests_execution_job_id", "ad_automation_requests", ["execution_job_id"])
    op.create_index("ix_ad_automation_requests_source", "ad_automation_requests", ["source"])
    op.create_index("ix_ad_automation_requests_status", "ad_automation_requests", ["status"])
    op.create_index("ix_ad_automation_requests_tenant_updated", "ad_automation_requests", ["tenant_id", "updated_at"])
    op.create_index("ix_ad_automation_requests_worker_status", "ad_automation_requests", ["worker_id", "status"])

    op.create_table(
        "ad_automation_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("request_id", sa.String(length=36), nullable=False),
        sa.Column("actor_type", sa.String(length=24), nullable=False, server_default="agent"),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("stage", sa.String(length=48), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["request_id"], ["ad_automation_requests.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ad_automation_events_tenant_id", "ad_automation_events", ["tenant_id"])
    op.create_index("ix_ad_automation_events_request_id", "ad_automation_events", ["request_id"])
    op.create_index("ix_ad_automation_events_event_type", "ad_automation_events", ["event_type"])
    op.create_index("ix_ad_automation_events_request_created", "ad_automation_events", ["request_id", "created_at"])

    op.create_table(
        "agent_workflow_learnings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("worker_id", sa.String(length=36), nullable=False),
        sa.Column("learning_key", sa.String(length=160), nullable=False),
        sa.Column("symptom", sa.Text(), nullable=False),
        sa.Column("cause", sa.Text(), nullable=True),
        sa.Column("recovery_plan_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="proposed"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "worker_id", "learning_key", name="uq_agent_learning_worker_key"),
    )
    op.create_index("ix_agent_workflow_learnings_tenant_id", "agent_workflow_learnings", ["tenant_id"])
    op.create_index("ix_agent_workflow_learnings_worker_id", "agent_workflow_learnings", ["worker_id"])
    op.create_index("ix_agent_workflow_learnings_status", "agent_workflow_learnings", ["status"])
    op.create_index("ix_agent_learning_worker_status", "agent_workflow_learnings", ["worker_id", "status"])

    # Preserve the useful production/demo history while changing the primary UX
    # from manual campaign forms to one agent-facing work queue.
    bind = op.get_bind()
    existing = list(
        bind.execute(
            sa.text(
                """
                SELECT c.id, c.tenant_id, c.ad_account_id, c.name, c.objective,
                       c.daily_budget_minor, c.currency, c.targeting_json, c.creative_json,
                       c.status, c.version, c.created_by_user_id, c.created_at, c.updated_at,
                       a.facebook_account_id, f.assigned_worker_id
                FROM campaign_drafts c
                JOIN ad_accounts a ON a.id = c.ad_account_id
                JOIN facebook_accounts f ON f.id = a.facebook_account_id
                """
            )
        ).mappings()
    )
    request_table = sa.table(
        "ad_automation_requests",
        sa.column("id", sa.String), sa.column("tenant_id", sa.String),
        sa.column("worker_id", sa.String), sa.column("facebook_account_id", sa.String),
        sa.column("ad_account_id", sa.String), sa.column("campaign_draft_id", sa.String),
        sa.column("approval_request_id", sa.String), sa.column("execution_job_id", sa.String),
        sa.column("source", sa.String), sa.column("intent", sa.String),
        sa.column("request_text", sa.Text), sa.column("title", sa.String),
        sa.column("status", sa.String), sa.column("stage", sa.String),
        sa.column("progress_message", sa.Text), sa.column("plan_json", sa.JSON),
        sa.column("resolution_json", sa.JSON), sa.column("recovery_json", sa.JSON),
        sa.column("requested_by_user_id", sa.String), sa.column("attempt_count", sa.Integer),
        sa.column("recovery_count", sa.Integer), sa.column("requested_at", sa.DateTime(timezone=True)),
        sa.column("completed_at", sa.DateTime(timezone=True)), sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    event_table = sa.table(
        "ad_automation_events",
        sa.column("id", sa.String), sa.column("tenant_id", sa.String),
        sa.column("request_id", sa.String), sa.column("actor_type", sa.String),
        sa.column("event_type", sa.String), sa.column("stage", sa.String),
        sa.column("message", sa.Text), sa.column("payload_json", sa.JSON),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    for row in existing:
        latest = bind.execute(
            sa.text(
                """
                SELECT id, status, job_type, attempt_count, last_error, completed_at
                FROM execution_jobs WHERE campaign_draft_id = :campaign_id
                ORDER BY requested_at DESC LIMIT 1
                """
            ),
            {"campaign_id": row["id"]},
        ).mappings().first()
        approval_id = bind.execute(
            sa.text(
                "SELECT id FROM approval_requests WHERE campaign_draft_id = :campaign_id ORDER BY requested_at DESC LIMIT 1"
            ),
            {"campaign_id": row["id"]},
        ).scalar()
        request_id = str(uuid4())
        execution_status = latest["status"] if latest else None
        if execution_status == "succeeded":
            work_status, stage, progress = "completed", "review", "Lịch sử cũ: execution đã hoàn tất và dừng trước publish."
        elif execution_status == "awaiting_user":
            work_status, stage, progress = "awaiting_user", "handoff", "Lịch sử cũ: execution đang cần người dùng xử lý."
        elif execution_status == "failed":
            work_status, stage, progress = "failed", "recovery", "Lịch sử cũ: execution chưa hoàn tất."
        elif execution_status in {"queued", "claimed", "running"}:
            work_status, stage, progress = "running", (latest["job_type"] or "preflight"), "Lịch sử cũ: worker đang xử lý."
        elif row["status"] == "pending_approval":
            work_status, stage, progress = "awaiting_approval", "approval", "Lịch sử cũ: đang chờ duyệt."
        else:
            work_status, stage, progress = "completed", "review", "Đã nhập lịch sử campaign nội bộ vào màn hình theo dõi."
        plan = {
            "campaign_id": row["id"], "version": row["version"], "name": row["name"],
            "objective": row["objective"], "daily_budget_minor": row["daily_budget_minor"],
            "currency": row["currency"], "targeting_json": row["targeting_json"] or {},
            "creative_json": row["creative_json"] or {},
        }
        bind.execute(
            request_table.insert().values(
                id=request_id, tenant_id=row["tenant_id"], worker_id=row["assigned_worker_id"],
                facebook_account_id=row["facebook_account_id"], ad_account_id=row["ad_account_id"],
                campaign_draft_id=row["id"], approval_request_id=approval_id,
                execution_job_id=latest["id"] if latest else None, source="import",
                intent="create_campaign", request_text=f"Campaign lịch sử: {row['name']}", title=row["name"],
                status=work_status, stage=stage, progress_message=progress, plan_json=plan,
                resolution_json={"imported_from": "campaign_drafts"}, recovery_json={"max_automatic_retries": 1, "learnings": []},
                requested_by_user_id=row["created_by_user_id"], attempt_count=latest["attempt_count"] if latest else 0,
                recovery_count=0, requested_at=row["created_at"], completed_at=latest["completed_at"] if latest and work_status in {"completed", "failed"} else None,
                updated_at=row["updated_at"],
            )
        )
        bind.execute(
            event_table.insert().values(
                id=str(uuid4()), tenant_id=row["tenant_id"], request_id=request_id,
                actor_type="migration", event_type="request.imported", stage=stage,
                message=progress, payload_json={"campaign_draft_id": row["id"]}, created_at=row["updated_at"],
            )
        )


def downgrade() -> None:
    op.drop_table("agent_workflow_learnings")
    op.drop_table("ad_automation_events")
    op.drop_table("ad_automation_requests")
