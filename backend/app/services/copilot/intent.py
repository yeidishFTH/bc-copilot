from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class CopilotIntent(StrEnum):
    """Supported user intents for Copilot routing."""

    PROCEDURE = "procedure"
    DOCUMENT_LOOKUP = "document_lookup"
    CITATION = "citation"
    SUMMARY = "summary"
    COMPARISON = "comparison"
    CHANGE_LOG = "change_log"
    GENERAL_QUESTION = "general_question"


@dataclass(frozen=True, slots=True)
class IntentClassification:
    """Result returned by the deterministic intent classifier."""

    intent: CopilotIntent
    confidence: float
    matched_signals: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _IntentRule:
    intent: CopilotIntent
    pattern: re.Pattern[str]
    weight: float
    signal: str


class IntentClassifier:
    """
    Classify a Hebrew user question using deterministic weighted rules.

    Design goals:
    - no external model call;
    - negligible latency and cost;
    - explainable classification;
    - safe fallback to general_question;
    - stable behaviour suitable for tests and routing.
    """

    _MIN_CONFIDENT_SCORE = 1.0

    _RULES = (
        # Comparison must be evaluated strongly because comparison questions
        # may also contain procedural words such as "איך".
        _IntentRule(
            intent=CopilotIntent.COMPARISON,
            pattern=re.compile(
                r"(?:השוו(?:ה|ה|י)?|"
                r"מה\s+ההבדל|"
                r"הבדלים?\s+בין|"
                r"בין.+לבין|"
                r"לעומת)",
                flags=re.IGNORECASE,
            ),
            weight=3.0,
            signal="comparison_phrase",
        ),
        _IntentRule(
            intent=CopilotIntent.SUMMARY,
            pattern=re.compile(
                r"(?:סכ(?:ם|מי|מו)|"
                r"תמצת|"
                r"בקצרה|"
                r"תקציר|"
                r"עיקרי\s+הדברים)",
                flags=re.IGNORECASE,
            ),
            weight=3.0,
            signal="summary_phrase",
        ),
        _IntentRule(
            intent=CopilotIntent.CHANGE_LOG,
            pattern=re.compile(
                r"(?:מה\s+השתנה|"
                r"אילו\s+שינויים|"
                r"שינויים?\s+(?:אחרונים|חדשים)|"
                r"גרסה\s+קודמת|"
                r"לעומת\s+הגרסה|"
                r"עודכן\s+מאז)",
                flags=re.IGNORECASE,
            ),
            weight=3.2,
            signal="change_phrase",
        ),
        _IntentRule(
            intent=CopilotIntent.CITATION,
            pattern=re.compile(
                r"(?:איפה\s+(?:זה\s+)?כתוב|"
                r"באיזה\s+(?:עמוד|מסמך|נוהל|סעיף)|"
                r"הראה\s+לי\s+את\s+המקור|"
                r"תן(?:\s+לי)?(?:\s+את)?\s+ה?מקור|"
                r"מה\s+המקור|"
                r"צטט|"
                r"ציטוט)",
                flags=re.IGNORECASE,
            ),
            weight=3.0,
            signal="citation_phrase",
        ),
        _IntentRule(
            intent=CopilotIntent.DOCUMENT_LOOKUP,
            pattern=re.compile(
                r"(?:מצא\s+(?:לי\s+)?(?:את\s+)?|"
                r"חפש\s+(?:לי\s+)?(?:את\s+)?|"
                r"תראה\s+(?:לי\s+)?(?:את\s+)?|"
                r"איזה\s+(?:נוהל|מדריך|מסמך|טופס)|"
                r"יש\s+(?:נוהל|מדריך|מסמך|טופס)|"
                r"פתח\s+(?:את\s+)?(?:הנוהל|המדריך|המסמך))",
                flags=re.IGNORECASE,
            ),
            weight=2.8,
            signal="document_lookup_phrase",
        ),
        _IntentRule(
            intent=CopilotIntent.PROCEDURE,
            pattern=re.compile(
                r"(?:איך\s+(?:עושים|מבצעים|פועלים|מטפלים)|"
                r"כיצד\s+(?:עושים|מבצעים|פועלים|מטפלים)|"
                r"מה\s+(?:צריך|צריכים)\s+לעשות|"
                r"מהם?\s+השלבים|"
                r"שלבי\s+(?:הביצוע|הטיפול|העבודה)|"
                r"מה\s+הנוהל|"
                r"מה\s+עושים\s+(?:כאשר|כש|אם)|"
                r"טיפול\s+במקרה)",
                flags=re.IGNORECASE,
            ),
            weight=2.8,
            signal="procedure_phrase",
        ),

        # Supporting document nouns strengthen lookup/procedure classification
        # but are deliberately weak alone.
        _IntentRule(
            intent=CopilotIntent.DOCUMENT_LOOKUP,
            pattern=re.compile(
                r"\b(?:נוהל|מדריך|מסמך|טופס|צ׳קליסט|צ'קליסט)\b",
                flags=re.IGNORECASE,
            ),
            weight=0.55,
            signal="document_noun",
        ),
        _IntentRule(
            intent=CopilotIntent.PROCEDURE,
            pattern=re.compile(
                r"\b(?:שלבים|פעולות|תהליך|טיפול|לבצע)\b",
                flags=re.IGNORECASE,
            ),
            weight=0.45,
            signal="procedure_noun",
        ),
    )

    _PRIORITY = {
        CopilotIntent.COMPARISON: 0,
        CopilotIntent.CHANGE_LOG: 1,
        CopilotIntent.SUMMARY: 2,
        CopilotIntent.CITATION: 3,
        CopilotIntent.DOCUMENT_LOOKUP: 4,
        CopilotIntent.PROCEDURE: 5,
        CopilotIntent.GENERAL_QUESTION: 6,
    }

    def classify(
        self,
        question: str,
    ) -> IntentClassification:
        normalized = self._normalize_question(question)

        scores: dict[CopilotIntent, float] = {
            intent: 0.0
            for intent in CopilotIntent
        }
        signals: dict[CopilotIntent, list[str]] = {
            intent: []
            for intent in CopilotIntent
        }

        for rule in self._RULES:
            if rule.pattern.search(normalized):
                scores[rule.intent] += rule.weight
                signals[rule.intent].append(rule.signal)

        best_intent = min(
            CopilotIntent,
            key=lambda intent: (
                -scores[intent],
                self._PRIORITY[intent],
            ),
        )
        best_score = scores[best_intent]

        if best_score < self._MIN_CONFIDENT_SCORE:
            return IntentClassification(
                intent=CopilotIntent.GENERAL_QUESTION,
                confidence=0.5,
                matched_signals=(),
            )

        second_score = max(
            (
                score
                for intent, score in scores.items()
                if intent != best_intent
            ),
            default=0.0,
        )

        confidence = self._calculate_confidence(
            best_score=best_score,
            second_score=second_score,
        )

        return IntentClassification(
            intent=best_intent,
            confidence=confidence,
            matched_signals=tuple(
                dict.fromkeys(signals[best_intent])
            ),
        )

    @staticmethod
    def _calculate_confidence(
        *,
        best_score: float,
        second_score: float,
    ) -> float:
        margin = max(best_score - second_score, 0.0)

        confidence = (
            0.58
            + min(best_score, 4.0) * 0.075
            + min(margin, 3.0) * 0.04
        )

        return round(
            min(max(confidence, 0.5), 0.98),
            3,
        )

    @staticmethod
    def _normalize_question(
        question: str,
    ) -> str:
        if not isinstance(question, str):
            raise ValueError(
                "question must be a string"
            )

        normalized = " ".join(question.split())

        if not normalized:
            raise ValueError(
                "question cannot be empty"
            )

        return normalized
