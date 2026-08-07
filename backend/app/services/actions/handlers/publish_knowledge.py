from __future__ import annotations

from collections.abc import Callable

from app.services.mediawiki.writer import MediaWikiWriter


def build_publish_knowledge_handler(
    writer_factory: Callable[[], MediaWikiWriter],
):
    async def publish_knowledge(
        payload: dict,
    ) -> dict:

        writer = writer_factory()

        result = await writer.edit_page(
            title=payload.get(
                "title",
                payload.get("document", ""),
            ),
            content=payload.get(
                "content",
                "",
            ),
            summary=payload.get(
                "summary",
                "Published by Bitcoin Change Copilot",
            ),
        )

        return {
            "executed": True,
            "action": "publish_knowledge",
            "document": payload.get(
                "document"
            ),
            "mediawiki": result,
        }

    return publish_knowledge
