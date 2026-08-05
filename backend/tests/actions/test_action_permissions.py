import pytest
from uuid import uuid4

from app.db.models import (
    ApprovalRequest,
    AccountRole,
)

from app.services.actions.executor import (
    ActionExecutor,
    ActionExecutionError,
)

from app.services.actions.default_registry import (
    build_action_registry,
)


class FakeRepository:

    async def save(self, approval):
        return approval

    async def commit(self):
        pass


class DenyPermissionService:

    async def has_permission(
        self,
        *,
        account,
        permission_key,
    ):
        return False


class FakeAccount:

    id = uuid4()
    role = AccountRole.branch_user


@pytest.mark.asyncio
async def test_branch_user_cannot_publish_knowledge():

    executor = ActionExecutor(
        registry=build_action_registry(),
        repository=FakeRepository(),
        permission_service=DenyPermissionService(),
    )

    approval = ApprovalRequest(
        action="publish_knowledge",
        status="APPROVED",
        requested_by=uuid4(),
        payload={
            "document": "נוהל KYC",
        },
    )

    with pytest.raises(ActionExecutionError):
        await executor.execute(
            approval,
            FakeAccount(),
        )
