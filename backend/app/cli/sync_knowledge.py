from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence

from app.core.config import Settings, get_settings
from app.db.models import SyncStatus
from app.db.session import AsyncSessionFactory, dispose_engine
from app.services.knowledge import KnowledgeCategory
from app.services.knowledge.persistence import (
    KnowledgeDocumentRepository,
    SyncRepository,
)
from app.services.mediawiki import (
    MediaWikiAPI,
    MediaWikiAuthenticator,
    MediaWikiCredentials,
    MediaWikiKnowledgeSource,
    MediaWikiPageRepository,
    MediaWikiRevisionRepository,
)

from app.services.mediawiki.utils import (
    split_mediawiki_api_url,
)
from app.services.sync import (
    SyncContext,
    SyncEngine,
    SyncExecutionResult,
)
from app.services.transport import HttpTransport


class EmptyCategoryReader:
    """
    Temporary category reader for the initial knowledge sync.

    Categories are not currently used by SyncEngine. This adapter preserves
    the MediaWikiKnowledgeSource contract until category persistence is added.
    """

    async def get_categories(
        self,
        page_identifier: str,
    ) -> Sequence[KnowledgeCategory]:
        del page_identifier
        return ()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize MediaWiki pages into the local knowledge database."
        )
    )
    parser.add_argument(
        "--namespace-id",
        type=int,
        default=0,
        help="MediaWiki namespace to synchronize. Default: 0.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Maximum number of pages to synchronize. "
            "Omit for a full namespace sync."
        ),
    )

    return parser


def require_mediawiki_credentials(
    settings: Settings,
) -> MediaWikiCredentials:
    username = settings.mediawiki_bot_username
    password = settings.mediawiki_bot_password

    if username is None or not username.strip():
        raise RuntimeError(
            "MEDIAWIKI_BOT_USERNAME is missing from .env"
        )

    if password is None or not password.get_secret_value():
        raise RuntimeError(
            "MEDIAWIKI_BOT_PASSWORD is missing from .env"
        )

    return MediaWikiCredentials(
        username=username.strip(),
        password=password.get_secret_value(),
    )


async def run_sync(
    *,
    namespace_id: int,
    limit: int | None,
) -> SyncExecutionResult:
    if namespace_id < 0:
        raise ValueError("namespace_id cannot be negative")

    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1")

    settings = get_settings()
    credentials = require_mediawiki_credentials(settings)

    base_url, api_path = split_mediawiki_api_url(
        settings.mediawiki_api_url
    )

    transport = HttpTransport(
        base_url=base_url,
        timeout_seconds=20.0,
    )

    authenticator = MediaWikiAuthenticator(
        transport=transport,
        credentials=credentials,
        api_path=api_path,
    )
    api = MediaWikiAPI(
        transport=transport,
        api_path=api_path,
    )

    source = MediaWikiKnowledgeSource(
        authenticator=authenticator,
        transport=transport,
        pages=MediaWikiPageRepository(api=api),
        revisions=MediaWikiRevisionRepository(api=api),
        categories=EmptyCategoryReader(),
    )

    try:
        async with AsyncSessionFactory() as session:
            context = SyncContext(
                source=source,
                documents=KnowledgeDocumentRepository(session),
                sync=SyncRepository(session),
                session=session,
            )

            engine = SyncEngine(context)

            return await engine.full_sync(
                namespace_id=namespace_id,
                limit=limit,
            )
    finally:
        if not transport.is_closed:
            await transport.close()


def result_payload(
    result: SyncExecutionResult,
) -> dict[str, object]:
    return {
        "run_id": str(result.run_id),
        "status": result.status.value,
        "pages_seen": result.pages_seen,
        "pages_created": result.pages_created,
        "pages_updated": result.pages_updated,
        "pages_unchanged": result.pages_unchanged,
        "pages_failed": result.pages_failed,
        "error_summary": result.error_summary,
    }


def exit_code_for_result(result: SyncExecutionResult) -> int:
    if result.status is SyncStatus.succeeded:
        return 0

    if result.status is SyncStatus.partial:
        return 2

    return 1


async def async_main() -> int:
    arguments = build_parser().parse_args()

    try:
        result = await run_sync(
            namespace_id=arguments.namespace_id,
            limit=arguments.limit,
        )
    except (RuntimeError, ValueError) as error:
        print(
            json.dumps(
                {
                    "status": "configuration_error",
                    "error": str(error),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    finally:
        await dispose_engine()

    print(
        json.dumps(
            result_payload(result),
            ensure_ascii=False,
            indent=2,
        )
    )

    return exit_code_for_result(result)


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
