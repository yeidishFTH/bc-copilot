from __future__ import annotations

from typing import Any

import pytest

from app.services.copilot import CopilotAnswerService
from app.services.copilot.models import CopilotConversationMessage
from app.services.knowledge.retrieval import (
    KnowledgeContext,
    KnowledgeContextSource,
)


class FakeContextService:
    def __init__(
        self,
        context: KnowledgeContext,
    ) -> None:
        self.context = context
        self.calls: list[dict[str, Any]] = []

    async def build_context(
        self,
        query: str,
        **kwargs: Any,
    ) -> KnowledgeContext:
        self.calls.append(
            {
                "query": query,
                **kwargs,
            }
        )
        return self.context


class FakeGenerator:
    def __init__(
        self,
        answer: str = "יש לפעול לפי הנוהל. [SOURCE 1]",
    ) -> None:
        self.answer = answer
        self.calls: list[dict[str, str]] = []

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
            }
        )
        return self.answer


def make_context() -> KnowledgeContext:
    source = KnowledgeContextSource(
        index=1,
        page_id="page-1",
        revision_id="revision-1",
        chunk_id="chunk-1",
        title="נוהל מחיקת כרטיס לקוח",
        heading_path=(
            "נוהל מחיקת כרטיס לקוח",
            "שלבי ביצוע",
        ),
        canonical_url=(
            "https://wiki.example.test/customer-deletion"
        ),
        content=(
            "קבלת הבקשה חייבת להתבצע מכתובת "
            "האימייל הרשומה."
        ),
        rank=4.7,
    )

    text = """
[SOURCE 1]
כותרת: נוהל מחיקת כרטיס לקוח
סעיף: שלבי ביצוע
תוכן:
קבלת הבקשה חייבת להתבצע מכתובת האימייל הרשומה.
""".strip()

    return KnowledgeContext(
        query="איך מוחקים כרטיס לקוח?",
        text=text,
        sources=(source,),
        character_count=len(text),
        estimated_tokens=40,
        truncated=False,
    )


@pytest.mark.asyncio
async def test_answer_generates_grounded_response() -> None:
    context_service = FakeContextService(make_context())
    generator = FakeGenerator()
    service = CopilotAnswerService(
        context_service=context_service,  # type: ignore[arg-type]
        generator=generator,
    )

    result = await service.answer(
        "  איך   מוחקים כרטיס לקוח?  ",
        namespace_ids=[0],
    )

    assert result.question == "איך מוחקים כרטיס לקוח?"
    assert result.answer == (
        "יש לפעול לפי הנוהל. [SOURCE 1]"
    )
    assert result.grounded is True
    assert len(result.sources) == 1
    assert result.sources[0].title == (
        "נוהל מחיקת כרטיס לקוח"
    )
    assert len(generator.calls) == 1
    assert "[SOURCE 1]" in (
        generator.calls[0]["user_prompt"]
    )
    assert "איך מוחקים כרטיס לקוח?" in (
        generator.calls[0]["user_prompt"]
    )


@pytest.mark.asyncio
async def test_answer_does_not_call_model_without_context() -> None:
    empty_context = KnowledgeContext(
        query="מידע לא קיים",
        text="",
        sources=(),
        character_count=0,
        estimated_tokens=0,
        truncated=False,
    )
    context_service = FakeContextService(empty_context)
    generator = FakeGenerator()
    service = CopilotAnswerService(
        context_service=context_service,  # type: ignore[arg-type]
        generator=generator,
    )

    result = await service.answer("מידע לא קיים")

    assert result.grounded is False
    assert result.sources == ()
    assert result.answer == service.NO_CONTEXT_ANSWER
    assert generator.calls == []


@pytest.mark.asyncio
async def test_answer_preserves_context_metadata() -> None:
    context = make_context()
    context_service = FakeContextService(context)
    generator = FakeGenerator()
    service = CopilotAnswerService(
        context_service=context_service,  # type: ignore[arg-type]
        generator=generator,
    )

    result = await service.answer("מחיקת כרטיס")

    assert (
        result.context_character_count
        == context.character_count
    )
    assert (
        result.context_estimated_tokens
        == context.estimated_tokens
    )
    assert result.context_truncated is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        "",
        "   ",
        "\n\t",
    ],
)
async def test_answer_rejects_empty_question(
    question: str,
) -> None:
    context_service = FakeContextService(make_context())
    generator = FakeGenerator()
    service = CopilotAnswerService(
        context_service=context_service,  # type: ignore[arg-type]
        generator=generator,
    )

    with pytest.raises(
        ValueError,
        match="question cannot be empty",
    ):
        await service.answer(question)

    assert context_service.calls == []
    assert generator.calls == []


@pytest.mark.asyncio
async def test_answer_rejects_overlong_question() -> None:
    context_service = FakeContextService(make_context())
    generator = FakeGenerator()
    service = CopilotAnswerService(
        context_service=context_service,  # type: ignore[arg-type]
        generator=generator,
    )

    with pytest.raises(
        ValueError,
        match="cannot exceed 2000",
    ):
        await service.answer("א" * 2_001)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "generated_answer",
    [
        "",
        "   ",
        "\n\t",
    ],
)
async def test_answer_rejects_empty_model_output(
    generated_answer: str,
) -> None:
    context_service = FakeContextService(make_context())
    generator = FakeGenerator(generated_answer)
    service = CopilotAnswerService(
        context_service=context_service,  # type: ignore[arg-type]
        generator=generator,
    )

    with pytest.raises(
        RuntimeError,
        match="empty answer",
    ):
        await service.answer("מחיקת כרטיס")


@pytest.mark.asyncio
async def test_answer_rejects_missing_model_citation() -> None:
    from app.services.copilot import CitationValidationError

    context_service = FakeContextService(make_context())
    generator = FakeGenerator(
        "יש לפעול לפי הנוהל ללא ציטוט."
    )
    service = CopilotAnswerService(
        context_service=context_service,  # type: ignore[arg-type]
        generator=generator,
    )

    with pytest.raises(
        CitationValidationError,
        match="does not cite",
    ):
        await service.answer("מחיקת כרטיס")


@pytest.mark.asyncio
async def test_answer_rejects_unknown_model_citation() -> None:
    from app.services.copilot import CitationValidationError

    context_service = FakeContextService(make_context())
    generator = FakeGenerator(
        "יש לפעול לפי הנוהל. [SOURCE 99]"
    )
    service = CopilotAnswerService(
        context_service=context_service,  # type: ignore[arg-type]
        generator=generator,
    )

    with pytest.raises(
        CitationValidationError,
        match="unavailable source indexes: 99",
    ):
        await service.answer("מחיקת כרטיס")


@pytest.mark.asyncio
async def test_answer_uses_history_for_follow_up_search() -> None:
    from app.services.copilot import (
        CopilotConversationMessage,
    )

    context_service = FakeContextService(make_context())
    generator = FakeGenerator()
    service = CopilotAnswerService(
        context_service=context_service,  # type: ignore[arg-type]
        generator=generator,
    )

    result = await service.answer(
        "ומה עושים אם הוא מסרב?",
        history=(
            CopilotConversationMessage(
                role="user",
                content="איך מזהים לקוח חדש?",
            ),
            CopilotConversationMessage(
                role="assistant",
                content=(
                    "יש לבצע זיהוי פנים מול פנים. "
                    "[SOURCE 1]"
                ),
            ),
        ),
    )

    assert result.question == "ומה עושים אם הוא מסרב?"
    assert context_service.calls[0]["query"] == (
        "איך מזהים לקוח חדש? "
        "ומה עושים אם הוא מסרב?"
    )

    prompt = generator.calls[0]["user_prompt"]

    assert "איך מזהים לקוח חדש?" in prompt
    assert "ומה עושים אם הוא מסרב?" in prompt
    assert "Copilot:" in prompt


@pytest.mark.asyncio
async def test_answer_rejects_too_much_history() -> None:
    from app.services.copilot import (
        CopilotConversationMessage,
    )

    context_service = FakeContextService(make_context())
    generator = FakeGenerator()
    service = CopilotAnswerService(
        context_service=context_service,  # type: ignore[arg-type]
        generator=generator,
    )

    history = tuple(
        CopilotConversationMessage(
            role="user",
            content=f"שאלה {index}",
        )
        for index in range(13)
    )

    with pytest.raises(
        ValueError,
        match="more than 12",
    ):
        await service.answer(
            "שאלה נוכחית",
            history=history,
        )


@pytest.mark.asyncio
async def test_answer_exposes_original_source_content() -> None:
    context = make_context()
    context_service = FakeContextService(context)
    generator = FakeGenerator()
    service = CopilotAnswerService(
        context_service=context_service,  # type: ignore[arg-type]
        generator=generator,
    )

    result = await service.answer("שאלה")

    assert result.sources
    assert result.sources[0].content == (
        context.sources[0].content
    )


@pytest.mark.asyncio
async def test_answer_uses_planner_defaults() -> None:
    context_service = FakeContextService(make_context())
    generator = FakeGenerator()
    service = CopilotAnswerService(
        context_service=context_service,  # type: ignore[arg-type]
        generator=generator,
    )

    await service.answer(
        "איפה כתוב שצריך לקבל בקשה במייל?"
    )

    call = context_service.calls[-1]

    assert call["search_limit"] == 14
    assert call["max_characters"] == 7_000
    assert call["max_chunks"] == 4
    assert call["max_chunks_per_page"] == 2


@pytest.mark.asyncio
async def test_explicit_retrieval_values_override_planner() -> None:
    context_service = FakeContextService(make_context())
    generator = FakeGenerator()
    service = CopilotAnswerService(
        context_service=context_service,  # type: ignore[arg-type]
        generator=generator,
    )

    await service.answer(
        "איפה כתוב שצריך לקבל בקשה במייל?",
        search_limit=42,
        max_characters=18_000,
        max_chunks=11,
        max_chunks_per_page=5,
    )

    call = context_service.calls[-1]

    assert call["search_limit"] == 42
    assert call["max_characters"] == 18_000
    assert call["max_chunks"] == 11
    assert call["max_chunks_per_page"] == 5


@pytest.mark.asyncio
async def test_summary_uses_broad_retrieval_plan() -> None:
    context_service = FakeContextService(make_context())
    generator = FakeGenerator()
    service = CopilotAnswerService(
        context_service=context_service,  # type: ignore[arg-type]
        generator=generator,
    )

    await service.answer(
        "סכם לי את נוהל מחיקת כרטיס הלקוח"
    )

    call = context_service.calls[-1]

    assert call["search_limit"] == 45
    assert call["max_characters"] == 22_000
    assert call["max_chunks"] == 15
    assert call["max_chunks_per_page"] == 8


@pytest.mark.asyncio
async def test_answer_does_not_pollute_new_topic_with_history() -> None:
    context_service = FakeContextService(make_context())
    generator = FakeGenerator(
        "תשובה עם מקור. [SOURCE 1]"
    )
    service = CopilotAnswerService(
        context_service=context_service,  # type: ignore[arg-type]
        generator=generator,
    )

    await service.answer(
        "איך עובדים עם Salesforce?",
        history=(
            CopilotConversationMessage(
                role="user",
                content="איך מוחקים לקוח?",
            ),
            CopilotConversationMessage(
                role="assistant",
                content="פועלים לפי נוהל המחיקה.",
            ),
        ),
    )

    assert context_service.calls[-1]["query"] == (
        "איך עובדים עם Salesforce?"
    )


@pytest.mark.asyncio
async def test_answer_resolves_contextual_follow_up_before_retrieval() -> None:
    context_service = FakeContextService(make_context())
    generator = FakeGenerator(
        "תשובה עם מקור. [SOURCE 1]"
    )
    service = CopilotAnswerService(
        context_service=context_service,  # type: ignore[arg-type]
        generator=generator,
    )

    await service.answer(
        "ומה אם הוא לקוח זר?",
        history=(
            CopilotConversationMessage(
                role="user",
                content="איך מוחקים לקוח?",
            ),
            CopilotConversationMessage(
                role="assistant",
                content="פועלים לפי נוהל המחיקה.",
            ),
        ),
    )

    assert context_service.calls[-1]["query"] == (
        "איך מוחקים לקוח? ומה אם הוא לקוח זר?"
    )
