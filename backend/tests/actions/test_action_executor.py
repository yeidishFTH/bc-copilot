import pytest
from uuid import uuid4

from app.db.models import (
    ApprovalRequest,
    AccountRole,
    UserAccount,
)

from app.services.actions.executor import (
    ActionExecutor,
)

from app.services.actions.default_registry import (
    build_action_registry,
)


class FakeRepository:

    async def save(self, approval):
        return approval

    async def commit(self):
        pass


class FakePermissionService:

    async def has_permission(
        self,
        *,
        account,
        permission_key,
    ):
        return True


@pytest.mark.asyncio
async def test_publish_knowledge_execution():

    registry = build_action_registry()

    executor = ActionExecutor(
        registry=registry,
        repository=FakeRepository(),
        permission_service=FakePermissionService(),
    )

    account = UserAccount(
        id=uuid4(),
        email="admin@test.com",
        display_name="Admin",
        account_type="individual",
        role=AccountRole.administrator,
        password_hash="test",
    )

    approval = ApprovalRequest(
        action="publish_knowledge",
        status="APPROVED",
        requested_by=uuid4(),
        payload={
            "document": "נוהל KYC",
        },
    )

    result = await executor.execute(
        approval,
        account,
    )

    assert result["executed"] is True
    assert result["action"] == "publish_knowledge"

    assert approval.execution_status == "EXECUTED"
    assert approval.executed_at is not None
    assert approval.execution_result == result
