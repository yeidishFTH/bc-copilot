"""Create knowledge engine foundation tables.

Revision ID: 20260723_0001
Revises:
Create Date: 2026-07-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260723_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    sync_status = postgresql.ENUM(
        "running", "succeeded", "partial", "failed", name="sync_status", create_type=False
    )
    sync_mode = postgresql.ENUM(
        "full", "incremental", "page", name="sync_mode", create_type=False
    )
    sync_status.create(op.get_bind(), checkfirst=True)
    sync_mode.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "knowledge_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wiki_page_id", sa.BigInteger(), nullable=False),
        sa.Column("namespace_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("normalized_title", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("latest_revision_id", sa.BigInteger(), nullable=False),
        sa.Column("wiki_touched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "indexed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_redirect", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_pages"),
        sa.UniqueConstraint("wiki_page_id", name="uq_knowledge_pages_wiki_page_id"),
    )
    op.create_index(
        "ix_knowledge_pages_normalized_title_trgm",
        "knowledge_pages",
        ["normalized_title"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"normalized_title": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_knowledge_pages_active_namespace",
        "knowledge_pages",
        ["is_active", "namespace_id"],
        unique=False,
    )

    op.create_table(
        "knowledge_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wiki_revision_id", sa.BigInteger(), nullable=False),
        sa.Column("parent_revision_id", sa.BigInteger(), nullable=True),
        sa.Column("revision_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("author_name", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "indexed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["knowledge_pages.id"],
            name="fk_knowledge_revisions_page_id_knowledge_pages",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_revisions"),
        sa.UniqueConstraint(
            "wiki_revision_id", name="uq_knowledge_revisions_wiki_revision_id"
        ),
    )
    op.create_index(
        "ix_knowledge_revisions_page_timestamp",
        "knowledge_revisions",
        ["page_id", "revision_timestamp"],
        unique=False,
    )

    op.create_table(
        "knowledge_content",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("raw_wikitext", sa.Text(), nullable=False),
        sa.Column("rendered_html", sa.Text(), nullable=False),
        sa.Column("plain_text", sa.Text(), nullable=False),
        sa.Column("lead_summary", sa.Text(), nullable=True),
        sa.Column("language_code", sa.String(length=12), nullable=False),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["knowledge_revisions.id"],
            name="fk_knowledge_content_revision_id_knowledge_revisions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_content"),
        sa.UniqueConstraint("revision_id", name="uq_knowledge_content_revision_id"),
    )
    op.create_index(
        "ix_knowledge_content_search_vector",
        "knowledge_content",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("heading_path", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["knowledge_revisions.id"],
            name="fk_knowledge_chunks_revision_id_knowledge_revisions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_chunks"),
        sa.UniqueConstraint(
            "revision_id", "position", name="uq_knowledge_chunks_revision_id"
        ),
    )
    op.create_index(
        "ix_knowledge_chunks_search_vector",
        "knowledge_chunks",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )

    op.create_table(
        "knowledge_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wiki_category_name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_categories"),
        sa.UniqueConstraint(
            "wiki_category_name", name="uq_knowledge_categories_wiki_category_name"
        ),
    )

    op.create_table(
        "knowledge_page_categories",
        sa.Column("page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["knowledge_categories.id"],
            name="fk_knowledge_page_categories_category_id_knowledge_categories",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["knowledge_pages.id"],
            name="fk_knowledge_page_categories_page_id_knowledge_pages",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "page_id", "category_id", name="pk_knowledge_page_categories"
        ),
    )

    op.create_table(
        "knowledge_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_page_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_wiki_page_id", sa.BigInteger(), nullable=True),
        sa.Column("target_title", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_page_id"],
            ["knowledge_pages.id"],
            name="fk_knowledge_links_source_page_id_knowledge_pages",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_links"),
        sa.UniqueConstraint(
            "source_page_id", "target_title", name="uq_knowledge_links_source_page_id"
        ),
    )
    op.create_index(
        "ix_knowledge_links_target_title",
        "knowledge_links",
        ["target_title"],
        unique=False,
    )

    op.create_table(
        "sync_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sync_status, nullable=False),
        sa.Column("mode", sync_mode, nullable=False),
        sa.Column("pages_seen", sa.Integer(), nullable=False),
        sa.Column("pages_created", sa.Integer(), nullable=False),
        sa.Column("pages_updated", sa.Integer(), nullable=False),
        sa.Column("pages_unchanged", sa.Integer(), nullable=False),
        sa.Column("pages_failed", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_sync_runs"),
    )
    op.create_index(
        "ix_sync_runs_started_status",
        "sync_runs",
        ["started_at", "status"],
        unique=False,
    )

    op.create_table(
        "sync_page_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sync_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wiki_page_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("revision_id", sa.BigInteger(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["sync_run_id"],
            ["sync_runs.id"],
            name="fk_sync_page_events_sync_run_id_sync_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sync_page_events"),
    )
    op.create_index(
        "ix_sync_page_events_run_status",
        "sync_page_events",
        ["sync_run_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sync_page_events_run_status", table_name="sync_page_events")
    op.drop_table("sync_page_events")
    op.drop_index("ix_sync_runs_started_status", table_name="sync_runs")
    op.drop_table("sync_runs")
    op.drop_index("ix_knowledge_links_target_title", table_name="knowledge_links")
    op.drop_table("knowledge_links")
    op.drop_table("knowledge_page_categories")
    op.drop_table("knowledge_categories")
    op.drop_index("ix_knowledge_chunks_search_vector", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.drop_index("ix_knowledge_content_search_vector", table_name="knowledge_content")
    op.drop_table("knowledge_content")
    op.drop_index(
        "ix_knowledge_revisions_page_timestamp", table_name="knowledge_revisions"
    )
    op.drop_table("knowledge_revisions")
    op.drop_index(
        "ix_knowledge_pages_active_namespace", table_name="knowledge_pages"
    )
    op.drop_index(
        "ix_knowledge_pages_normalized_title_trgm", table_name="knowledge_pages"
    )
    op.drop_table("knowledge_pages")

    postgresql.ENUM(name="sync_mode").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="sync_status").drop(op.get_bind(), checkfirst=True)
