from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from app.services.knowledge.models import (
    KnowledgeCategory,
    KnowledgePage,
    KnowledgeRevision,
)


@runtime_checkable
class KnowledgeSource(Protocol):
    """Contract implemented by every external knowledge-source adapter."""

    @property
    def source_name(self) -> str:
        """Return the stable name of the external source."""
        ...

    async def connect(self) -> None:
        """Open resources and authenticate when required."""
        ...

    async def close(self) -> None:
        """Release network and session resources."""
        ...

    async def health(self) -> bool:
        """Return whether the source is reachable and usable."""
        ...

    async def list_pages(
        self,
        *,
        namespace_id: int = 0,
        limit: int | None = None,
    ) -> Sequence[KnowledgePage]:
        """Return pages available in the requested namespace."""
        ...

    async def get_page(self, identifier: str) -> KnowledgePage:
        """Return a page by source-specific ID or canonical title."""
        ...

    async def get_revision(self, revision_id: str) -> KnowledgeRevision:
        """Return one immutable revision by its source-specific ID."""
        ...

    async def get_categories(
        self,
        page_identifier: str,
    ) -> Sequence[KnowledgeCategory]:
        """Return categories assigned to the requested page."""
        ...
