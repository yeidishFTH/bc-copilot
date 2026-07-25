from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CopilotSource:
    """One knowledge source cited by a Copilot answer."""

    index: int
    title: str
    heading_path: tuple[str, ...]
    canonical_url: str
    chunk_id: str
    rank: float


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
