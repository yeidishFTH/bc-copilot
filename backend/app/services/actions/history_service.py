from __future__ import annotations

from app.services.actions.approval_repository import (
    ApprovalRequestRepository,
)


class ApprovalHistoryService:
    """
    Read-only service for action history.
    """

    ACTION_LABELS = {
        "publish_knowledge": "פרסום ידע לוויקי",
    }

    STATUS_LABELS = {
        "PENDING": "ממתין לאישור",
        "APPROVED": "אושר",
        "REJECTED": "נדחה",
    }

    EXECUTION_LABELS = {
        "EXECUTED": "בוצע",
        "FAILED": "נכשל",
        "EXECUTING": "מתבצע",
    }

    def __init__(
        self,
        repository: ApprovalRequestRepository,
    ) -> None:
        self._repository = repository


    async def list_recent(
        self,
        *,
        limit: int = 50,
    ) -> list[dict]:

        approvals = await (
            self._repository.list_recent(
                limit=limit
            )
        )

        return [
            self._serialize(item)
            for item in approvals
        ]


    def _serialize(
        self,
        item,
    ) -> dict:

        return {
            "id": str(item.id),

            "action": item.action,

            "action_label": (
                self.ACTION_LABELS.get(
                    item.action,
                    item.action,
                )
            ),

            "payload": item.payload,

            "target": (
                item.payload.get("target")
                if item.payload
                else None
            ),

            "operation": (
                item.payload.get("operation")
                if item.payload
                else None
            ),

            "status": item.status,

            "status_label": (
                self.STATUS_LABELS.get(
                    item.status,
                    item.status,
                )
            ),

            "requested_by": (
                self._serialize_user(
                    item.requester
                )
            ),

            "approved_by": (
                self._serialize_user(
                    item.approver
                )
                if item.approver
                else None
            ),

            "created_at": (
                item.created_at.isoformat()
                if item.created_at
                else None
            ),

            "approved_at": (
                item.approved_at.isoformat()
                if item.approved_at
                else None
            ),

            "execution_status": (
                item.execution_status
            ),

            "execution_status_label": (
                self.EXECUTION_LABELS.get(
                    item.execution_status,
                    item.execution_status,
                )
                if item.execution_status
                else None
            ),

            "executed_at": (
                item.executed_at.isoformat()
                if item.executed_at
                else None
            ),

            "execution_result": (
                item.execution_result
            ),

            "execution_error": (
                item.execution_error
            ),
        }


    def _serialize_user(
        self,
        user,
    ) -> dict | None:

        if user is None:
            return None

        return {
            "id": str(user.id),
            "display_name": (
                user.display_name
            ),
            "email": user.email,
        }
