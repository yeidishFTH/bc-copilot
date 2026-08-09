from __future__ import annotations

from app.services.actions.approval_repository import (
    ApprovalRequestRepository,
)


class ApprovalDashboardService:
    """
    Presentation service for approval dashboard.
    """

    ACTION_LABELS = {
        "publish_knowledge": "פרסום ידע לוויקי",
    }

    STATUS_LABELS = {
        "PENDING": "ממתין לאישור",
        "APPROVED": "אושר",
        "REJECTED": "נדחה",
        "CANCELLED": "בוטל",
    }

    def __init__(
        self,
        repository: ApprovalRequestRepository,
    ) -> None:
        self._repository = repository


    async def list_dashboard(
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

        payload = item.payload or {}

        available_actions = []

        if item.status == "PENDING":
            available_actions = [
                "approve",
                "reject",
                "cancel",
            ]

        elif item.status == "APPROVED":
            available_actions = [
                "execute",
            ]

        return {
            "id": str(item.id),

            "action": {
                "key": item.action,
                "label": self.ACTION_LABELS.get(
                    item.action,
                    item.action,
                ),
            },

            "document": payload.get(
                "document"
            ),

            "target": payload.get(
                "target"
            ),

            "operation": payload.get(
                "operation"
            ),

            "status": {
                "key": item.status,
                "label": self.STATUS_LABELS.get(
                    item.status,
                    item.status,
                ),
            },

            "requested_by": (
                {
                    "id": str(
                        item.requested_by
                    ),
                }
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

            "available_actions": available_actions,
        }
