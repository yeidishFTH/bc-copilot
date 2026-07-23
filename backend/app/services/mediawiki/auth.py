from __future__ import annotations

from typing import Any, Mapping

from app.services.knowledge import KnowledgeAuthenticationError
from app.services.mediawiki.exceptions import (
    MediaWikiAPIError,
    MediaWikiProtocolError,
)
from app.services.mediawiki.models import (
    MediaWikiCredentials,
    MediaWikiSession,
)
from app.services.transport import HttpResponse, HttpTransport


class MediaWikiAuthenticator:
    """Manage one authenticated MediaWiki Action API session."""

    def __init__(
        self,
        *,
        transport: HttpTransport,
        credentials: MediaWikiCredentials,
        api_path: str = "",
    ) -> None:
        if not credentials.username.strip():
            raise ValueError("MediaWiki username cannot be empty")

        if not credentials.password:
            raise ValueError("MediaWiki password cannot be empty")

        self._transport = transport
        self._credentials = credentials
        self._api_path = api_path
        self._session: MediaWikiSession | None = None
        self._csrf_token: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return self._session is not None

    @property
    def session(self) -> MediaWikiSession | None:
        return self._session

    async def login(self) -> MediaWikiSession:
        """Authenticate using a MediaWiki Bot Password."""

        login_token = await self._fetch_token("login")

        response = await self._transport.post(
            self._api_path,
            data={
                "action": "login",
                "lgname": self._credentials.username,
                "lgpassword": self._credentials.password,
                "lgtoken": login_token,
                "format": "json",
                "formatversion": "2",
            },
            retry=False,
        )

        payload = self._decode_payload(response)
        self._raise_api_error(payload)

        login_data = payload.get("login")
        if not isinstance(login_data, Mapping):
            raise MediaWikiProtocolError(
                "MediaWiki login response does not contain a login object"
            )

        result = login_data.get("result")
        if result != "Success":
            reason = login_data.get("reason")
            message = (
                str(reason)
                if reason
                else f"MediaWiki login failed with result: {result!r}"
            )
            raise KnowledgeAuthenticationError(message)

        self._csrf_token = None
        self._session = await self.validate_session()
        return self._session

    async def validate_session(self) -> MediaWikiSession:
        """Verify that the current cookies represent an authenticated user."""

        response = await self._transport.get(
            self._api_path,
            params={
                "action": "query",
                "meta": "userinfo",
                "uiprop": "groups|rights",
                "format": "json",
                "formatversion": "2",
            },
        )

        payload = self._decode_payload(response)
        self._raise_api_error(payload)

        query = payload.get("query")
        if not isinstance(query, Mapping):
            raise MediaWikiProtocolError(
                "MediaWiki userinfo response does not contain a query object"
            )

        user_info = query.get("userinfo")
        if not isinstance(user_info, Mapping):
            raise MediaWikiProtocolError(
                "MediaWiki userinfo response does not contain user information"
            )

        if bool(user_info.get("anon")):
            self._clear_session()
            raise KnowledgeAuthenticationError(
                "MediaWiki session is anonymous or has expired"
            )

        user_id = user_info.get("id")
        username = user_info.get("name")

        if not isinstance(user_id, int) or not isinstance(username, str):
            raise MediaWikiProtocolError(
                "MediaWiki userinfo response contains invalid identity fields"
            )

        groups = self._string_tuple(user_info.get("groups"))
        rights = self._string_tuple(user_info.get("rights"))

        session = MediaWikiSession(
            user_id=user_id,
            username=username,
            groups=groups,
            rights=rights,
        )
        self._session = session
        return session

    async def get_csrf_token(
        self,
        *,
        force_refresh: bool = False,
    ) -> str:
        """Return a session-bound CSRF token, caching it when possible."""

        if not self.is_authenticated:
            raise KnowledgeAuthenticationError(
                "MediaWiki authentication is required before requesting a CSRF token"
            )

        if self._csrf_token is not None and not force_refresh:
            return self._csrf_token

        token = await self._fetch_token("csrf")

        if token == "+\\":
            self._clear_session()
            raise KnowledgeAuthenticationError(
                "MediaWiki returned an anonymous CSRF token"
            )

        self._csrf_token = token
        return token

    async def logout(self) -> None:
        """Log out and invalidate the local authentication state."""

        if not self.is_authenticated:
            self._clear_session()
            return

        csrf_token = await self.get_csrf_token()

        response = await self._transport.post(
            self._api_path,
            data={
                "action": "logout",
                "token": csrf_token,
                "format": "json",
                "formatversion": "2",
            },
            retry=False,
        )

        payload = self._decode_payload(response)
        self._raise_api_error(payload)
        self._clear_session()

    async def _fetch_token(self, token_type: str) -> str:
        response = await self._transport.get(
            self._api_path,
            params={
                "action": "query",
                "meta": "tokens",
                "type": token_type,
                "format": "json",
                "formatversion": "2",
            },
        )

        payload = self._decode_payload(response)
        self._raise_api_error(payload)

        query = payload.get("query")
        if not isinstance(query, Mapping):
            raise MediaWikiProtocolError(
                f"MediaWiki {token_type} token response has no query object"
            )

        tokens = query.get("tokens")
        if not isinstance(tokens, Mapping):
            raise MediaWikiProtocolError(
                f"MediaWiki {token_type} token response has no tokens object"
            )

        token_key = f"{token_type}token"
        token = tokens.get(token_key)

        if not isinstance(token, str) or not token:
            raise MediaWikiProtocolError(
                f"MediaWiki response does not contain {token_key}"
            )

        return token

    def _clear_session(self) -> None:
        self._session = None
        self._csrf_token = None

    @staticmethod
    def _decode_payload(response: HttpResponse) -> Mapping[str, Any]:
        try:
            payload = response.json()
        except (UnicodeDecodeError, ValueError) as error:
            raise MediaWikiProtocolError(
                "MediaWiki returned invalid JSON"
            ) from error

        if not isinstance(payload, Mapping):
            raise MediaWikiProtocolError(
                "MediaWiki returned a non-object JSON response"
            )

        return payload

    @staticmethod
    def _raise_api_error(payload: Mapping[str, Any]) -> None:
        error = payload.get("error")
        if not isinstance(error, Mapping):
            return

        code = str(error.get("code", "unknown"))
        message = str(
            error.get("info")
            or error.get("*")
            or "Unknown MediaWiki API error"
        )

        raise MediaWikiAPIError(
            code=code,
            message=message,
        )

    @staticmethod
    def _string_tuple(value: object) -> tuple[str, ...]:
        if not isinstance(value, list):
            return ()

        return tuple(item for item in value if isinstance(item, str))
