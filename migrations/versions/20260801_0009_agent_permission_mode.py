"""Add per-worker Hermes permission mode.

Revision ID: 20260801_0009
Revises: 20260801_0008
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260801_0009"
down_revision: Union[str, Sequence[str], None] = "20260801_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_provider_configs",
        sa.Column(
            "agent_permission_mode",
            sa.String(length=32),
            nullable=False,
            server_default="ads_safe",
        ),
    )


def downgrade() -> None:
    op.drop_column("ai_provider_configs", "agent_permission_mode")
