from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeSearchRequest(BaseModel):
    """Knowledge retrieval request for API and Copilot consumers."""

    query: str = Field(
        min_length=1,
        max_length=500,
        description="Natural-language or keyword search query.",
        examples=["איך מבצעים ספירת מזומן בפתיחת סניף?"],
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum number of ranked chunks to return.",
    )
    namespace_ids: list[int] | None = Field(
        default=None,
        description=(
            "Optional MediaWiki namespace filters. "
            "Every value must be non-negative."
        ),
        examples=[[0]],
    )


class KnowledgeSearchItem(BaseModel):
    """One ranked knowledge chunk exposed by the API."""

    page_id: str
    revision_id: str
    chunk_id: str
    wiki_page_id: int
    wiki_revision_id: int
    title: str
    canonical_url: str
    namespace_id: int
    position: int
    heading_path: list[str]
    content: str
    token_count: int | None
    rank: float


class KnowledgeSearchResponse(BaseModel):
    """Ranked knowledge search response."""

    query: str
    count: int
    results: list[KnowledgeSearchItem]
