from __future__ import annotations

from collections.abc import Sequence

from app.services.copilot.citations import (
    CitationValidator,
)
from app.services.copilot.models import (
    CopilotAnswer,
    CopilotSource,
)
from app.services.copilot.prompts import (
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.services.copilot.protocol import TextGenerationClient
from app.services.knowledge.retrieval import (
    KnowledgeContextService,
)


class CopilotAnswerService:
    """Build grounded answers from retrieved enterprise knowledge."""

    DEFAULT_SEARCH_LIMIT = 30
    DEFAULT_MAX_CHARACTERS = 12_000
    DEFAULT_MAX_CHUNKS = 8
    DEFAULT_MAX_CHUNKS_PER_PAGE = 3

    NO_CONTEXT_ANSWER = (
        "לא מצאתי במאגר הידע מקור שמספק תשובה מספקת לשאלה הזו. "
        "מומלץ לנסח את השאלה מחדש או לפנות לגורם המקצועי המתאים."
    )

    def __init__(
        self,
        *,
        context_service: KnowledgeContextService,
        generator: TextGenerationClient,
        citation_validator: CitationValidator | None = None,
    ) -> None:
        self._context_service = context_service
        self._generator = generator
        self._citation_validator = (
            citation_validator
            or CitationValidator()
        )

    async def answer(
        self,
        question: str,
        *,
        namespace_ids: Sequence[int] | None = None,
        search_limit: int = DEFAULT_SEARCH_LIMIT,
        max_characters: int = DEFAULT_MAX_CHARACTERS,
        max_chunks: int = DEFAULT_MAX_CHUNKS,
        max_chunks_per_page: int = DEFAULT_MAX_CHUNKS_PER_PAGE,
    ) -> CopilotAnswer:
        normalized_question = self._normalize_question(question)

        context = await self._context_service.build_context(
            normalized_question,
            search_limit=search_limit,
            namespace_ids=namespace_ids,
            max_characters=max_characters,
            max_chunks=max_chunks,
            max_chunks_per_page=max_chunks_per_page,
        )

        sources = tuple(
            CopilotSource(
                index=source.index,
                title=source.title,
                heading_path=source.heading_path,
                canonical_url=source.canonical_url,
                chunk_id=source.chunk_id,
                rank=source.rank,
            )
            for source in context.sources
        )

        if not context.sources:
            return CopilotAnswer(
                question=normalized_question,
                answer=self.NO_CONTEXT_ANSWER,
                sources=(),
                grounded=False,
                context_character_count=0,
                context_estimated_tokens=0,
                context_truncated=False,
            )

        answer = await self._generator.generate(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_user_prompt(
                question=normalized_question,
                context=context.text,
            ),
        )

        normalized_answer = self._normalize_generated_answer(
            answer
        )

        self._citation_validator.validate(
            normalized_answer,
            available_source_indexes=tuple(
                source.index
                for source in sources
            ),
            require_citation=True,
        )

        return CopilotAnswer(
            question=normalized_question,
            answer=normalized_answer,
            sources=sources,
            grounded=True,
            context_character_count=context.character_count,
            context_estimated_tokens=context.estimated_tokens,
            context_truncated=context.truncated,
        )

    @staticmethod
    def _normalize_question(question: str) -> str:
        if not isinstance(question, str):
            raise ValueError("question must be a string")

        normalized = " ".join(question.split())

        if not normalized:
            raise ValueError("question cannot be empty")

        if len(normalized) > 2_000:
            raise ValueError(
                "question cannot exceed 2000 characters"
            )

        return normalized

    @staticmethod
    def _normalize_generated_answer(answer: str) -> str:
        if not isinstance(answer, str):
            raise RuntimeError(
                "text generation client returned a non-string answer"
            )

        normalized = answer.strip()

        if not normalized:
            raise RuntimeError(
                "text generation client returned an empty answer"
            )

        return normalized
