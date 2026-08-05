"""Add approval execution tracking.

Revision ID: bd0bf0d1e5c6
Revises: 20260803_0008
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "bd0bf0d1e5c6"
down_revision: str | None = "20260803_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "approval_requests",
        sa.Column(
            "execution_status",
            sa.Text(),
            nullable=True,
        ),
    )

    op.add_column(
        "approval_requests",
        sa.Column(
            "executed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "approval_requests",
        sa.Column(
            "execution_result",
            sa.JSON(),
            nullable=True,
        ),
    )

    op.add_column(
        "approval_requests",
        sa.Column(
            "execution_error",
            sa.Text(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "approval_requests",
        "execution_error",
    )

    op.drop_column(
        "approval_requests",
        "execution_result",
    )

    op.drop_column(
        "approval_requests",
        "executed_at",
    )

    op.drop_column(
        "approval_requests",
        "execution_status",
    )
