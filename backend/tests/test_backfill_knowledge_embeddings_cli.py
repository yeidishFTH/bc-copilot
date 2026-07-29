from __future__ import annotations

from pydantic import SecretStr
import pytest

from app.cli.backfill_knowledge_embeddings import (
    DryRunEmbeddingGenerator,
    build_parser,
    require_openai_api_key,
    result_payload,
    validate_embedding_settings,
)
from app.core.config import Settings
from app.services.knowledge.embedding_backfill import (
    EmbeddingBackfillResult,
)


def make_settings(
    *,
    api_key: str | None = "test-key",
    model: str = "text-embedding-3-small",
    dimensions: int = 1536,
    batch_size: int = 100,
) -> Settings:
    return Settings(
        openai_api_key=(
            SecretStr(api_key)
            if api_key is not None
            else None
        ),
        openai_embedding_model=model,
        openai_embedding_dimensions=dimensions,
        openai_embedding_batch_size=batch_size,
    )


def test_parser_accepts_dry_run_arguments() -> None:
    arguments = build_parser().parse_args(
        [
            "--dry-run",
            "--limit",
            "5",
            "--batch-size",
            "2",
        ]
    )

    assert arguments.dry_run is True
    assert arguments.limit == 5
    assert arguments.batch_size == 2


def test_parser_defaults_are_safe() -> None:
    arguments = build_parser().parse_args([])

    assert arguments.dry_run is False
    assert arguments.limit is None
    assert arguments.batch_size is None


def test_api_key_is_loaded() -> None:
    assert require_openai_api_key(
        make_settings()
    ) == "test-key"


@pytest.mark.parametrize(
    "api_key",
    [
        None,
        "",
        "   ",
    ],
)
def test_missing_api_key_is_rejected(
    api_key: str | None,
) -> None:
    with pytest.raises(
        RuntimeError,
        match="OPENAI_API_KEY",
    ):
        require_openai_api_key(
            make_settings(api_key=api_key)
        )


def test_embedding_settings_are_validated() -> None:
    validate_embedding_settings(
        make_settings()
    )


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        (
            make_settings(model=""),
            "MODEL",
        ),
        (
            make_settings(dimensions=768),
            "DIMENSIONS",
        ),
        (
            make_settings(batch_size=0),
            "BATCH_SIZE",
        ),
        (
            make_settings(batch_size=501),
            "BATCH_SIZE",
        ),
    ],
)
def test_invalid_embedding_settings_are_rejected(
    settings: Settings,
    message: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=message,
    ):
        validate_embedding_settings(settings)


def test_result_payload_is_json_ready() -> None:
    result = EmbeddingBackfillResult(
        dry_run=False,
        processed=5,
        stored=5,
        batches=1,
        remaining_limit=0,
    )

    payload = result_payload(
        result,
        model_id="embedding-test",
        dimensions=1536,
        batch_size=5,
    )

    assert payload == {
        "status": "succeeded",
        "dry_run": False,
        "model": "embedding-test",
        "dimensions": 1536,
        "batch_size": 5,
        "processed": 5,
        "stored": 5,
        "batches": 1,
        "remaining_limit": 0,
    }


@pytest.mark.asyncio
async def test_dry_run_generator_must_not_be_called() -> None:
    generator = DryRunEmbeddingGenerator()

    with pytest.raises(
        RuntimeError,
        match="dry-run",
    ):
        await generator.generate(("text",))
