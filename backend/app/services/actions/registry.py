from __future__ import annotations

from collections.abc import Callable

from .models import ActionDefinition


class ActionRegistry:
    """
    Stores action handlers and metadata definitions.
    """

    def __init__(self):
        self._handlers: dict[str, Callable] = {}
        self._definitions: dict[str, ActionDefinition] = {}


    def register(
        self,
        name: str,
        handler: Callable,
        definition: ActionDefinition | None = None,
    ) -> None:

        self._handlers[name] = handler

        if definition is not None:
            self._definitions[name] = definition


    def get(
        self,
        name: str,
    ) -> Callable | None:

        return self._handlers.get(name)


    def get_definition(
        self,
        name: str,
    ) -> ActionDefinition | None:

        return self._definitions.get(name)
