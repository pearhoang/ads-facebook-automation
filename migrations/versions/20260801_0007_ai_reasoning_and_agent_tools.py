"""Add per-worker Hermes thinking and reasoning settings.

Revision ID: 20260801_0007
Revises: 20260801_0006
Create Date: 2026-08-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260801_0007"
down_revision: Union[str, Sequence[str], None] = "20260801_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ai_provider_configs",
        sa.Column("thinking_mode", sa.String(length=16), server_default="auto", nullable=False),
    )
    op.add_column(
        "ai_provider_configs",
        sa.Column(
            "reasoning_effort",
            sa.String(length=16),
            server_default="provider_default",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("ai_provider_configs", "reasoning_effort")
    op.drop_column("ai_provider_configs", "thinking_mode")
