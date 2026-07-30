"""Add branches and user accounts.

Revision ID: 20260730_0005
Revises: 20260729_0004
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0005"
down_revision: str | None = "20260729_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "branches",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "code",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "name",
            sa.String(length=120),
            nullable=False,
        ),
        sa.Column(
            "email",
            sa.String(length=320),
            nullable=False,
        ),
        sa.Column(
            "address",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "phone",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "weekday_hours",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "friday_hours",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "is_accessible",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_branches"),
        ),
        sa.UniqueConstraint(
            "code",
            name=op.f("uq_branches_code"),
        ),
        sa.UniqueConstraint(
            "email",
            name=op.f("uq_branches_email"),
        ),
    )

    op.create_index(
        "ix_branches_active_name",
        "branches",
        [
            "is_active",
            "name",
        ],
        unique=False,
    )

    op.create_table(
        "user_accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "email",
            sa.String(length=320),
            nullable=False,
        ),
        sa.Column(
            "display_name",
            sa.String(length=160),
            nullable=False,
        ),
        sa.Column(
            "account_type",
            sa.String(length=10),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            postgresql.UUID(as_uuid=True),
        ),
        sa.Column(
            "password_hash",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "password_changed_at",
            sa.DateTime(timezone=True),
        ),
        sa.Column(
            "failed_login_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "locked_until",
            sa.DateTime(timezone=True),
        ),
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "account_type IN "
            "('branch', 'individual')",
            name="account_type",
        ),
        sa.CheckConstraint(
            "role IN "
            "('branch_user', 'management', "
            "'administrator')",
            name="account_role",
        ),
        sa.CheckConstraint(
            "("
            "account_type = 'branch' "
            "AND branch_id IS NOT NULL "
            "AND role = 'branch_user'"
            ") OR ("
            "account_type = 'individual' "
            "AND branch_id IS NULL "
            "AND role IN "
            "('management', 'administrator')"
            ")",
            name="account_branch_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["branches.id"],
            name=op.f(
                "fk_user_accounts_branch_id_branches"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "id",
            name=op.f("pk_user_accounts"),
        ),
        sa.UniqueConstraint(
            "email",
            name=op.f("uq_user_accounts_email"),
        ),
    )

    op.create_index(
        "ix_user_accounts_active_type",
        "user_accounts",
        [
            "is_active",
            "account_type",
        ],
        unique=False,
    )

    op.create_index(
        "ix_user_accounts_branch_role",
        "user_accounts",
        [
            "branch_id",
            "role",
        ],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_accounts_branch_role",
        table_name="user_accounts",
    )
    op.drop_index(
        "ix_user_accounts_active_type",
        table_name="user_accounts",
    )
    op.drop_table("user_accounts")

    op.drop_index(
        "ix_branches_active_name",
        table_name="branches",
    )
    op.drop_table("branches")
