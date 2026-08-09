from __future__ import annotations

from app.services.mediawiki.writer import (
    MediaWikiWriter,
)


class PublishKnowledgeService:
    """
    Retrieves knowledge content and publishes it to MediaWiki.
    """

    def __init__(
        self,
        *,
        context_service,
        writer: MediaWikiWriter,
    ) -> None:
        self._context_service = context_service
        self._writer = writer

    async def publish(
        self,
        *,
        document: str,
    ) -> dict:

        context = await (
            self._context_service.build_context(
                document
            )
        )

        if not context.sources:
            raise ValueError(
                "Knowledge document not found"
            )

        source = context.sources[0]

        content = self._build_wikitext(
            source
        )

        if not self._writer._authenticator.is_authenticated:
            await self._writer._authenticator.login()

        result = await self._writer.edit_page(
            title=source.title,
            content=content,
            summary=(
                "Published by "
                "Bitcoin Change Copilot"
            ),
        )

        return {
            "executed": True,
            "action": "publish_knowledge",
            "document": document,
            "mediawiki": result,
        }

    def _build_wikitext(
        self,
        source,
    ) -> str:

        return f"""
<div dir="rtl" lang="he">

= {source.title} =

סוג מסמך: {source.document_type or ""}

קטגוריה: {source.category or ""}

---

{source.content}

</div>
""".strip()
