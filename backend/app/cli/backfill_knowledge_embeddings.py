from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Sequence

from app.core.config import Settings, get_settings
from app.db.session import (
    AsyncSessionFactory,
    dispose_engine,
)
from app.services.knowledge.embedding_backfill import (
    EmbeddingBackfillResult,
    EmbeddingBackfillService,
)
from app.services.knowledge.embeddings import (
    EmbeddingVector,
)
from app.services.knowledge.openai_embeddings import (
    OpenAIEmbeddingGenerator,
)
from app.services.knowledge.persistence.repositories.embeddings import (
    KnowledgeEmbeddingRepository,
)


class DryRunEmbeddingGenerator:
    """
    Placeholder used only during dry-run execution.

    EmbeddingBackfillService must never invoke this generator when
    dry_run=True. A call therefore indicates a service regression.
    """

    model_id = "dry-run-no-generation"
    dimensions = 1536

    async def generate(
        self,
        texts: Sequence[str],
    ) -> tuple[EmbeddingVector, ...]:
        del texts

        raise RuntimeError(
            "embedding generator was called during dry-run"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate and persist embeddings for knowledge chunks "
            "that do not yet have a vector."
        )
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Inspect pending chunks without generating or "
            "persisting embeddings."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Maximum total number of chunks to process. "
            "Omit to process all pending chunks."
        ),
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help=(
            "Number of chunks committed in each database batch. "
            "Defaults to OPENAI_EMBEDDING_BATCH_SIZE."
        ),
    )

    return parser


def require_openai_api_key(
    settings: Settings,
) -> str:
    secret = settings.openai_api_key

    if secret is None:
        raise RuntimeError(
            "OPENAI_API_KEY is missing from .env"
        )

    api_key = secret.get_secret_value().strip()

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing from .env"
        )

    return api_key


def validate_embedding_settings(
    settings: Settings,
) -> None:
    model = settings.openai_embedding_model

    if not isinstance(model, str) or not model.strip():
        raise ValueError(
            "OPENAI_EMBEDDING_MODEL cannot be empty"
        )

    dimensions = (
        settings.openai_embedding_dimensions
    )

    if dimensions != 1536:
        raise ValueError(
            "OPENAI_EMBEDDING_DIMENSIONS must be 1536 "
            "because knowledge_chunks.embedding is vector(1536)"
        )

    batch_size = (
        settings.openai_embedding_batch_size
    )

    if (
        isinstance(batch_size, bool)
        or not isinstance(batch_size, int)
        or batch_size < 1
        or batch_size
        > EmbeddingBackfillService.MAX_BATCH_SIZE
    ):
        raise ValueError(
            "OPENAI_EMBEDDING_BATCH_SIZE must be between "
            f"1 and {EmbeddingBackfillService.MAX_BATCH_SIZE}"
        )


def result_payload(
    result: EmbeddingBackfillResult,
    *,
    model_id: str,
    dimensions: int,
    batch_size: int,
) -> dict[str, object]:
    return {
        "status": "succeeded",
        "dry_run": result.dry_run,
        "model": model_id,
        "dimensions": dimensions,
        "batch_size": batch_size,
        "processed": result.processed,
        "stored": result.stored,
        "batches": result.batches,
        "remaining_limit": result.remaining_limit,
    }


async def run_backfill(
    *,
    dry_run: bool,
    limit: int | None,
    batch_size: int | None,
    settings: Settings | None = None,
) -> dict[str, object]:
    resolved_settings = settings or get_settings()

    validate_embedding_settings(
        resolved_settings
    )

    resolved_batch_size = (
        resolved_settings.openai_embedding_batch_size
        if batch_size is None
        else batch_size
    )

    if (
        isinstance(resolved_batch_size, bool)
        or not isinstance(resolved_batch_size, int)
        or resolved_batch_size < 1
        or resolved_batch_size
        > EmbeddingBackfillService.MAX_BATCH_SIZE
    ):
        raise ValueError(
            "batch_size must be between "
            f"1 and {EmbeddingBackfillService.MAX_BATCH_SIZE}"
        )

    if limit is not None and (
        isinstance(limit, bool)
        or not isinstance(limit, int)
        or limit < 1
    ):
        raise ValueError(
            "limit must be greater than zero"
        )

    if dry_run:
        generator = DryRunEmbeddingGenerator()
    else:
        generator = OpenAIEmbeddingGenerator(
            api_key=require_openai_api_key(
                resolved_settings
            ),
            model=(
                resolved_settings
                .openai_embedding_model
            ),
            dimensions=(
                resolved_settings
                .openai_embedding_dimensions
            ),
            max_batch_size=(
                resolved_settings
                .openai_embedding_batch_size
            ),
            timeout_seconds=(
                resolved_settings
                .openai_timeout_seconds
            ),
        )

    async with AsyncSessionFactory() as session:
        service = EmbeddingBackfillService(
            repository=KnowledgeEmbeddingRepository(
                session
            ),
            generator=generator,
            session=session,
        )

        result = await service.run(
            batch_size=resolved_batch_size,
            limit=limit,
            dry_run=dry_run,
        )

    return result_payload(
        result,
        model_id=generator.model_id,
        dimensions=generator.dimensions,
        batch_size=resolved_batch_size,
    )


async def async_main() -> int:
    arguments = build_parser().parse_args()

    try:
        payload = await run_backfill(
            dry_run=arguments.dry_run,
            limit=arguments.limit,
            batch_size=arguments.batch_size,
        )
    except (RuntimeError, ValueError) as error:
        payload = {
            "status": "configuration_error",
            "error": str(error),
        }

        print(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            )
        )

        return 1
    except Exception as error:
        payload = {
            "status": "failed",
            "error": str(error),
        }

        print(
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            )
        )

        return 2
    finally:
        await dispose_engine()

    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0


def main() -> None:
    raise SystemExit(
        asyncio.run(async_main())
    )


if __name__ == "__main__":
    main()
