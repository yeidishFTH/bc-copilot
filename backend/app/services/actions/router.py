from __future__ import annotations

from app.db.models import UserAccount

from app.services.auth.permissions import (
    PermissionService,
)

from .context import ActionExecutionContext
from .models import ActionRequest
from .permissions import can_execute_action
from .registry import ActionRegistry


class ActionRouter:

    def __init__(
        self,
        permission_service: PermissionService,
    ):
        self.registry = ActionRegistry()
        self.permission_service = permission_service


    def resolve(
        self,
        request: ActionRequest,
    ):

        return self.registry.get(
            request.action
        )


    async def create_execution_context(
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

        authorized = await can_execute_action(
            account,
            action,
            self.permission_service,
        )

        return ActionExecutionContext(
            account=account,
            request=request,
            action=action,
            authorized=authorized,
        )
