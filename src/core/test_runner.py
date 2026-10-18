
from typing import Any

from src.core.models import TestCase, TestResult
from src.core.targeted_generator import generate_targeted_inputs
from src.languages.python.adapter import PythonAdapter
from src.coverage.coverage_analyzer import analyze_branch_coverage


def run_python_test_suite(
    source_code: str,
    max_cases: int = 100,
) -> dict[str, Any]:
    """Generate and execute targeted tests for supported Python conditions."""

    if max_cases < 1:
        raise ValueError("max_cases must be at least 1")

    adapter = PythonAdapter()

    # Parse and analyze the supplied program.
    adapter.parse(source_code)
    conditions = adapter.analyze(source_code)

    # Do not generate or execute an empty-input test when no
    # supported conditions exist.
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

    # This estimates condition outcomes; it is not authoritative
    # runtime branch coverage.
    coverage = analyze_branch_coverage(source_code, input_cases)

    if not input_cases:
        message = (
            "Conditions were detected, but no usable test inputs "
            "could be generated."
        )
    else:
        message = None

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
        "message": message,
    }
