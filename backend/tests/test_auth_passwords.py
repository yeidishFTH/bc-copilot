import pytest

from app.services.auth import PasswordService


def test_password_hash_is_not_plaintext() -> None:
    service = PasswordService()

    password_hash = service.hash_password(
        "12345678"
    )

    assert password_hash != "12345678"
    assert password_hash.startswith("$argon2")
    assert service.verify_password(
        "12345678",
        password_hash,
    )


def test_wrong_password_is_rejected() -> None:
    service = PasswordService()

    password_hash = service.hash_password(
        "12345678"
    )

    assert not service.verify_password(
        "wrong-password",
        password_hash,
    )


def test_invalid_hash_is_rejected() -> None:
    service = PasswordService()

    assert not service.verify_password(
        "12345678",
        "not-an-argon2-hash",
    )


@pytest.mark.parametrize(
    "password",
    [
        "",
    ],
)
def test_empty_password_is_rejected(
    password: str,
) -> None:
    service = PasswordService()

    with pytest.raises(ValueError):
        service.hash_password(password)
