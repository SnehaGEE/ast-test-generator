
from typing import Any

from src.core.models import TestCase, TestResult
from src.core.targeted_generator import generate_targeted_inputs
from src.core.test_runner import (
    _describe_unsupported,
    _join_messages,
    run_python_test_suite,
)
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
    """Generate and execute targeted tests for a supported language."""

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

    adapter = COMPILED_ADAPTERS[language]()
    adapter.parse(source_code)
    conditions = adapter.analyze(source_code)
    unsupported = adapter.untracked(source_code)

    messages = []
    if include_invalid_inputs or include_fuzz_inputs:
        messages.append(
            "Invalid-input and fuzz tests are only available for Python."
        )

    if not conditions:
        return {
            "results": [],
            "total_tests": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "coverage": {
                "success": True,
                "error": None,
                "branches": [],
                "branch_coverage_percent": None,
                "unsupported": unsupported,
            },
            "message": _join_messages(
                "No supported conditions were detected; "
                "no targeted tests were generated.",
                _describe_unsupported(unsupported, TRACKED[language]),
                *messages,
            ),
        }

    condition_data = [
        {
            "variable": condition.variable,
            "operator": condition.operator,
            "constant": condition.value,
            "line": condition.line,
        }
        for condition in conditions
    ]

    input_cases = generate_targeted_inputs(
        condition_data,
        max_cases=max_cases,
    )

    test_cases = [
        TestCase(
            inputs=inputs,
            description="AST-derived targeted test",
        )
        for inputs in input_cases
    ]

    results: list[TestResult] = []
    hits: set[tuple[int, bool]] = set()
    with adapter.compile(source_code) as program:
        for case in test_cases:
            result, reached = program.run(case)
            result.category = "targeted"
            results.append(result)
            hits |= reached
        coverage = program.coverage(hits)

    coverage["unsupported"] = unsupported

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
            coverage.get("error"),
            _describe_unsupported(unsupported, TRACKED[language]),
            *messages,
        ),
    }
