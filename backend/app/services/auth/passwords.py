from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)


class PasswordService:
    """Hash and verify account passwords with Argon2id."""

    def __init__(
        self,
        hasher: PasswordHasher | None = None,
    ) -> None:
        self._hasher = hasher or PasswordHasher()

    def hash_password(self, password: str) -> str:
        normalized = self._normalize(password)

        return self._hasher.hash(normalized)

    def verify_password(
        self,
        password: str,
        password_hash: str,
    ) -> bool:
        try:
            return self._hasher.verify(
                password_hash,
                self._normalize(password),
            )
        except (
            InvalidHashError,
            VerificationError,
            VerifyMismatchError,
        ):
            return False

    def needs_rehash(
        self,
        password_hash: str,
    ) -> bool:
        try:
            return self._hasher.check_needs_rehash(
                password_hash
            )
        except InvalidHashError:
            return True

    @staticmethod
    def _normalize(password: str) -> str:
        if not isinstance(password, str):
            raise TypeError(
                "Password must be a string"
            )

        if not password:
            raise ValueError(
                "Password cannot be empty"
            )

        return password
