from __future__ import annotations

from collections.abc import Callable

from .registry import ActionRegistry
from .models import ActionDefinition

from .handlers.publish_knowledge import (
    build_publish_knowledge_handler,
)


async def _mock_publish_knowledge(
    payload: dict,
) -> dict:
    return {
        "executed": True,
        "action": "publish_knowledge",
        "document": payload.get(
            "document"
        ),
    }


def build_action_registry(
    *,
    publish_handler: Callable | None = None,
) -> ActionRegistry:

    registry = ActionRegistry()

    registry.register(
        "publish_knowledge",
        publish_handler or _mock_publish_knowledge,
        definition=ActionDefinition(
            name="publish_knowledge",
            description="פרסום מסמך ידע לוויקי",
            required_permissions=[
                "knowledge.publish",
            ],
            allowed_roles=[
                "administrator",
            ],
            requires_approval=True,
        ),
    )

    return registry
