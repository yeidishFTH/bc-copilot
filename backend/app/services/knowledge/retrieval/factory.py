from __future__ import annotations

from typing import Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.services.knowledge.openai_embeddings import (
    OpenAIEmbeddingGenerator,
)
from app.services.knowledge.persistence import (
    KnowledgeSearchRepository,
    KnowledgeVectorSearchRepository,
)
from app.services.knowledge.retrieval.hybrid import (
    HybridRetrievalService,
)
from app.services.knowledge.retrieval.semantic import (
    SemanticRetrievalService,
)
from app.services.knowledge.retrieval.service import (
    KnowledgeRetrievalService,
)


class RetrievalConfigurationError(RuntimeError):
    """Raised when the selected retrieval mode cannot be built."""


@runtime_checkable
class KnowledgeRetriever(Protocol):
    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        namespace_ids: object = None,
    ) -> object:
        ...


def build_knowledge_retriever(
    *,
    session: AsyncSession,
    settings: Settings,
    api_key: str | None = None,
    access_role: str | None = None,
) -> KnowledgeRetriever:
    """
    Build the configured retrieval implementation.

    Lexical retrieval remains the safe default and does not require
    embedding configuration or an OpenAI API key.
    """

    mode = settings.copilot_retrieval_mode

    lexical = KnowledgeRetrievalService(
        KnowledgeSearchRepository(
            session,
            access_role=access_role,
        )
    )

    if mode == "lexical":
        return lexical

    resolved_api_key = _normalize_api_key(
        api_key
    )

    semantic = SemanticRetrievalService(
        generator=OpenAIEmbeddingGenerator(
            api_key=resolved_api_key,
            model=settings.openai_embedding_model,
            dimensions=settings.openai_embedding_dimensions,
            max_batch_size=1,
            timeout_seconds=settings.openai_timeout_seconds,
        ),
        search=KnowledgeVectorSearchRepository(
            session,
            access_role=access_role,
        ),
    )

    if mode == "semantic":
        return semantic

    if mode == "hybrid":
        return HybridRetrievalService(
            lexical=lexical,
            semantic=semantic,
        )

    raise RetrievalConfigurationError(
        "Unsupported COPILOT_RETRIEVAL_MODE: "
        f"{mode!r}"
    )


def _normalize_api_key(
    api_key: str | None,
) -> str:
    if api_key is None:
        raise RetrievalConfigurationError(
            "OPENAI_API_KEY is required when "
            "COPILOT_RETRIEVAL_MODE is semantic or hybrid"
        )

    normalized = api_key.strip()

    if not normalized:
        raise RetrievalConfigurationError(
            "OPENAI_API_KEY is required when "
            "COPILOT_RETRIEVAL_MODE is semantic or hybrid"
        )

    return normalized
