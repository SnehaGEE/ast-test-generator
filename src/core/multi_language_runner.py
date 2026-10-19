
from typing import Any

from src.core.models import TestCase, TestResult
from src.core.targeted_generator import generate_targeted_inputs
from src.languages.python.adapter import PythonAdapter
from src.languages.java.adapter import JavaAdapter
from src.languages.c.adapter import CAdapter


ADAPTERS = {
    "python": PythonAdapter,
    "java": JavaAdapter,
    "c": CAdapter,
}


def run_test_suite(
    source_code: str,
    language: str = "python",
    max_cases: int = 100,
) -> dict[str, Any]:
    """Generate and execute targeted tests for a supported language."""

    if max_cases < 1:
        raise ValueError("max_cases must be at least 1")

    language = language.lower().strip()

    if language not in ADAPTERS:
        raise ValueError(
            f"Unsupported language: {language}. "
            "Choose python, java, or c."
        )

    adapter = ADAPTERS[language]()
    adapter.parse(source_code)
    conditions = adapter.analyze(source_code)

    if not conditions:
        return {
            "results": [],
            "total_tests": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "coverage": {
                "covered": 0,
                "total": 0,
                "percentage": 0.0,
            },
            "message": (
                "No supported conditions were detected; "
                "no targeted tests were generated."
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

    results: list[TestResult] = []

    for inputs in input_cases:
        test_case = TestCase(
            inputs=inputs,
            description="AST-derived targeted test",
        )
        results.append(adapter.execute(source_code, test_case))

    return {
        "results": results,
        "total_tests": len(results),
        "successful_executions": sum(
            result.executed for result in results
        ),
        "failed_executions": sum(
            not result.executed for result in results
        ),
        "coverage": {
            "covered": 0,
            "total": len(conditions),
            "percentage": 0.0,
        },
        "message": (
            "Execution completed. Runtime branch coverage "
            "has not been measured by this runner."
        ),
    }
