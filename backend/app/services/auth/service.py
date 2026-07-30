from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AuthSession,
    UserAccount,
)
from app.services.auth.passwords import PasswordService
from app.services.auth.sessions import (
    IssuedSessionToken,
    SessionTokenService,
)


class AuthenticationError(Exception):
    """Base authentication failure."""


class InvalidCredentialsError(AuthenticationError):
    """Email or password is invalid."""


class AccountInactiveError(AuthenticationError):
    """Account is disabled."""


class AccountLockedError(AuthenticationError):
    """Account is temporarily locked."""


class SessionInvalidError(AuthenticationError):
    """Session is missing, expired or revoked."""


class PasswordChangeError(AuthenticationError):
    """Password replacement failed validation."""


@dataclass(frozen=True, slots=True)
class LoginResult:
    account: UserAccount
    token: IssuedSessionToken


class AuthenticationService:
    def __init__(
        self,
        *,
        session: AsyncSession,
        password_service: PasswordService,
        token_service: SessionTokenService,
        max_failed_attempts: int = 5,
        lock_minutes: int = 15,
    ) -> None:
        if max_failed_attempts <= 0:
            raise ValueError(
                "Maximum failed attempts must be positive"
            )

        if lock_minutes <= 0:
            raise ValueError(
                "Lock duration must be positive"
            )

        self._session = session
        self._passwords = password_service
        self._tokens = token_service
        self._max_failed_attempts = (
            max_failed_attempts
        )
        self._lock_minutes = lock_minutes

    async def login(
        self,
        *,
        email: str,
        password: str,
        created_ip: str | None,
        user_agent: str | None,
        now: datetime | None = None,
    ) -> LoginResult:
        current_time = self._utc(now)
        normalized_email = email.strip().lower()

        account = (
            await self._session.execute(
                select(UserAccount).where(
                    UserAccount.email
                    == normalized_email
                )
            )
        ).scalar_one_or_none()

        if account is None:
            raise InvalidCredentialsError

        if not account.is_active:
            raise AccountInactiveError

        if (
            account.locked_until is not None
            and self._utc(account.locked_until)
            > current_time
        ):
            raise AccountLockedError

        valid_password = (
            self._passwords.verify_password(
                password,
                account.password_hash,
            )
        )

        if not valid_password:
            account.failed_login_attempts += 1

            if (
                account.failed_login_attempts
                >= self._max_failed_attempts
            ):
                account.locked_until = (
                    current_time
                    + timedelta(
                        minutes=self._lock_minutes
                    )
                )

            await self._session.commit()

            raise InvalidCredentialsError

        account.failed_login_attempts = 0
        account.locked_until = None
        account.last_login_at = current_time

        issued = self._tokens.issue(
            now=current_time
        )

        self._session.add(
            AuthSession(
                account_id=account.id,
                token_hash=issued.token_hash,
                expires_at=issued.expires_at,
                last_seen_at=current_time,
                created_ip=created_ip,
                user_agent=user_agent,
            )
        )

        await self._session.commit()
        await self._session.refresh(account)

        return LoginResult(
            account=account,
            token=issued,
        )

    async def get_account_for_token(
        self,
        raw_token: str,
        *,
        now: datetime | None = None,
        update_last_seen: bool = True,
    ) -> UserAccount:
        current_time = self._utc(now)
        token_hash = self._tokens.hash_token(
            raw_token
        )

        row = (
            await self._session.execute(
                select(
                    AuthSession,
                    UserAccount,
                )
                .join(
                    UserAccount,
                    UserAccount.id
                    == AuthSession.account_id,
                )
                .where(
                    AuthSession.token_hash
                    == token_hash
                )
            )
        ).one_or_none()

        if row is None:
            raise SessionInvalidError

        auth_session, account = row

        if auth_session.revoked_at is not None:
            raise SessionInvalidError

        if (
            self._utc(auth_session.expires_at)
            <= current_time
        ):
            raise SessionInvalidError

        if not account.is_active:
            raise AccountInactiveError

        if update_last_seen:
            auth_session.last_seen_at = current_time
            await self._session.commit()

        return account

    async def change_password(
        self,
        *,
        account: UserAccount,
        current_password: str,
        new_password: str,
        now: datetime | None = None,
    ) -> UserAccount:
        if not self._passwords.verify_password(
            current_password,
            account.password_hash,
        ):
            raise InvalidCredentialsError

        if current_password == new_password:
            raise PasswordChangeError(
                "New password must be different"
            )

        account.password_hash = (
            self._passwords.hash_password(
                new_password
            )
        )
        account.must_change_password = False
        account.password_changed_at = self._utc(
            now
        )

        await self._session.commit()
        await self._session.refresh(account)

        return account

    async def logout(
        self,
        raw_token: str,
        *,
        now: datetime | None = None,
    ) -> None:
        token_hash = self._tokens.hash_token(
            raw_token
        )

        auth_session = (
            await self._session.execute(
                select(AuthSession).where(
                    AuthSession.token_hash
                    == token_hash
                )
            )
        ).scalar_one_or_none()

        if auth_session is None:
            return

        if auth_session.revoked_at is None:
            auth_session.revoked_at = self._utc(
                now
            )
            await self._session.commit()

    @staticmethod
    def _utc(
        value: datetime | None,
    ) -> datetime:
        result = value or datetime.now(UTC)

        if result.tzinfo is None:
            return result.replace(tzinfo=UTC)

        return result.astimezone(UTC)
