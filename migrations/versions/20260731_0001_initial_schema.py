"""Initial control-plane schema.

Revision ID: 20260731_0001
Revises:
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260731_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("normalized_email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_normalized_email", "users", ["normalized_email"], unique=True)
    op.create_index("ix_users_status", "users", ["status"], unique=False)
    op.create_table(
        "workers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("worker_key", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workers_status", "workers", ["status"], unique=False)
    op.create_index("ix_workers_worker_key", "workers", ["worker_key"], unique=True)
    op.create_table(
        "tenant_memberships",
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id", "tenant_id"),
    )
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"], unique=False)
    op.create_index("ix_user_sessions_tenant_id", "user_sessions", ["tenant_id"], unique=False)
    op.create_index("ix_user_sessions_token_hash", "user_sessions", ["token_hash"], unique=True)
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"], unique=False)
    op.create_table(
        "worker_tenant_assignments",
        sa.Column("worker_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("worker_id", "tenant_id"),
    )
    op.create_table(
        "facebook_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("assigned_worker_id", sa.String(length=36), nullable=False),
        sa.Column("label", sa.String(length=160), nullable=False),
        sa.Column("profile_key", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("facebook_user_id", sa.String(length=80), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_worker_id"], ["workers.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_key"),
    )
    op.create_index("ix_facebook_accounts_assigned_worker_id", "facebook_accounts", ["assigned_worker_id"], unique=False)
    op.create_index("ix_facebook_accounts_status", "facebook_accounts", ["status"], unique=False)
    op.create_index("ix_facebook_accounts_tenant_id", "facebook_accounts", ["tenant_id"], unique=False)
    op.create_index("ix_facebook_accounts_tenant_worker", "facebook_accounts", ["tenant_id", "assigned_worker_id"], unique=False)
    op.create_table(
        "browser_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("worker_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("novnc_url", sa.Text(), nullable=True),
        sa.Column("web_port", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["facebook_accounts.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_browser_sessions_account_id", "browser_sessions", ["account_id"], unique=False)
    op.create_index("ix_browser_sessions_account_status", "browser_sessions", ["account_id", "status"], unique=False)
    op.create_index("ix_browser_sessions_status", "browser_sessions", ["status"], unique=False)
    op.create_index("ix_browser_sessions_tenant_id", "browser_sessions", ["tenant_id"], unique=False)
    op.create_index("ix_browser_sessions_worker_id", "browser_sessions", ["worker_id"], unique=False)
    op.create_index("ix_browser_sessions_worker_status", "browser_sessions", ["worker_id", "status"], unique=False)
    active_states = sa.text("status IN ('requested','starting','awaiting_user','ready','closing')")
    op.create_index(
        "uq_browser_sessions_one_active_per_account",
        "browser_sessions",
        ["account_id"],
        unique=True,
        sqlite_where=active_states,
        postgresql_where=active_states,
    )


def downgrade() -> None:
    op.drop_index("uq_browser_sessions_one_active_per_account", table_name="browser_sessions")
    op.drop_index("ix_browser_sessions_worker_status", table_name="browser_sessions")
    op.drop_index("ix_browser_sessions_worker_id", table_name="browser_sessions")
    op.drop_index("ix_browser_sessions_tenant_id", table_name="browser_sessions")
    op.drop_index("ix_browser_sessions_status", table_name="browser_sessions")
    op.drop_index("ix_browser_sessions_account_status", table_name="browser_sessions")
    op.drop_index("ix_browser_sessions_account_id", table_name="browser_sessions")
    op.drop_table("browser_sessions")
    op.drop_index("ix_facebook_accounts_tenant_worker", table_name="facebook_accounts")
    op.drop_index("ix_facebook_accounts_tenant_id", table_name="facebook_accounts")
    op.drop_index("ix_facebook_accounts_status", table_name="facebook_accounts")
    op.drop_index("ix_facebook_accounts_assigned_worker_id", table_name="facebook_accounts")
    op.drop_table("facebook_accounts")
    op.drop_table("worker_tenant_assignments")
    op.drop_index("ix_user_sessions_user_id", table_name="user_sessions")
    op.drop_index("ix_user_sessions_token_hash", table_name="user_sessions")
    op.drop_index("ix_user_sessions_tenant_id", table_name="user_sessions")
    op.drop_index("ix_user_sessions_expires_at", table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_table("tenant_memberships")
    op.drop_index("ix_workers_worker_key", table_name="workers")
    op.drop_index("ix_workers_status", table_name="workers")
    op.drop_table("workers")
    op.drop_index("ix_users_status", table_name="users")
    op.drop_index("ix_users_normalized_email", table_name="users")
    op.drop_table("users")
    op.drop_table("tenants")
