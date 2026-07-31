from __future__ import annotations

from sqlalchemy.dialects import postgresql

from app.services.knowledge.embeddings import (
    EmbeddingVector,
)
from app.services.knowledge.persistence.repositories.search import (
    KnowledgeSearchRepository,
)
from app.services.knowledge.persistence.repositories.vector_search import (
    KnowledgeVectorSearchRepository,
)


def compile_sql(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
        )
    )


def test_lexical_without_role_is_open_only() -> None:
    sql = compile_sql(
        KnowledgeSearchRepository
        .build_search_statement(
            "נוהל",
            access_role=None,
        )
    )

    assert "cardinality" in sql
    assert "coalesce" in sql
    assert "access_roles" in sql
    assert "ANY" not in sql


def test_lexical_with_role_allows_matching_role() -> None:
    sql = compile_sql(
        KnowledgeSearchRepository
        .build_search_statement(
            "נוהל",
            access_role="management",
        )
    )

    assert "cardinality" in sql
    assert "access_roles" in sql
    assert "ANY" in sql


def test_vector_without_role_is_open_only() -> None:
    statement = (
        KnowledgeVectorSearchRepository
        .build_search_statement(
            EmbeddingVector(
                values=tuple(
                    0.0
                    for _ in range(1536)
                )
            ),
            access_role=None,
        )
    )

    sql = compile_sql(statement)

    assert "cardinality" in sql
    assert "coalesce" in sql
    assert "access_roles" in sql
    assert "ANY" not in sql


def test_vector_with_role_allows_matching_role() -> None:
    statement = (
        KnowledgeVectorSearchRepository
        .build_search_statement(
            EmbeddingVector(
                values=tuple(
                    0.0
                    for _ in range(1536)
                )
            ),
            access_role="administrator",
        )
    )

    sql = compile_sql(statement)

    assert "cardinality" in sql
    assert "access_roles" in sql
    assert "ANY" in sql


def test_lexical_rejects_unknown_role() -> None:
    try:
        (
            KnowledgeSearchRepository
            .build_search_statement(
                "נוהל",
                access_role="unknown",
            )
        )
    except ValueError as error:
        assert str(error) == (
            "access_role is not recognized"
        )
    else:
        raise AssertionError(
            "Unknown role must be rejected"
        )


def test_vector_rejects_unknown_role() -> None:
    try:
        (
            KnowledgeVectorSearchRepository
            .build_search_statement(
                EmbeddingVector(
                    values=tuple(
                        0.0
                        for _ in range(1536)
                    )
                ),
                access_role="unknown",
            )
        )
    except ValueError as error:
        assert str(error) == (
            "access_role is not recognized"
        )
    else:
        raise AssertionError(
            "Unknown role must be rejected"
        )
