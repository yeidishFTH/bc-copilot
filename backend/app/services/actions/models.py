from __future__ import annotations

from pydantic import BaseModel, Field


class ActionRequest(BaseModel):
    action: str
    document: str | None = None
    requires_approval: bool = False


class ActionDefinition(BaseModel):
    name: str
    description: str

    allowed_roles: list[str] = Field(
        default_factory=list
    )

    required_permissions: list[str] = Field(
        default_factory=list
    )

    requires_approval: bool = False
