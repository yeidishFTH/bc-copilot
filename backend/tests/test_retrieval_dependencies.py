from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from app.api import dependencies
from app.core.config import Settings
from app.services.knowledge.models import (
    KnowledgeSearchResult,
)
from app.services.knowledge.retrieval import (
    RetrievalConfigurationError,
)


class FakeSession:
    pass


class FakeRetriever:
    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        namespace_ids: Sequence[int] | None = None,
    ) -> tuple[KnowledgeSearchResult, ...]:
        del query, limit, namespace_ids
        return ()


def settings(
    *,
    mode: str = "lexical",
    api_key: str | None = "test-key",
) -> Settings:
    return Settings(
        copilot_retrieval_mode=mode,
        openai_api_key=(
            SecretStr(api_key)
            if api_key is not None
            else None
        ),
    )


def test_retrieval_dependency_uses_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retriever = FakeRetriever()
    captured: dict[str, Any] = {}

    def fake_factory(**kwargs: Any) -> FakeRetriever:
        captured.update(kwargs)
        return retriever

    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: settings(mode="hybrid"),
    )
    monkeypatch.setattr(
        dependencies,
        "build_knowledge_retriever",
        fake_factory,
    )

    session = FakeSession()

    result = (
        dependencies
        .get_knowledge_retrieval_service(
            session=session  # type: ignore[arg-type]
        )
    )

    assert result is retriever
    assert captured["session"] is session
    assert (
        captured["settings"]
        .copilot_retrieval_mode
        == "hybrid"
    )
    assert captured["api_key"] == "test-key"


def test_copilot_dependency_uses_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retriever = FakeRetriever()
    captured: dict[str, Any] = {}

    def fake_factory(**kwargs: Any) -> FakeRetriever:
        captured.update(kwargs)
        return retriever

    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: settings(mode="hybrid"),
    )
    monkeypatch.setattr(
        dependencies,
        "build_knowledge_retriever",
        fake_factory,
    )

    session = FakeSession()

    service = dependencies.get_copilot_answer_service(
        session=session  # type: ignore[arg-type]
    )

    assert service is not None
    assert captured["session"] is session
    assert captured["api_key"] == "test-key"
    assert (
        captured["settings"]
        .copilot_retrieval_mode
        == "hybrid"
    )


def test_retrieval_configuration_error_becomes_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        dependencies,
        "get_settings",
        lambda: settings(mode="hybrid"),
    )

    def failing_factory(**_: Any) -> None:
        raise RetrievalConfigurationError(
            "hybrid retrieval is unavailable"
        )

    monkeypatch.setattr(
        dependencies,
        "build_knowledge_retriever",
        failing_factory,
    )

    with pytest.raises(HTTPException) as error:
        dependencies.get_knowledge_retrieval_service(
            session=FakeSession()  # type: ignore[arg-type]
        )

    assert error.value.status_code == 503
    assert (
        error.value.detail
        == "hybrid retrieval is unavailable"
    )
