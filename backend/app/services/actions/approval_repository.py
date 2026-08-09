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




    async def list_recent(
        self,
        *,
        limit: int = 50,
    ) -> list[ApprovalRequest]:

        result = await self._session.execute(
            select(ApprovalRequest)
            .order_by(
                ApprovalRequest.created_at.desc()
            )
            .limit(limit)
        )

        return list(
            result.scalars().all()
        )


    async def list_pending(
        self,
        *,
        limit: int = 50,
    ) -> list[ApprovalRequest]:

        result = await self._session.execute(
            select(ApprovalRequest)
            .where(
                ApprovalRequest.status == "PENDING"
            )
            .where(
                ApprovalRequest.action == "publish_knowledge"
            )
            .where(
                ApprovalRequest.payload["document"].astext.is_not(None)
            )
            .where(
                ApprovalRequest.payload["document"].astext != ""
            )
            .where(
                ApprovalRequest.payload["target"].astext == "mediawiki"
            )
            .where(
                ApprovalRequest.payload["operation"].astext == "publish"
            )
            .order_by(
                ApprovalRequest.created_at.desc()
            )
            .limit(limit)
        )

        return list(
            result.scalars().all()
        )



    async def commit(self) -> None:
        await self._session.commit()
