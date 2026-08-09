from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ApprovalAction(str, Enum):
    approve = "approve"
    reject = "reject"
    cancel = "cancel"
    execute = "execute"


class ApprovalActionCommand(BaseModel):
    action: ApprovalAction
