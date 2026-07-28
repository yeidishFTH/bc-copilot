from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.services.copilot.entities import (
    CopilotEntity,
    EntityDetector,
)
from app.services.copilot.models import (
    CopilotConversationMessage,
)


@dataclass(frozen=True, slots=True)
class ConversationResolution:
    """Resolved conversational question used for retrieval."""

    original_question: str
    resolved_question: str
    is_follow_up: bool
    used_history_messages: tuple[str, ...]
    current_entities: tuple[CopilotEntity, ...]
    context_entities: tuple[CopilotEntity, ...]


class ConversationMemoryResolver:
    """
    Resolve contextual Hebrew follow-up questions deterministically.

    Version 1 does not call an LLM and does not persist server-side state.
    It decides whether the supplied history is relevant and produces the
    explicit retrieval question consumed by Intent, Planner and Retrieval.
    """

    MAX_RESOLVED_LENGTH = 2_000
    MAX_PREVIOUS_USER_MESSAGES = 2

    _FOLLOW_UP_PATTERN = re.compile(
        r"^(?:"
        r"ו?מה\s+(?:אם|לגבי|קורה|עושים|הדין)|"
        r"ו?אם\b|"
        r"ו?אז\b|"
        r"ו?במקרה\s+ש|"
        r"ו?כאשר\b|"
        r"ו?כש\b|"
        r"ו?למה\b|"
        r"ו?איך\s+זה|"
        r"ו?איפה\s+זה|"
        r"ו?מי\s+אחראי\s+על\s+זה|"
        r"תסכם(?:\s+לי)?(?:\s+את\s+זה)?|"
        r"תקצר(?:\s+את\s+זה)?|"
        r"תפרט(?:\s+על\s+זה)?|"
        r"תראה(?:\s+לי)?\s+את\s+המקור|"
        r"ומה\s+איתו|"
        r"ומה\s+איתה"
        r")",
        flags=re.IGNORECASE,
    )

    _CONTEXT_REFERENCE_PATTERN = re.compile(
        r"(?:"
        r"\bהוא\b|"
        r"\bהיא\b|"
        r"\bאותו\b|"
        r"\bאותה\b|"
        r"\bאיתו\b|"
        r"\bאיתה\b|"
        r"\bזה\b|"
        r"\bזו\b|"
        r"\bזאת\b|"
        r"\bכבר\b|"
        r"\bשם\b|"
        r"\bבמקרה\s+הזה\b"
        r")",
        flags=re.IGNORECASE,
    )

    def __init__(
        self,
        *,
        entity_detector: EntityDetector | None = None,
    ) -> None:
        self._entity_detector = (
            entity_detector
            or EntityDetector()
        )

    def resolve(
        self,
        question: str,
        history: Sequence[CopilotConversationMessage] = (),
    ) -> ConversationResolution:
        normalized_question = self._normalize_text(
            question,
            field_name="question",
        )

        previous_user_messages = tuple(
            self._normalize_text(
                message.content,
                field_name="history message",
            )
            for message in history
            if message.role == "user"
        )

        current_detection = self._entity_detector.detect(
            normalized_question
        )

        is_follow_up = self._is_follow_up(
            normalized_question,
            has_history=bool(previous_user_messages),
            current_entity_count=len(
                current_detection.entities
            ),
        )

        if not is_follow_up:
            return ConversationResolution(
                original_question=normalized_question,
                resolved_question=normalized_question,
                is_follow_up=False,
                used_history_messages=(),
                current_entities=(
                    current_detection.entity_ids
                ),
                context_entities=(),
            )

        relevant_history = previous_user_messages[
            -self.MAX_PREVIOUS_USER_MESSAGES:
        ]

        context_text = " ".join(relevant_history)

        context_detection = self._entity_detector.detect(
            context_text
        )

        resolved_question = self._combine_unique(
            (*relevant_history, normalized_question)
        )

        return ConversationResolution(
            original_question=normalized_question,
            resolved_question=resolved_question[
                :self.MAX_RESOLVED_LENGTH
            ],
            is_follow_up=True,
            used_history_messages=relevant_history,
            current_entities=(
                current_detection.entity_ids
            ),
            context_entities=(
                context_detection.entity_ids
            ),
        )

    @classmethod
    def _is_follow_up(
        cls,
        question: str,
        *,
        has_history: bool,
        current_entity_count: int,
    ) -> bool:
        if not has_history:
            return False

        if cls._FOLLOW_UP_PATTERN.search(question):
            return True

        if cls._CONTEXT_REFERENCE_PATTERN.search(question):
            return True

        # Very short questions with no independently identifiable business
        # entity usually depend on the preceding conversation.
        word_count = len(question.split())

        return (
            word_count <= 5
            and current_entity_count == 0
        )

    @staticmethod
    def _combine_unique(
        values: Sequence[str],
    ) -> str:
        unique: list[str] = []
        seen: set[str] = set()

        for value in values:
            normalized = " ".join(value.split())
            key = normalized.casefold()

            if not normalized or key in seen:
                continue

            seen.add(key)
            unique.append(normalized)

        return " ".join(unique)

    @staticmethod
    def _normalize_text(
        value: str,
        *,
        field_name: str,
    ) -> str:
        if not isinstance(value, str):
            raise ValueError(
                f"{field_name} must be a string"
            )

        normalized = " ".join(value.split())

        if not normalized:
            raise ValueError(
                f"{field_name} cannot be empty"
            )

        return normalized
