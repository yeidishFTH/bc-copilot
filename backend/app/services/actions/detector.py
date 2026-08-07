from __future__ import annotations

from .models import ActionRequest


class ActionDetector:

    def detect(
        self,
        text: str,
    ) -> ActionRequest | None:

        normalized = text.lower()

        action_words = [
            "פרסם",
            "תעלה",
            "העלה",
            "publish",
        ]

        wiki_words = [
            "וויקי",
            "ויקי",
            "wiki",
        ]

        has_action = any(
            word in normalized
            for word in action_words
        )

        has_target = any(
            word in normalized
            for word in wiki_words
        )

        if not (
            has_action
            and has_target
        ):
            return None

        document = self._extract_document(
            text
        )

        return ActionRequest(
            action="publish_knowledge",
            document=document,
            requires_approval=True,
        )


    def _extract_document(
        self,
        text: str,
    ) -> str | None:

        document = text

        remove_words = [
            "פרסם",
            "תעלה",
            "העלה",
            "לוויקי",
            "ויקי",
            "wiki",
            "publish",
            "את",
        ]

        for word in remove_words:
            document = document.replace(
                word,
                "",
            )

        document = (
            document
            .strip()
            .strip(",.")
            .strip()
        )

        return (
            document
            if document
            else None
        )
