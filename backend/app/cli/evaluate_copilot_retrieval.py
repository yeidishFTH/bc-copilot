from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.db.session import AsyncSessionFactory
from app.services.copilot.multi_query_retrieval import (
    MultiQueryRetrievalService,
)
from app.services.knowledge.retrieval import (
    RetrievalConfigurationError,
    build_knowledge_retriever,
)


DEFAULT_DATASET = Path(
    "evaluation/golden_questions.json"
)
DEFAULT_REPORT_DIRECTORY = Path(
    "evaluation/reports"
)


@dataclass(frozen=True, slots=True)
class GoldenQuestion:
    id: str
    question: str
    expected_titles: tuple[str, ...]
    preferred_title: str | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class RankedResult:
    position: int
    title: str
    heading_path: tuple[str, ...]
    chunk_id: str
    rank: float


@dataclass(frozen=True, slots=True)
class QuestionEvaluation:
    id: str
    question: str
    expected_titles: tuple[str, ...]
    preferred_title: str | None
    top_results: tuple[RankedResult, ...]
    first_expected_position: int | None
    preferred_position: int | None
    top_1_hit: bool
    top_3_hit: bool
    top_5_hit: bool
    preferred_top_1_hit: bool | None
    latency_ms: float
    executed_queries: tuple[str, ...]
    raw_result_count: int
    unique_result_count: int


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    generated_at: str
    dataset_path: str
    retrieval_mode: str
    question_count: int
    top_1_accuracy: float
    top_3_accuracy: float
    top_5_accuracy: float
    preferred_top_1_accuracy: float | None
    average_latency_ms: float
    median_latency_ms: float
    maximum_latency_ms: float
    evaluations: tuple[QuestionEvaluation, ...]


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate intent-aware multi-query retrieval "
            "against a golden question set."
        )
    )

    parser.add_argument(
        "--retrieval-mode",
        choices=(
            "lexical",
            "semantic",
            "hybrid",
        ),
        default=None,
        help=(
            "Retrieval mode to evaluate. Defaults to "
            "COPILOT_RETRIEVAL_MODE."
        ),
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Path to the golden question JSON file.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of final unique results per question.",
    )
    parser.add_argument(
        "--per-query-limit",
        type=int,
        default=20,
        help="Number of results requested for each rewritten query.",
    )
    parser.add_argument(
        "--max-queries",
        type=int,
        default=5,
        help="Maximum rewritten queries executed per question.",
    )
    parser.add_argument(
        "--namespace-id",
        type=int,
        action="append",
        dest="namespace_ids",
        help=(
            "Namespace to search. May be supplied repeatedly. "
            "Defaults to namespace 0."
        ),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional explicit JSON report path.",
    )
    parser.add_argument(
        "--fail-below-top3",
        type=float,
        default=None,
        help=(
            "Exit with failure when Top-3 accuracy is below "
            "this percentage."
        ),
    )

    return parser


def load_golden_questions(
    path: Path,
) -> tuple[GoldenQuestion, ...]:
    if not path.exists():
        raise FileNotFoundError(
            f"Golden question dataset not found: {path}"
        )

    raw_data = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(raw_data, list):
        raise ValueError(
            "Golden question dataset must contain a JSON list"
        )

    questions: list[GoldenQuestion] = []
    seen_ids: set[str] = set()

    for index, raw_item in enumerate(raw_data, start=1):
        if not isinstance(raw_item, dict):
            raise ValueError(
                f"Dataset item {index} must be an object"
            )

        question_id = normalize_required_string(
            raw_item.get("id"),
            field_name=f"item {index}.id",
        )
        question = normalize_required_string(
            raw_item.get("question"),
            field_name=f"item {index}.question",
        )

        if question_id in seen_ids:
            raise ValueError(
                f"Duplicate golden question id: {question_id}"
            )

        seen_ids.add(question_id)

        raw_expected_titles = raw_item.get(
            "expected_titles"
        )

        if (
            not isinstance(raw_expected_titles, list)
            or not raw_expected_titles
        ):
            raise ValueError(
                f"item {index}.expected_titles "
                "must be a non-empty list"
            )

        expected_titles = tuple(
            normalize_required_string(
                title,
                field_name=(
                    f"item {index}.expected_titles"
                ),
            )
            for title in raw_expected_titles
        )

        preferred_title = normalize_optional_string(
            raw_item.get("preferred_title")
        )
        notes = normalize_optional_string(
            raw_item.get("notes")
        )

        if (
            preferred_title is not None
            and preferred_title not in expected_titles
        ):
            raise ValueError(
                f"Preferred title for {question_id} "
                "must also appear in expected_titles"
            )

        questions.append(
            GoldenQuestion(
                id=question_id,
                question=question,
                expected_titles=expected_titles,
                preferred_title=preferred_title,
                notes=notes,
            )
        )

    if not questions:
        raise ValueError(
            "Golden question dataset cannot be empty"
        )

    return tuple(questions)


async def evaluate_question(
    *,
    service: MultiQueryRetrievalService,
    golden: GoldenQuestion,
    limit: int,
    per_query_limit: int,
    max_queries: int,
    namespace_ids: tuple[int, ...],
) -> QuestionEvaluation:
    started_at = time.perf_counter()

    retrieval = await service.search(
        golden.question,
        limit=limit,
        per_query_limit=per_query_limit,
        max_queries=max_queries,
        namespace_ids=namespace_ids,
    )

    latency_ms = (
        time.perf_counter() - started_at
    ) * 1000

    top_results = tuple(
        RankedResult(
            position=index,
            title=result.title,
            heading_path=result.heading_path,
            chunk_id=result.chunk_id,
            rank=result.rank,
        )
        for index, result in enumerate(
            retrieval.results,
            start=1,
        )
    )

    first_expected_position = first_matching_position(
        top_results,
        golden.expected_titles,
    )

    preferred_position = (
        first_matching_position(
            top_results,
            (golden.preferred_title,),
        )
        if golden.preferred_title is not None
        else None
    )

    return QuestionEvaluation(
        id=golden.id,
        question=golden.question,
        expected_titles=golden.expected_titles,
        preferred_title=golden.preferred_title,
        top_results=top_results,
        first_expected_position=first_expected_position,
        preferred_position=preferred_position,
        top_1_hit=first_expected_position == 1,
        top_3_hit=(
            first_expected_position is not None
            and first_expected_position <= 3
        ),
        top_5_hit=(
            first_expected_position is not None
            and first_expected_position <= 5
        ),
        preferred_top_1_hit=(
            preferred_position == 1
            if golden.preferred_title is not None
            else None
        ),
        latency_ms=round(latency_ms, 3),
        executed_queries=retrieval.executed_queries,
        raw_result_count=retrieval.raw_result_count,
        unique_result_count=(
            retrieval.unique_result_count
        ),
    )


async def run_evaluation(
    *,
    dataset_path: Path,
    limit: int,
    per_query_limit: int,
    max_queries: int,
    namespace_ids: tuple[int, ...],
    retrieval_mode: str | None = None,
    settings: Settings | None = None,
) -> EvaluationSummary:
    golden_questions = load_golden_questions(
        dataset_path
    )

    evaluations: list[QuestionEvaluation] = []

    base_settings = settings or get_settings()
    resolved_mode = (
        retrieval_mode
        or base_settings.copilot_retrieval_mode
    )

    evaluation_settings = base_settings.model_copy(
        update={
            "copilot_retrieval_mode": resolved_mode,
        }
    )

    secret = evaluation_settings.openai_api_key
    api_key = (
        secret.get_secret_value().strip()
        if secret is not None
        else None
    )

    async with AsyncSessionFactory() as session:
        try:
            retrieval = build_knowledge_retriever(
                session=session,
                settings=evaluation_settings,
                api_key=api_key,
            )
        except RetrievalConfigurationError as error:
            raise RuntimeError(str(error)) from error

        service = MultiQueryRetrievalService(
            retrieval
        )

        for golden in golden_questions:
            evaluation = await evaluate_question(
                service=service,
                golden=golden,
                limit=limit,
                per_query_limit=per_query_limit,
                max_queries=max_queries,
                namespace_ids=namespace_ids,
            )
            evaluations.append(evaluation)

    latencies = [
        evaluation.latency_ms
        for evaluation in evaluations
    ]

    preferred_evaluations = [
        evaluation
        for evaluation in evaluations
        if evaluation.preferred_top_1_hit is not None
    ]

    return EvaluationSummary(
        generated_at=datetime.now(UTC).isoformat(),
        dataset_path=str(dataset_path),
        retrieval_mode=resolved_mode,
        question_count=len(evaluations),
        top_1_accuracy=accuracy_percentage(
            evaluation.top_1_hit
            for evaluation in evaluations
        ),
        top_3_accuracy=accuracy_percentage(
            evaluation.top_3_hit
            for evaluation in evaluations
        ),
        top_5_accuracy=accuracy_percentage(
            evaluation.top_5_hit
            for evaluation in evaluations
        ),
        preferred_top_1_accuracy=(
            accuracy_percentage(
                bool(
                    evaluation.preferred_top_1_hit
                )
                for evaluation
                in preferred_evaluations
            )
            if preferred_evaluations
            else None
        ),
        average_latency_ms=round(
            statistics.fmean(latencies),
            3,
        ),
        median_latency_ms=round(
            statistics.median(latencies),
            3,
        ),
        maximum_latency_ms=round(
            max(latencies),
            3,
        ),
        evaluations=tuple(evaluations),
    )


def first_matching_position(
    results: tuple[RankedResult, ...],
    expected_titles: tuple[str, ...],
) -> int | None:
    normalized_expected = {
        normalize_title(title)
        for title in expected_titles
        if title is not None
    }

    for result in results:
        if normalize_title(result.title) in normalized_expected:
            return result.position

    return None


def normalize_title(value: str) -> str:
    return " ".join(value.split()).casefold()


def normalize_required_string(
    value: object,
    *,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise ValueError(
            f"{field_name} must be a string"
        )

    normalized = " ".join(value.split())

    if not normalized:
        raise ValueError(
            f"{field_name} cannot be empty"
        )

    return normalized


def normalize_optional_string(
    value: object,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(
            "Optional string field must be a string"
        )

    normalized = " ".join(value.split())

    return normalized or None


def accuracy_percentage(
    values: Any,
) -> float:
    materialized = list(values)

    if not materialized:
        return 0.0

    return round(
        (
            sum(bool(value) for value in materialized)
            / len(materialized)
        )
        * 100,
        2,
    )


def print_console_report(
    summary: EvaluationSummary,
) -> None:
    print("\n" + "=" * 80)
    print("BITCOIN CHANGE COPILOT RETRIEVAL EVALUATION")
    print("=" * 80)

    for evaluation in summary.evaluations:
        expected = " / ".join(
            evaluation.expected_titles
        )
        actual_top_1 = (
            evaluation.top_results[0].title
            if evaluation.top_results
            else "(no results)"
        )

        if evaluation.top_1_hit:
            result_icon = "✅"
        elif evaluation.top_3_hit:
            result_icon = "🟡"
        else:
            result_icon = "❌"

        print("\n" + "-" * 80)
        print(
            f"{result_icon} {evaluation.id}: "
            f"{evaluation.question}"
        )
        print(f"Expected: {expected}")
        print(f"Top 1:    {actual_top_1}")
        print(
            "Expected position:",
            evaluation.first_expected_position
            or "not found",
        )

        if evaluation.preferred_title is not None:
            print(
                "Preferred:",
                evaluation.preferred_title,
            )
            print(
                "Preferred position:",
                evaluation.preferred_position
                or "not found",
            )

        print(
            f"Latency: {evaluation.latency_ms:.2f} ms"
        )
        print(
            "Queries:",
            " | ".join(
                evaluation.executed_queries
            ),
        )

        for result in evaluation.top_results[:3]:
            print(
                f"  {result.position}. "
                f"{result.title} "
                f"(rank={result.rank:.3f})"
            )

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(
        f"Questions:       {summary.question_count}"
    )
    print(
        f"Top-1 accuracy:  "
        f"{summary.top_1_accuracy:.2f}%"
    )
    print(
        f"Top-3 accuracy:  "
        f"{summary.top_3_accuracy:.2f}%"
    )
    print(
        f"Top-5 accuracy:  "
        f"{summary.top_5_accuracy:.2f}%"
    )

    if summary.preferred_top_1_accuracy is not None:
        print(
            "Preferred Top-1: "
            f"{summary.preferred_top_1_accuracy:.2f}%"
        )

    print(
        f"Average latency: "
        f"{summary.average_latency_ms:.2f} ms"
    )
    print(
        f"Median latency:  "
        f"{summary.median_latency_ms:.2f} ms"
    )
    print(
        f"Maximum latency: "
        f"{summary.maximum_latency_ms:.2f} ms"
    )


def save_report(
    summary: EvaluationSummary,
    report_path: Path | None,
) -> Path:
    if report_path is None:
        timestamp = datetime.now(UTC).strftime(
            "%Y%m%d-%H%M%S"
        )
        report_path = (
            DEFAULT_REPORT_DIRECTORY
            / f"retrieval-evaluation-{timestamp}.json"
        )

    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path.write_text(
        json.dumps(
            asdict(summary),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return report_path


async def async_main() -> int:
    args = build_argument_parser().parse_args()

    namespace_ids = tuple(
        args.namespace_ids
        if args.namespace_ids is not None
        else (0,)
    )

    summary = await run_evaluation(
        dataset_path=args.dataset,
        limit=args.limit,
        per_query_limit=args.per_query_limit,
        max_queries=args.max_queries,
        namespace_ids=namespace_ids,
        retrieval_mode=args.retrieval_mode,
    )

    print_console_report(summary)

    report_path = save_report(
        summary,
        args.report,
    )

    print(f"\nReport saved: {report_path}")

    if (
        args.fail_below_top3 is not None
        and summary.top_3_accuracy
        < args.fail_below_top3
    ):
        print(
            "\nEvaluation failed: "
            f"Top-3 accuracy "
            f"{summary.top_3_accuracy:.2f}% "
            f"is below required "
            f"{args.fail_below_top3:.2f}%."
        )
        return 1

    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
