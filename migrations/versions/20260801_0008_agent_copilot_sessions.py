"""Add Hermes conversation mirror and outbound agent jobs.

Revision ID: 20260801_0008
Revises: 20260801_0007
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260801_0008"
down_revision: Union[str, Sequence[str], None] = "20260801_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_conversations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("worker_id", sa.String(length=36), nullable=False),
        sa.Column("profile", sa.String(length=16), nullable=False),
        sa.Column("hermes_session_id", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "worker_id", "profile", "hermes_session_id", name="uq_agent_conversations_hermes_session"),
    )
    op.create_index("ix_agent_conversations_tenant_id", "agent_conversations", ["tenant_id"])
    op.create_index("ix_agent_conversations_worker_id", "agent_conversations", ["worker_id"])
    op.create_index("ix_agent_conversations_profile", "agent_conversations", ["profile"])
    op.create_index("ix_agent_conversations_source", "agent_conversations", ["source"])
    op.create_index("ix_agent_conversations_status", "agent_conversations", ["status"])
    op.create_index("ix_agent_conversations_tenant_updated", "agent_conversations", ["tenant_id", "updated_at"])
    op.create_index("ix_agent_conversations_worker_profile", "agent_conversations", ["worker_id", "profile"])

    op.create_table(
        "agent_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("external_key", sa.String(length=255), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversations.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("conversation_id", "external_key", name="uq_agent_messages_external_key"),
    )
    op.create_index("ix_agent_messages_tenant_id", "agent_messages", ["tenant_id"])
    op.create_index("ix_agent_messages_conversation_id", "agent_messages", ["conversation_id"])
    op.create_index("ix_agent_messages_conversation_created", "agent_messages", ["conversation_id", "created_at"])

    op.create_table(
        "agent_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("worker_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=True),
        sa.Column("profile", sa.String(length=16), nullable=False),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
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
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversations.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_jobs_tenant_id", "agent_jobs", ["tenant_id"])
    op.create_index("ix_agent_jobs_worker_id", "agent_jobs", ["worker_id"])
    op.create_index("ix_agent_jobs_conversation_id", "agent_jobs", ["conversation_id"])
    op.create_index("ix_agent_jobs_profile", "agent_jobs", ["profile"])
    op.create_index("ix_agent_jobs_job_type", "agent_jobs", ["job_type"])
    op.create_index("ix_agent_jobs_status", "agent_jobs", ["status"])
    op.create_index("ix_agent_jobs_worker_status", "agent_jobs", ["worker_id", "status"])
    op.create_index("ix_agent_jobs_tenant_created", "agent_jobs", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_table("agent_jobs")
    op.drop_table("agent_messages")
    op.drop_table("agent_conversations")
