from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.services.knowledge.persistence import (
    KnowledgeSearchRepository,
)
from app.services.knowledge.retrieval import (
    KnowledgeRetrievalService,
)


def get_knowledge_retrieval_service(
    session: AsyncSession = Depends(get_db_session),
) -> KnowledgeRetrievalService:
    repository = KnowledgeSearchRepository(session)
    return KnowledgeRetrievalService(repository)
