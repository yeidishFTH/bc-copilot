from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import (
    get_copilot_answer_service,
)
from app.models.copilot import (
    CopilotAskRequest,
    CopilotAskResponse,
    CopilotSourceResponse,
)
from app.services.copilot import (
    CitationValidationError,
    CopilotAnswerService,
    OpenAIResponseError,
)

router = APIRouter(
    prefix="/copilot",
    tags=["copilot"],
)


@router.post(
    "/ask",
    response_model=CopilotAskResponse,
)
async def ask_copilot(
    request: CopilotAskRequest,
    service: CopilotAnswerService = Depends(
        get_copilot_answer_service
    ),
) -> CopilotAskResponse:
    try:
        result = await service.answer(
            request.question,
            namespace_ids=request.namespace_ids,
            search_limit=request.search_limit,
            max_characters=request.max_characters,
            max_chunks=request.max_chunks,
            max_chunks_per_page=(
                request.max_chunks_per_page
            ),
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
    except (
        CitationValidationError,
        OpenAIResponseError,
    ) as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "Copilot could not generate a valid "
                "grounded answer"
            ),
        ) from error

    return CopilotAskResponse(
        question=result.question,
        answer=result.answer,
        grounded=result.grounded,
        sources=[
            CopilotSourceResponse(
                index=source.index,
                title=source.title,
                heading_path=list(
                    source.heading_path
                ),
                canonical_url=(
                    source.canonical_url
                ),
                chunk_id=source.chunk_id,
                rank=source.rank,
            )
            for source in result.sources
        ],
        context_character_count=(
            result.context_character_count
        ),
        context_estimated_tokens=(
            result.context_estimated_tokens
        ),
        context_truncated=(
            result.context_truncated
        ),
    )
