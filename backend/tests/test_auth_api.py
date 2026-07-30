from dataclasses import dataclass
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_authentication_service,
)
from app.db.models import (
    AccountRole,
    AccountType,
)
from app.main import app
from app.services.auth import (
    InvalidCredentialsError,
    IssuedSessionToken,
    LoginResult,
    SessionInvalidError,
)


@dataclass
class FakeAccount:
    id: object
    email: str
    display_name: str
    account_type: AccountType
    role: AccountRole
    branch_id: object | None
    must_change_password: bool


class FakeAuthenticationService:
    def __init__(self) -> None:
        self.account = FakeAccount(
            id=uuid4(),
            email="idan@bitcoinchange.co.il",
            display_name="עידן",
            account_type=AccountType.individual,
            role=AccountRole.administrator,
            branch_id=None,
            must_change_password=True,
        )
        self.valid_session = True
        self.login_valid = True
        self.logout_called = False

    async def login(self, **_: object) -> LoginResult:
        if not self.login_valid:
            raise InvalidCredentialsError

        return LoginResult(
            account=self.account,  # type: ignore[arg-type]
            token=IssuedSessionToken(
                raw_token="test-session-token",
                token_hash="a" * 64,
                expires_at=__import__(
                    "datetime"
                ).datetime.now(
                    __import__("datetime").UTC
                ),
            ),
        )

    async def get_account_for_token(
        self,
        _: str,
    ) -> FakeAccount:
        if not self.valid_session:
            raise SessionInvalidError

        return self.account

    async def change_password(
        self,
        **_: object,
    ) -> FakeAccount:
        self.account.must_change_password = False
        return self.account

    async def logout(self, _: str) -> None:
        self.logout_called = True


def build_client(
    service: FakeAuthenticationService,
) -> TestClient:
    app.dependency_overrides[
        get_authentication_service
    ] = lambda: service

    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_login_sets_http_only_cookie() -> None:
    service = FakeAuthenticationService()

    with build_client(service) as client:
        response = client.post(
            "/api/auth/login",
            json={
                "email": "idan@bitcoinchange.co.il",
                "password": "12345678",
            },
        )

    assert response.status_code == 200
    assert (
        response.json()["account"]["email"]
        == "idan@bitcoinchange.co.il"
    )
    assert (
        response.json()["account"][
            "must_change_password"
        ]
        is True
    )

    cookie = response.headers["set-cookie"]

    assert "bc_workspace_session=" in cookie
    assert "HttpOnly" in cookie


def test_invalid_login_is_rejected() -> None:
    service = FakeAuthenticationService()
    service.login_valid = False

    with build_client(service) as client:
        response = client.post(
            "/api/auth/login",
            json={
                "email": "idan@bitcoinchange.co.il",
                "password": "wrong",
            },
        )

    assert response.status_code == 401


def test_me_requires_cookie() -> None:
    service = FakeAuthenticationService()

    with build_client(service) as client:
        response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_returns_current_account() -> None:
    service = FakeAuthenticationService()

    with build_client(service) as client:
        client.cookies.set(
            "bc_workspace_session",
            "test-session-token",
        )

        response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert (
        response.json()["account"]["role"]
        == "administrator"
    )


def test_change_password_clears_forced_flag() -> None:
    service = FakeAuthenticationService()

    with build_client(service) as client:
        client.cookies.set(
            "bc_workspace_session",
            "test-session-token",
        )

        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "12345678",
                "new_password": "NewPassword123!",
            },
        )

    assert response.status_code == 200
    assert (
        response.json()["account"][
            "must_change_password"
        ]
        is False
    )


def test_logout_revokes_session_and_cookie() -> None:
    service = FakeAuthenticationService()

    with build_client(service) as client:
        client.cookies.set(
            "bc_workspace_session",
            "test-session-token",
        )

        response = client.post(
            "/api/auth/logout"
        )

    assert response.status_code == 200
    assert service.logout_called
    assert (
        "bc_workspace_session="
        in response.headers["set-cookie"]
    )


def test_auth_routes_use_configured_cookie_name() -> None:
    from pathlib import Path

    route_source = Path(
        "app/api/routes/auth.py"
    ).read_text(encoding="utf-8")

    assert (
        "request.cookies.get("
        in route_source
    )
    assert (
        "settings.auth_cookie_name"
        in route_source
    )
    assert (
        'alias="bc_workspace_session"'
        not in route_source
    )
