"""Create approval requests table.

Revision ID: 20260803_0008
Revises: 20260730_0007
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260803_0008"
down_revision: str | None = "20260730_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "approval_requests",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "action",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "requested_by",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "approved_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "approved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["user_accounts.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"],
            ["user_accounts.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_approval_requests_status",
        "approval_requests",
        ["status"],
    )

    op.create_index(
        "ix_approval_requests_requested_by",
        "approval_requests",
        ["requested_by"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_approval_requests_requested_by",
        table_name="approval_requests",
    )

    op.drop_index(
        "ix_approval_requests_status",
        table_name="approval_requests",
    )

    op.drop_table("approval_requests")
