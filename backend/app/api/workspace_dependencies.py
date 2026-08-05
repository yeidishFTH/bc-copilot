from __future__ import annotations

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_dependencies import (
    require_workspace_access,
)
from app.core.config import get_settings
from app.db.models import UserAccount
from app.db.session import get_db_session
from app.services.copilot import (
    CopilotAnswerService,
    MultiQueryKnowledgeContextService,
    MultiQueryRetrievalService,
    OpenAITextGenerationClient,
)

from app.services.actions import (
    ApprovalService,
)
from app.services.knowledge.retrieval import (
    KnowledgeRetriever,
    RetrievalConfigurationError,
    build_knowledge_retriever,
)


def _account_access_role(
    account: UserAccount,
) -> str:
    role = account.role

    value = getattr(
        role,
        "value",
        role,
    )

    if not isinstance(value, str):
        raise HTTPException(
            status_code=403,
            detail="Account role is invalid",
        )

    normalized = value.strip().casefold()

    allowed_roles = {
        "branch_user",
        "management",
        "administrator",
    }

    if normalized not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail="Account role is invalid",
        )

    return normalized


def get_authorized_knowledge_retrieval_service(
    account: UserAccount = Depends(
        require_workspace_access
    ),
    session: AsyncSession = Depends(
        get_db_session
    ),
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
            access_role=_account_access_role(
                account
            ),
        )
    except RetrievalConfigurationError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error


def get_authorized_copilot_answer_service(
    account: UserAccount = Depends(
        require_workspace_access
    ),
    session: AsyncSession = Depends(
        get_db_session
    ),
) -> CopilotAnswerService:
    settings = get_settings()

    if settings.openai_api_key is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Copilot text generation "
                "is not configured"
            ),
        )

    api_key = (
        settings.openai_api_key
        .get_secret_value()
        .strip()
    )

    if not api_key:
        raise HTTPException(
            status_code=503,
            detail=(
                "Copilot text generation "
                "is not configured"
            ),
        )

    try:
        retrieval_service = (
            build_knowledge_retriever(
                session=session,
                settings=settings,
                api_key=api_key,
                access_role=(
                    _account_access_role(
                        account
                    )
                ),
            )
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
        timeout_seconds=(
            settings.openai_timeout_seconds
        ),
    )

    approval_service = ApprovalService(
        session=session,
    )

    return CopilotAnswerService(
        context_service=context_service,
        generator=generator,
        approval_service=approval_service,
    )
