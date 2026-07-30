from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)

from app.api.auth_dependencies import (
    current_account,
)
from app.api.dependencies import (
    get_authentication_service,
)
from app.core.config import get_settings
from app.db.models import UserAccount
from app.models.auth import (
    AuthAccountResponse,
    AuthSessionResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    LoginRequest,
    LogoutResponse,
)
from app.services.auth import (
    AccountInactiveError,
    AccountLockedError,
    AuthenticationService,
    InvalidCredentialsError,
    PasswordChangeError,
)


router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)


def account_response(
    account: UserAccount,
) -> AuthAccountResponse:
    return AuthAccountResponse(
        id=str(account.id),
        email=account.email,
        display_name=account.display_name,
        account_type=account.account_type,
        role=account.role,
        branch_id=(
            str(account.branch_id)
            if account.branch_id is not None
            else None
        ),
        must_change_password=(
            account.must_change_password
        ),
    )


def set_session_cookie(
    response: Response,
    raw_token: str,
) -> None:
    settings = get_settings()

    response.set_cookie(
        key=settings.auth_cookie_name,
        value=raw_token,
        max_age=(
            settings.auth_session_hours
            * 60
            * 60
        ),
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
    )


def delete_session_cookie(
    response: Response,
) -> None:
    settings = get_settings()

    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        secure=settings.auth_cookie_secure,
        httponly=True,
        samesite=settings.auth_cookie_samesite,
    )


@router.post(
    "/login",
    response_model=AuthSessionResponse,
)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: AuthenticationService = Depends(
        get_authentication_service
    ),
) -> AuthSessionResponse:
    try:
        result = await service.login(
            email=str(payload.email),
            password=payload.password,
            created_ip=(
                request.client.host
                if request.client is not None
                else None
            ),
            user_agent=request.headers.get(
                "user-agent"
            ),
        )
    except AccountLockedError as error:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail="Account temporarily locked",
        ) from error
    except AccountInactiveError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        ) from error
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from error

    set_session_cookie(
        response,
        result.token.raw_token,
    )

    return AuthSessionResponse(
        account=account_response(
            result.account
        ),
    )


@router.get(
    "/me",
    response_model=AuthSessionResponse,
)
async def me(
    account: UserAccount = Depends(
        current_account
    ),
) -> AuthSessionResponse:
    return AuthSessionResponse(
        account=account_response(account),
    )


@router.post(
    "/change-password",
    response_model=ChangePasswordResponse,
)
async def change_password(
    payload: ChangePasswordRequest,
    account: UserAccount = Depends(
        current_account
    ),
    service: AuthenticationService = Depends(
        get_authentication_service
    ),
) -> ChangePasswordResponse:
    try:
        updated = await service.change_password(
            account=account,
            current_password=(
                payload.current_password
            ),
            new_password=payload.new_password,
        )
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        ) from error
    except PasswordChangeError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return ChangePasswordResponse(
        account=account_response(updated),
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
)
async def logout(
    request: Request,
    response: Response,
    service: AuthenticationService = Depends(
        get_authentication_service
    ),
) -> LogoutResponse:
    settings = get_settings()
    session_token = request.cookies.get(
        settings.auth_cookie_name
    )

    if session_token:
        await service.logout(session_token)

    delete_session_cookie(response)

    return LogoutResponse()
