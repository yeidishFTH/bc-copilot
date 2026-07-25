from __future__ import annotations

from pydantic import BaseModel, Field


class CopilotAskRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=2_000,
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


class CopilotAskResponse(BaseModel):
    question: str
    answer: str
    grounded: bool
    sources: list[CopilotSourceResponse]
    context_character_count: int
    context_estimated_tokens: int
    context_truncated: bool
