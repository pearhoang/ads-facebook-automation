"""Add Meta resources, creative assets and browser handoff URL.

Revision ID: 20260731_0004
Revises: 20260731_0003
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260731_0004"
down_revision: Union[str, Sequence[str], None] = "20260731_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("browser_sessions", sa.Column("launch_url", sa.Text(), nullable=True))

    op.create_table(
        "meta_resources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("ad_account_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("external_id", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("verified_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["ad_account_id"], ["ad_accounts.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["verified_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ad_account_id",
            "kind",
            "label",
            name="uq_meta_resources_account_kind_label",
        ),
    )
    op.create_index("ix_meta_resources_ad_account_id", "meta_resources", ["ad_account_id"])
    op.create_index("ix_meta_resources_kind", "meta_resources", ["kind"])
    op.create_index("ix_meta_resources_status", "meta_resources", ["status"])
    op.create_index("ix_meta_resources_tenant_id", "meta_resources", ["tenant_id"])
    op.create_index("ix_meta_resources_tenant_kind", "meta_resources", ["tenant_id", "kind"])

    op.create_table(
        "creative_assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.String(length=36), nullable=False),
        sa.Column("ad_account_id", sa.String(length=36), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("byte_size > 0", name="ck_creative_assets_positive_size"),
        sa.ForeignKeyConstraint(["ad_account_id"], ["ad_accounts.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ad_account_id",
            "sha256",
            name="uq_creative_assets_account_sha256",
        ),
    )
    op.create_index("ix_creative_assets_ad_account_id", "creative_assets", ["ad_account_id"])
    op.create_index("ix_creative_assets_status", "creative_assets", ["status"])
    op.create_index("ix_creative_assets_tenant_id", "creative_assets", ["tenant_id"])
    op.create_index(
        "ix_creative_assets_tenant_status",
        "creative_assets",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_creative_assets_tenant_status", table_name="creative_assets")
    op.drop_index("ix_creative_assets_tenant_id", table_name="creative_assets")
    op.drop_index("ix_creative_assets_status", table_name="creative_assets")
    op.drop_index("ix_creative_assets_ad_account_id", table_name="creative_assets")
    op.drop_table("creative_assets")
    op.drop_index("ix_meta_resources_tenant_kind", table_name="meta_resources")
    op.drop_index("ix_meta_resources_tenant_id", table_name="meta_resources")
    op.drop_index("ix_meta_resources_status", table_name="meta_resources")
    op.drop_index("ix_meta_resources_kind", table_name="meta_resources")
    op.drop_index("ix_meta_resources_ad_account_id", table_name="meta_resources")
    op.drop_table("meta_resources")
    op.drop_column("browser_sessions", "launch_url")
