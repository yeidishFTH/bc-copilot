from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QueryRewrite:
    """Deterministic expansion of one user query."""

    original_query: str
    normalized_query: str
    search_queries: tuple[str, ...]
    matched_aliases: tuple[str, ...]
    matched_document_names: tuple[str, ...]


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
            canonical="מערכת Salesforce",
            token_groups=(
                frozenset(
                    {
                        "salesforce",
                        "crm",
                    }
                ),
            ),
            phrases=(
                "מערכת לקוחות",
                "מערכת salesforce",
            ),
            expansions=(
                "מערכת Salesforce",
                "Salesforce",
                "CRM",
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
    )

    def rewrite(
        self,
        query: str,
    ) -> QueryRewrite:
        normalized = self._normalize_query(query)
        normalized_casefold = normalized.casefold()
        tokens = self._tokenize(normalized)

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
