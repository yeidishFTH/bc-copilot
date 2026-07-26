"""Add structured metadata for knowledge revisions.

Revision ID: 20260726_0003
Revises: 20260724_0002
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260726_0003"
down_revision: str | None = "20260724_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_revision_metadata",
        sa.Column(
            "revision_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "document_type",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "portal",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "category",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "audience",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "owner",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "responsible_department",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "updated_on",
            sa.Date(),
            nullable=True,
        ),
        sa.Column(
            "version",
            sa.Text(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["knowledge_revisions.id"],
            name=(
                "fk_knowledge_revision_metadata_"
                "revision_id_knowledge_revisions"
            ),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "revision_id",
            name=(
                "pk_knowledge_revision_metadata"
            ),
        ),
    )

    op.create_index(
        "ix_knowledge_revision_metadata_status",
        "knowledge_revision_metadata",
        ["status"],
    )
    op.create_index(
        "ix_knowledge_revision_metadata_document_type",
        "knowledge_revision_metadata",
        ["document_type"],
    )
    op.create_index(
        "ix_knowledge_revision_metadata_portal",
        "knowledge_revision_metadata",
        ["portal"],
    )
    op.create_index(
        "ix_knowledge_revision_metadata_category",
        "knowledge_revision_metadata",
        ["category"],
    )
    op.create_index(
        "ix_knowledge_revision_metadata_updated_on",
        "knowledge_revision_metadata",
        ["updated_on"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_revision_metadata_updated_on",
        table_name="knowledge_revision_metadata",
    )
    op.drop_index(
        "ix_knowledge_revision_metadata_category",
        table_name="knowledge_revision_metadata",
    )
    op.drop_index(
        "ix_knowledge_revision_metadata_portal",
        table_name="knowledge_revision_metadata",
    )
    op.drop_index(
        "ix_knowledge_revision_metadata_document_type",
        table_name="knowledge_revision_metadata",
    )
    op.drop_index(
        "ix_knowledge_revision_metadata_status",
        table_name="knowledge_revision_metadata",
    )
    op.drop_table(
        "knowledge_revision_metadata"
    )
