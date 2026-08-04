"""Store encrypted SSH password for reusable worker operations.

Revision ID: 20260804_0010
Revises: 20260801_0009
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260804_0010"
down_revision: Union[str, Sequence[str], None] = "20260801_0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("workers", sa.Column("ssh_password_ciphertext", sa.Text(), nullable=True))
    op.add_column(
        "worker_enrollments",
        sa.Column("ssh_password_ciphertext", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("worker_enrollments", "ssh_password_ciphertext")
    op.drop_column("workers", "ssh_password_ciphertext")
