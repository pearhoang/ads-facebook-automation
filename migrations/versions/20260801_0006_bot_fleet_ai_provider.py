"""Add multi-VPS fleet enrollment and encrypted AI provider settings.

Revision ID: 20260801_0006
Revises: 20260801_0005
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260801_0006"
down_revision: Union[str, Sequence[str], None] = "20260801_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workers",
        sa.Column("lifecycle_status", sa.String(length=32), server_default="active", nullable=False),
    )
    op.add_column("workers", sa.Column("runtime_version", sa.String(length=80), nullable=True))
    op.add_column("workers", sa.Column("agent_version", sa.String(length=80), nullable=True))
    op.add_column(
        "workers",
        sa.Column("capabilities_json", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
    )
    op.add_column("workers", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column("workers", sa.Column("host", sa.String(length=255), nullable=True))
    op.add_column("workers", sa.Column("ssh_user", sa.String(length=80), nullable=True))
    op.add_column("workers", sa.Column("ssh_host_fingerprint", sa.String(length=128), nullable=True))
    op.add_column(
        "workers",
        sa.Column("install_status", sa.String(length=32), server_default="registered", nullable=False),
    )
    op.add_column("workers", sa.Column("installed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workers", sa.Column("drained_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("workers", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "workers",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workers_lifecycle_status", "workers", ["lifecycle_status"])
    op.create_index("ix_workers_install_status", "workers", ["install_status"])

    op.create_table(
        "worker_enrollments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("worker_key", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("repo_url", sa.Text(), nullable=False),
        sa.Column("repo_branch", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("worker_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_worker_enrollments_expires_at", "worker_enrollments", ["expires_at"])
    op.create_index("ix_worker_enrollments_status", "worker_enrollments", ["status"])
    op.create_index("ix_worker_enrollments_tenant_id", "worker_enrollments", ["tenant_id"])
    op.create_index(
        "ix_worker_enrollments_tenant_status",
        "worker_enrollments",
        ["tenant_id", "status"],
    )
    op.create_index("ix_worker_enrollments_token_hash", "worker_enrollments", ["token_hash"], unique=True)
    op.create_index("ix_worker_enrollments_worker_key", "worker_enrollments", ["worker_key"])

    op.create_table(
        "worker_credentials",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("worker_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_worker_credentials_status", "worker_credentials", ["status"])
    op.create_index("ix_worker_credentials_token_hash", "worker_credentials", ["token_hash"], unique=True)
    op.create_index("ix_worker_credentials_worker_id", "worker_credentials", ["worker_id"])
    op.create_index(
        "ix_worker_credentials_worker_status",
        "worker_credentials",
        ["worker_id", "status"],
    )

    op.create_table(
        "ai_provider_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("provider_type", sa.String(length=40), nullable=False),
        sa.Column("provider_name", sa.String(length=80), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("api_key_ciphertext", sa.Text(), nullable=True),
        sa.Column("api_key_hint", sa.String(length=24), nullable=True),
        sa.Column("execution_scope", sa.String(length=24), nullable=False),
        sa.Column("worker_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("last_test_status", sa.String(length=24), nullable=True),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "worker_id", name="uq_ai_provider_configs_tenant_worker"),
    )
    op.create_index("ix_ai_provider_configs_status", "ai_provider_configs", ["status"])
    op.create_index("ix_ai_provider_configs_tenant_id", "ai_provider_configs", ["tenant_id"])

    op.create_table(
        "worker_operations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("worker_id", sa.String(length=36), nullable=True),
        sa.Column("enrollment_id", sa.String(length=36), nullable=True),
        sa.Column("operation_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("ssh_user", sa.String(length=80), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["enrollment_id"], ["worker_enrollments.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_worker_operations_operation_type", "worker_operations", ["operation_type"])
    op.create_index("ix_worker_operations_status", "worker_operations", ["status"])
    op.create_index("ix_worker_operations_tenant_id", "worker_operations", ["tenant_id"])
    op.create_index(
        "ix_worker_operations_tenant_created",
        "worker_operations",
        ["tenant_id", "created_at"],
    )
    op.create_index("ix_worker_operations_worker_id", "worker_operations", ["worker_id"])


def downgrade() -> None:
    op.drop_index("ix_worker_operations_worker_id", table_name="worker_operations")
    op.drop_index("ix_worker_operations_tenant_created", table_name="worker_operations")
    op.drop_index("ix_worker_operations_tenant_id", table_name="worker_operations")
    op.drop_index("ix_worker_operations_status", table_name="worker_operations")
    op.drop_index("ix_worker_operations_operation_type", table_name="worker_operations")
    op.drop_table("worker_operations")
    op.drop_index("ix_ai_provider_configs_tenant_id", table_name="ai_provider_configs")
    op.drop_index("ix_ai_provider_configs_status", table_name="ai_provider_configs")
    op.drop_table("ai_provider_configs")
    op.drop_index("ix_worker_credentials_worker_status", table_name="worker_credentials")
    op.drop_index("ix_worker_credentials_worker_id", table_name="worker_credentials")
    op.drop_index("ix_worker_credentials_token_hash", table_name="worker_credentials")
    op.drop_index("ix_worker_credentials_status", table_name="worker_credentials")
    op.drop_table("worker_credentials")
    op.drop_index("ix_worker_enrollments_worker_key", table_name="worker_enrollments")
    op.drop_index("ix_worker_enrollments_token_hash", table_name="worker_enrollments")
    op.drop_index("ix_worker_enrollments_tenant_status", table_name="worker_enrollments")
    op.drop_index("ix_worker_enrollments_tenant_id", table_name="worker_enrollments")
    op.drop_index("ix_worker_enrollments_status", table_name="worker_enrollments")
    op.drop_index("ix_worker_enrollments_expires_at", table_name="worker_enrollments")
    op.drop_table("worker_enrollments")
    op.drop_index("ix_workers_install_status", table_name="workers")
    op.drop_index("ix_workers_lifecycle_status", table_name="workers")
    for column in (
        "updated_at",
        "revoked_at",
        "drained_at",
        "last_error",
        "installed_at",
        "install_status",
        "ssh_host_fingerprint",
        "ssh_user",
        "host",
        "capabilities_json",
        "agent_version",
        "runtime_version",
        "lifecycle_status",
    ):
        op.drop_column("workers", column)
