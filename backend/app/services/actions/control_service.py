from __future__ import annotations

from uuid import UUID

from app.services.actions.approval_repository import (
    ApprovalRequestRepository,
)


class ApprovalControlService:
    """
    Builds approval control view.
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

    ACTION_LABELS_CONTROL = {
        "approve": "אישור",
        "reject": "דחייה",
        "cancel": "ביטול",
        "execute": "ביצוע",
    }


    def __init__(
        self,
        repository: ApprovalRequestRepository,
    ) -> None:
        self._repository = repository


    async def get_control(
        self,
        approval_id: UUID,
    ) -> dict | None:

        approval = await (
            self._repository.get_by_id(
                approval_id
            )
        )

        if approval is None:
            return None

        payload = approval.payload or {}

        actions = []

        if approval.status == "PENDING":
            actions = [
                "approve",
                "reject",
                "cancel",
            ]

        elif approval.status == "APPROVED":
            actions = [
                "execute",
            ]

        return {
            "id": str(
                approval.id
            ),

            "title": (
                self.ACTION_LABELS.get(
                    approval.action,
                    approval.action,
                )
            ),

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
                "key": approval.status,
                "label": (
                    self.STATUS_LABELS.get(
                        approval.status,
                        approval.status,
                    )
                ),
            },

            "available_actions": [
                {
                    "key": action,
                    "label": (
                        self.ACTION_LABELS_CONTROL[
                            action
                        ]
                    ),
                }
                for action in actions
            ],
        }
