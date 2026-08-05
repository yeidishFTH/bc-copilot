from __future__ import annotations

from app.db.models import UserAccount

from app.services.auth.permissions import (
    PermissionService,
)

from .models import ActionDefinition


async def can_execute_action(
    account: UserAccount,
    action: ActionDefinition,
    permission_service: PermissionService,
) -> bool:

    # New permission model
    if action.required_permissions:

        for permission in action.required_permissions:
            allowed = await permission_service.has_permission(
                account=account,
                permission_key=permission,
            )

            if allowed:
                return True

        return False


    # Backward compatibility
    role = account.role

    value = getattr(
        role,
        "value",
        role,
    )

    if not isinstance(value, str):
        return False

    allowed_roles = {
        item.casefold()
        for item in action.allowed_roles
    }

    return value.casefold() in allowed_roles
