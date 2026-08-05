from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from .models import ActionRequest


@dataclass(frozen=True, slots=True)
class ActionApprovalRequest:
    """
    Represents an approval request before action execution.
    """

    id: str
    action: str
    requested_by: str
    payload: dict[str, object]
    status: str
    created_at: datetime
    approved_by: str | None = None
    approved_at: datetime | None = None


def create_approval_request(
    *,
    requester: str,
    action_request: ActionRequest,
) -> ActionApprovalRequest:

    return ActionApprovalRequest(
        id=str(uuid4()),
        action=action_request.action,
        requested_by=requester,
        payload={
            "document": action_request.document,
        },
        status="PENDING",
        created_at=datetime.now(
            timezone.utc
        ),
    )
