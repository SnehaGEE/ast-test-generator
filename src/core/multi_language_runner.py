
from typing import Any

from src.core.models import TestCase, TestResult
from src.core.test_runner import (
    _describe_unsupported,
    _join_messages,
    plan_test_cases,
    run_python_test_suite,
    verified_suggestions,
)
from src.coverage.coverage_analyzer import suggest_missing_branch_tests
from src.languages.java.adapter import JavaAdapter
from src.languages.c.adapter import CAdapter


COMPILED_ADAPTERS = {
    "java": JavaAdapter,
    "c": CAdapter,
}

SUPPORTED_LANGUAGES = {"python", *COMPILED_ADAPTERS}

# Which statements the coverage percentage counts, per language.
TRACKED = {"java": "if/else if and while", "c": "if/else if and while"}


def run_test_suite(
    source_code: str,
    language: str = "python",
    max_cases: int = 100,
    include_invalid_inputs: bool = False,
    include_fuzz_inputs: bool = False,
) -> dict[str, Any]:
    """Generate and execute targeted, invalid-input and fuzz tests."""

    if max_cases < 1:
        raise ValueError("max_cases must be at least 1")

    language = language.lower().strip()

    if language not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language: {language}. "
            "Choose python, java, or c."
        )

    if language == "python":
        return run_python_test_suite(
            source_code=source_code,
            max_cases=max_cases,
            include_invalid_inputs=include_invalid_inputs,
            include_fuzz_inputs=include_fuzz_inputs,
        )

    return _run_compiled_test_suite(
        source_code,
        language,
        max_cases,
        include_invalid_inputs,
        include_fuzz_inputs,
    )


def _run_compiled_test_suite(
    source_code: str,
    language: str,
    max_cases: int,
    include_invalid_inputs: bool,
    include_fuzz_inputs: bool,
) -> dict[str, Any]:
    """Java and C: plan tests, run them on one probed build, report coverage."""

    adapter = COMPILED_ADAPTERS[language]()
    adapter.parse(source_code)
    conditions = adapter.analyze(source_code)
    unsupported = adapter.untracked(source_code)
    unsupported_note = _describe_unsupported(unsupported, TRACKED[language])

    if (
        not conditions
        and not include_invalid_inputs
        and not include_fuzz_inputs
    ):
        return {
            "results": [],
            "total_tests": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "coverage": {
                "success": True,
                "error": None,
                "branches": [],
                # None means "not measured", which is not the same as 0%.
                "branch_coverage_percent": None,
                "unsupported": unsupported,
                "suggestions": [],
            },
            "message": _join_messages(
                "No supported conditions were detected; "
                "no targeted tests were generated.",
                unsupported_note,
            ),
        }

    planned, base, extras_note = plan_test_cases(
        conditions,
        max_cases,
        include_invalid_inputs,
        include_fuzz_inputs,
    )

    results: list[TestResult] = []
    hits: set[tuple[int, bool]] = set()

    with adapter.compile(source_code) as program:
        for case, category in planned:
            result, reached = program.run(case)
            result.category = category
            results.append(result)
            hits |= reached

        coverage = program.coverage(hits)
        coverage["suggestions"] = []

        if coverage["success"]:
            line_of = {branch.id: branch.line for branch in program.branches}

            def reaches(inputs, line, target_outcome):
                _, reached = program.run(TestCase(inputs=inputs))
                wanted = target_outcome == "true"
                return any(
                    line_of.get(branch_id) == line and outcome == wanted
                    for branch_id, outcome in reached
                )

            candidates = suggest_missing_branch_tests(
                source_code,
                coverage,
                conditions=[
                    {
                        "variable": condition.variable,
                        "operator": condition.operator,
                        "constant": condition.value,
                        "line": condition.line,
                    }
                    for condition in conditions
                ],
            )
            coverage["suggestions"] = verified_suggestions(
                candidates, base, reaches
            )

    coverage["unsupported"] = unsupported

    base_message = (
        "No usable test inputs could be generated. "
        "Supported conditions or input variables may be required."
        if not planned
        else None
    )

    return {
        "results": results,
        "total_tests": len(results),
        "successful_executions": sum(
            result.executed for result in results
        ),
        "failed_executions": sum(
            not result.executed for result in results
        ),
        "coverage": coverage,
        "message": _join_messages(
            base_message,
            coverage.get("error"),
            extras_note,
            unsupported_note,
        ),
    }
