from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.main import app


DEFAULT_DATASET = Path(
    "evaluation/answer_quality_cases.json"
)
DEFAULT_REPORT_DIRECTORY = Path(
    "evaluation/reports"
)


@dataclass(frozen=True, slots=True)
class AnswerQualityCase:
    id: str
    question: str
    expected_source_titles: tuple[str, ...]
    required_any_terms: tuple[str, ...]
    required_all_terms: tuple[str, ...]
    forbidden_terms: tuple[str, ...]
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class AnswerQualityResult:
    id: str
    question: str
    passed: bool
    status_code: int
    grounded: bool
    answer_present: bool
    expected_source_found: bool
    required_any_passed: bool
    required_all_passed: bool
    forbidden_terms_passed: bool
    expected_source_titles: tuple[str, ...]
    actual_source_titles: tuple[str, ...]
    missing_required_all_terms: tuple[str, ...]
    matched_required_any_terms: tuple[str, ...]
    matched_forbidden_terms: tuple[str, ...]
    answer_preview: str
    latency_ms: float
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnswerQualitySummary:
    generated_at: str
    dataset_path: str
    case_count: int
    passed_count: int
    failed_count: int
    pass_rate: float
    grounded_rate: float
    source_accuracy: float
    average_latency_ms: float
    median_latency_ms: float
    maximum_latency_ms: float
    results: tuple[AnswerQualityResult, ...]


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate final Copilot answer quality, "
            "grounding and source usage."
        )
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help=(
            "Validate the dataset without calling "
            "the Copilot or OpenAI."
        ),
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Run real Copilot requests. This may use "
            "the configured OpenAI API and incur cost."
        ),
    )
    parser.add_argument(
        "--fail-below",
        type=float,
        default=None,
        help=(
            "Return failure when the answer-quality "
            "pass rate is below this percentage."
        ),
    )

    return parser


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
            "Optional string must be a string"
        )

    normalized = " ".join(value.split())

    return normalized or None


def normalize_string_list(
    value: object,
    *,
    field_name: str,
    allow_empty: bool,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(
            f"{field_name} must be a list"
        )

    normalized = tuple(
        normalize_required_string(
            item,
            field_name=field_name,
        )
        for item in value
    )

    if not allow_empty and not normalized:
        raise ValueError(
            f"{field_name} cannot be empty"
        )

    return normalized


def load_answer_quality_cases(
    path: Path,
) -> tuple[AnswerQualityCase, ...]:
    if not path.exists():
        raise FileNotFoundError(
            f"Answer-quality dataset not found: {path}"
        )

    raw_data = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(raw_data, list):
        raise ValueError(
            "Answer-quality dataset must be a JSON list"
        )

    cases: list[AnswerQualityCase] = []
    seen_ids: set[str] = set()

    for index, raw_item in enumerate(
        raw_data,
        start=1,
    ):
        if not isinstance(raw_item, dict):
            raise ValueError(
                f"Dataset item {index} must be an object"
            )

        case_id = normalize_required_string(
            raw_item.get("id"),
            field_name=f"item {index}.id",
        )

        if case_id in seen_ids:
            raise ValueError(
                f"Duplicate answer-quality case id: "
                f"{case_id}"
            )

        seen_ids.add(case_id)

        cases.append(
            AnswerQualityCase(
                id=case_id,
                question=normalize_required_string(
                    raw_item.get("question"),
                    field_name=(
                        f"item {index}.question"
                    ),
                ),
                expected_source_titles=(
                    normalize_string_list(
                        raw_item.get(
                            "expected_source_titles"
                        ),
                        field_name=(
                            f"item {index}."
                            "expected_source_titles"
                        ),
                        allow_empty=False,
                    )
                ),
                required_any_terms=(
                    normalize_string_list(
                        raw_item.get(
                            "required_any_terms",
                            [],
                        ),
                        field_name=(
                            f"item {index}."
                            "required_any_terms"
                        ),
                        allow_empty=True,
                    )
                ),
                required_all_terms=(
                    normalize_string_list(
                        raw_item.get(
                            "required_all_terms",
                            [],
                        ),
                        field_name=(
                            f"item {index}."
                            "required_all_terms"
                        ),
                        allow_empty=True,
                    )
                ),
                forbidden_terms=(
                    normalize_string_list(
                        raw_item.get(
                            "forbidden_terms",
                            [],
                        ),
                        field_name=(
                            f"item {index}."
                            "forbidden_terms"
                        ),
                        allow_empty=True,
                    )
                ),
                notes=normalize_optional_string(
                    raw_item.get("notes")
                ),
            )
        )

    if not cases:
        raise ValueError(
            "Answer-quality dataset cannot be empty"
        )

    return tuple(cases)


def normalized_contains(
    text: str,
    term: str,
) -> bool:
    return term.casefold() in text.casefold()


def extract_answer(payload: dict[str, Any]) -> str:
    for field_name in (
        "answer",
        "response",
        "content",
        "text",
    ):
        value = payload.get(field_name)

        if isinstance(value, str):
            return value.strip()

    return ""


def extract_source_titles(
    payload: dict[str, Any],
) -> tuple[str, ...]:
    raw_sources = payload.get("sources", [])

    if not isinstance(raw_sources, list):
        return ()

    titles: list[str] = []

    for source in raw_sources:
        if not isinstance(source, dict):
            continue

        title = source.get("title")

        if isinstance(title, str) and title.strip():
            titles.append(" ".join(title.split()))

    return tuple(titles)


def evaluate_payload(
    *,
    case: AnswerQualityCase,
    status_code: int,
    payload: dict[str, Any],
    latency_ms: float,
) -> AnswerQualityResult:
    answer = extract_answer(payload)
    source_titles = extract_source_titles(payload)
    grounded = payload.get("grounded") is True

    expected_normalized = {
        title.casefold()
        for title in case.expected_source_titles
    }

    expected_source_found = any(
        title.casefold() in expected_normalized
        for title in source_titles
    )

    matched_required_any = tuple(
        term
        for term in case.required_any_terms
        if normalized_contains(answer, term)
    )

    required_any_passed = (
        not case.required_any_terms
        or bool(matched_required_any)
    )

    missing_required_all = tuple(
        term
        for term in case.required_all_terms
        if not normalized_contains(answer, term)
    )

    required_all_passed = (
        not missing_required_all
    )

    matched_forbidden = tuple(
        term
        for term in case.forbidden_terms
        if normalized_contains(answer, term)
    )

    forbidden_terms_passed = (
        not matched_forbidden
    )

    answer_present = bool(answer)

    errors: list[str] = []

    if status_code != 200:
        errors.append(
            f"Unexpected status code: {status_code}"
        )

    if not answer_present:
        errors.append("Answer is empty")

    if not grounded:
        errors.append(
            "Answer is not marked as grounded"
        )

    if not expected_source_found:
        errors.append(
            "Expected source was not returned"
        )

    if not required_any_passed:
        errors.append(
            "None of the required-any terms appeared"
        )

    if not required_all_passed:
        errors.append(
            "Missing required-all terms: "
            + ", ".join(missing_required_all)
        )

    if not forbidden_terms_passed:
        errors.append(
            "Forbidden terms appeared: "
            + ", ".join(matched_forbidden)
        )

    passed = not errors

    return AnswerQualityResult(
        id=case.id,
        question=case.question,
        passed=passed,
        status_code=status_code,
        grounded=grounded,
        answer_present=answer_present,
        expected_source_found=(
            expected_source_found
        ),
        required_any_passed=required_any_passed,
        required_all_passed=required_all_passed,
        forbidden_terms_passed=(
            forbidden_terms_passed
        ),
        expected_source_titles=(
            case.expected_source_titles
        ),
        actual_source_titles=source_titles,
        missing_required_all_terms=(
            missing_required_all
        ),
        matched_required_any_terms=(
            matched_required_any
        ),
        matched_forbidden_terms=(
            matched_forbidden
        ),
        answer_preview=answer[:500],
        latency_ms=round(latency_ms, 3),
        errors=tuple(errors),
    )


def percentage(
    values: list[bool],
) -> float:
    if not values:
        return 0.0

    return round(
        sum(values) / len(values) * 100,
        2,
    )


def run_live_evaluation(
    cases: tuple[AnswerQualityCase, ...],
) -> AnswerQualitySummary:
    results: list[AnswerQualityResult] = []

    with TestClient(app) as client:
        for case in cases:
            started_at = time.perf_counter()

            response = client.post(
                "/api/copilot/ask",
                json={
                    "question": case.question,
                },
            )

            latency_ms = (
                time.perf_counter() - started_at
            ) * 1000

            try:
                payload = response.json()
            except ValueError:
                payload = {}

            if not isinstance(payload, dict):
                payload = {}

            results.append(
                evaluate_payload(
                    case=case,
                    status_code=response.status_code,
                    payload=payload,
                    latency_ms=latency_ms,
                )
            )

    latencies = [
        result.latency_ms
        for result in results
    ]

    return AnswerQualitySummary(
        generated_at=datetime.now(UTC).isoformat(),
        dataset_path=str(DEFAULT_DATASET),
        case_count=len(results),
        passed_count=sum(
            result.passed
            for result in results
        ),
        failed_count=sum(
            not result.passed
            for result in results
        ),
        pass_rate=percentage(
            [
                result.passed
                for result in results
            ]
        ),
        grounded_rate=percentage(
            [
                result.grounded
                for result in results
            ]
        ),
        source_accuracy=percentage(
            [
                result.expected_source_found
                for result in results
            ]
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
        results=tuple(results),
    )


def print_summary(
    summary: AnswerQualitySummary,
) -> None:
    print("\n" + "=" * 80)
    print("BITCOIN CHANGE COPILOT ANSWER QUALITY")
    print("=" * 80)

    for result in summary.results:
        icon = "✅" if result.passed else "❌"

        print("\n" + "-" * 80)
        print(
            f"{icon} {result.id}: "
            f"{result.question}"
        )
        print(
            "Grounded:",
            result.grounded,
        )
        print(
            "Expected source found:",
            result.expected_source_found,
        )
        print(
            "Sources:",
            " | ".join(
                result.actual_source_titles
            )
            or "(none)",
        )
        print(
            f"Latency: {result.latency_ms:.2f} ms"
        )

        if result.errors:
            print("Errors:")

            for error in result.errors:
                print("  -", error)

        print("Answer preview:")
        print(result.answer_preview or "(empty)")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print("Cases:", summary.case_count)
    print("Passed:", summary.passed_count)
    print("Failed:", summary.failed_count)
    print(
        f"Pass rate:       "
        f"{summary.pass_rate:.2f}%"
    )
    print(
        f"Grounded rate:   "
        f"{summary.grounded_rate:.2f}%"
    )
    print(
        f"Source accuracy: "
        f"{summary.source_accuracy:.2f}%"
    )
    print(
        f"Average latency: "
        f"{summary.average_latency_ms:.2f} ms"
    )


def save_report(
    summary: AnswerQualitySummary,
    report_path: Path | None,
) -> Path:
    if report_path is None:
        timestamp = datetime.now(UTC).strftime(
            "%Y%m%d-%H%M%S"
        )
        report_path = (
            DEFAULT_REPORT_DIRECTORY
            / f"answer-quality-{timestamp}.json"
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


def main() -> int:
    args = build_argument_parser().parse_args()

    cases = load_answer_quality_cases(
        args.dataset
    )

    print(
        f"Validated {len(cases)} "
        "answer-quality cases."
    )

    if args.validate_only:
        print(
            "✅ Dataset validation completed. "
            "No API or OpenAI call was made."
        )
        return 0

    if not args.live:
        print(
            "No live evaluation was requested."
        )
        print(
            "Use --live to call the Copilot API."
        )
        return 0

    summary = run_live_evaluation(cases)
    print_summary(summary)

    report_path = save_report(
        summary,
        args.report,
    )

    print("\nReport saved:", report_path)

    if (
        args.fail_below is not None
        and summary.pass_rate < args.fail_below
    ):
        print(
            f"Answer quality {summary.pass_rate:.2f}% "
            f"is below {args.fail_below:.2f}%."
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
