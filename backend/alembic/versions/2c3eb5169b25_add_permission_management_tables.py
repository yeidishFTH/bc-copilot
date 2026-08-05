"""add permission management tables

Revision ID: 2c3eb5169b25
Revises: bd0bf0d1e5c6
Create Date: 2026-08-05 11:52:03.021215
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "2c3eb5169b25"
down_revision: str | Sequence[str] | None = "bd0bf0d1e5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:

    op.create_table(
        "permissions",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "key",
            sa.String(length=120),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=160),
            nullable=False,
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )


    op.create_table(
        "role_permissions",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "permission_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


    op.create_table(
        "user_permissions",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "permission_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:

    op.drop_table("user_permissions")
    op.drop_table("role_permissions")
    op.drop_table("permissions")
