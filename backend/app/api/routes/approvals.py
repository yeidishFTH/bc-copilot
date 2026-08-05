from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from app.api.auth_dependencies import (
    require_workspace_access,
)
from app.db.models import UserAccount
from app.services.actions.approval_service import (
    ApprovalService,
)
from app.api.dependencies import (
    get_approval_service,
    get_action_executor,
)


router = APIRouter(
    prefix="/approvals",
    tags=["approvals"],
    dependencies=[
        Depends(require_workspace_access),
    ],
)


@router.post("/{approval_id}/approve")
async def approve_request(
    approval_id: UUID,
    account: UserAccount = Depends(
        require_workspace_access
    ),
    service: ApprovalService = Depends(
        get_approval_service
    ),
):
    try:
        approval = await service.approve(
            approval_id=approval_id,
            approved_by=account.id,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    return {
        "id": str(approval.id),
        "status": approval.status,
        "approved_by": str(
            approval.approved_by
        ),
        "approved_at": approval.approved_at,
    }


@router.post("/{approval_id}/reject")
async def reject_request(
    approval_id: UUID,
    account: UserAccount = Depends(
        require_workspace_access
    ),
    service: ApprovalService = Depends(
        get_approval_service
    ),
):
    try:
        approval = await service.reject(
            approval_id=approval_id,
            rejected_by=account.id,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    return {
        "id": str(approval.id),
        "status": approval.status,
        "approved_by": str(
            approval.approved_by
        ),
        "approved_at": approval.approved_at,
    }


@router.post("/{approval_id}/execute")
async def execute_request(
    approval_id: UUID,
    account: UserAccount = Depends(
        require_workspace_access
    ),
    service: ApprovalService = Depends(
        get_approval_service
    ),
    executor = Depends(
        get_action_executor
    ),
):
    try:
        approval = await service.get(
            approval_id
        )

        if approval is None:
            raise ValueError(
                "Approval request not found"
            )

        result = await executor.execute(
            approval
        )

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    return {
        "id": str(approval.id),
        "status": approval.status,
        "execution_status": (
            approval.execution_status
        ),
        "result": result,
    }
