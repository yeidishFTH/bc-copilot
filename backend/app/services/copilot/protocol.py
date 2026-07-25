from __future__ import annotations

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
