import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SyncStatus(str, enum.Enum):
    running = "running"
    succeeded = "succeeded"
    partial = "partial"
    failed = "failed"


class SyncMode(str, enum.Enum):
    full = "full"
    incremental = "incremental"
    page = "page"


class KnowledgePage(Base):
    __tablename__ = "knowledge_pages"
    __table_args__ = (
        UniqueConstraint("wiki_page_id"),
        Index("ix_knowledge_pages_normalized_title_trgm", "normalized_title"),
        Index("ix_knowledge_pages_active_namespace", "is_active", "namespace_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    wiki_page_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    namespace_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_title: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    latest_revision_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    wiki_touched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    is_redirect: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    revisions: Mapped[list["KnowledgeRevision"]] = relationship(
        back_populates="page",
        cascade="all, delete-orphan",
    )
    categories: Mapped[list["KnowledgePageCategory"]] = relationship(
        back_populates="page",
        cascade="all, delete-orphan",
    )


class KnowledgeRevision(Base):
    __tablename__ = "knowledge_revisions"
    __table_args__ = (
        UniqueConstraint("wiki_revision_id"),
        Index("ix_knowledge_revisions_page_timestamp", "page_id", "revision_timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_pages.id", ondelete="CASCADE"),
        nullable=False,
    )
    wiki_revision_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    parent_revision_id: Mapped[int | None] = mapped_column(BigInteger)
    revision_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    author_name: Mapped[str | None] = mapped_column(Text)
    comment: Mapped[str | None] = mapped_column(Text)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    indexed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    page: Mapped[KnowledgePage] = relationship(back_populates="revisions")
    content: Mapped["KnowledgeContent"] = relationship(
        back_populates="revision",
        cascade="all, delete-orphan",
        uselist=False,
    )
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="revision",
        cascade="all, delete-orphan",
    )


class KnowledgeContent(Base):
    __tablename__ = "knowledge_content"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_revisions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    raw_wikitext: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_html: Mapped[str] = mapped_column(Text, nullable=False)
    plain_text: Mapped[str] = mapped_column(Text, nullable=False)
    lead_summary: Mapped[str | None] = mapped_column(Text)
    language_code: Mapped[str] = mapped_column(String(12), nullable=False, default="he")
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)

    revision: Mapped[KnowledgeRevision] = relationship(back_populates="content")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("revision_id", "position"),
        Index("ix_knowledge_chunks_search_vector", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_revisions.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    heading_path: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)

    revision: Mapped[KnowledgeRevision] = relationship(back_populates="chunks")


class KnowledgeCategory(Base):
    __tablename__ = "knowledge_categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    wiki_category_name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)

    pages: Mapped[list["KnowledgePageCategory"]] = relationship(
        back_populates="category",
        cascade="all, delete-orphan",
    )


class KnowledgePageCategory(Base):
    __tablename__ = "knowledge_page_categories"

    page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_pages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_categories.id", ondelete="CASCADE"),
        primary_key=True,
    )

    page: Mapped[KnowledgePage] = relationship(back_populates="categories")
    category: Mapped[KnowledgeCategory] = relationship(back_populates="pages")


class KnowledgeLink(Base):
    __tablename__ = "knowledge_links"
    __table_args__ = (
        UniqueConstraint("source_page_id", "target_title"),
        Index("ix_knowledge_links_target_title", "target_title"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_page_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_pages.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_wiki_page_id: Mapped[int | None] = mapped_column(BigInteger)
    target_title: Mapped[str] = mapped_column(Text, nullable=False)


class SyncRun(Base):
    __tablename__ = "sync_runs"
    __table_args__ = (Index("ix_sync_runs_started_status", "started_at", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus, name="sync_status"), nullable=False
    )
    mode: Mapped[SyncMode] = mapped_column(Enum(SyncMode, name="sync_mode"), nullable=False)
    pages_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_unchanged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pages_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)


class SyncPageEvent(Base):
    __tablename__ = "sync_page_events"
    __table_args__ = (
        Index("ix_sync_page_events_run_status", "sync_run_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    sync_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sync_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    wiki_page_id: Mapped[int | None] = mapped_column(BigInteger)
    title: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    revision_id: Mapped[int | None] = mapped_column(BigInteger)
    message: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
