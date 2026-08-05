from __future__ import annotations

from app.db.models import UserAccount

from .models import ActionDefinition



def normalize_role(
    account: UserAccount,
) -> str:

    role = account.role

    value = getattr(
        role,
        "value",
        role,
    )

    if not isinstance(value, str):
        return ""

    return value.strip().casefold()



def can_execute_action(
    account: UserAccount,
    action: ActionDefinition,
) -> bool:

    role = normalize_role(
        account
    )

    allowed_roles = {
        item.casefold()
        for item in action.allowed_roles
    }

    return role in allowed_roles
