from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.copilot.entities import (
    CopilotEntity,
    EntityDetector,
)


@dataclass(frozen=True, slots=True)
class QueryRewrite:
    """Deterministic expansion of one user query."""

    original_query: str
    normalized_query: str
    search_queries: tuple[str, ...]
    matched_aliases: tuple[str, ...]
    matched_document_names: tuple[str, ...]
    detected_entities: tuple[CopilotEntity, ...] = ()


@dataclass(frozen=True, slots=True)
class _AliasRule:
    canonical: str
    token_groups: tuple[frozenset[str], ...]
    phrases: tuple[str, ...]
    expansions: tuple[str, ...]


class QueryRewriter:
    """
    Expand Hebrew Copilot queries using deterministic domain aliases.

    Matching combines:
    - normalized tokens;
    - common Hebrew inflections;
    - attached Hebrew prepositions;
    - exact domain phrases.

    The rewriter does not call an external model.
    """

    MAX_SEARCH_QUERIES = 8

    _ENTITY_EXPANSIONS = {
        CopilotEntity.FOREIGN_CUSTOMER: (
            "נוהל זיהוי ואימות לקוח",
            "KYC",
            "דרכון",
        ),
        CopilotEntity.PASSPORT: (
            "נוהל זיהוי ואימות לקוח",
            "לקוחות זרים",
            "KYC",
        ),
        CopilotEntity.ID_DOCUMENT: (
            "נוהל זיהוי ואימות לקוח",
            "KYC",
            "תעודה מזהה",
        ),
        CopilotEntity.KYC: (
            "נוהל זיהוי ואימות לקוח",
            "זיהוי ואימות לקוח",
        ),
        CopilotEntity.AML: (
            "נוהל התקשרות עם מחלקת ציות",
            "ציות ורגולציה",
        ),
        CopilotEntity.COMPLIANCE: (
            "נוהל התקשרות עם מחלקת ציות",
            "ציות ורגולציה",
            "AML",
        ),
        CopilotEntity.CUSTOMER_DELETION: (
            "נוהל מחיקת כרטיס לקוח",
            "מחיקת כרטיס לקוח",
        ),
        CopilotEntity.SALESFORCE: (
            "מערכת Salesforce",
            "CRM",
        ),
        CopilotEntity.ATM: (
            "נוהל מכירת USDT ERC-20 וטיפול בתקלות",
            "Lamassu",
            "USDT",
        ),
        CopilotEntity.LAMASSU: (
            "נוהל מכירת USDT ERC-20 וטיפול בתקלות",
            "USDT",
            "ERC-20",
        ),
        CopilotEntity.TRANSACTION: (
            "יצירת עסקה",
            "עסקת מכירה הדרכה וריענון",
        ),
        CopilotEntity.USDT: (
            "נוהל מכירת USDT ERC-20 וטיפול בתקלות",
            "Lamassu",
            "ERC-20",
        ),
        CopilotEntity.BRANCH_OPENING: (
            "צ'קליסט פתיחת ותחזוקת סניף",
            "פתיחת סניף",
        ),
        CopilotEntity.DAY_CLOSING: (
            "נוהל סגירת יום",
            "סגירת סניף",
        ),
        CopilotEntity.CASH_COUNT: (
            "נוהל סגירת יום",
            "ספירה סופית",
        ),
        CopilotEntity.WHATSAPP: (
            "נוהל מענה שיחות WhatsApp",
            "WhatsApp",
        ),
        CopilotEntity.EMPLOYEE_ONBOARDING: (
            "נוהל קליטת עובד",
            "קליטת עובד חדש",
            "תהליך קליטת עובד",
            "חפיפת עובד חדש",
            "הדרכת עובד חדש",
        ),
    }


    _HEBREW_PREFIXES = (
        "ולכש",
        "וכש",
        "לכש",
        "וה",
        "וב",
        "ול",
        "ומ",
        "וש",
        "וכ",
        "כש",
        "ה",
        "ב",
        "ל",
        "מ",
        "ו",
        "ש",
        "כ",
    )

    _ALIAS_RULES = (
        _AliasRule(
            canonical="מחיקת כרטיס לקוח",
            token_groups=(
                frozenset(
                    {
                        "מחיקה",
                        "מחיקת",
                        "מוחק",
                        "מוחקת",
                        "מוחקים",
                        "מוחקות",
                        "למחוק",
                    }
                ),
                frozenset(
                    {
                        "לקוח",
                        "לקוחה",
                        "חשבון",
                        "כרטיס",
                    }
                ),
            ),
            phrases=(
                "מחיקת לקוח",
                "מחיקת חשבון",
                "מחיקת כרטיס",
                "למחוק לקוח",
                "למחוק את הלקוח",
            ),
            expansions=(
                "מחיקת כרטיס לקוח",
                "נוהל מחיקת כרטיס לקוח",
                "מחיקת חשבון לקוח",
            ),
        ),
        _AliasRule(
            canonical="זיהוי ואימות לקוח",
            token_groups=(
                frozenset(
                    {
                        "זיהוי",
                        "מזהה",
                        "מזהים",
                        "לזהות",
                        "אימות",
                        "מאמת",
                        "מאמתים",
                        "לאמת",
                        "kyc",
                    }
                ),
                frozenset(
                    {
                        "לקוח",
                        "לקוחה",
                        "זהות",
                        "תעודה",
                    }
                ),
            ),
            phrases=(
                "זיהוי לקוח",
                "אימות לקוח",
                "בדיקת זהות",
                "צילום תעודת זהות",
                "תעודה מזהה",
            ),
            expansions=(
                "זיהוי ואימות לקוח",
                "נוהל זיהוי ואימות לקוח",
                "KYC",
                "תעודה מזהה",
            ),
        ),
        _AliasRule(
            canonical="לקוחות זרים",
            token_groups=(
                frozenset(
                    {
                        "לקוח",
                        "לקוחה",
                        "לקוחות",
                    }
                ),
                frozenset(
                    {
                        "זר",
                        "זרה",
                        "זרים",
                        "זרות",
                        "דרכון",
                        "passport",
                    }
                ),
            ),
            phrases=(
                "לקוח זר",
                "לקוחה זרה",
                "לקוחות זרים",
                "רישום לקוח זר",
            ),
            expansions=(
                "לקוחות זרים",
                "דגשים בעת רישום לקוחות זרים",
                "דרכון",
                "passport",
            ),
        ),
        _AliasRule(
            canonical="קליטת עובד חדש",
            token_groups=(
                frozenset(
                    {
                        "עובד",
                        "עובדת",
                        "עובדים",
                        "עובדות",
                    }
                ),
                frozenset(
                    {
                        "חדש",
                        "חדשה",
                        "חדשים",
                        "חדשות",
                        "קליטה",
                        "קליטת",
                        "חפיפה",
                        "חפיפת",
                        "הדרכה",
                        "הכשרה",
                        "onboarding",
                    }
                ),
            ),
            phrases=(
                "קליטת עובד",
                "קליטת עובד חדש",
                "עובד חדש",
                "עובדת חדשה",
                "חפיפת עובד",
                "חפיפה לעובד",
                "הדרכת עובד חדש",
                "הכשרת עובד חדש",
                "לפני הגעת עובד",
                "לפני שהעובד מגיע",
                "onboarding",
                "employee onboarding",
                "new employee",
            ),
            expansions=(
                "קליטת עובד חדש",
                "נוהל קליטת עובד",
                "תהליך קליטת עובד",
                "חפיפת עובד חדש",
                "הדרכת עובד חדש",
                "לפני הגעת עובד חדש",
            ),
        ),
        _AliasRule(
            canonical="מערכת Salesforce",
            token_groups=(
                frozenset(
                    {
                        "salesforce",
                        "סיילספורס",
                        "crm",
                        "accounts",
                        "account",
                    }
                ),
            ),
            phrases=(
                "מערכת לקוחות",
                "מערכת salesforce",
                "מערכת סיילספורס",
                "סיילספורס",
                "accounts",
                "account",
            ),
            expansions=(
                "מערכת Salesforce",
                "Salesforce",
                "CRM",
                "Accounts",
            ),
        ),
        _AliasRule(
            canonical="כספומט Lamassu",
            token_groups=(
                frozenset(
                    {
                        "כספומט",
                        "כספומטים",
                        "atm",
                        "lamassu",
                    }
                ),
            ),
            phrases=(
                "מכונת ביטקוין",
                "כספומט ביטקוין",
            ),
            expansions=(
                "כספומט",
                "ATM",
                "Lamassu",
            ),
        ),
        _AliasRule(
            canonical="פתיחת סניף",
            token_groups=(
                frozenset(
                    {
                        "פתיחה",
                        "פתיחת",
                        "פותח",
                        "פותחים",
                        "לפתוח",
                    }
                ),
                frozenset(
                    {
                        "סניף",
                        "משימות",
                        "משימה",
                    }
                ),
            ),
            phrases=(
                "פתיחת סניף",
                "משימות פתיחה",
                "משימות הפתיחה",
                "פותחים סניף",
                "תחילת משמרת בוקר",
                "משמרת בוקר",
                "בתחילת משמרת",
                "תחילת המשמרת",
            ),
            expansions=(
                "פתיחת סניף",
                "צ'קליסט פתיחת ותחזוקת סניף",
                "צ׳קליסט פתיחת ותחזוקת סניף",
                "משימות פתיחה",
            ),
        ),
        _AliasRule(
            canonical="סגירת יום",
            token_groups=(
                frozenset(
                    {
                        "סגירה",
                        "סגירת",
                        "סוגר",
                        "סוגרים",
                        "לסגור",
                        "סופית",
                    }
                ),
                frozenset(
                    {
                        "יום",
                        "סניף",
                        "משימות",
                        "ספירה",
                    }
                ),
            ),
            phrases=(
                "סגירת יום",
                "סגירת סניף",
                "משימות סגירה",
                "ספירה סופית",
            ),
            expansions=(
                "נוהל סגירת יום",
                "סגירת סניף",
                "ספירה סופית",
            ),
        ),
        _AliasRule(
            canonical="מחלקת ציות",
            token_groups=(
                frozenset(
                    {
                        "ציות",
                        "aml",
                    }
                ),
            ),
            phrases=(
                "מחלקת ציות",
                "קצין ציות",
                "קצינת ציות",
                "ציות ורגולציה",
            ),
            expansions=(
                "מחלקת ציות",
                "נוהל התקשרות עם מחלקת ציות",
                "ציות ורגולציה",
                "AML",
            ),
        ),
        _AliasRule(
            canonical="יצירת עסקה",
            token_groups=(
                frozenset(
                    {
                        "יצירה",
                        "יצירת",
                        "יוצר",
                        "יוצרים",
                        "ליצור",
                        "ביצוע",
                        "מבצע",
                        "מבצעים",
                        "לבצע",
                        "פתיחת",
                        "פותח",
                    }
                ),
                frozenset(
                    {
                        "עסקה",
                        "עסקת",
                    }
                ),
            ),
            phrases=(
                "יצירת עסקה",
                "ביצוע עסקה",
                "פתיחת עסקה",
                "מבצעים עסקה",
            ),
            expansions=(
                "יצירת עסקה",
                "עסקת מכירה הדרכה וריענון",
                "ביצוע עסקה",
            ),
        ),
    )

    _DOCUMENT_NAMES = (
        "נוהל מחיקת כרטיס לקוח",
        "נוהל זיהוי ואימות לקוח",
        "נוהל סגירת יום",
        "נוהל התקשרות עם מחלקת ציות",
        "צ'קליסט פתיחת ותחזוקת סניף",
        "צ׳קליסט פתיחת ותחזוקת סניף",
        "מערכת Salesforce",
        "יצירת עסקה",
        "ציות ורגולציה",
        "נוהל קליטת עובד",
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

    def rewrite(
        self,
        query: str,
    ) -> QueryRewrite:
        normalized = self._normalize_query(query)
        normalized_casefold = normalized.casefold()
        tokens = self._tokenize(normalized)
        entity_detection = self._entity_detector.detect(
            normalized
        )

        search_queries: list[str] = [normalized]
        matched_aliases: list[str] = []
        matched_document_names: list[str] = []

        for document_name in self._DOCUMENT_NAMES:
            if document_name.casefold() in normalized_casefold:
                matched_document_names.append(document_name)
                self._append_unique(
                    search_queries,
                    document_name,
                )

        for rule in self._ALIAS_RULES:
            if not self._matches_rule(
                rule,
                normalized_casefold=normalized_casefold,
                tokens=tokens,
            ):
                continue

            matched_aliases.append(rule.canonical)

            for expansion in rule.expansions:
                self._append_unique(
                    search_queries,
                    expansion,
                )

                if (
                    len(search_queries)
                    >= self.MAX_SEARCH_QUERIES
                ):
                    break

            if (
                len(search_queries)
                >= self.MAX_SEARCH_QUERIES
            ):
                break

        for entity in entity_detection.entity_ids:
            expansions = self._ENTITY_EXPANSIONS.get(
                entity,
                (),
            )

            for expansion in expansions:
                self._append_unique(
                    search_queries,
                    expansion,
                )

                if (
                    len(search_queries)
                    >= self.MAX_SEARCH_QUERIES
                ):
                    break

            if (
                len(search_queries)
                >= self.MAX_SEARCH_QUERIES
            ):
                break

        overview_signals = (
            "מה המשמעות של",
            "מה המשמעות",
            "מה זה",
            "מהי",
            "מהו",
            "הסבר",
            "הסבירו",
            "סקירה",
            "רקע על",
        )

        is_overview_query = any(
            signal in normalized_casefold
            for signal in overview_signals
        )

        if (
            is_overview_query
            and CopilotEntity.COMPLIANCE
            in entity_detection.entity_ids
        ):
            procedure_title = (
                "נוהל התקשרות עם מחלקת ציות"
            )
            overview_title = "ציות ורגולציה"

            search_queries = [
                item
                for item in search_queries
                if item.casefold()
                != procedure_title.casefold()
            ]

            search_queries = [
                search_queries[0],
                overview_title,
                *search_queries[1:],
            ]

        search_queries = list(
            dict.fromkeys(search_queries)
        )[:self.MAX_SEARCH_QUERIES]

        return QueryRewrite(
            original_query=query,
            normalized_query=normalized,
            search_queries=tuple(search_queries),
            matched_aliases=tuple(
                dict.fromkeys(matched_aliases)
            ),
            matched_document_names=tuple(
                dict.fromkeys(
                    matched_document_names
                )
            ),
            detected_entities=(
                entity_detection.entity_ids
            ),
        )

    @classmethod
    def _matches_rule(
        cls,
        rule: _AliasRule,
        *,
        normalized_casefold: str,
        tokens: frozenset[str],
    ) -> bool:
        if any(
            phrase.casefold() in normalized_casefold
            for phrase in rule.phrases
        ):
            return True

        return all(
            bool(group.intersection(tokens))
            for group in rule.token_groups
        )

    @classmethod
    def _tokenize(
        cls,
        value: str,
    ) -> frozenset[str]:
        raw_tokens = re.findall(
            r"[א-תA-Za-z0-9׳']+",
            value.casefold(),
        )

        tokens: set[str] = set()

        for token in raw_tokens:
            tokens.add(token)

            stripped = cls._strip_hebrew_prefix(token)

            if stripped:
                tokens.add(stripped)

        return frozenset(tokens)

    @classmethod
    def _strip_hebrew_prefix(
        cls,
        token: str,
    ) -> str:
        if not re.fullmatch(
            r"[א-ת׳']+",
            token,
        ):
            return token

        for prefix in cls._HEBREW_PREFIXES:
            if (
                token.startswith(prefix)
                and len(token) - len(prefix) >= 3
            ):
                return token[len(prefix):]

        return token

    @staticmethod
    def _append_unique(
        values: list[str],
        value: str,
    ) -> None:
        normalized_value = " ".join(value.split())

        if not normalized_value:
            return

        existing = {
            item.casefold()
            for item in values
        }

        if normalized_value.casefold() not in existing:
            values.append(normalized_value)

    @staticmethod
    def _normalize_query(
        query: str,
    ) -> str:
        if not isinstance(query, str):
            raise ValueError(
                "query must be a string"
            )

        normalized = " ".join(query.split())

        if not normalized:
            raise ValueError(
                "query cannot be empty"
            )

        return normalized
