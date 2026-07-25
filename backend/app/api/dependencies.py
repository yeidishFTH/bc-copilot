from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.services.copilot import (
    CopilotAnswerService,
    OpenAITextGenerationClient,
)
from app.services.knowledge.persistence import (
    KnowledgeSearchRepository,
)
from app.services.knowledge.retrieval import (
    KnowledgeContextService,
    KnowledgeRetrievalService,
)


def get_knowledge_retrieval_service(
    session: AsyncSession = Depends(get_db_session),
) -> KnowledgeRetrievalService:
    repository = KnowledgeSearchRepository(session)
    return KnowledgeRetrievalService(repository)


def get_copilot_answer_service(
    session: AsyncSession = Depends(get_db_session),
) -> CopilotAnswerService:
    settings = get_settings()

    if settings.openai_api_key is None:
        raise HTTPException(
            status_code=503,
            detail="Copilot text generation is not configured",
        )

    api_key = (
        settings.openai_api_key
        .get_secret_value()
        .strip()
    )

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Copilot text generation is not configured",
        )

    search_repository = KnowledgeSearchRepository(session)
    retrieval_service = KnowledgeRetrievalService(
        search_repository
    )
    context_service = KnowledgeContextService(
        retrieval_service
    )
    generator = OpenAITextGenerationClient(
        api_key=api_key,
        model=settings.openai_model,
        timeout_seconds=settings.openai_timeout_seconds,
    )

    return CopilotAnswerService(
        context_service=context_service,
        generator=generator,
    )
