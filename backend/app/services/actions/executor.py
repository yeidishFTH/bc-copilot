from __future__ import annotations

from datetime import datetime, timezone

from app.db.models import ApprovalRequest

from .approval_repository import (
    ApprovalRequestRepository,
)
from .registry import ActionRegistry


class ActionExecutionError(Exception):
    """Raised when an action cannot be executed."""


class ActionExecutor:
    """
    Executes approved actions through registered handlers.
    """

    def __init__(
        self,
        *,
        registry: ActionRegistry,
        repository: ApprovalRequestRepository,
    ) -> None:
        self._registry = registry
        self._repository = repository


    async def execute(
        self,
        approval: ApprovalRequest,
    ) -> dict:

        if approval.status != "APPROVED":
            raise ActionExecutionError(
                "Only approved requests can execute"
            )

        handler = self._registry.get(
            approval.action
        )

        if handler is None:
            raise ActionExecutionError(
                f"No handler registered for {approval.action}"
            )

        approval.execution_status = "EXECUTING"

        await self._repository.save(
            approval
        )

        await self._repository.commit()

        try:
            result = await handler(
                approval.payload
            )

            approval.execution_status = (
                "EXECUTED"
            )
            approval.executed_at = (
                datetime.now(timezone.utc)
            )
            approval.execution_result = result
            approval.execution_error = None

            await self._repository.save(
                approval
            )

            await self._repository.commit()

            return result

        except Exception as error:
            approval.execution_status = "FAILED"
            approval.execution_error = str(error)
            approval.executed_at = (
                datetime.now(timezone.utc)
            )

            await self._repository.save(
                approval
            )

            await self._repository.commit()

            raise ActionExecutionError(
                str(error)
            ) from error
