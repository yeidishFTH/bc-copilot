import pytest
from uuid import uuid4

from app.services.actions import ActionRequest
from app.services.actions.approval_service import ApprovalService


class FakeResult:
    def __init__(self, item):
        self._item = item

    def scalar_one_or_none(self):
        return self._item


class FakeSession:
    def __init__(self):
        self.items = []

    def add(self, item):
        self.items.append(item)

    async def flush(self):
        if self.items:
            item = self.items[0]

            if item.id is None:
                item.id = uuid4()

    async def execute(self, statement):
        if self.items:
            return FakeResult(
                self.items[0]
            )

        return FakeResult(None)

    async def commit(self):
        pass


async def create_pending_approval():
    session = FakeSession()

    service = ApprovalService(
        session=session
    )

    request = ActionRequest(
        action="publish_knowledge",
        document="נוהל KYC",
    )

    approval = await service.create(
        requester_id=uuid4(),
        action_request=request,
    )

    await service.commit()

    return service, approval


@pytest.mark.asyncio
async def test_approval_lifecycle():

    service, approval = await create_pending_approval()

    assert approval.status == "PENDING"

    approved = await service.approve(
        approval_id=approval.id,
        approved_by=uuid4(),
    )

    assert approved.status == "APPROVED"
    assert approved.approved_by is not None
    assert approved.approved_at is not None


@pytest.mark.asyncio
async def test_cancel_pending_approval():

    service, approval = await create_pending_approval()

    cancelled = await service.cancel(
        approval_id=approval.id,
        cancelled_by=uuid4(),
    )

    assert cancelled.status == "CANCELLED"
    assert cancelled.approved_by is not None
    assert cancelled.approved_at is not None


@pytest.mark.asyncio
async def test_cannot_cancel_approved_approval():

    service, approval = await create_pending_approval()

    await service.approve(
        approval_id=approval.id,
        approved_by=uuid4(),
    )

    with pytest.raises(
        ValueError,
        match="Only pending requests can be cancelled",
    ):
        await service.cancel(
            approval_id=approval.id,
            cancelled_by=uuid4(),
        )
