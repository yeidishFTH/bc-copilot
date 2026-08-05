from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    UserAccount,
    Permission,
    RolePermission,
    UserPermission,
)


class PermissionService:
    """
    Central permission resolver.

    Resolution order:
    1. Direct user permissions
    2. Role permissions
    """

    def __init__(
        self,
        session: AsyncSession,
    ):
        self._session = session


    async def has_permission(
        self,
        *,
        account: UserAccount,
        permission_key: str,
    ) -> bool:

        # Direct user permission
        user_result = await self._session.execute(
            select(UserPermission)
            .join(
                Permission,
                Permission.id ==
                UserPermission.permission_id,
            )
            .where(
                UserPermission.user_id == account.id,
                Permission.key == permission_key,
            )
        )

        if user_result.scalar_one_or_none():
            return True


        # Role permission
        role_result = await self._session.execute(
            select(RolePermission)
            .join(
                Permission,
                Permission.id ==
                RolePermission.permission_id,
            )
            .where(
                RolePermission.role == account.role,
                Permission.key == permission_key,
            )
        )

        if role_result.scalar_one_or_none():
            return True


        return False
