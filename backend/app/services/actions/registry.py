from __future__ import annotations

from collections.abc import Callable


class ActionRegistry:
    """
    Maps action names to execution handlers.
    """

    def __init__(self):
        self._handlers: dict[str, Callable] = {}

    def register(
        self,
        name: str,
        handler: Callable,
    ) -> None:
        self._handlers[name] = handler

    def get(
        self,
        name: str,
    ) -> Callable | None:
        return self._handlers.get(name)
