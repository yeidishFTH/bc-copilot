from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from app.services.actions.action_command import (
    ApprovalActionCommand,
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
    get_approval_history_service,
    get_approval_dashboard_service,
    get_approval_control_service,
)


router = APIRouter(
    prefix="/approvals",
    tags=["approvals"],
    dependencies=[
        Depends(require_workspace_access),
    ],
)


@router.get("/history")
async def approval_history(
    limit: int = 50,
    history_service = Depends(
        get_approval_history_service
    ),
):
    return await history_service.list_recent(
        limit=limit
    )



@router.get("/dashboard")
async def approval_dashboard(
    limit: int = 50,
    dashboard_service = Depends(
        get_approval_dashboard_service
    ),
):
    return await dashboard_service.list_dashboard(
        limit=limit
    )



@router.get("/pending")
async def pending_approvals(
    limit: int = 50,
    service: ApprovalService = Depends(
        get_approval_service
    ),
):
    approvals = await service.list_pending(
        limit=limit
    )

    action_labels = {
        "publish_knowledge": (
            "פרסום ידע לוויקי"
        ),
    }

    return [
        {
            "id": str(item.id),

            "action": {
                "key": item.action,
                "label": action_labels.get(
                    item.action,
                    item.action,
                ),
            },

            "document": (
                item.payload.get("document")
                if item.payload
                else None
            ),

            "target": (
                item.payload.get("target")
                if item.payload
                else None
            ),

            "operation": (
                item.payload.get("operation")
                if item.payload
                else None
            ),

            "requested_by": (
                {
                    "id": str(item.requester.id),
                    "display_name": (
                        item.requester.display_name
                    ),
                    "email": (
                        item.requester.email
                    ),
                }
                if item.requester
                else None
            ),

            "created_at": (
                item.created_at.isoformat()
                if item.created_at
                else None
            ),
        }
        for item in approvals
    ]


@router.post("/{approval_id}/cancel")
async def cancel_request(
    approval_id: UUID,
    account: UserAccount = Depends(
        require_workspace_access
    ),
    service: ApprovalService = Depends(
        get_approval_service
    ),
):
    try:
        approval = await service.cancel(
            approval_id=approval_id,
            cancelled_by=account.id,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    return {
        "id": str(approval.id),
        "status": approval.status,
        "cancelled_by": str(
            approval.approved_by
        ),
        "cancelled_at": approval.approved_at,
    }



@router.get("/{approval_id}/control")
async def approval_control(
    approval_id: UUID,
    control_service = Depends(
        get_approval_control_service
    ),
):
    result = await control_service.get_control(
        approval_id
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Approval request not found",
        )

    return result



@router.post("/{approval_id}/action")
async def approval_action(
    approval_id: UUID,
    command: ApprovalActionCommand,
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

    approval = await service.get(
        approval_id
    )

    if approval is None:
        raise HTTPException(
            status_code=404,
            detail="Approval request not found",
        )


    if command.action.value == "approve":

        approval = await service.approve(
            approval_id=approval_id,
            approved_by=account.id,
        )

        return {
            "id": str(approval.id),
            "status": approval.status,
        }


    if command.action.value == "reject":

        approval = await service.reject(
            approval_id=approval_id,
            rejected_by=account.id,
        )

        return {
            "id": str(approval.id),
            "status": approval.status,
        }


    if command.action.value == "cancel":

        approval = await service.cancel(
            approval_id=approval_id,
            cancelled_by=account.id,
        )

        return {
            "id": str(approval.id),
            "status": approval.status,
        }


    if command.action.value == "execute":

        result = await executor.execute(
            approval,
            account,
        )

        return {
            "id": str(approval.id),
            "status": approval.status,
            "execution_status": (
                approval.execution_status
            ),
            "result": result,
        }


    raise HTTPException(
        status_code=400,
        detail="Unsupported approval action",
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
            approval,
            account,
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
