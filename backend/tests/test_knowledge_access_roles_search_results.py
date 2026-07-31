from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.services.knowledge.models import (
    KnowledgeSearchResult,
)
from app.services.knowledge.persistence.repositories.search import (
    KnowledgeSearchRepository,
)
from app.services.knowledge.persistence.repositories.vector_search import (
    KnowledgeVectorSearchRepository,
)


def make_row(
    *,
    access_roles: list[str] | None,
) -> SimpleNamespace:
    return SimpleNamespace(
        page_id="11111111-1111-1111-1111-111111111111",
        revision_id="22222222-2222-2222-2222-222222222222",
        chunk_id="33333333-3333-3333-3333-333333333333",
        wiki_page_id=100,
        wiki_revision_id=200,
        title="נוהל הנהלה",
        canonical_url=(
            "https://wiki.bitcoinchange.co.il/"
            "index.php/נוהל_הנהלה"
        ),
        namespace_id=0,
        position=0,
        heading_path=["כללי"],
        content="תוכן מוגבל",
        token_count=10,
        rank=1.5,
        distance=0.1,
        status="מאושר",
        document_type="נוהל",
        portal="הנהלה",
        category="נהלים",
        audience=["הנהלה"],
        access_roles=access_roles,
        owner="הנהלה",
        responsible_department="Management",
        updated_on=date(2026, 7, 31),
        version="1.0",
    )


def test_domain_search_result_defaults_to_open_access() -> None:
    result = KnowledgeSearchResult(
        page_id="page",
        revision_id="revision",
        chunk_id="chunk",
        wiki_page_id=1,
        wiki_revision_id=2,
        title="מסמך",
        canonical_url="https://example.test/wiki",
        namespace_id=0,
        position=0,
        heading_path=(),
        content="תוכן",
        token_count=None,
        rank=1.0,
    )

    assert result.access_roles == ()


def test_lexical_result_maps_access_roles() -> None:
    result = (
        KnowledgeSearchRepository
        ._row_to_result(
            make_row(
                access_roles=[
                    "management",
                    "administrator",
                ]
            )
        )
    )

    assert result.access_roles == (
        "management",
        "administrator",
    )


def test_lexical_result_defaults_missing_roles_to_open() -> None:
    row = make_row(access_roles=None)
    delattr(row, "access_roles")

    result = (
        KnowledgeSearchRepository
        ._row_to_result(row)
    )

    assert result.access_roles == ()


def test_vector_result_maps_access_roles() -> None:
    result = (
        KnowledgeVectorSearchRepository
        ._row_to_result(
            make_row(
                access_roles=[
                    "branch_user",
                    "management",
                ]
            )
        )
    )

    assert result.access_roles == (
        "branch_user",
        "management",
    )


def test_vector_result_defaults_null_roles_to_open() -> None:
    result = (
        KnowledgeVectorSearchRepository
        ._row_to_result(
            make_row(access_roles=None)
        )
    )

    assert result.access_roles == ()
