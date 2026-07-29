"""Add pgvector embedding storage for knowledge chunks.

Revision ID: 20260729_0004
Revises: 20260726_0003
Create Date: 2026-07-29
"""

from collections.abc import Sequence

from alembic import op
from pgvector.sqlalchemy import Vector


revision: str = "20260729_0004"
down_revision: str | None = "20260726_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


EMBEDDING_DIMENSIONS = 1536


def upgrade() -> None:
    """
    Enable pgvector and add nullable chunk embedding storage.

    The column remains nullable until the embedding backfill pipeline
    has generated vectors for all active knowledge chunks.
    """

    op.execute(
        "CREATE EXTENSION IF NOT EXISTS vector"
    )

    import sqlalchemy as sa

    op.add_column(
        "knowledge_chunks",
        sa.Column(
            "embedding",
            Vector(EMBEDDING_DIMENSIONS),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(
        "knowledge_chunks",
        "embedding",
    )
