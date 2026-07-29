from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from app.services.knowledge.embeddings import (
    EmbeddingVector,
)
from app.services.openai import (
    OpenAIClientBase,
    OpenAIConfigurationError,
    OpenAIResponseError,
)


class OpenAIEmbeddingGenerator(OpenAIClientBase):
    """
    Generate dense vectors through the OpenAI Embeddings API.

    The generator preserves input order, validates response indexes,
    verifies the configured vector dimensions, and exposes only
    provider-neutral EmbeddingVector values to the rest of the system.
    """

    EMBEDDINGS_PATH = "/v1/embeddings"
    DEFAULT_MODEL = "text-embedding-3-small"
    DEFAULT_DIMENSIONS = 1536
    DEFAULT_MAX_BATCH_SIZE = 100

    MIN_DIMENSIONS = 1
    MAX_DIMENSIONS = 4096
    MIN_BATCH_SIZE = 1
    MAX_BATCH_SIZE = 2048

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_MODEL,
        dimensions: int = DEFAULT_DIMENSIONS,
        max_batch_size: int = DEFAULT_MAX_BATCH_SIZE,
        timeout_seconds: float = 60.0,
        base_url: str = OpenAIClientBase.DEFAULT_BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            base_url=base_url,
            transport=transport,
        )

        self._model = self._validate_model(model)
        self._dimensions = self._validate_dimensions(
            dimensions
        )
        self._max_batch_size = self._validate_batch_size(
            max_batch_size
        )

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    @property
    def max_batch_size(self) -> int:
        return self._max_batch_size

    async def generate(
        self,
        texts: Sequence[str],
    ) -> tuple[EmbeddingVector, ...]:
        normalized_texts = self._validate_texts(texts)

        if not normalized_texts:
            return ()

        generated: list[EmbeddingVector] = []

        for start in range(
            0,
            len(normalized_texts),
            self._max_batch_size,
        ):
            batch = normalized_texts[
                start : start + self._max_batch_size
            ]

            generated.extend(
                await self._generate_batch(batch)
            )

        return tuple(generated)

    async def _generate_batch(
        self,
        texts: tuple[str, ...],
    ) -> tuple[EmbeddingVector, ...]:
        payload = await self._post_json(
            self.EMBEDDINGS_PATH,
            body={
                "model": self._model,
                "input": list(texts),
                "dimensions": self._dimensions,
                "encoding_format": "float",
            },
            timeout_message=(
                "OpenAI embedding request timed out"
            ),
            connection_message=(
                "OpenAI embedding service could not be reached"
            ),
        )

        return self._extract_embeddings(
            payload,
            expected_count=len(texts),
        )

    def _extract_embeddings(
        self,
        payload: Mapping[str, Any],
        *,
        expected_count: int,
    ) -> tuple[EmbeddingVector, ...]:
        data = payload.get("data")

        if not isinstance(data, list):
            raise OpenAIResponseError(
                "OpenAI embedding response contains no data array"
            )

        indexed_vectors: dict[int, EmbeddingVector] = {}

        for item in data:
            if not isinstance(item, Mapping):
                raise OpenAIResponseError(
                    "OpenAI embedding response contains an invalid item"
                )

            index = item.get("index")

            if (
                isinstance(index, bool)
                or not isinstance(index, int)
            ):
                raise OpenAIResponseError(
                    "OpenAI embedding response contains an invalid index"
                )

            if index < 0 or index >= expected_count:
                raise OpenAIResponseError(
                    "OpenAI embedding response contains an "
                    "out-of-range index"
                )

            if index in indexed_vectors:
                raise OpenAIResponseError(
                    "OpenAI embedding response contains a "
                    "duplicate index"
                )

            raw_embedding = item.get("embedding")

            if not isinstance(raw_embedding, list):
                raise OpenAIResponseError(
                    "OpenAI embedding response contains no vector"
                )

            try:
                values = tuple(
                    float(value)
                    for value in raw_embedding
                )
            except (TypeError, ValueError) as error:
                raise OpenAIResponseError(
                    "OpenAI embedding response contains "
                    "non-numeric values"
                ) from error

            if len(values) != self._dimensions:
                raise OpenAIResponseError(
                    "OpenAI embedding response has unexpected "
                    f"dimensions: expected {self._dimensions}, "
                    f"received {len(values)}"
                )

            try:
                vector = EmbeddingVector(values)
            except ValueError as error:
                raise OpenAIResponseError(
                    "OpenAI embedding response contains "
                    "an invalid vector"
                ) from error

            indexed_vectors[index] = vector

        expected_indexes = set(range(expected_count))

        if set(indexed_vectors) != expected_indexes:
            missing = sorted(
                expected_indexes - set(indexed_vectors)
            )

            raise OpenAIResponseError(
                "OpenAI embedding response is missing "
                f"indexes: {', '.join(str(index) for index in missing)}"
            )

        return tuple(
            indexed_vectors[index]
            for index in range(expected_count)
        )

    @staticmethod
    def _validate_model(model: str) -> str:
        if not isinstance(model, str):
            raise OpenAIConfigurationError(
                "OpenAI embedding model must be a string"
            )

        normalized = model.strip()

        if not normalized:
            raise OpenAIConfigurationError(
                "OpenAI embedding model cannot be empty"
            )

        return normalized

    @classmethod
    def _validate_dimensions(
        cls,
        dimensions: int,
    ) -> int:
        if (
            isinstance(dimensions, bool)
            or not isinstance(dimensions, int)
        ):
            raise OpenAIConfigurationError(
                "OpenAI embedding dimensions must be an integer"
            )

        if not (
            cls.MIN_DIMENSIONS
            <= dimensions
            <= cls.MAX_DIMENSIONS
        ):
            raise OpenAIConfigurationError(
                "OpenAI embedding dimensions must be between "
                f"{cls.MIN_DIMENSIONS} and "
                f"{cls.MAX_DIMENSIONS}"
            )

        return dimensions

    @classmethod
    def _validate_batch_size(
        cls,
        max_batch_size: int,
    ) -> int:
        if (
            isinstance(max_batch_size, bool)
            or not isinstance(max_batch_size, int)
        ):
            raise OpenAIConfigurationError(
                "OpenAI embedding batch size must be an integer"
            )

        if not (
            cls.MIN_BATCH_SIZE
            <= max_batch_size
            <= cls.MAX_BATCH_SIZE
        ):
            raise OpenAIConfigurationError(
                "OpenAI embedding batch size must be between "
                f"{cls.MIN_BATCH_SIZE} and "
                f"{cls.MAX_BATCH_SIZE}"
            )

        return max_batch_size

    @staticmethod
    def _validate_texts(
        texts: Sequence[str],
    ) -> tuple[str, ...]:
        if isinstance(texts, (str, bytes)):
            raise ValueError(
                "texts must be a sequence of strings"
            )

        normalized: list[str] = []

        for text in texts:
            if not isinstance(text, str):
                raise ValueError(
                    "texts must contain only strings"
                )

            cleaned = " ".join(text.split())

            if not cleaned:
                raise ValueError(
                    "embedding text cannot be empty"
                )

            normalized.append(cleaned)

        return tuple(normalized)
