from __future__ import annotations

from datetime import date

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CopilotConversationMessageRequest(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(
        min_length=1,
        max_length=4_000,
    )

    @field_validator("content")
    @classmethod
    def validate_content(
        cls,
        value: str,
    ) -> str:
        normalized = " ".join(value.split())

        if not normalized:
            raise ValueError(
                "conversation content cannot be empty"
            )

        return normalized


class CopilotAskRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=2_000,
    )
    history: list[
        CopilotConversationMessageRequest
    ] = Field(
        default_factory=list,
        max_length=12,
    )
    namespace_ids: list[int] | None = None
    search_limit: int = Field(
        default=30,
        ge=1,
        le=100,
    )
    max_characters: int = Field(
        default=12_000,
        ge=500,
        le=100_000,
    )
    max_chunks: int = Field(
        default=8,
        ge=1,
        le=50,
    )
    max_chunks_per_page: int = Field(
        default=3,
        ge=1,
        le=50,
    )


class CopilotSourceResponse(BaseModel):
    index: int
    title: str
    heading_path: list[str]
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
    audience: list[str] = Field(
        default_factory=list
    )
    owner: str | None = None
    responsible_department: str | None = None
    updated_on: date | None = None
    version: str | None = None


class CopilotCitationClaimResponse(BaseModel):
    index: int
    text: str
    source_indexes: list[int]
    source_chunk_ids: list[str]
    source_titles: list[str]
    source_headings: list[str]


class CopilotAskResponse(BaseModel):
    question: str
    answer: str
    grounded: bool
    sources: list[CopilotSourceResponse]
    context_character_count: int
    context_estimated_tokens: int
    context_truncated: bool
    citation_claims: list[
        CopilotCitationClaimResponse
    ] = Field(default_factory=list)
