from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
)

from app.db.models import (
    AccountRole,
    AccountType,
)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(
        min_length=1,
        max_length=256,
    )


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(
        min_length=1,
        max_length=256,
    )
    new_password: str = Field(
        min_length=10,
        max_length=256,
    )


class AuthAccountResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: str
    email: EmailStr
    display_name: str
    account_type: AccountType
    role: AccountRole
    branch_id: str | None
    must_change_password: bool


class AuthSessionResponse(BaseModel):
    account: AuthAccountResponse
    authenticated: bool = True


class LogoutResponse(BaseModel):
    authenticated: bool = False


class ChangePasswordResponse(BaseModel):
    account: AuthAccountResponse
    password_changed: bool = True
