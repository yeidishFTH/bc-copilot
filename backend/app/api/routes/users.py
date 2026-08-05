from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from app.api.auth_dependencies import (
    require_workspace_access,
)

from app.api.dependencies import (
    get_user_service,
    get_permission_service,
)

from app.db.models import UserAccount

from app.services.auth.permissions import (
    PermissionService,
)

from app.services.users.service import (
    UserService,
)

from app.services.users.schemas import (
    UserResponse,
    UserCreate,
)


router = APIRouter(
    prefix="/users",
    tags=["users"],
)


@router.get(
    "",
    response_model=list[UserResponse],
)
async def list_users(
    account: UserAccount = Depends(
        require_workspace_access
    ),
    service: UserService = Depends(
        get_user_service
    ),
    permission_service: PermissionService = Depends(
        get_permission_service
    ),
):

    allowed = await permission_service.has_permission(
        account=account,
        permission_key="users.manage",
    )

    if not allowed:
        raise HTTPException(
            status_code=403,
            detail="Missing users.manage permission",
        )

    return await service.list_users()


@router.post(
    "",
    response_model=UserResponse,
)
async def create_user(
    data: UserCreate,
    account: UserAccount = Depends(
        require_workspace_access
    ),
    service: UserService = Depends(
        get_user_service
    ),
    permission_service: PermissionService = Depends(
        get_permission_service
    ),
):

    allowed = await permission_service.has_permission(
        account=account,
        permission_key="users.manage",
    )

    if not allowed:
        raise HTTPException(
            status_code=403,
            detail="Missing users.manage permission",
        )

    return await service.create_user(
        data
    )
