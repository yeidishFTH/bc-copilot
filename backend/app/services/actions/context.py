from __future__ import annotations

from datetime import datetime, timezone

from app.db.models import UserAccount

from .models import (
    ActionDefinition,
    ActionRequest,
)


class ActionExecutionContext:
    """
    Runtime context for an authorized Copilot action.
    """

    def __init__(
        self,
        account: UserAccount,
        request: ActionRequest,
        action: ActionDefinition,
        authorized: bool,
    ):

        self.account = account
        self.request = request
        self.action = action
        self.authorized = authorized

        self.created_at = datetime.now(
            timezone.utc
        )


    @property
    def user_id(self):

        return self.account.id


    @property
    def role(self) -> str:

        role = self.account.role

        value = getattr(
            role,
            "value",
            role,
        )

        return (
            value
            if isinstance(value, str)
            else ""
        )


    def audit_payload(self) -> dict:

        return {
            "user_id": self.user_id,
            "role": self.role,
            "action": self.action.name,
            "document": (
                self.request.document
            ),
            "authorized": (
                self.authorized
            ),
            "created_at": (
                self.created_at.isoformat()
            ),
        }
