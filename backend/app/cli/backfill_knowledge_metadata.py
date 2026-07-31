from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from typing import Any

from sqlalchemy import select

from app.db.models import (
    KnowledgeContent,
    KnowledgeRevision,
    KnowledgeRevisionMetadata,
)
from app.db.session import AsyncSessionFactory
from app.services.wiki_parser.metadata import WikiMetadataParser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Parse stored WikiText and populate structured "
            "knowledge revision metadata."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report without modifying the database.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of revisions to process.",
    )
    return parser


def metadata_values(
    raw_wikitext: str,
) -> dict[str, Any]:
    parsed = WikiMetadataParser().parse(raw_wikitext)

    return {
        "status": parsed.status,
        "document_type": parsed.document_type,
        "portal": parsed.portal,
        "category": parsed.category,
        "audience": list(parsed.audience),
        "access_roles": list(
            parsed.access_roles
        ),
        "owner": parsed.owner,
        "responsible_department": (
            parsed.responsible_department
        ),
        "updated_on": parsed.updated_on,
        "version": parsed.version,
    }


def has_meaningful_metadata(
    values: dict[str, Any],
) -> bool:
    return any(
        value not in (None, "", [], ())
        for value in values.values()
    )


async def backfill(
    *,
    dry_run: bool,
    limit: int | None,
) -> dict[str, int | bool]:
    if limit is not None and limit < 1:
        raise ValueError("limit must be greater than zero")

    parser = WikiMetadataParser()

    async with AsyncSessionFactory() as session:
        statement = (
            select(
                KnowledgeRevision,
                KnowledgeContent.raw_wikitext,
            )
            .join(
                KnowledgeContent,
                KnowledgeContent.revision_id
                == KnowledgeRevision.id,
            )
            .order_by(
                KnowledgeRevision.wiki_revision_id.asc(),
                KnowledgeRevision.id.asc(),
            )
        )

        if limit is not None:
            statement = statement.limit(limit)

        rows = (
            await session.execute(statement)
        ).all()

        processed = 0
        created = 0
        updated = 0
        unchanged = 0
        empty = 0

        for revision, raw_wikitext in rows:
            processed += 1

            parsed = parser.parse(raw_wikitext)

            values: dict[str, Any] = {
                "status": parsed.status,
                "document_type": parsed.document_type,
                "portal": parsed.portal,
                "category": parsed.category,
                "audience": list(parsed.audience),
                "access_roles": list(
                    parsed.access_roles
                ),
                "owner": parsed.owner,
                "responsible_department": (
                    parsed.responsible_department
                ),
                "updated_on": parsed.updated_on,
                "version": parsed.version,
            }

            if not has_meaningful_metadata(values):
                empty += 1

            existing = await session.get(
                KnowledgeRevisionMetadata,
                revision.id,
            )

            if existing is None:
                created += 1

                if not dry_run:
                    session.add(
                        KnowledgeRevisionMetadata(
                            revision_id=revision.id,
                            **values,
                        )
                    )

                continue

            changed = False

            for field_name, value in values.items():
                if getattr(existing, field_name) != value:
                    changed = True

                    if not dry_run:
                        setattr(
                            existing,
                            field_name,
                            value,
                        )

            if changed:
                updated += 1
            else:
                unchanged += 1

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

        return {
            "dry_run": dry_run,
            "processed": processed,
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
            "empty": empty,
        }


async def async_main() -> int:
    args = build_parser().parse_args()

    result = await backfill(
        dry_run=args.dry_run,
        limit=args.limit,
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
