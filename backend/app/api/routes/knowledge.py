from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_knowledge_retrieval_service
from app.models.knowledge import (
    KnowledgeSearchItem,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)
from app.services.knowledge.retrieval import (
    KnowledgeRetrievalService,
)

router = APIRouter(
    prefix="/knowledge",
    tags=["knowledge"],
)


@router.post(
    "/search",
    response_model=KnowledgeSearchResponse,
)
async def search_knowledge(
    request: KnowledgeSearchRequest,
    service: KnowledgeRetrievalService = Depends(
        get_knowledge_retrieval_service
    ),
) -> KnowledgeSearchResponse:
    try:
        results = await service.search(
            request.query,
            limit=request.limit,
            namespace_ids=request.namespace_ids,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail="Knowledge search unavailable",
        ) from error

    normalized_query = " ".join(request.query.split())

    items = [
        KnowledgeSearchItem(
            page_id=result.page_id,
            revision_id=result.revision_id,
            chunk_id=result.chunk_id,
            wiki_page_id=result.wiki_page_id,
            wiki_revision_id=result.wiki_revision_id,
            title=result.title,
            canonical_url=result.canonical_url,
            namespace_id=result.namespace_id,
            position=result.position,
            heading_path=list(result.heading_path),
            content=result.content,
            token_count=result.token_count,
            rank=result.rank,
        )
        for result in results
    ]

    return KnowledgeSearchResponse(
        query=normalized_query,
        count=len(items),
        results=items,
    )
