import pytest
from uuid import uuid4

from app.db.models import (
    ApprovalRequest,
    AccountRole,
    UserAccount,
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


class FakePermissionService:

    async def has_permission(
        self,
        *,
        account,
        permission_key,
    ):
        return True


def build_executor():

    return ActionExecutor(
        registry=build_action_registry(),
        repository=FakeRepository(),
        permission_service=FakePermissionService(),
    )


def build_admin_account():

    return UserAccount(
        id=uuid4(),
        email="admin@test.com",
        display_name="Admin",
        account_type="individual",
        role=AccountRole.administrator,
        password_hash="test",
    )


def build_approval(
    status="APPROVED",
):
    return ApprovalRequest(
        action="publish_knowledge",
        status=status,
        requested_by=uuid4(),
        payload={
            "document": "נוהל KYC",
        },
    )


@pytest.mark.asyncio
async def test_publish_knowledge_execution():

    executor = build_executor()

    account = build_admin_account()

    approval = build_approval()

    result = await executor.execute(
        approval,
        account,
    )

    assert result["executed"] is True
    assert result["action"] == "publish_knowledge"

    assert approval.execution_status == "EXECUTED"
    assert approval.executed_at is not None
    assert approval.execution_result == result


@pytest.mark.asyncio
async def test_pending_approval_cannot_execute():

    executor = build_executor()

    approval = build_approval(
        status="PENDING"
    )

    account = build_admin_account()

    with pytest.raises(
        ActionExecutionError,
        match="Only approved requests can execute",
    ):
        await executor.execute(
            approval,
            account,
        )


@pytest.mark.asyncio
async def test_executed_approval_cannot_execute_twice():

    executor = build_executor()

    approval = build_approval()

    approval.execution_status = "EXECUTED"

    account = build_admin_account()

    with pytest.raises(
        ActionExecutionError,
        match="Approval already executed",
    ):
        await executor.execute(
            approval,
            account,
        )


@pytest.mark.asyncio
async def test_cancelled_approval_cannot_execute():

    executor = build_executor()

    approval = build_approval(
        status="CANCELLED"
    )

    account = build_admin_account()

    with pytest.raises(
        ActionExecutionError,
        match="Only approved requests can execute",
    ):
        await executor.execute(
            approval,
            account,
        )
