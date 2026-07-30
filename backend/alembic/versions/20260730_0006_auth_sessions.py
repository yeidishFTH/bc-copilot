"""Add opaque authentication sessions.

Revision ID: 20260730_0006
Revises: 20260730_0005
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0006"
down_revision: str | None = "20260730_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "auth_sessions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "token_hash",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
        ),
        sa.Column(
            "created_ip",
            sa.String(length=64),
        ),
        sa.Column(
            "user_agent",
            sa.Text(),
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["user_accounts.id"],
            name=op.f(
                "fk_auth_sessions_account_id_user_accounts"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_auth_sessions"),
        ),
        sa.UniqueConstraint(
            "token_hash",
            name=op.f(
                "uq_auth_sessions_token_hash"
            ),
        ),
    )

    op.create_index(
        "ix_auth_sessions_account_expires",
        "auth_sessions",
        [
            "account_id",
            "expires_at",
        ],
        unique=False,
    )

    op.create_index(
        "ix_auth_sessions_active_expires",
        "auth_sessions",
        [
            "revoked_at",
            "expires_at",
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auth_sessions_active_expires",
        table_name="auth_sessions",
    )
    op.drop_index(
        "ix_auth_sessions_account_expires",
        table_name="auth_sessions",
    )
    op.drop_table("auth_sessions")
