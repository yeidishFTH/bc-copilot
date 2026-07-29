from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.knowledge.retrieval import (
    HybridRetrievalService,
    KnowledgeRetrievalService,
    RetrievalConfigurationError,
    SemanticRetrievalService,
    build_knowledge_retriever,
)


class FakeSession:
    pass


def make_settings(
    *,
    mode: str = "lexical",
) -> Settings:
    return Settings(
        copilot_retrieval_mode=mode,
        openai_embedding_model=(
            "text-embedding-3-small"
        ),
        openai_embedding_dimensions=1536,
        openai_embedding_batch_size=100,
    )


def test_default_retrieval_mode_is_lexical() -> None:
    settings = Settings()

    assert (
        settings.copilot_retrieval_mode
        == "lexical"
    )


def test_builds_lexical_without_api_key() -> None:
    retriever = build_knowledge_retriever(
        session=FakeSession(),  # type: ignore[arg-type]
        settings=make_settings(
            mode="lexical"
        ),
        api_key=None,
    )

    assert isinstance(
        retriever,
        KnowledgeRetrievalService,
    )


def test_builds_semantic_retrieval() -> None:
    retriever = build_knowledge_retriever(
        session=FakeSession(),  # type: ignore[arg-type]
        settings=make_settings(
            mode="semantic"
        ),
        api_key="test-key",
    )

    assert isinstance(
        retriever,
        SemanticRetrievalService,
    )


def test_builds_hybrid_retrieval() -> None:
    retriever = build_knowledge_retriever(
        session=FakeSession(),  # type: ignore[arg-type]
        settings=make_settings(
            mode="hybrid"
        ),
        api_key="test-key",
    )

    assert isinstance(
        retriever,
        HybridRetrievalService,
    )


@pytest.mark.parametrize(
    "mode",
    [
        "semantic",
        "hybrid",
    ],
)
@pytest.mark.parametrize(
    "api_key",
    [
        None,
        "",
        "   ",
    ],
)
def test_embedding_modes_require_api_key(
    mode: str,
    api_key: str | None,
) -> None:
    with pytest.raises(
        RetrievalConfigurationError,
        match="OPENAI_API_KEY",
    ):
        build_knowledge_retriever(
            session=FakeSession(),  # type: ignore[arg-type]
            settings=make_settings(mode=mode),
            api_key=api_key,
        )


@pytest.mark.parametrize(
    "mode",
    [
        "vector",
        "fulltext",
        "",
    ],
)
def test_invalid_mode_is_rejected_by_settings(
    mode: str,
) -> None:
    with pytest.raises(ValidationError):
        Settings(
            copilot_retrieval_mode=mode,
        )


def test_lexical_mode_does_not_build_embeddings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden_generator(
        **_: Any,
    ) -> None:
        raise AssertionError(
            "embedding generator should not be built"
        )

    monkeypatch.setattr(
        (
            "app.services.knowledge.retrieval."
            "factory.OpenAIEmbeddingGenerator"
        ),
        forbidden_generator,
    )

    retriever = build_knowledge_retriever(
        session=FakeSession(),  # type: ignore[arg-type]
        settings=make_settings(
            mode="lexical"
        ),
    )

    assert isinstance(
        retriever,
        KnowledgeRetrievalService,
    )
