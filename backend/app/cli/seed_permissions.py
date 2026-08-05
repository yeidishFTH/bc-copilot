from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select

from app.db.session import AsyncSessionFactory
from app.db.models import (
    Permission,
    RolePermission,
    AccountRole,
)


PERMISSIONS = [
    (
        "knowledge.view",
        "צפייה בידע",
        "צפייה במסמכי הוויקי והידע הארגוני",
    ),
    (
        "knowledge.create",
        "יצירת ידע",
        "יצירת מסמכים חדשים",
    ),
    (
        "knowledge.edit",
        "עריכת ידע",
        "עריכת מסמכים קיימים",
    ),
    (
        "knowledge.publish",
        "פרסום לוויקי",
        "פרסום שינויי ידע לוויקי",
    ),
    (
        "approval.view",
        "צפייה באישורים",
        "צפייה בבקשות אישור",
    ),
    (
        "approval.approve",
        "אישור פעולות",
        "אישור פעולות של Copilot",
    ),
    (
        "users.view",
        "צפייה במשתמשים",
        "צפייה ברשימת משתמשים",
    ),
    (
        "users.manage",
        "ניהול משתמשים",
        "ניהול משתמשים והרשאות",
    ),
]


async def main():

    async with AsyncSessionFactory() as session:

        permissions = {}

        for key, name, description in PERMISSIONS:

            result = await session.execute(
                select(Permission).where(
                    Permission.key == key
                )
            )

            permission = result.scalar_one_or_none()

            if permission is None:
                permission = Permission(
                    id=uuid.uuid4(),
                    key=key,
                    name=name,
                    description=description,
                )

                session.add(permission)

            permissions[key] = permission


        await session.flush()


        admin_permissions = permissions.values()

        for permission in admin_permissions:

            exists = await session.execute(
                select(RolePermission).where(
                    RolePermission.role ==
                    AccountRole.administrator,
                    RolePermission.permission_id ==
                    permission.id,
                )
            )

            if exists.scalar_one_or_none() is None:
                session.add(
                    RolePermission(
                        role=AccountRole.administrator,
                        permission_id=permission.id,
                    )
                )


        await session.commit()

        print("✅ Permission seed completed")


if __name__ == "__main__":
    asyncio.run(main())
