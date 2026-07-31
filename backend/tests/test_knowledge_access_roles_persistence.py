from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ARRAY

from app.cli.backfill_knowledge_metadata import (
    metadata_values,
)
from app.db.models import (
    KnowledgePage,
    KnowledgeRevisionMetadata,
)
from app.services.knowledge.models import (
    KnowledgeDocumentRevision,
)
from app.services.knowledge.persistence.mappers import (
    KnowledgePersistenceMapper,
)


def make_page(
    *,
    wiki_page_id: int,
    latest_revision_id: int,
    title: str,
) -> KnowledgePage:
    return KnowledgePage(
        wiki_page_id=wiki_page_id,
        namespace_id=0,
        title=title,
        normalized_title=title.casefold(),
        canonical_url=(
            "https://wiki.bitcoinchange.co.il/"
            f"index.php/{title.replace(' ', '_')}"
        ),
        latest_revision_id=latest_revision_id,
        is_redirect=False,
        is_active=True,
    )


def test_metadata_model_exposes_access_roles() -> None:
    column = (
        KnowledgeRevisionMetadata
        .__table__
        .columns["access_roles"]
    )

    assert isinstance(
        column.type,
        ARRAY,
    )
    assert column.type.item_type.python_type is str
    assert column.nullable is False


def test_revision_mapper_persists_access_roles() -> None:
    page = make_page(
        wiki_page_id=100,
        latest_revision_id=200,
        title="מסמך הנהלה",
    )

    revision = KnowledgeDocumentRevision(
        id="200",
        document_id="100",
        timestamp=datetime.now(timezone.utc),
        raw_content="""
{{Metadata
| סטטוס = מאושר
| סוג מסמך = נוהל
| קהל יעד = הנהלה
| הרשאות גישה = הנהלה, מנהל מערכת
}}
תוכן מסמך
""",
    )

    persistence_revision, _ = (
        KnowledgePersistenceMapper
        .revision_to_models(
            revision,
            page=page,
        )
    )

    metadata = (
        persistence_revision.document_metadata
    )

    assert metadata is not None
    assert metadata.audience == ["הנהלה"]
    assert metadata.access_roles == [
        "management",
        "administrator",
    ]


def test_revision_mapper_defaults_to_open_access() -> None:
    page = make_page(
        wiki_page_id=101,
        latest_revision_id=201,
        title="מסמך פתוח",
    )

    revision = KnowledgeDocumentRevision(
        id="201",
        document_id="101",
        timestamp=datetime.now(timezone.utc),
        raw_content="""
{{Metadata
| סוג מסמך = מדריך
| קהל יעד = כלל העובדים
}}
תוכן מסמך
""",
    )

    persistence_revision, _ = (
        KnowledgePersistenceMapper
        .revision_to_models(
            revision,
            page=page,
        )
    )

    metadata = (
        persistence_revision.document_metadata
    )

    assert metadata is not None
    assert metadata.access_roles == []


def test_backfill_extracts_access_roles() -> None:
    values = metadata_values(
        """
{{Metadata
| סוג מסמך = נוהל
| הרשאות גישה =
  סניף,
  הנהלה,
  מנהל מערכת
}}
"""
    )

    assert values["access_roles"] == [
        "branch_user",
        "management",
        "administrator",
    ]


def test_backfill_defaults_to_open_access() -> None:
    values = metadata_values(
        """
{{Metadata
| סוג מסמך = מדריך
| קהל יעד = נציגים
}}
"""
    )

    assert values["access_roles"] == []
