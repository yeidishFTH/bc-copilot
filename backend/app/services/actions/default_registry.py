from __future__ import annotations

from .registry import ActionRegistry
from .handlers.publish_knowledge import (
    publish_knowledge,
)


def build_action_registry() -> ActionRegistry:
    registry = ActionRegistry()

    registry.register(
        "publish_knowledge",
        publish_knowledge,
    )

    return registry
