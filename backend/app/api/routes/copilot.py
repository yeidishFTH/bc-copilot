from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

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
    CopilotConversationMessage,
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
            history=tuple(
                CopilotConversationMessage(
                    role=message.role,
                    content=message.content,
                )
                for message in request.history
            ),
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


@router.post("/ask/stream")
async def stream_copilot_answer(
    request: CopilotAskRequest,
    service: CopilotAnswerService = Depends(
        get_copilot_answer_service
    ),
) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[bytes]:
        try:
            async for event in service.stream_answer(
                request.question,
                history=tuple(
                    CopilotConversationMessage(
                        role=message.role,
                        content=message.content,
                    )
                    for message in request.history
                ),
                namespace_ids=request.namespace_ids,
                search_limit=request.search_limit,
                max_characters=request.max_characters,
                max_chunks=request.max_chunks,
                max_chunks_per_page=(
                    request.max_chunks_per_page
                ),
            ):
                yield (
                    json.dumps(
                        event,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                ).encode("utf-8")

        except ValueError as error:
            yield (
                json.dumps(
                    {
                        "type": "error",
                        "detail": str(error),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            ).encode("utf-8")

        except (
            CitationValidationError,
            OpenAIResponseError,
            RuntimeError,
        ):
            yield (
                json.dumps(
                    {
                        "type": "error",
                        "detail": (
                            "Copilot could not generate a valid "
                            "grounded answer"
                        ),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            ).encode("utf-8")

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
