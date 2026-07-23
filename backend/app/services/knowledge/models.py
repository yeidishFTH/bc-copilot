from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class KnowledgeCategory:
    """A source-neutral category assigned to a knowledge document."""

    name: str
    display_name: str | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeLink:
    """A source-neutral link from one knowledge document to another."""

    target_title: str
    target_document_id: str | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeDocumentRevision:
    """An immutable revision retrieved from a knowledge source."""

    id: str
    document_id: str
    timestamp: datetime
    raw_content: str
    parent_id: str | None = None
    author_name: str | None = None
    comment: str | None = None
    rendered_html: str | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """Source-neutral document metadata and its current relationships."""

    id: str
    title: str
    canonical_url: str
    namespace_id: int = 0
    latest_revision_id: str | None = None
    is_redirect: bool = False
    categories: tuple[KnowledgeCategory, ...] = field(default_factory=tuple)
    links: tuple[KnowledgeLink, ...] = field(default_factory=tuple)
