from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.services.knowledge import (
    EmbeddingGenerator,
    OpenAIEmbeddingGenerator,
)
from app.services.openai import (
    OpenAIConfigurationError,
    OpenAIResponseError,
)


def make_vector(
    dimensions: int,
    *,
    offset: float = 0.0,
) -> list[float]:
    return [
        offset + (index / max(dimensions, 1))
        for index in range(dimensions)
    ]


def test_generator_implements_embedding_protocol() -> None:
    generator = OpenAIEmbeddingGenerator(
        api_key="test-key",
        dimensions=4,
    )

    assert isinstance(generator, EmbeddingGenerator)


def test_generator_exposes_configuration() -> None:
    generator = OpenAIEmbeddingGenerator(
        api_key="test-key",
        model="embedding-test",
        dimensions=8,
        max_batch_size=3,
    )

    assert generator.model_id == "embedding-test"
    assert generator.dimensions == 8
    assert generator.max_batch_size == 3


@pytest.mark.asyncio
async def test_generate_calls_embeddings_api() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/embeddings"
        assert request.headers["Authorization"] == (
            "Bearer test-key"
        )

        payload = json.loads(request.content)

        assert payload == {
            "model": "embedding-test",
            "input": [
                "מחיקת כרטיס לקוח",
                "פתיחת סניף",
            ],
            "dimensions": 4,
            "encoding_format": "float",
        }

        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [
                    {
                        "object": "embedding",
                        "index": 0,
                        "embedding": make_vector(
                            4,
                            offset=0.1,
                        ),
                    },
                    {
                        "object": "embedding",
                        "index": 1,
                        "embedding": make_vector(
                            4,
                            offset=0.2,
                        ),
                    },
                ],
                "model": "embedding-test",
            },
        )

    generator = OpenAIEmbeddingGenerator(
        api_key="test-key",
        model="embedding-test",
        dimensions=4,
        transport=httpx.MockTransport(handler),
    )

    vectors = await generator.generate(
        (
            "  מחיקת   כרטיס לקוח  ",
            "פתיחת סניף",
        )
    )

    assert len(vectors) == 2
    assert vectors[0].dimensions == 4
    assert vectors[1].dimensions == 4
    assert vectors[0] != vectors[1]


@pytest.mark.asyncio
async def test_generate_restores_order_using_indexes() -> None:
    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "index": 1,
                        "embedding": [
                            0.9,
                            0.8,
                        ],
                    },
                    {
                        "index": 0,
                        "embedding": [
                            0.1,
                            0.2,
                        ],
                    },
                ]
            },
        )

    generator = OpenAIEmbeddingGenerator(
        api_key="test-key",
        dimensions=2,
        transport=httpx.MockTransport(handler),
    )

    vectors = await generator.generate(
        ("first", "second")
    )

    assert vectors[0].values == (0.1, 0.2)
    assert vectors[1].values == (0.9, 0.8)


@pytest.mark.asyncio
async def test_generate_splits_large_input_into_batches() -> None:
    requests: list[list[str]] = []

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        payload = json.loads(request.content)
        inputs = payload["input"]
        requests.append(inputs)

        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "index": index,
                        "embedding": [
                            float(index),
                            float(len(text)),
                        ],
                    }
                    for index, text in enumerate(inputs)
                ]
            },
        )

    generator = OpenAIEmbeddingGenerator(
        api_key="test-key",
        dimensions=2,
        max_batch_size=2,
        transport=httpx.MockTransport(handler),
    )

    vectors = await generator.generate(
        (
            "one",
            "two",
            "three",
            "four",
            "five",
        )
    )

    assert requests == [
        ["one", "two"],
        ["three", "four"],
        ["five"],
    ]
    assert len(vectors) == 5


@pytest.mark.asyncio
async def test_generate_accepts_empty_batch() -> None:
    generator = OpenAIEmbeddingGenerator(
        api_key="test-key",
        dimensions=2,
    )

    assert await generator.generate(()) == ()


@pytest.mark.parametrize(
    "texts",
    [
        "single text",
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
    generator = OpenAIEmbeddingGenerator(
        api_key="test-key",
        dimensions=2,
    )

    with pytest.raises(ValueError):
        await generator.generate(texts)


@pytest.mark.asyncio
async def test_generate_rejects_missing_data() -> None:
    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={},
        )

    generator = OpenAIEmbeddingGenerator(
        api_key="test-key",
        dimensions=2,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        OpenAIResponseError,
        match="no data array",
    ):
        await generator.generate(("text",))


@pytest.mark.asyncio
async def test_generate_rejects_wrong_dimensions() -> None:
    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "index": 0,
                        "embedding": [0.1],
                    }
                ]
            },
        )

    generator = OpenAIEmbeddingGenerator(
        api_key="test-key",
        dimensions=2,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        OpenAIResponseError,
        match="unexpected dimensions",
    ):
        await generator.generate(("text",))


@pytest.mark.asyncio
async def test_generate_rejects_duplicate_index() -> None:
    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "index": 0,
                        "embedding": [0.1, 0.2],
                    },
                    {
                        "index": 0,
                        "embedding": [0.3, 0.4],
                    },
                ]
            },
        )

    generator = OpenAIEmbeddingGenerator(
        api_key="test-key",
        dimensions=2,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        OpenAIResponseError,
        match="duplicate index",
    ):
        await generator.generate(
            ("first", "second")
        )


@pytest.mark.asyncio
async def test_generate_rejects_missing_index() -> None:
    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "index": 0,
                        "embedding": [0.1, 0.2],
                    }
                ]
            },
        )

    generator = OpenAIEmbeddingGenerator(
        api_key="test-key",
        dimensions=2,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        OpenAIResponseError,
        match="missing indexes: 1",
    ):
        await generator.generate(
            ("first", "second")
        )


@pytest.mark.asyncio
async def test_generate_preserves_http_error() -> None:
    async def handler(
        _: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            429,
            json={
                "error": {
                    "message": "Rate limit reached",
                }
            },
        )

    generator = OpenAIEmbeddingGenerator(
        api_key="test-key",
        dimensions=2,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(
        OpenAIResponseError,
        match="HTTP 429: Rate limit reached",
    ):
        await generator.generate(("text",))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"api_key": "test", "model": ""},
            "model",
        ),
        (
            {
                "api_key": "test",
                "dimensions": 0,
            },
            "dimensions",
        ),
        (
            {
                "api_key": "test",
                "dimensions": True,
            },
            "dimensions",
        ),
        (
            {
                "api_key": "test",
                "max_batch_size": 0,
            },
            "batch size",
        ),
        (
            {
                "api_key": "test",
                "max_batch_size": True,
            },
            "batch size",
        ),
    ],
)
def test_generator_rejects_invalid_configuration(
    kwargs: dict[str, Any],
    message: str,
) -> None:
    with pytest.raises(
        OpenAIConfigurationError,
        match=message,
    ):
        OpenAIEmbeddingGenerator(**kwargs)
