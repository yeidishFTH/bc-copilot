from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.db.models import (
    AccountRole,
    AccountType,
)


class UserCreate(BaseModel):
    email: str
    display_name: str
    account_type: AccountType
    role: AccountRole
    branch_id: UUID | None = None
    password: str


class UserRoleUpdate(BaseModel):
    role: AccountRole


class UserBranchUpdate(BaseModel):
    branch_id: UUID | None


class UserPermissionAssign(BaseModel):
    permission_key: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    role: AccountRole
    account_type: AccountType
    branch_id: UUID | None
    is_active: bool

    class Config:
        from_attributes = True
