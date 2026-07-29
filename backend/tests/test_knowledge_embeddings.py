from __future__ import annotations

import math
from typing import Any

import pytest

from app.services.knowledge import (
    DeterministicEmbeddingGenerator,
    EmbeddingGenerator,
    EmbeddingVector,
)


def test_generator_implements_protocol() -> None:
    generator = DeterministicEmbeddingGenerator()

    assert isinstance(generator, EmbeddingGenerator)


def test_embedding_vector_exposes_dimensions() -> None:
    vector = EmbeddingVector(
        values=(0.1, 0.2, 0.3),
    )

    assert vector.dimensions == 3


@pytest.mark.parametrize(
    "values",
    [
        (),
        (float("nan"),),
        (float("inf"),),
        (True,),
        ("0.5",),
    ],
)
def test_embedding_vector_rejects_invalid_values(
    values: tuple[Any, ...],
) -> None:
    with pytest.raises(ValueError, match="embedding"):
        EmbeddingVector(
            values=values,  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_generate_preserves_input_order() -> None:
    generator = DeterministicEmbeddingGenerator(
        dimensions=8
    )

    results = await generator.generate(
        (
            "מחיקת כרטיס לקוח",
            "פתיחת סניף",
        )
    )

    assert len(results) == 2
    assert all(
        result.dimensions == 8
        for result in results
    )
    assert results[0] != results[1]


@pytest.mark.asyncio
async def test_generate_is_deterministic() -> None:
    generator = DeterministicEmbeddingGenerator(
        dimensions=12
    )

    first = await generator.generate(
        ("זיהוי ואימות לקוח",)
    )
    second = await generator.generate(
        ("זיהוי ואימות לקוח",)
    )

    assert first == second


@pytest.mark.asyncio
async def test_generate_normalizes_whitespace() -> None:
    generator = DeterministicEmbeddingGenerator(
        dimensions=8
    )

    first = await generator.generate(
        ("  ספירת   מזומן  ",)
    )
    second = await generator.generate(
        ("ספירת מזומן",)
    )

    assert first == second


@pytest.mark.asyncio
async def test_generated_vectors_are_unit_normalized() -> None:
    generator = DeterministicEmbeddingGenerator(
        dimensions=32
    )

    result = (
        await generator.generate(
            ("נוהל פתיחת סניף",)
        )
    )[0]

    magnitude = math.sqrt(
        sum(
            value * value
            for value in result.values
        )
    )

    assert magnitude == pytest.approx(
        1.0,
        abs=1e-12,
    )


@pytest.mark.asyncio
async def test_generate_accepts_empty_batch() -> None:
    generator = DeterministicEmbeddingGenerator()

    assert await generator.generate(()) == ()


@pytest.mark.parametrize(
    "texts",
    [
        "טקסט יחיד",
        b"bytes",
        ("",),
        ("   ",),
        (123,),
    ],
)
@pytest.mark.asyncio
async def test_generate_rejects_invalid_texts(
    texts: Any,
) -> None:
    generator = DeterministicEmbeddingGenerator()

    with pytest.raises(ValueError):
        await generator.generate(texts)


@pytest.mark.parametrize(
    "dimensions",
    [
        0,
        1,
        4097,
        True,
        8.5,
    ],
)
def test_generator_rejects_invalid_dimensions(
    dimensions: Any,
) -> None:
    with pytest.raises(
        ValueError,
        match="dimensions",
    ):
        DeterministicEmbeddingGenerator(
            dimensions=dimensions,
        )


def test_generator_exposes_stable_metadata() -> None:
    generator = DeterministicEmbeddingGenerator(
        dimensions=24
    )

    assert generator.dimensions == 24
    assert generator.model_id == (
        "deterministic-sha256-development-v1"
    )
