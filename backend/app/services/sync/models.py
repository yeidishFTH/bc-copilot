from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SyncStatus
from app.services.knowledge import KnowledgeSource
from app.services.knowledge.persistence import (
    KnowledgeDocumentRepository,
    SyncRepository,
)


@dataclass(slots=True)
class SyncContext:
    """Dependencies required by one sync execution."""

    source: KnowledgeSource
    documents: KnowledgeDocumentRepository
    sync: SyncRepository
    session: AsyncSession


@dataclass(slots=True)
class SyncCounters:
    """Mutable counters collected during one sync run."""

    pages_seen: int = 0
    pages_created: int = 0
    pages_updated: int = 0
    pages_unchanged: int = 0
    pages_failed: int = 0


@dataclass(frozen=True, slots=True)
class SyncExecutionResult:
    """Final source-neutral result returned by SyncEngine."""

    run_id: UUID
    status: SyncStatus
    pages_seen: int
    pages_created: int
    pages_updated: int
    pages_unchanged: int
    pages_failed: int
    error_summary: str | None = None
