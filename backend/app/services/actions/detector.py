from __future__ import annotations

from .models import ActionRequest


class ActionDetector:

    def detect(
        self,
        text: str,
    ) -> ActionRequest | None:

        normalized = text.lower()

        publish_words = [
            "פרסם",
            "תעלה",
            "העלה",
            "לוויקי",
            "לוויקיה",
            "wiki",
            "publish",
            "את",
        ]

        if not any(
            word in normalized
            for word in publish_words
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
            "תעלה",
            "העלה",
            "פרסם",
            "לוויקי",
            "לוויקיה",
            "ל wiki",
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
