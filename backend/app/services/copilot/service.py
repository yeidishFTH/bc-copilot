from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from app.services.copilot.citations import (
    CitationValidator,
)
from app.services.copilot.claim_citations import (
    ClaimCitationMapper,
)
from app.services.copilot.conversation_memory import (
    ConversationMemoryResolver,
)
from app.services.copilot.intent import (
    IntentClassifier,
)
from app.services.copilot.planner import (
    CopilotPlanner,
)
from app.services.copilot.models import (
    CopilotAnswer,
    CopilotConversationMessage,
    CopilotSource,
)
from app.services.copilot.prompts import (
    SYSTEM_PROMPT,
    build_user_prompt,
)
from app.services.copilot.protocol import (
    StreamingTextGenerationClient,
    TextGenerationClient,
)
from app.services.knowledge.retrieval import (
    KnowledgeContextService,
)
from app.services.actions import (
    CopilotActionDetector,
    ApprovalService,
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
        intent_classifier: IntentClassifier | None = None,
        planner: CopilotPlanner | None = None,
        citation_validator: CitationValidator | None = None,
        claim_citation_mapper: ClaimCitationMapper | None = None,
        conversation_resolver: ConversationMemoryResolver | None = None,
        action_detector: CopilotActionDetector | None = None,
        approval_service: ApprovalService | None = None,
    ) -> None:
        self._context_service = context_service
        self._generator = generator
        self._intent_classifier = (
            intent_classifier
            or IntentClassifier()
        )
        self._planner = planner or CopilotPlanner()
        self._citation_validator = (
            citation_validator
            or CitationValidator()
        )
        self._claim_citation_mapper = (
            claim_citation_mapper
            or ClaimCitationMapper()
        )
        self._conversation_resolver = (
            conversation_resolver
            or ConversationMemoryResolver()
        )
        self._action_detector = (
            action_detector
            or CopilotActionDetector()
        )
        self._approval_service = approval_service

    async def answer(
        self,
        question: str,
        *,
        account=None,
        history: Sequence[CopilotConversationMessage] = (),
        namespace_ids: Sequence[int] | None = None,
        search_limit: int | None = None,
        max_characters: int | None = None,
        max_chunks: int | None = None,
        max_chunks_per_page: int | None = None,
    ) -> CopilotAnswer:
        normalized_question = self._normalize_question(question)
        normalized_history = self._normalize_history(history)
        conversation_resolution = (
            self._conversation_resolver.resolve(
                normalized_question,
                normalized_history,
            )
        )
        retrieval_query = (
            conversation_resolution.resolved_question
        )

        print("DEBUG normalized_question:", normalized_question)
        print("DEBUG retrieval_query:", retrieval_query)

        action_decision = (
            self._action_detector.detect(
                retrieval_query
            )
        )

        print(
            "DEBUG action_request:",
            action_decision.action_request
        )

        if action_decision.is_action:

            if account is None:
                raise ValueError(
                    "Account is required for action execution"
                )

            if self._approval_service is None:
                raise RuntimeError(
                    "Approval service is not configured"
                )

            approval = await self._approval_service.create(
                requester_id=account.id,
                action_request=(
                    action_decision.action_request
                ),
            )

            await self._approval_service.commit()

            return CopilotAnswer(
                question=normalized_question,
                answer=(
                    "זוהתה בקשת פעולה: "
                    f"{action_decision.action_request.action}. "
                    "נוצרה בקשת אישור לביצוע."
                ),
                sources=(),
                grounded=False,
                context_character_count=0,
                context_estimated_tokens=0,
                context_truncated=False,
                answer_type="approval_required",
                action={
                    "name": action_decision.action_request.action,
                    "requires_approval": True,
                },
                approval={
                    "id": str(approval.id),
                    "status": approval.status,
                    "requested_by": str(approval.requested_by),
                },
            )

        classification = self._intent_classifier.classify(
            retrieval_query
        )
        plan = self._planner.plan(
            classification,
            retrieval_query,
        )

        resolved_search_limit = (
            search_limit
            if search_limit is not None
            else plan.search_limit
        )
        resolved_max_characters = (
            max_characters
            if max_characters is not None
            else plan.max_characters
        )
        resolved_max_chunks = (
            max_chunks
            if max_chunks is not None
            else plan.max_chunks
        )
        resolved_max_chunks_per_page = (
            max_chunks_per_page
            if max_chunks_per_page is not None
            else plan.max_chunks_per_page
        )

        context = await self._build_context(
            retrieval_query,
            strategy=plan.strategy,
            search_limit=resolved_search_limit,
            namespace_ids=namespace_ids,
            max_characters=resolved_max_characters,
            max_chunks=resolved_max_chunks,
            max_chunks_per_page=resolved_max_chunks_per_page,
        )

        sources = tuple(
            CopilotSource(
                index=source.index,
                title=source.title,
                heading_path=source.heading_path,
                canonical_url=source.canonical_url,
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
                audience=source.audience,
                owner=source.owner,
                responsible_department=(
                    source.responsible_department
                ),
                updated_on=source.updated_on,
                version=source.version,
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
                history=normalized_history,
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


        citation_mapping = (
            self._claim_citation_mapper.map(
                normalized_answer,
                sources=sources,
            )
        )

        return CopilotAnswer(
            question=normalized_question,
            answer=normalized_answer,
            sources=sources,
            grounded=True,
            context_character_count=context.character_count,
            context_estimated_tokens=context.estimated_tokens,
            context_truncated=context.truncated,
            citation_claims=citation_mapping.claims,
        )

    async def stream_answer(
        self,
        question: str,
        *,
        history: Sequence[CopilotConversationMessage] = (),
        namespace_ids: Sequence[int] | None = None,
        search_limit: int | None = None,
        max_characters: int | None = None,
        max_chunks: int | None = None,
        max_chunks_per_page: int | None = None,
    ) -> AsyncIterator[dict[str, object]]:
        normalized_question = self._normalize_question(question)
        normalized_history = self._normalize_history(history)
        conversation_resolution = (
            self._conversation_resolver.resolve(
                normalized_question,
                normalized_history,
            )
        )
        retrieval_query = (
            conversation_resolution.resolved_question
        )

        classification = self._intent_classifier.classify(
            retrieval_query
        )
        plan = self._planner.plan(
            classification,
            retrieval_query,
        )

        resolved_search_limit = (
            search_limit
            if search_limit is not None
            else plan.search_limit
        )
        resolved_max_characters = (
            max_characters
            if max_characters is not None
            else plan.max_characters
        )
        resolved_max_chunks = (
            max_chunks
            if max_chunks is not None
            else plan.max_chunks
        )
        resolved_max_chunks_per_page = (
            max_chunks_per_page
            if max_chunks_per_page is not None
            else plan.max_chunks_per_page
        )

        context = await self._build_context(
            retrieval_query,
            strategy=plan.strategy,
            search_limit=resolved_search_limit,
            namespace_ids=namespace_ids,
            max_characters=resolved_max_characters,
            max_chunks=resolved_max_chunks,
            max_chunks_per_page=resolved_max_chunks_per_page,
        )

        sources = tuple(
            CopilotSource(
                index=source.index,
                title=source.title,
                heading_path=source.heading_path,
                canonical_url=source.canonical_url,
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
                audience=source.audience,
                owner=source.owner,
                responsible_department=(
                    source.responsible_department
                ),
                updated_on=source.updated_on,
                version=source.version,
            )
            for source in context.sources
        )

        yield {
            "type": "metadata",
            "question": normalized_question,
            "grounded": bool(sources),
            "sources": [
                {
                    "index": source.index,
                    "title": source.title,
                    "heading_path": list(
                        source.heading_path
                    ),
                    "canonical_url": (
                        source.canonical_url
                    ),
                    "chunk_id": source.chunk_id,
                    "rank": source.rank,
                    "page_id": source.page_id,
                    "revision_id": source.revision_id,
                    "wiki_page_id": source.wiki_page_id,
                    "wiki_revision_id": (
                        source.wiki_revision_id
                    ),
                    "content": source.content,
                    "status": source.status,
                    "document_type": (
                        source.document_type
                    ),
                    "portal": source.portal,
                    "category": source.category,
                    "audience": list(
                        source.audience
                    ),
                    "owner": source.owner,
                    "responsible_department": (
                        source.responsible_department
                    ),
                    "updated_on": (
                        source.updated_on.isoformat()
                        if source.updated_on
                        else None
                    ),
                    "version": source.version,
                }
                for source in sources
            ],
            "context_character_count": (
                context.character_count
            ),
            "context_estimated_tokens": (
                context.estimated_tokens
            ),
            "context_truncated": context.truncated,
        }

        if not sources:
            yield {
                "type": "delta",
                "delta": self.NO_CONTEXT_ANSWER,
            }
            yield {
                "type": "complete",
                "answer": self.NO_CONTEXT_ANSWER,
                "grounded": False,
            }
            return

        if not isinstance(
            self._generator,
            StreamingTextGenerationClient,
        ):
            raise RuntimeError(
                "configured text generator does not support streaming"
            )

        answer_parts: list[str] = []

        async for delta in self._generator.stream(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_user_prompt(
                question=normalized_question,
                context=context.text,
                history=normalized_history,
            ),
        ):
            if not delta:
                continue

            answer_parts.append(delta)

            yield {
                "type": "delta",
                "delta": delta,
            }

        normalized_answer = self._normalize_generated_answer(
            "".join(answer_parts)
        )

        self._citation_validator.validate(
            normalized_answer,
            available_source_indexes=tuple(
                source.index
                for source in sources
            ),
            require_citation=True,
        )


        citation_mapping = (
            self._claim_citation_mapper.map(
                normalized_answer,
                sources=sources,
            )
        )

        yield {
            "type": "complete",
            "answer": normalized_answer,
            "grounded": True,
            "citation_claims": [
                {
                    "index": claim.index,
                    "text": claim.text,
                    "source_indexes": list(
                        claim.source_indexes
                    ),
                    "source_chunk_ids": list(
                        claim.source_chunk_ids
                    ),
                    "source_titles": list(
                        claim.source_titles
                    ),
                    "source_headings": list(
                        claim.source_headings
                    ),
                }
                for claim in citation_mapping.claims
            ],
        }

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

    @classmethod
    def _normalize_history(
        cls,
        history: Sequence[CopilotConversationMessage],
    ) -> tuple[CopilotConversationMessage, ...]:
        if len(history) > 12:
            raise ValueError(
                "history cannot contain more than 12 messages"
            )

        normalized: list[CopilotConversationMessage] = []

        for message in history:
            if not isinstance(
                message,
                CopilotConversationMessage,
            ):
                raise ValueError(
                    "history must contain "
                    "CopilotConversationMessage values"
                )

            if message.role not in {"user", "assistant"}:
                raise ValueError(
                    "history role must be user or assistant"
                )

            content = " ".join(message.content.split())

            if not content:
                raise ValueError(
                    "history message content cannot be empty"
                )

            if len(content) > 4_000:
                raise ValueError(
                    "history message content cannot exceed "
                    "4000 characters"
                )

            normalized.append(
                CopilotConversationMessage(
                    role=message.role,
                    content=content,
                )
            )

        return tuple(normalized)

    async def _build_context(
        self,
        query: str,
        *,
        strategy: object,
        search_limit: int,
        namespace_ids: Sequence[int] | None,
        max_characters: int,
        max_chunks: int,
        max_chunks_per_page: int,
    ):
        strategy_builder = getattr(
            self._context_service,
            "build_context_with_strategy",
            None,
        )

        arguments = {
            "search_limit": search_limit,
            "namespace_ids": namespace_ids,
            "max_characters": max_characters,
            "max_chunks": max_chunks,
            "max_chunks_per_page": max_chunks_per_page,
        }

        if callable(strategy_builder):
            return await strategy_builder(
                query,
                strategy=strategy,
                **arguments,
            )

        return await self._context_service.build_context(
            query,
            **arguments,
        )

    def _build_retrieval_query(
        question: str,
        history: Sequence[CopilotConversationMessage],
    ) -> str:
        previous_user_messages = [
            message.content
            for message in history
            if message.role == "user"
        ]

        relevant_history = previous_user_messages[-2:]

        if not relevant_history:
            return question

        combined = " ".join(
            [*relevant_history, question]
        )

        return combined[:2_000]

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
