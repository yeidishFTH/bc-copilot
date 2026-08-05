from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from app.services.copilot.claim_citations import (
    CitationClaim,
)


@dataclass(frozen=True, slots=True)
class CopilotConversationMessage:
    """One previous message supplied as conversational context."""

    role: str
    content: str


@dataclass(frozen=True, slots=True)
class CopilotSource:
    """One knowledge source cited by a Copilot answer."""

    index: int
    title: str
    heading_path: tuple[str, ...]
    canonical_url: str
    chunk_id: str
    rank: float
    page_id: str | None = None
    revision_id: str | None = None
    wiki_page_id: int | None = None
    wiki_revision_id: int | None = None
    content: str = ""
    status: str | None = None
    document_type: str | None = None
    portal: str | None = None
    category: str | None = None
    audience: tuple[str, ...] = ()
    owner: str | None = None
    responsible_department: str | None = None
    updated_on: date | None = None
    version: str | None = None


@dataclass(frozen=True, slots=True)
class CopilotAnswer:
    """Grounded answer returned by the Copilot application service."""

    question: str
    answer: str
    sources: tuple[CopilotSource, ...]
    grounded: bool
    context_character_count: int
    context_estimated_tokens: int
    context_truncated: bool
    citation_claims: tuple[CitationClaim, ...] = ()
    answer_type: str = "knowledge_answer"
    action: dict[str, Any] | None = None
    approval: dict[str, Any] | None = None
