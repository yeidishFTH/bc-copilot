from __future__ import annotations

from collections.abc import Callable

from app.services.actions.publish_knowledge_service import (
    PublishKnowledgeService,
)


def build_publish_knowledge_handler(
    service_factory: Callable[
        [],
        PublishKnowledgeService,
    ],
):
    async def publish_knowledge(
        payload: dict,
    ) -> dict:

        service = service_factory()

        return await service.publish(
            document=payload.get(
                "document",
                "",
            ),
        )

    return publish_knowledge
