from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.auth_dependencies import require_workspace_access
from app.api.workspace_dependencies import (
    get_authorized_copilot_answer_service,
)
from app.models.copilot import (
    CopilotAskRequest,
    CopilotAskResponse,
    CopilotCitationClaimResponse,
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
    dependencies=[
        Depends(require_workspace_access),
    ],
)


@router.post(
    "/ask",
    response_model=CopilotAskResponse,
)
async def ask_copilot(
    request: CopilotAskRequest,
    service: CopilotAnswerService = Depends(
        get_authorized_copilot_answer_service
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
                page_id=source.page_id,
                revision_id=source.revision_id,
                wiki_page_id=source.wiki_page_id,
                wiki_revision_id=source.wiki_revision_id,
                content=source.content,
                status=source.status,
                document_type=source.document_type,
                portal=source.portal,
                category=source.category,
                audience=list(source.audience),
                owner=source.owner,
                responsible_department=(
                    source.responsible_department
                ),
                updated_on=source.updated_on,
                version=source.version,
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
        citation_claims=[
            CopilotCitationClaimResponse(
                index=claim.index,
                text=claim.text,
                source_indexes=list(
                    claim.source_indexes
                ),
                source_chunk_ids=list(
                    claim.source_chunk_ids
                ),
                source_titles=list(
                    claim.source_titles
                ),
                source_headings=list(
                    claim.source_headings
                ),
            )
            for claim in result.citation_claims
        ],
    )


@router.post("/ask/stream")
async def stream_copilot_answer(
    request: CopilotAskRequest,
    service: CopilotAnswerService = Depends(
        get_authorized_copilot_answer_service
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
