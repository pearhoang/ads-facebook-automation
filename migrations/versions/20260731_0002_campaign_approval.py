"""Add ad accounts, campaign drafts, approvals, and audit events.

Revision ID: 20260731_0002
Revises: 20260731_0001
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260731_0002"
down_revision: Union[str, Sequence[str], None] = "20260731_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ad_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("facebook_account_id", sa.String(length=36), nullable=False),
        sa.Column("meta_ad_account_id", sa.String(length=80), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("timezone_name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["facebook_account_id"], ["facebook_accounts.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "meta_ad_account_id", name="uq_ad_accounts_tenant_meta_id"),
    )
    op.create_index("ix_ad_accounts_facebook_account_id", "ad_accounts", ["facebook_account_id"])
    op.create_index("ix_ad_accounts_status", "ad_accounts", ["status"])
    op.create_index("ix_ad_accounts_tenant_id", "ad_accounts", ["tenant_id"])

    op.create_table(
        "campaign_drafts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("ad_account_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("objective", sa.String(length=40), nullable=False),
        sa.Column("daily_budget_minor", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("targeting_json", sa.JSON(), nullable=False),
        sa.Column("creative_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("updated_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("daily_budget_minor > 0", name="ck_campaign_drafts_positive_budget"),
        sa.ForeignKeyConstraint(["ad_account_id"], ["ad_accounts.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaign_drafts_ad_account_id", "campaign_drafts", ["ad_account_id"])
    op.create_index("ix_campaign_drafts_status", "campaign_drafts", ["status"])
    op.create_index("ix_campaign_drafts_tenant_id", "campaign_drafts", ["tenant_id"])
    op.create_index("ix_campaign_drafts_tenant_status", "campaign_drafts", ["tenant_id", "status"])

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("campaign_draft_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("decided_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("snapshot_json", sa.JSON(), nullable=False),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["campaign_draft_id"], ["campaign_drafts.id"]),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_requests_campaign_draft_id", "approval_requests", ["campaign_draft_id"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])
    op.create_index("ix_approval_requests_tenant_id", "approval_requests", ["tenant_id"])
    op.create_index("ix_approval_requests_tenant_status", "approval_requests", ["tenant_id", "status"])
    pending = sa.text("status = 'pending'")
    op.create_index(
        "uq_approval_requests_one_pending_per_campaign",
        "approval_requests",
        ["campaign_draft_id"],
        unique=True,
        sqlite_where=pending,
        postgresql_where=pending,
    )

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("actor_user_id", sa.String(length=36), nullable=True),
        sa.Column("actor_type", sa.String(length=24), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_action", "audit_events", ["action"])
    op.create_index("ix_audit_events_entity_id", "audit_events", ["entity_id"])
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"])
    op.create_index("ix_audit_events_tenant_created", "audit_events", ["tenant_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_tenant_created", table_name="audit_events")
    op.drop_index("ix_audit_events_tenant_id", table_name="audit_events")
    op.drop_index("ix_audit_events_entity_id", table_name="audit_events")
    op.drop_index("ix_audit_events_action", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("uq_approval_requests_one_pending_per_campaign", table_name="approval_requests")
    op.drop_index("ix_approval_requests_tenant_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_tenant_id", table_name="approval_requests")
    op.drop_index("ix_approval_requests_status", table_name="approval_requests")
    op.drop_index("ix_approval_requests_campaign_draft_id", table_name="approval_requests")
    op.drop_table("approval_requests")
    op.drop_index("ix_campaign_drafts_tenant_status", table_name="campaign_drafts")
    op.drop_index("ix_campaign_drafts_tenant_id", table_name="campaign_drafts")
    op.drop_index("ix_campaign_drafts_status", table_name="campaign_drafts")
    op.drop_index("ix_campaign_drafts_ad_account_id", table_name="campaign_drafts")
    op.drop_table("campaign_drafts")
    op.drop_index("ix_ad_accounts_tenant_id", table_name="ad_accounts")
    op.drop_index("ix_ad_accounts_status", table_name="ad_accounts")
    op.drop_index("ix_ad_accounts_facebook_account_id", table_name="ad_accounts")
    op.drop_table("ad_accounts")
