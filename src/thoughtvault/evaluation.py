from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .ask import answer_question
from .embeddings import DEFAULT_EMBEDDING_MODEL
from .synthesis import DEFAULT_OLLAMA_HOST, DEFAULT_OLLAMA_MODEL

Answerer = Callable[..., dict[str, object]]
REFUSAL_MARKERS = (
    "无法确认",
    "无法从",
    "不能确认",
    "没有找到",
    "无法可靠确认",
    "cannot confirm",
    "could not confirm",
    "not found",
    "資料から確認できない",
    "確認できません",
)


@dataclass(frozen=True)
class EvaluationCase:
    case_id: str
    query: str
    expected_route: str | None = None
    expected_status: str | None = None
    expected_first_path: str | None = None
    expected_paths: tuple[str, ...] = ()
    expected_evidence_kinds: tuple[str, ...] = ()
    answer_contains: tuple[str, ...] = ()
    answer_not_contains: tuple[str, ...] = ()
    expect_refusal: bool = False


@dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    query: str
    passed: bool
    checks: tuple[str, ...]
    answer: str
    source_paths: tuple[str, ...]


@dataclass(frozen=True)
class EvaluationSummary:
    total: int
    passed: int
    failed: int
    results: tuple[EvaluationResult, ...]


def load_evaluation_cases(path: str | Path) -> list[EvaluationCase]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_cases = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(raw_cases, list):
        raise ValueError("Evaluation file must contain a JSON list or an object with a 'cases' list.")

    cases = []
    for index, raw in enumerate(raw_cases, start=1):
        if not isinstance(raw, dict) or not str(raw.get("query", "")).strip():
            raise ValueError(f"Evaluation case {index} must contain a non-empty query.")
        cases.append(
            EvaluationCase(
                case_id=str(raw.get("id") or f"case-{index}"),
                query=str(raw["query"]).strip(),
                expected_route=(
                    str(raw["expected_route"])
                    if raw.get("expected_route") is not None
                    else None
                ),
                expected_status=(
                    str(raw["expected_status"])
                    if raw.get("expected_status") is not None
                    else None
                ),
                expected_first_path=(
                    str(raw["expected_first_path"])
                    if raw.get("expected_first_path") is not None
                    else None
                ),
                expected_paths=tuple(str(value) for value in raw.get("expected_paths", [])),
                expected_evidence_kinds=tuple(
                    str(value) for value in raw.get("expected_evidence_kinds", [])
                ),
                answer_contains=tuple(str(value) for value in raw.get("answer_contains", [])),
                answer_not_contains=tuple(str(value) for value in raw.get("answer_not_contains", [])),
                expect_refusal=bool(raw.get("expect_refusal", False)),
            )
        )
    return cases


def _evaluate_case(case: EvaluationCase, result: dict[str, object]) -> EvaluationResult:
    answer = str(result.get("answer", ""))
    lowered_answer = answer.lower()
    evidence = result.get("evidence") or []
    source_paths = tuple(dict.fromkeys(str(item.path) for item in evidence))
    evidence_kinds = tuple(dict.fromkeys(str(item.kind) for item in evidence))
    raw_route = result.get("query_route") or {}
    actual_route = str(raw_route.get("route", "")) if isinstance(raw_route, dict) else ""
    actual_status = str(result.get("status", ""))
    checks = []
    passed = True

    if case.expected_route:
        matched = actual_route == case.expected_route
        checks.append(f"{'PASS' if matched else 'FAIL'} route:{case.expected_route}")
        passed = passed and matched

    if case.expected_status:
        matched = actual_status == case.expected_status
        checks.append(f"{'PASS' if matched else 'FAIL'} status:{case.expected_status}")
        passed = passed and matched

    if case.expected_first_path:
        first_path = source_paths[0] if source_paths else ""
        matched = case.expected_first_path.lower() in first_path.lower()
        checks.append(f"{'PASS' if matched else 'FAIL'} first_source:{case.expected_first_path}")
        passed = passed and matched

    for expected_path in case.expected_paths:
        matched = any(expected_path.lower() in path.lower() for path in source_paths)
        checks.append(f"{'PASS' if matched else 'FAIL'} source:{expected_path}")
        passed = passed and matched

    for expected_kind in case.expected_evidence_kinds:
        matched = expected_kind in evidence_kinds
        checks.append(f"{'PASS' if matched else 'FAIL'} evidence_kind:{expected_kind}")
        passed = passed and matched

    for term in case.answer_contains:
        matched = term.lower() in lowered_answer
        checks.append(f"{'PASS' if matched else 'FAIL'} contains:{term}")
        passed = passed and matched

    for term in case.answer_not_contains:
        matched = term.lower() not in lowered_answer
        checks.append(f"{'PASS' if matched else 'FAIL'} excludes:{term}")
        passed = passed and matched

    if case.expect_refusal:
        matched = any(marker.lower() in lowered_answer for marker in REFUSAL_MARKERS)
        checks.append(f"{'PASS' if matched else 'FAIL'} refusal")
        passed = passed and matched

    if not checks:
        checks.append("PASS completed")

    return EvaluationResult(
        case_id=case.case_id,
        query=case.query,
        passed=passed,
        checks=tuple(checks),
        answer=answer,
        source_paths=source_paths,
    )


def run_evaluation(
    suite_path: str | Path,
    db_path: str | None = None,
    model: str = DEFAULT_OLLAMA_MODEL,
    embedding_model: str | None = DEFAULT_EMBEDDING_MODEL,
    ollama_host: str = DEFAULT_OLLAMA_HOST,
    timeout: float = 120.0,
    limit: int = 5,
    use_ai: bool = True,
    answerer: Answerer = answer_question,
) -> EvaluationSummary:
    cases = load_evaluation_cases(suite_path)
    results = []
    for case in cases:
        answer_result = answerer(
            case.query,
            db_path,
            model=model,
            embedding_model=embedding_model,
            ollama_host=ollama_host,
            timeout=timeout,
            limit=limit,
            use_ai=use_ai,
            save=False,
        )
        results.append(_evaluate_case(case, answer_result))
    passed = sum(result.passed for result in results)
    return EvaluationSummary(
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        results=tuple(results),
    )
