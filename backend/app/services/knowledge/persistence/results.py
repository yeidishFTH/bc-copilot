from __future__ import annotations

import enum
from dataclasses import dataclass

from app.db.models import KnowledgePage, KnowledgeRevision


class DocumentUpsertStatus(str, enum.Enum):
    """Result of persisting one knowledge document revision."""

    created = "created"
    updated = "updated"
    unchanged = "unchanged"


@dataclass(frozen=True, slots=True)
class DocumentUpsertResult:
    """Persistence result returned to the sync orchestration layer."""

    status: DocumentUpsertStatus
    page: KnowledgePage
    revision: KnowledgeRevision | None

    @property
    def created(self) -> bool:
        return self.status is DocumentUpsertStatus.created

    @property
    def updated(self) -> bool:
        return self.status is DocumentUpsertStatus.updated

    @property
    def unchanged(self) -> bool:
        return self.status is DocumentUpsertStatus.unchanged
