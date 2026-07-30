from app.services.auth import (
    AuthenticationService,
    InvalidCredentialsError,
    PasswordChangeError,
)


def test_authentication_service_exports() -> None:
    assert AuthenticationService is not None
    assert InvalidCredentialsError is not None
    assert PasswordChangeError is not None
