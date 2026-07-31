from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import workspace_dependencies
from app.db.models import AccountRole
from app.services.knowledge.retrieval import (
    HybridRetrievalService,
    KnowledgeRetrievalService,
)


class FakeSession:
    pass


def make_account(
    role: AccountRole,
):
    return SimpleNamespace(
        role=role,
        must_change_password=False,
        is_active=True,
    )


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        (
            AccountRole.branch_user,
            "branch_user",
        ),
        (
            AccountRole.management,
            "management",
        ),
        (
            AccountRole.administrator,
            "administrator",
        ),
    ],
)
def test_account_access_role_normalizes_enum(
    role: AccountRole,
    expected: str,
) -> None:
    assert (
        workspace_dependencies
        ._account_access_role(
            make_account(role)
        )
        == expected
    )


def test_invalid_account_role_is_rejected() -> None:
    account = SimpleNamespace(
        role="unknown",
    )

    with pytest.raises(
        HTTPException,
        match="Account role is invalid",
    ):
        workspace_dependencies._account_access_role(
            account
        )


def test_authorized_knowledge_dependency_scopes_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_builder(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(
        workspace_dependencies,
        "build_knowledge_retriever",
        fake_builder,
    )

    result = (
        workspace_dependencies
        .get_authorized_knowledge_retrieval_service(
            account=make_account(
                AccountRole.management
            ),
            session=FakeSession(),  # type: ignore[arg-type]
        )
    )

    assert result is not None
    assert captured["access_role"] == "management"


def test_real_lexical_dependency_scopes_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = (
        workspace_dependencies
        .get_settings()
    )

    monkeypatch.setattr(
        settings,
        "copilot_retrieval_mode",
        "lexical",
    )

    retriever = (
        workspace_dependencies
        .get_authorized_knowledge_retrieval_service(
            account=make_account(
                AccountRole.branch_user
            ),
            session=FakeSession(),  # type: ignore[arg-type]
        )
    )

    assert isinstance(
        retriever,
        KnowledgeRetrievalService,
    )

    assert (
        retriever
        ._search
        ._access_role
        == "branch_user"
    )


def test_real_hybrid_factory_scope_contract() -> None:
    from app.core.config import Settings
    from app.services.knowledge.retrieval import (
        build_knowledge_retriever,
    )

    retriever = build_knowledge_retriever(
        session=FakeSession(),  # type: ignore[arg-type]
        settings=Settings(
            copilot_retrieval_mode="hybrid",
            openai_embedding_dimensions=1536,
        ),
        api_key="test-key",
        access_role="administrator",
    )

    assert isinstance(
        retriever,
        HybridRetrievalService,
    )

    assert (
        retriever
        ._lexical
        ._search
        ._access_role
        == "administrator"
    )

    assert (
        retriever
        ._semantic
        ._search
        ._access_role
        == "administrator"
    )
