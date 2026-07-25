from __future__ import annotations

import re
from collections.abc import Sequence

from sqlalchemy import Select, case, desc, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    KnowledgeChunk,
    KnowledgePage,
    KnowledgeRevision,
)
from app.services.knowledge.models import KnowledgeSearchResult


class KnowledgeSearchRepository:
    """
    Retrieve ranked knowledge chunks using PostgreSQL full-text search.

    Natural-language queries are converted into a conservative OR expression.
    The repository deliberately avoids language stemming or aggressive Hebrew
    prefix removal because those transformations can create invalid words.
    """

    DEFAULT_LIMIT = 10
    MAX_LIMIT = 100
    MAX_QUERY_TERMS = 12

    _TOKEN_PATTERN = re.compile(
        r"[^\W_]+",
        flags=re.UNICODE,
    )

    _STOP_WORDS = frozenset(
        {
            "אני",
            "אנחנו",
            "את",
            "אתה",
            "אתם",
            "איך",
            "איפה",
            "אם",
            "או",
            "גם",
            "הוא",
            "היא",
            "הם",
            "הן",
            "זה",
            "זו",
            "זאת",
            "יש",
            "כאשר",
            "כדי",
            "כל",
            "לא",
            "לי",
            "לו",
            "לנו",
            "מה",
            "מי",
            "מתי",
            "מבקש",
            "מבקשת",
            "צריך",
            "צריכה",
            "צריכים",
            "על",
            "עם",
            "של",
            "שלו",
            "שלה",
            "שלהם",
            "שלהן",
            "שם",
            "לעשות",
        }
    )

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search_chunks(
        self,
        query: str,
        *,
        limit: int = DEFAULT_LIMIT,
        namespace_ids: Sequence[int] | None = None,
    ) -> list[KnowledgeSearchResult]:
        statement = self.build_search_statement(
            query,
            limit=limit,
            namespace_ids=namespace_ids,
        )

        result = await self._session.execute(statement)

        return [
            self._row_to_result(row)
            for row in result.all()
        ]

    @classmethod
    def build_search_statement(
        cls,
        query: str,
        *,
        limit: int = DEFAULT_LIMIT,
        namespace_ids: Sequence[int] | None = None,
    ) -> Select:
        """Build the PostgreSQL full-text search statement."""

        normalized_query = cls._normalize_query(query)
        normalized_limit = cls._normalize_limit(limit)
        normalized_namespaces = cls._normalize_namespace_ids(
            namespace_ids
        )

        search_terms = cls._search_terms(normalized_query)
        broad_expression = cls._build_broad_search_expression(
            normalized_query
        )

        strict_query = func.plainto_tsquery(
            "simple",
            normalized_query,
        )
        broad_query = func.websearch_to_tsquery(
            "simple",
            broad_expression,
        )

        content_rank = func.ts_rank_cd(
            KnowledgeChunk.search_vector,
            broad_query,
        )

        strict_match_boost = case(
            (
                KnowledgeChunk.search_vector.op("@@")(
                    strict_query
                ),
                1.0,
            ),
            else_=0.0,
        )

        exact_title_boost = case(
            (
                KnowledgePage.normalized_title.contains(
                    normalized_query.casefold()
                ),
                2.0,
            ),
            else_=0.0,
        )

        title_term_boost = literal(0.0)

        for term in search_terms[: cls.MAX_QUERY_TERMS]:
            title_term_boost = (
                title_term_boost
                + case(
                    (
                        KnowledgePage.normalized_title.contains(
                            term
                        ),
                        0.35,
                    ),
                    else_=0.0,
                )
            )

        rank = (
            content_rank
            + strict_match_boost
            + exact_title_boost
            + title_term_boost
        ).label("rank")

        statement = (
            select(
                KnowledgePage.id.label("page_id"),
                KnowledgeRevision.id.label("revision_id"),
                KnowledgeChunk.id.label("chunk_id"),
                KnowledgePage.wiki_page_id,
                KnowledgeRevision.wiki_revision_id,
                KnowledgePage.title,
                KnowledgePage.canonical_url,
                KnowledgePage.namespace_id,
                KnowledgeChunk.position,
                KnowledgeChunk.heading_path,
                KnowledgeChunk.content,
                KnowledgeChunk.token_count,
                rank,
            )
            .select_from(KnowledgeChunk)
            .join(
                KnowledgeRevision,
                KnowledgeRevision.id
                == KnowledgeChunk.revision_id,
            )
            .join(
                KnowledgePage,
                KnowledgePage.id
                == KnowledgeRevision.page_id,
            )
            .where(
                KnowledgePage.is_active.is_(True),
                KnowledgePage.latest_revision_id
                == KnowledgeRevision.wiki_revision_id,
                KnowledgeChunk.search_vector.is_not(None),
                KnowledgeChunk.search_vector.op("@@")(
                    broad_query
                ),
            )
            .order_by(
                desc(rank),
                KnowledgePage.title.asc(),
                KnowledgeChunk.position.asc(),
            )
            .limit(normalized_limit)
        )

        if normalized_namespaces is not None:
            statement = statement.where(
                KnowledgePage.namespace_id.in_(
                    normalized_namespaces
                )
            )

        return statement

    @classmethod
    def _build_broad_search_expression(
        cls,
        query: str,
    ) -> str:
        """
        Build a PostgreSQL web-search expression.

        Meaningful terms are joined with OR so a natural-language question
        does not require every word to appear in the same chunk.
        """

        terms = cls._search_terms(query)

        if not terms:
            return cls._normalize_query(query)

        return " OR ".join(terms)

    @classmethod
    def _search_terms(
        cls,
        query: str,
    ) -> tuple[str, ...]:
        """
        Extract stable terms from a natural-language query.

        Prefix expansion is intentionally conservative. It only applies
        transformations that are unlikely to create invalid Hebrew words.
        """

        normalized_query = cls._normalize_query(query)
        terms: list[str] = []

        for match in cls._TOKEN_PATTERN.finditer(
            normalized_query.casefold()
        ):
            token = match.group(0)

            for candidate in cls._expand_hebrew_token(token):
                if len(candidate) < 2:
                    continue

                if candidate in cls._STOP_WORDS:
                    continue

                if candidate not in terms:
                    terms.append(candidate)

                if len(terms) >= cls.MAX_QUERY_TERMS:
                    return tuple(terms)

        return tuple(terms)

    @staticmethod
    def _expand_hebrew_token(
        token: str,
    ) -> tuple[str, ...]:
        """
        Return safe query variants for common Hebrew prefixes.

        Examples:
        - הכרטיס -> הכרטיס, כרטיס
        - כשלקוח -> כשלקוח, לקוח

        Prefixes such as מ, ל, ש, כ and ב are not removed generically because
        doing so can create invalid terms such as מחוק -> חוק.
        """

        candidates = [token]

        if token.startswith("כש") and len(token) >= 5:
            base = token[2:]

            if len(base) >= 3:
                candidates.append(base)

        elif token.startswith("ה") and len(token) >= 5:
            base = token[1:]

            if len(base) >= 3:
                candidates.append(base)

        return tuple(candidates)

    @staticmethod
    def _row_to_result(
        row: object,
    ) -> KnowledgeSearchResult:
        return KnowledgeSearchResult(
            page_id=str(row.page_id),
            revision_id=str(row.revision_id),
            chunk_id=str(row.chunk_id),
            wiki_page_id=row.wiki_page_id,
            wiki_revision_id=row.wiki_revision_id,
            title=row.title,
            canonical_url=row.canonical_url,
            namespace_id=row.namespace_id,
            position=row.position,
            heading_path=tuple(row.heading_path),
            content=row.content,
            token_count=row.token_count,
            rank=float(row.rank),
        )

    @staticmethod
    def _normalize_query(query: str) -> str:
        if not isinstance(query, str):
            raise ValueError("query must be a string")

        normalized = " ".join(query.split())

        if not normalized:
            raise ValueError("query cannot be empty")

        return normalized

    @classmethod
    def _normalize_limit(
        cls,
        limit: int,
    ) -> int:
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise ValueError("limit must be an integer")

        if limit < 1 or limit > cls.MAX_LIMIT:
            raise ValueError(
                f"limit must be between 1 and {cls.MAX_LIMIT}"
            )

        return limit

    @staticmethod
    def _normalize_namespace_ids(
        namespace_ids: Sequence[int] | None,
    ) -> tuple[int, ...] | None:
        if namespace_ids is None:
            return None

        normalized: list[int] = []

        for namespace_id in namespace_ids:
            if (
                isinstance(namespace_id, bool)
                or not isinstance(namespace_id, int)
                or namespace_id < 0
            ):
                raise ValueError(
                    "namespace_ids must contain "
                    "non-negative integers"
                )

            if namespace_id not in normalized:
                normalized.append(namespace_id)

        if not normalized:
            raise ValueError("namespace_ids cannot be empty")

        return tuple(normalized)
