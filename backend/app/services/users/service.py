from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    UserAccount,
    Permission,
    UserPermission,
)

from app.services.auth.passwords import (
    PasswordService,
)

from .schemas import (
    UserCreate,
)


class UserService:

    def __init__(
        self,
        session: AsyncSession,
    ):
        self._session = session
        self._passwords = PasswordService()


    async def list_users(
        self,
    ) -> list[UserAccount]:

        result = await self._session.execute(
            select(UserAccount)
        )

        return list(
            result.scalars()
        )


    async def create_user(
        self,
        data: UserCreate,
    ) -> UserAccount:

        account = UserAccount(
            email=data.email,
            display_name=data.display_name,
            account_type=data.account_type,
            role=data.role,
            branch_id=data.branch_id,
            password_hash=(
                self._passwords.hash_password(
                    data.password
                )
            ),
            must_change_password=True,
        )

        self._session.add(
            account
        )

        await self._session.flush()

        return account


    async def update_role(
        self,
        account: UserAccount,
        role,
    ) -> UserAccount:

        account.role = role

        await self._session.flush()

        return account


    async def update_branch(
        self,
        account: UserAccount,
        branch_id: UUID | None,
    ) -> UserAccount:

        account.branch_id = branch_id

        await self._session.flush()

        return account


    async def assign_permission(
        self,
        account: UserAccount,
        permission_key: str,
    ):

        permission = await self._session.execute(
            select(Permission).where(
                Permission.key == permission_key
            )
        )

        permission = (
            permission.scalar_one_or_none()
        )

        if permission is None:
            raise ValueError(
                "Permission not found"
            )


        user_permission = UserPermission(
            user_id=account.id,
            permission_id=permission.id,
        )

        self._session.add(
            user_permission
        )

        await self._session.flush()

        return user_permission


    async def remove_permission(
        self,
        account: UserAccount,
        permission_id: UUID,
    ):

        result = await self._session.execute(
            select(UserPermission).where(
                UserPermission.user_id == account.id,
                UserPermission.permission_id == permission_id,
            )
        )

        item = (
            result.scalar_one_or_none()
        )

        if item:
            await self._session.delete(
                item
            )

        await self._session.flush()

        return item
