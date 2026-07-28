from __future__ import annotations

from app.services.copilot.conversation_memory import (
    ConversationMemoryResolver,
)
from app.services.copilot.entities import (
    CopilotEntity,
)
from app.services.copilot.models import (
    CopilotConversationMessage,
)


def message(
    role: str,
    content: str,
) -> CopilotConversationMessage:
    return CopilotConversationMessage(
        role=role,
        content=content,
    )


def test_standalone_question_does_not_use_history() -> None:
    resolver = ConversationMemoryResolver()

    result = resolver.resolve(
        "איך עובדים עם Salesforce?",
        history=(
            message(
                "user",
                "איך מוחקים לקוח?",
            ),
            message(
                "assistant",
                "פועלים לפי נוהל המחיקה.",
            ),
        ),
    )

    assert result.is_follow_up is False
    assert result.resolved_question == (
        "איך עובדים עם Salesforce?"
    )
    assert result.used_history_messages == ()


def test_follow_up_uses_previous_user_topic() -> None:
    resolver = ConversationMemoryResolver()

    result = resolver.resolve(
        "ומה אם הוא לקוח זר?",
        history=(
            message(
                "user",
                "איך מוחקים לקוח?",
            ),
            message(
                "assistant",
                "פועלים לפי נוהל המחיקה.",
            ),
        ),
    )

    assert result.is_follow_up is True
    assert result.resolved_question == (
        "איך מוחקים לקוח? ומה אם הוא לקוח זר?"
    )
    assert result.used_history_messages == (
        "איך מוחקים לקוח?",
    )


def test_follow_up_uses_last_two_user_messages() -> None:
    resolver = ConversationMemoryResolver()

    result = resolver.resolve(
        "ומה אם הוא כבר עבר KYC?",
        history=(
            message(
                "user",
                "איך מוחקים לקוח?",
            ),
            message(
                "assistant",
                "פועלים לפי נוהל המחיקה.",
            ),
            message(
                "user",
                "ומה אם הוא לקוח זר?",
            ),
            message(
                "assistant",
                "יש לבדוק דרישות זיהוי.",
            ),
        ),
    )

    assert result.resolved_question == (
        "איך מוחקים לקוח? "
        "ומה אם הוא לקוח זר? "
        "ומה אם הוא כבר עבר KYC?"
    )


def test_detects_context_and_current_entities() -> None:
    resolver = ConversationMemoryResolver()

    result = resolver.resolve(
        "ומה אם הוא לקוח זר?",
        history=(
            message(
                "user",
                "איך מוחקים לקוח?",
            ),
        ),
    )

    assert (
        CopilotEntity.CUSTOMER_DELETION
        in result.context_entities
    )
    assert (
        CopilotEntity.FOREIGN_CUSTOMER
        in result.current_entities
    )


def test_short_contextual_question_uses_history() -> None:
    resolver = ConversationMemoryResolver()

    result = resolver.resolve(
        "ומי אחראי?",
        history=(
            message(
                "user",
                "איך מוחקים לקוח?",
            ),
        ),
    )

    assert result.is_follow_up is True
    assert "איך מוחקים לקוח?" in (
        result.resolved_question
    )


def test_no_history_means_standalone_question() -> None:
    resolver = ConversationMemoryResolver()

    result = resolver.resolve(
        "ומה אם הוא לקוח זר?",
    )

    assert result.is_follow_up is False
    assert result.resolved_question == (
        "ומה אם הוא לקוח זר?"
    )


def test_new_explicit_entity_starts_new_topic() -> None:
    resolver = ConversationMemoryResolver()

    result = resolver.resolve(
        "איך מוכרים USDT דרך הכספומט?",
        history=(
            message(
                "user",
                "איך מוחקים לקוח?",
            ),
        ),
    )

    assert result.is_follow_up is False
    assert result.resolved_question == (
        "איך מוכרים USDT דרך הכספומט?"
    )


def test_duplicate_history_question_is_not_repeated() -> None:
    resolver = ConversationMemoryResolver()

    result = resolver.resolve(
        "תסכם לי את זה",
        history=(
            message(
                "user",
                "איך מוחקים לקוח?",
            ),
            message(
                "user",
                "איך מוחקים לקוח?",
            ),
        ),
    )

    assert result.resolved_question == (
        "איך מוחקים לקוח? תסכם לי את זה"
    )
