from __future__ import annotations

from fastapi import (
    Depends,
    HTTPException,
    Request,
    status,
)

from app.api.dependencies import (
    get_authentication_service,
)
from app.core.config import get_settings
from app.db.models import UserAccount
from app.services.auth import (
    AccountInactiveError,
    AuthenticationService,
    SessionInvalidError,
)


async def current_account(
    request: Request,
    service: AuthenticationService = Depends(
        get_authentication_service
    ),
) -> UserAccount:
    """Return the account represented by the session cookie."""

    settings = get_settings()
    session_token = request.cookies.get(
        settings.auth_cookie_name
    )

    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    try:
        return await service.get_account_for_token(
            session_token
        )
    except (
        SessionInvalidError,
        AccountInactiveError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        ) from error


async def require_workspace_access(
    account: UserAccount = Depends(
        current_account
    ),
) -> UserAccount:
    """Require a fully activated account for workspace access."""

    if account.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required",
        )

    return account
