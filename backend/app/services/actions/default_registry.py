from __future__ import annotations

from .registry import ActionRegistry
from .models import ActionDefinition

from .handlers.publish_knowledge import (
    publish_knowledge,
)


def build_action_registry() -> ActionRegistry:

    registry = ActionRegistry()

    registry.register(
        "publish_knowledge",
        publish_knowledge,
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
