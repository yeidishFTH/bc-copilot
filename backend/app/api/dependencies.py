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



def get_approval_history_service(
    session: AsyncSession = Depends(
        get_db_session
    ),
):
    from app.services.actions.approval_repository import (
        ApprovalRequestRepository,
    )
    from app.services.actions.history_service import (
        ApprovalHistoryService,
    )

    return ApprovalHistoryService(
        ApprovalRequestRepository(
            session
        )
    )


def get_approval_control_service(
    session: AsyncSession = Depends(
        get_db_session
    ),
):
    from app.services.actions.approval_repository import (
        ApprovalRequestRepository,
    )
    from app.services.actions.control_service import (
        ApprovalControlService,
    )

    return ApprovalControlService(
        ApprovalRequestRepository(
            session
        )
    )



def get_approval_dashboard_service(
    session: AsyncSession = Depends(
        get_db_session
    ),
):
    from app.services.actions.approval_repository import (
        ApprovalRequestRepository,
    )
    from app.services.actions.dashboard_service import (
        ApprovalDashboardService,
    )

    return ApprovalDashboardService(
        ApprovalRequestRepository(
            session
        )
    )



def get_mediawiki_writer():
    from urllib.parse import urlsplit

    from app.services.mediawiki import (
        MediaWikiAuthenticator,
        MediaWikiCredentials,
        MediaWikiWriter,
    )
    from app.services.transport import HttpTransport

    settings = get_settings()

    if (
        settings.mediawiki_bot_username is None
        or settings.mediawiki_bot_password is None
    ):
        raise HTTPException(
            status_code=503,
            detail="MediaWiki integration is not configured",
        )

    parsed = urlsplit(
        settings.mediawiki_api_url
    )

    transport = HttpTransport(
        base_url=f"{parsed.scheme}://{parsed.netloc}",
        timeout_seconds=20.0,
    )

    authenticator = MediaWikiAuthenticator(
        transport=transport,
        credentials=MediaWikiCredentials(
            username=(
                settings.mediawiki_bot_username.strip()
            ),
            password=(
                settings.mediawiki_bot_password
                .get_secret_value()
            ),
        ),
        api_path=parsed.path,
    )

    return MediaWikiWriter(
        transport=transport,
        authenticator=authenticator,
        api_path=parsed.path,
    )





def get_publish_knowledge_service(
    session: AsyncSession = Depends(
        get_db_session
    ),
):
    from app.services.actions.publish_knowledge_service import (
        PublishKnowledgeService,
    )

    settings = get_settings()

    api_key = (
        settings.openai_api_key
        .get_secret_value()
        .strip()
        if settings.openai_api_key is not None
        else None
    )

    retrieval_service = build_knowledge_retriever(
        session=session,
        settings=settings,
        api_key=api_key,
    )

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

    return PublishKnowledgeService(
        context_service=context_service,
        writer=get_mediawiki_writer(),
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
    from app.services.auth.permissions import (
        PermissionService,
    )

    from app.services.actions.publish_knowledge_service import (
        PublishKnowledgeService,
    )

    settings = get_settings()

    api_key = (
        settings.openai_api_key
        .get_secret_value()
        .strip()
        if settings.openai_api_key is not None
        else None
    )

    retrieval_service = build_knowledge_retriever(
        session=session,
        settings=settings,
        api_key=api_key,
    )

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

    publish_service = PublishKnowledgeService(
        context_service=context_service,
        writer=get_mediawiki_writer(),
    )

    return ActionExecutor(
        registry=build_action_registry(
            publish_handler=(
                __build_publish_handler(
                    publish_service
                )
            ),
        ),
        repository=ApprovalRequestRepository(
            session
        ),
        permission_service=PermissionService(
            session
        ),
    )



def __build_publish_handler(
    publish_service,
):
    from app.services.actions.handlers.publish_knowledge import (
        build_publish_knowledge_handler,
    )

    return build_publish_knowledge_handler(
        lambda: publish_service
    )


def get_user_service(
    session: AsyncSession = Depends(
        get_db_session
    ),
):
    from app.services.users.service import (
        UserService,
    )

    return UserService(
        session=session,
    )


def get_permission_service(
    session: AsyncSession = Depends(
        get_db_session
    ),
):
    from app.services.auth.permissions import (
        PermissionService,
    )

    return PermissionService(
        session=session,
    )
