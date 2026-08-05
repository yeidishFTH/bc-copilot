from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApprovalRequest

from .models import ActionRequest
from .approval_repository import (
    ApprovalRequestRepository,
)


class ApprovalService:
    """
    Business service for approval lifecycle.
    """

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._repository = (
            ApprovalRequestRepository(
                session
            )
        )


    async def create(
        self,
        *,
        requester_id: UUID,
        action_request: ActionRequest,
    ) -> ApprovalRequest:

        print(
            "DEBUG ApprovalService action_request:",
            action_request
        )

        payload = {
            "document": action_request.document,
        }

        print(
            "DEBUG CREATE PAYLOAD:",
            payload
        )

        approval = ApprovalRequest(
            action=action_request.action,
            requested_by=requester_id,
            payload=payload,
            status="PENDING",
        )

        print(
            "DEBUG MODEL PAYLOAD:",
            approval.payload
        )

        return await self._repository.create(
            approval
        )


    async def get(
        self,
        approval_id: UUID,
    ) -> ApprovalRequest | None:

        return await self._repository.get_by_id(
            approval_id
        )


    async def approve(
        self,
        *,
        approval_id: UUID,
        approved_by: UUID,
    ) -> ApprovalRequest:

        approval = await self.get(
            approval_id
        )

        if approval is None:
            raise ValueError(
                "Approval request not found"
            )

        if approval.status != "PENDING":
            raise ValueError(
                "Approval request is not pending"
            )

        approval.status = "APPROVED"
        approval.approved_by = approved_by
        approval.approved_at = datetime.now(
            timezone.utc
        )

        approval = await self._repository.save(
            approval
        )

        await self.commit()

        return approval


    async def reject(
        self,
        *,
        approval_id: UUID,
        rejected_by: UUID,
    ) -> ApprovalRequest:

        approval = await self.get(
            approval_id
        )

        if approval is None:
            raise ValueError(
                "Approval request not found"
            )

        if approval.status != "PENDING":
            raise ValueError(
                "Approval request is not pending"
            )

        approval.status = "REJECTED"
        approval.approved_by = rejected_by
        approval.approved_at = datetime.now(
            timezone.utc
        )

        approval = await self._repository.save(
            approval
        )

        await self.commit()

        return approval


    async def commit(self) -> None:
        await self._repository.commit()
