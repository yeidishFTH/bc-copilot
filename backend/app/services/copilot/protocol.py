from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable


@runtime_checkable
class TextGenerationClient(Protocol):
    """Minimal contract implemented by an external language model client."""

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        ...


@runtime_checkable
class StreamingTextGenerationClient(
    TextGenerationClient,
    Protocol,
):
    """Text-generation client capable of yielding incremental text."""

    def stream(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> AsyncIterator[str]:
        ...
