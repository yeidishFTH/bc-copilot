from __future__ import annotations

from app.db.models import UserAccount

from .context import ActionExecutionContext
from .models import ActionRequest
from .permissions import can_execute_action
from .registry import ActionRegistry


class ActionRouter:

    def __init__(self):
        self.registry = ActionRegistry()


    def resolve(
        self,
        request: ActionRequest,
    ):

        return self.registry.get(
            request.action
        )


    def create_execution_context(
        self,
        account: UserAccount,
        request: ActionRequest,
    ) -> ActionExecutionContext:

        action = self.resolve(
            request
        )

        if action is None:
            raise ValueError(
                "Unknown action"
            )

        authorized = can_execute_action(
            account,
            action,
        )

        return ActionExecutionContext(
            account=account,
            request=request,
            action=action,
            authorized=authorized,
        )
