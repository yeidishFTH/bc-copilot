from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr

from app.cli import evaluate_copilot_retrieval
from app.cli.evaluate_copilot_retrieval import (
    build_argument_parser,
    run_evaluation,
)
from app.core.config import Settings


def test_parser_accepts_retrieval_mode() -> None:
    arguments = build_argument_parser().parse_args(
        [
            "--retrieval-mode",
            "hybrid",
        ]
    )

    assert arguments.retrieval_mode == "hybrid"


def test_parser_defaults_to_configured_mode() -> None:
    arguments = build_argument_parser().parse_args([])

    assert arguments.retrieval_mode is None


@pytest.mark.parametrize(
    "mode",
    [
        "lexical",
        "semantic",
        "hybrid",
    ],
)
def test_parser_accepts_supported_modes(
    mode: str,
) -> None:
    arguments = build_argument_parser().parse_args(
        [
            "--retrieval-mode",
            mode,
        ]
    )

    assert arguments.retrieval_mode == mode


def test_parser_rejects_invalid_mode() -> None:
    with pytest.raises(SystemExit):
        build_argument_parser().parse_args(
            [
                "--retrieval-mode",
                "invalid",
            ]
        )


@pytest.mark.asyncio
async def test_run_evaluation_uses_selected_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    dataset = tmp_path / "questions.json"
    dataset.write_text(
        """
[
  {
    "id": "q1",
    "question": "איך מוחקים כרטיס לקוח?",
    "expected_titles": [
      "נוהל מחיקת כרטיס לקוח"
    ],
    "preferred_title": "נוהל מחיקת כרטיס לקוח"
  }
]
""".strip(),
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    class FakeRetriever:
        async def search(
            self,
            query: str,
            *,
            limit: int = 10,
            namespace_ids: object = None,
        ) -> tuple[object, ...]:
            del query, limit, namespace_ids
            return ()

    class FakeMultiQuery:
        def __init__(
            self,
            retrieval: object,
        ) -> None:
            captured["retrieval"] = retrieval

        async def search(
            self,
            question: str,
            **_: Any,
        ) -> object:
            del question

            return type(
                "Result",
                (),
                {
                    "results": (),
                    "executed_queries": (),
                    "raw_result_count": 0,
                    "unique_result_count": 0,
                },
            )()

    def fake_factory(**kwargs: Any) -> FakeRetriever:
        captured.update(kwargs)
        return FakeRetriever()

    class FakeSessionContext:
        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(
            self,
            *_: object,
        ) -> None:
            return None

    monkeypatch.setattr(
        evaluate_copilot_retrieval,
        "AsyncSessionFactory",
        lambda: FakeSessionContext(),
    )
    monkeypatch.setattr(
        evaluate_copilot_retrieval,
        "build_knowledge_retriever",
        fake_factory,
    )
    monkeypatch.setattr(
        evaluate_copilot_retrieval,
        "MultiQueryRetrievalService",
        FakeMultiQuery,
    )

    summary = await run_evaluation(
        dataset_path=dataset,
        limit=5,
        per_query_limit=10,
        max_queries=3,
        namespace_ids=(0,),
        retrieval_mode="hybrid",
        settings=Settings(
            _env_file=None,
            openai_api_key=SecretStr(
                "test-key"
            ),
        ),
    )

    assert summary.retrieval_mode == "hybrid"
    assert (
        captured["settings"]
        .copilot_retrieval_mode
        == "hybrid"
    )
    assert captured["api_key"] == "test-key"


@pytest.mark.asyncio
async def test_async_main_forwards_retrieval_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    report_path = tmp_path / "report.json"

    class ParsedArguments:
        dataset = tmp_path / "questions.json"
        limit = 5
        per_query_limit = 10
        max_queries = 3
        namespace_ids = [0]
        report = report_path
        fail_below_top3 = None
        retrieval_mode = "hybrid"

    ParsedArguments.dataset.write_text(
        "[]",
        encoding="utf-8",
    )

    class FakeParser:
        def parse_args(self) -> ParsedArguments:
            return ParsedArguments()

    async def fake_run_evaluation(
        **kwargs: Any,
    ) -> object:
        captured.update(kwargs)

        return type(
            "Summary",
            (),
            {
                "retrieval_mode": "hybrid",
                "top_1_accuracy": 100.0,
                "top_3_accuracy": 100.0,
                "top_5_accuracy": 100.0,
                "preferred_top_1_accuracy": 100.0,
                "average_latency_ms": 1.0,
                "median_latency_ms": 1.0,
                "maximum_latency_ms": 1.0,
                "question_count": 0,
                "evaluations": (),
            },
        )()

    monkeypatch.setattr(
        evaluate_copilot_retrieval,
        "build_argument_parser",
        lambda: FakeParser(),
    )
    monkeypatch.setattr(
        evaluate_copilot_retrieval,
        "run_evaluation",
        fake_run_evaluation,
    )
    monkeypatch.setattr(
        evaluate_copilot_retrieval,
        "save_report",
        lambda *_: report_path,
    )
    monkeypatch.setattr(
        evaluate_copilot_retrieval,
        "print_console_report",
        lambda _: None,
    )

    exit_code = (
        await evaluate_copilot_retrieval.async_main()
    )

    assert exit_code == 0
    assert captured["retrieval_mode"] == "hybrid"
    assert captured["dataset_path"] == (
        ParsedArguments.dataset
    )
    assert captured["namespace_ids"] == (0,)
