from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class CopilotEntity(StrEnum):
    """Business entities recognized in Copilot questions."""

    CUSTOMER = "customer"
    FOREIGN_CUSTOMER = "foreign_customer"
    PASSPORT = "passport"
    ID_DOCUMENT = "id_document"
    KYC = "kyc"
    AML = "aml"
    COMPLIANCE = "compliance"
    CUSTOMER_DELETION = "customer_deletion"
    SALESFORCE = "salesforce"
    ATM = "atm"
    LAMASSU = "lamassu"
    TRANSACTION = "transaction"
    USDT = "usdt"
    BITCOIN = "bitcoin"
    ETHEREUM = "ethereum"
    BRANCH = "branch"
    BRANCH_OPENING = "branch_opening"
    DAY_CLOSING = "day_closing"
    CASH_COUNT = "cash_count"
    WHATSAPP = "whatsapp"
    EMPLOYEE_ONBOARDING = "employee_onboarding"
    EMERGENCY_EVACUATION = "emergency_evacuation"
    MENTOR_REPORT = "mentor_report"
    REPRESENTATIVE_ROLE = "representative_role"
    COUPON = "coupon"


@dataclass(frozen=True, slots=True)
class DetectedEntity:
    """One entity detected in a user question."""

    entity: CopilotEntity
    confidence: float
    matched_terms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EntityDetection:
    """Entity analysis result for one question."""

    original_text: str
    normalized_text: str
    entities: tuple[DetectedEntity, ...]

    @property
    def entity_ids(self) -> tuple[CopilotEntity, ...]:
        return tuple(
            item.entity
            for item in self.entities
        )

    def contains(
        self,
        entity: CopilotEntity,
    ) -> bool:
        return entity in self.entity_ids


@dataclass(frozen=True, slots=True)
class _EntityRule:
    entity: CopilotEntity
    phrases: tuple[str, ...] = ()
    token_groups: tuple[frozenset[str], ...] = ()
    confidence: float = 0.88


class EntityDetector:
    """
    Detect Bitcoin Change business entities deterministically.

    Matching combines:
    - exact normalized phrases;
    - token groups;
    - common Hebrew inflections;
    - attached Hebrew prefixes.

    No LLM or network request is used.
    """

    _TOKEN_PATTERN = re.compile(
        r"[א-תA-Za-z0-9׳'״\"]+"
    )

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

    _RULES = (
        _EntityRule(
            entity=CopilotEntity.FOREIGN_CUSTOMER,
            phrases=(
                "לקוח זר",
                "לקוחה זרה",
                "לקוחות זרים",
                "תושב חוץ",
                "תושבת חוץ",
                "לקוח מחול",
                "לקוח מחו״ל",
                "לקוח מחו\"ל",
                "foreign customer",
            ),
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
                        "מחול",
                        "חו״ל",
                        "חו\"ל",
                    }
                ),
            ),
            confidence=0.97,
        ),
        _EntityRule(
            entity=CopilotEntity.PASSPORT,
            phrases=(
                "דרכון",
                "מספר דרכון",
                "צילום דרכון",
                "passport",
            ),
            token_groups=(
                frozenset(
                    {
                        "דרכון",
                        "דרכונים",
                        "passport",
                    }
                ),
            ),
            confidence=0.98,
        ),
        _EntityRule(
            entity=CopilotEntity.ID_DOCUMENT,
            phrases=(
                "תעודת זהות",
                "תעודה מזהה",
                "צילום תעודה",
                "מסמך מזהה",
            ),
            token_groups=(
                frozenset(
                    {
                        "תעודה",
                        "תעודת",
                        "מסמך",
                    }
                ),
                frozenset(
                    {
                        "זהות",
                        "מזהה",
                    }
                ),
            ),
            confidence=0.95,
        ),
        _EntityRule(
            entity=CopilotEntity.KYC,
            phrases=(
                "kyc",
                "זיהוי לקוח",
                "אימות לקוח",
                "זיהוי ואימות לקוח",
                "בדיקת זהות",
            ),
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
                    }
                ),
            ),
            confidence=0.94,
        ),
        _EntityRule(
            entity=CopilotEntity.AML,
            phrases=(
                "aml",
                "הלבנת הון",
                "איסור הלבנת הון",
                "מימון טרור",
            ),
            confidence=0.98,
        ),
        _EntityRule(
            entity=CopilotEntity.COMPLIANCE,
            phrases=(
                "מחלקת ציות",
                "קצין ציות",
                "קצינת ציות",
                "ציות ורגולציה",
                "ציות",
                "compliance",
            ),
            token_groups=(
                frozenset(
                    {
                        "ציות",
                        "compliance",
                    }
                ),
            ),
            confidence=0.95,
        ),
        _EntityRule(
            entity=CopilotEntity.CUSTOMER_DELETION,
            phrases=(
                "מחיקת לקוח",
                "מחיקת כרטיס לקוח",
                "מחיקת חשבון",
                "למחוק לקוח",
                "למחוק את הלקוח",
            ),
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
            confidence=0.97,
        ),
        _EntityRule(
            entity=CopilotEntity.SALESFORCE,
            phrases=(
                "salesforce",
                "סיילספורס",
                "מערכת salesforce",
                "מערכת סיילספורס",
                "מערכת לקוחות",
                "crm",
                "accounts",
                "account",
            ),
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
            confidence=0.99,
        ),
        _EntityRule(
            entity=CopilotEntity.LAMASSU,
            phrases=(
                "lamassu",
                "lamassu admin",
            ),
            token_groups=(
                frozenset(
                    {
                        "lamassu",
                    }
                ),
            ),
            confidence=0.99,
        ),
        _EntityRule(
            entity=CopilotEntity.ATM,
            phrases=(
                "כספומט",
                "כספומטים",
                "atm",
                "מכונת ביטקוין",
                "מכונה",
            ),
            token_groups=(
                frozenset(
                    {
                        "כספומט",
                        "כספומטים",
                        "atm",
                    }
                ),
            ),
            confidence=0.95,
        ),
        _EntityRule(
            entity=CopilotEntity.TRANSACTION,
            phrases=(
                "יצירת עסקה",
                "ביצוע עסקה",
                "פתיחת עסקה",
                "מבצעים עסקה",
                "עסקת קנייה",
                "עסקת מכירה",
            ),
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
                        "עסקאות",
                    }
                ),
            ),
            confidence=0.93,
        ),
        _EntityRule(
            entity=CopilotEntity.USDT,
            phrases=(
                "usdt",
                "tether",
                "erc-20",
                "erc20",
            ),
            confidence=0.99,
        ),
        _EntityRule(
            entity=CopilotEntity.BITCOIN,
            phrases=(
                "bitcoin",
                "ביטקוין",
                "btc",
            ),
            confidence=0.99,
        ),
        _EntityRule(
            entity=CopilotEntity.ETHEREUM,
            phrases=(
                "ethereum",
                "אתריום",
                "eth",
            ),
            confidence=0.99,
        ),
        _EntityRule(
            entity=CopilotEntity.BRANCH_OPENING,
            phrases=(
                "פתיחת סניף",
                "משימות פתיחה",
                "משימות הפתיחה",
                "פותחים סניף",
                "פתיחת משמרת",
                "תחילת משמרת בוקר",
                "משמרת בוקר",
                "בתחילת משמרת",
                "תחילת המשמרת",
            ),
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
                        "משמרת",
                        "משימות",
                    }
                ),
            ),
            confidence=0.95,
        ),
        _EntityRule(
            entity=CopilotEntity.DAY_CLOSING,
            phrases=(
                "סגירת יום",
                "סגירת סניף",
                "משימות סגירה",
                "סוגרים יום",
                "סוגרים סניף",
            ),
            token_groups=(
                frozenset(
                    {
                        "סגירה",
                        "סגירת",
                        "סוגר",
                        "סוגרים",
                        "לסגור",
                    }
                ),
                frozenset(
                    {
                        "יום",
                        "סניף",
                        "משמרת",
                    }
                ),
            ),
            confidence=0.95,
        ),
        _EntityRule(
            entity=CopilotEntity.CASH_COUNT,
            phrases=(
                "ספירת מזומן",
                "ספירת קופה",
                "ספירה סופית",
                "ספירת פתיחה",
                "ספירת אמצע",
                "ספירת סגירה",
            ),
            token_groups=(
                frozenset(
                    {
                        "ספירה",
                        "ספירת",
                        "סופית",
                    }
                ),
                frozenset(
                    {
                        "מזומן",
                        "קופה",
                        "פתיחה",
                        "אמצע",
                        "סגירה",
                    }
                ),
            ),
            confidence=0.94,
        ),
        _EntityRule(
            entity=CopilotEntity.WHATSAPP,
            phrases=(
                "whatsapp",
                "וואטסאפ",
                "ווטסאפ",
                "הודעות וואטסאפ",
                "שיחות whatsapp",
            ),
            confidence=0.99,
        ),
        _EntityRule(
            entity=CopilotEntity.EMPLOYEE_ONBOARDING,
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
                    }
                ),
            ),
            confidence=0.97,
        ),
        _EntityRule(
            entity=CopilotEntity.EMERGENCY_EVACUATION,
            phrases=(
                "פינוי בזמן חירום",
                "פינוי סניף בחירום",
                "לפנות את הסניף",
                "פינוי הסניף",
                "יציאה מהסניף בחירום",
                "מרחב מוגן",
                "בזמן אזעקה",
                "בזמן חירום",
            ),
            token_groups=(
                frozenset(
                    {
                        "חירום",
                        "אזעקה",
                        "התרעה",
                        "פינוי",
                        "לפנות",
                    }
                ),
                frozenset(
                    {
                        "סניף",
                        "הסניף",
                        "מרחב",
                        "מוגן",
                        "יוצאים",
                        "יציאה",
                    }
                ),
            ),
            confidence=0.98,
        ),
        _EntityRule(
            entity=CopilotEntity.MENTOR_REPORT,
            phrases=(
                "טופס דיווח חונך",
                "דיווח חונך",
                "משוב חונך",
                "הערכת חניך",
                "התקדמות החניך",
                "התקדמות של עובד חדש",
                "חונך מדווח",
                "חונך ממלא",
            ),
            token_groups=(
                frozenset(
                    {
                        "חונך",
                        "חונכת",
                        "חניך",
                        "חניכה",
                    }
                ),
                frozenset(
                    {
                        "דיווח",
                        "מדווח",
                        "משוב",
                        "הערכה",
                        "התקדמות",
                        "טופס",
                    }
                ),
            ),
            confidence=0.98,
        ),
        _EntityRule(
            entity=CopilotEntity.REPRESENTATIVE_ROLE,
            phrases=(
                "תפקיד הנציג",
                "תפקיד נציג השירות",
                "אחריות נציג השירות",
                "תחומי האחריות של נציג",
                "מה מצופה מנציג",
                "ציפיות מנציג",
                "משימות נציג",
                "נציג במהלך המשמרת",
            ),
            token_groups=(
                frozenset(
                    {
                        "נציג",
                        "נציגת",
                        "הנציג",
                        "נציגים",
                    }
                ),
                frozenset(
                    {
                        "תפקיד",
                        "אחריות",
                        "מצופה",
                        "ציפיות",
                        "משימות",
                        "משמרת",
                    }
                ),
            ),
            confidence=0.97,
        ),
        _EntityRule(
            entity=CopilotEntity.COUPON,
            phrases=(
                "נוהל קופונים",
                "קופון ללקוח",
                "קופוני הנחה",
                "קוד הנחה",
                "הנחה באמצעות קופון",
                "שימוש בקופון",
                "כללי שימוש בקופון",
                "קוד קופון",
            ),
            token_groups=(
                frozenset(
                    {
                        "קופון",
                        "קופונים",
                        "קוד",
                        "קודי",
                    }
                ),
                frozenset(
                    {
                        "הנחה",
                        "הטבה",
                        "לקוח",
                        "שימוש",
                        "כללים",
                    }
                ),
            ),
            confidence=0.99,
        ),
        _EntityRule(
            entity=CopilotEntity.BRANCH,
            phrases=(
                "סניף",
                "סניפים",
                "מנהל סניף",
            ),
            token_groups=(
                frozenset(
                    {
                        "סניף",
                        "סניפים",
                    }
                ),
            ),
            confidence=0.82,
        ),
        _EntityRule(
            entity=CopilotEntity.CUSTOMER,
            phrases=(
                "לקוח",
                "לקוחה",
                "לקוחות",
                "כרטיס לקוח",
            ),
            token_groups=(
                frozenset(
                    {
                        "לקוח",
                        "לקוחה",
                        "לקוחות",
                    }
                ),
            ),
            confidence=0.80,
        ),
    )

    def detect(
        self,
        text: str,
    ) -> EntityDetection:
        normalized = self._normalize_text(text)
        normalized_casefold = normalized.casefold()
        tokens = self._tokenize(normalized)

        detected: list[DetectedEntity] = []

        for rule in self._RULES:
            matched_terms = self._match_rule(
                rule,
                normalized_casefold=normalized_casefold,
                tokens=tokens,
            )

            if not matched_terms:
                continue

            detected.append(
                DetectedEntity(
                    entity=rule.entity,
                    confidence=rule.confidence,
                    matched_terms=matched_terms,
                )
            )

        detected.sort(
            key=lambda item: (
                -item.confidence,
                item.entity.value,
            )
        )

        return EntityDetection(
            original_text=text,
            normalized_text=normalized,
            entities=tuple(detected),
        )

    @classmethod
    def _match_rule(
        cls,
        rule: _EntityRule,
        *,
        normalized_casefold: str,
        tokens: frozenset[str],
    ) -> tuple[str, ...]:
        matched: list[str] = []

        for phrase in rule.phrases:
            if phrase.casefold() in normalized_casefold:
                matched.append(phrase)

        if rule.token_groups and all(
            bool(group.intersection(tokens))
            for group in rule.token_groups
        ):
            for group in rule.token_groups:
                matching_tokens = sorted(
                    group.intersection(tokens)
                )
                matched.extend(matching_tokens)

        return tuple(dict.fromkeys(matched))

    @classmethod
    def _tokenize(
        cls,
        value: str,
    ) -> frozenset[str]:
        raw_tokens = cls._TOKEN_PATTERN.findall(
            value.casefold()
        )

        tokens: set[str] = set()

        for token in raw_tokens:
            tokens.add(token)

            stripped = cls._strip_hebrew_prefix(
                token
            )

            if stripped:
                tokens.add(stripped)

        return frozenset(tokens)

    @classmethod
    def _strip_hebrew_prefix(
        cls,
        token: str,
    ) -> str:
        if not re.fullmatch(
            r"[א-ת׳'״\"]+",
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
    def _normalize_text(
        text: str,
    ) -> str:
        if not isinstance(text, str):
            raise ValueError(
                "text must be a string"
            )

        normalized = " ".join(text.split())

        if not normalized:
            raise ValueError(
                "text cannot be empty"
            )

        return normalized
