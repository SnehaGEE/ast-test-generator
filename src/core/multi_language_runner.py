
from typing import Any

from src.core.models import TestCase, TestResult
from src.core.targeted_generator import generate_targeted_inputs
from src.core.test_runner import run_python_test_suite
from src.languages.java.adapter import JavaAdapter
from src.languages.c.adapter import CAdapter


COMPILED_ADAPTERS = {
    "java": JavaAdapter,
    "c": CAdapter,
}

SUPPORTED_LANGUAGES = {"python", *COMPILED_ADAPTERS}


def _not_measured(language: str) -> dict[str, Any]:
    return {
        "success": False,
        "error": (
            f"Runtime branch coverage is not yet measured "
            f"for {language}."
        ),
        "branches": [],
        "branch_coverage_percent": None,
    }


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
    coverage = _not_measured(language)

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
            "coverage": coverage,
            "message": " ".join(
                [
                    "No supported conditions were detected; "
                    "no targeted tests were generated.",
                    *messages,
                ]
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
    results: list[TestResult] = adapter.execute_many(
        source_code, test_cases
    )
    for result in results:
        result.category = "targeted"

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
        "message": " ".join([coverage["error"], *messages]),
    }
