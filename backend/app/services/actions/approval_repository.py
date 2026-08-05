from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ApprovalRequest


class ApprovalRequestRepository:
    """
    Persistence layer for approval requests.

    Repository does not commit transactions.
    Transaction ownership remains with caller.
    """

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session


    async def create(
        self,
        approval: ApprovalRequest,
    ) -> ApprovalRequest:

        self._session.add(
            approval
        )

        await self._session.flush()

        return approval



    async def save(
        self,
        approval: ApprovalRequest,
    ) -> ApprovalRequest:

        self._session.add(
            approval
        )

        await self._session.flush()

        return approval

    async def get_by_id(
        self,
        approval_id: UUID,
    ) -> ApprovalRequest | None:

        result = await self._session.execute(
            select(ApprovalRequest).where(
                ApprovalRequest.id == approval_id
            )
        )

        return result.scalar_one_or_none()


    async def commit(self) -> None:
        await self._session.commit()
