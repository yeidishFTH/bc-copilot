from __future__ import annotations

import hashlib
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class EmbeddingVector:
    """
    One validated dense vector produced for a knowledge text.

    Persistence details are deliberately excluded. The same value object
    can later be stored in PostgreSQL, another vector database, or used
    directly by an in-memory retrieval implementation.
    """

    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError(
                "embedding vector cannot be empty"
            )

        for value in self.values:
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
            ):
                raise ValueError(
                    "embedding values must be numeric"
                )

            if not math.isfinite(float(value)):
                raise ValueError(
                    "embedding values must be finite"
                )

    @property
    def dimensions(self) -> int:
        """Return the number of vector dimensions."""

        return len(self.values)


@runtime_checkable
class EmbeddingGenerator(Protocol):
    """
    Provider-neutral asynchronous embedding interface.

    Implementations may use OpenAI, a local model, or another service.
    Consumers must not depend on provider-specific response objects.
    """

    @property
    def model_id(self) -> str:
        """Return a stable identifier for the active model."""

        ...

    @property
    def dimensions(self) -> int:
        """Return the exact output vector size."""

        ...

    async def generate(
        self,
        texts: Sequence[str],
    ) -> tuple[EmbeddingVector, ...]:
        """
        Generate one embedding for every input while preserving order.
        """

        ...


class DeterministicEmbeddingGenerator:
    """
    Dependency-free deterministic generator for tests and development.

    This implementation does not provide semantic embeddings and must not
    be used as the production retrieval model. It exists so the embedding
    pipeline can be developed and tested before an external model is chosen.
    """

    DEFAULT_DIMENSIONS = 16
    MIN_DIMENSIONS = 2
    MAX_DIMENSIONS = 4096
    MODEL_ID = "deterministic-sha256-development-v1"

    def __init__(
        self,
        *,
        dimensions: int = DEFAULT_DIMENSIONS,
    ) -> None:
        self._dimensions = self._validate_dimensions(
            dimensions
        )

    @property
    def model_id(self) -> str:
        return self.MODEL_ID

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def generate(
        self,
        texts: Sequence[str],
    ) -> tuple[EmbeddingVector, ...]:
        normalized_texts = self._validate_texts(texts)

        return tuple(
            self._generate_one(text)
            for text in normalized_texts
        )

    def _generate_one(
        self,
        text: str,
    ) -> EmbeddingVector:
        raw_values: list[float] = []
        counter = 0

        while len(raw_values) < self._dimensions:
            digest = hashlib.sha256(
                f"{counter}:{text}".encode("utf-8")
            ).digest()

            for byte in digest:
                raw_values.append(
                    (float(byte) / 127.5) - 1.0
                )

                if len(raw_values) >= self._dimensions:
                    break

            counter += 1

        magnitude = math.sqrt(
            sum(value * value for value in raw_values)
        )

        if magnitude == 0.0:
            normalized = tuple(
                0.0 for _ in raw_values
            )
        else:
            normalized = tuple(
                value / magnitude
                for value in raw_values
            )

        return EmbeddingVector(normalized)

    @classmethod
    def _validate_dimensions(
        cls,
        dimensions: int,
    ) -> int:
        if (
            isinstance(dimensions, bool)
            or not isinstance(dimensions, int)
        ):
            raise ValueError(
                "dimensions must be an integer"
            )

        if not (
            cls.MIN_DIMENSIONS
            <= dimensions
            <= cls.MAX_DIMENSIONS
        ):
            raise ValueError(
                "dimensions must be between "
                f"{cls.MIN_DIMENSIONS} and "
                f"{cls.MAX_DIMENSIONS}"
            )

        return dimensions

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
