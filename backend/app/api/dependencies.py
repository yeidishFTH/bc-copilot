from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.services.copilot import (
    CopilotAnswerService,
    MultiQueryKnowledgeContextService,
    MultiQueryRetrievalService,
    OpenAITextGenerationClient,
)
from app.services.knowledge.retrieval import (
    KnowledgeContextService,
    KnowledgeRetriever,
    RetrievalConfigurationError,
    build_knowledge_retriever,
)


def get_knowledge_retrieval_service(
    session: AsyncSession = Depends(get_db_session),
) -> KnowledgeRetriever:
    settings = get_settings()

    api_key = (
        settings.openai_api_key
        .get_secret_value()
        .strip()
        if settings.openai_api_key is not None
        else None
    )

    try:
        return build_knowledge_retriever(
            session=session,
            settings=settings,
            api_key=api_key,
        )
    except RetrievalConfigurationError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error


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

    try:
        retrieval_service = build_knowledge_retriever(
            session=session,
            settings=settings,
            api_key=api_key,
        )
    except RetrievalConfigurationError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error

    multi_query_retrieval = (
        MultiQueryRetrievalService(
            retrieval_service
        )
    )
    context_service = (
        MultiQueryKnowledgeContextService(
            multi_query_retrieval
        )
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


def get_authentication_service(
    session: AsyncSession = Depends(
        get_db_session
    ),
) -> "AuthenticationService":
    from app.services.auth import (
        AuthenticationService,
        PasswordService,
        SessionTokenService,
    )

    settings = get_settings()

    return AuthenticationService(
        session=session,
        password_service=PasswordService(),
        token_service=SessionTokenService(
            session_hours=(
                settings.auth_session_hours
            ),
        ),
        max_failed_attempts=(
            settings.auth_max_failed_attempts
        ),
        lock_minutes=settings.auth_lock_minutes,
    )




def get_approval_service(
    session: AsyncSession = Depends(
        get_db_session
    ),
):
    from app.services.actions.approval_service import (
        ApprovalService,
    )

    return ApprovalService(
        session=session,
    )


def get_action_executor(
    session: AsyncSession = Depends(
        get_db_session
    ),
):
    from app.services.actions.executor import (
        ActionExecutor,
    )
    from app.services.actions.default_registry import (
        build_action_registry,
    )
    from app.services.actions.approval_repository import (
        ApprovalRequestRepository,
    )

    return ActionExecutor(
        registry=build_action_registry(),
        repository=ApprovalRequestRepository(
            session
        ),
    )
