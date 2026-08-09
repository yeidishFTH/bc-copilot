import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
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
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID, JSONB
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
    document_metadata: Mapped[
        "KnowledgeRevisionMetadata | None"
    ] = relationship(
        back_populates="revision",
        cascade="all, delete-orphan",
        uselist=False,
    )
    chunks: Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="revision",
        cascade="all, delete-orphan",
    )


class KnowledgeRevisionMetadata(Base):
    __tablename__ = "knowledge_revision_metadata"

    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "knowledge_revisions.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    status: Mapped[str | None] = mapped_column(
        Text
    )
    document_type: Mapped[str | None] = mapped_column(
        Text
    )
    portal: Mapped[str | None] = mapped_column(
        Text
    )
    category: Mapped[str | None] = mapped_column(
        Text
    )
    audience: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
    )
    access_roles: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
    )
    owner: Mapped[str | None] = mapped_column(
        Text
    )
    responsible_department: Mapped[str | None] = (
        mapped_column(Text)
    )
    updated_on: Mapped[date | None] = mapped_column(
        Date
    )
    version: Mapped[str | None] = mapped_column(
        Text
    )

    revision: Mapped["KnowledgeRevision"] = (
        relationship(
            back_populates="document_metadata",
        )
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
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))

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


class AccountType(str, enum.Enum):
    branch = "branch"
    individual = "individual"


class AccountRole(str, enum.Enum):
    branch_user = "branch_user"
    management = "management"
    administrator = "administrator"


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    key: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        unique=True,
    )

    name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    role: Mapped[AccountRole] = mapped_column(
        Enum(
            AccountRole,
            name="account_role",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
    )

    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "permissions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )


class UserPermission(Base):
    __tablename__ = "user_permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "user_accounts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "permissions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )


class Branch(Base):
    __tablename__ = "branches"
    __table_args__ = (
        UniqueConstraint("code"),
        UniqueConstraint("email"),
        Index("ix_branches_active_name", "is_active", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    code: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
    )
    address: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    phone: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    weekday_hours: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    friday_hours: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    is_accessible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    accounts: Mapped[list["UserAccount"]] = relationship(
        back_populates="branch",
    )


class UserAccount(Base):
    __tablename__ = "user_accounts"
    __table_args__ = (
        UniqueConstraint("email"),
        Index(
            "ix_user_accounts_active_type",
            "is_active",
            "account_type",
        ),
        Index(
            "ix_user_accounts_branch_role",
            "branch_id",
            "role",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )
    account_type: Mapped[AccountType] = mapped_column(
        Enum(
            AccountType,
            name="account_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    role: Mapped[AccountRole] = mapped_column(
        Enum(
            AccountRole,
            name="account_role",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
    )
    branch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "branches.id",
            ondelete="RESTRICT",
        ),
    )
    password_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    branch: Mapped[Branch | None] = relationship(
        back_populates="accounts",
    )
    sessions: Mapped[list["AuthSession"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )

    requested_approvals: Mapped[list["ApprovalRequest"]] = relationship(
        foreign_keys="ApprovalRequest.requested_by",
        back_populates="requester",
    )

    approved_approvals: Mapped[list["ApprovalRequest"]] = relationship(
        foreign_keys="ApprovalRequest.approved_by",
        back_populates="approver",
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash"),
        Index(
            "ix_auth_sessions_account_expires",
            "account_id",
            "expires_at",
        ),
        Index(
            "ix_auth_sessions_active_expires",
            "revoked_at",
            "expires_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "user_accounts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )
    created_ip: Mapped[str | None] = mapped_column(
        String(64),
    )
    user_agent: Mapped[str | None] = mapped_column(
        Text,
    )

    account: Mapped[UserAccount] = relationship(
        back_populates="sessions",
    )


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    action: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    requested_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "user_accounts.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="PENDING",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "user_accounts.id",
            ondelete="RESTRICT",
        ),
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    execution_status: Mapped[str | None] = mapped_column(
        Text,
    )

    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    execution_result: Mapped[dict | None] = mapped_column(
        JSONB,
    )

    execution_error: Mapped[str | None] = mapped_column(
        Text,
    )

    requester: Mapped["UserAccount"] = relationship(
        foreign_keys=[requested_by],
        back_populates="requested_approvals",
    )

    approver: Mapped["UserAccount | None"] = relationship(
        foreign_keys=[approved_by],
        back_populates="approved_approvals",
    )
