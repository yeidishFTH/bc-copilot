"""Add knowledge access roles metadata.

Revision ID: 20260730_0007
Revises: 20260730_0006
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0007"
down_revision: str | None = "20260730_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_revision_metadata",
        sa.Column(
            "access_roles",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text(
                "ARRAY[]::text[]"
            ),
        ),
    )

    op.create_index(
        "ix_knowledge_revision_metadata_access_roles",
        "knowledge_revision_metadata",
        ["access_roles"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_revision_metadata_access_roles",
        table_name="knowledge_revision_metadata",
    )

    op.drop_column(
        "knowledge_revision_metadata",
        "access_roles",
    )
