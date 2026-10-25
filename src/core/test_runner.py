from typing import Any

from src.core.models import TestCase, TestResult
from src.core.targeted_generator import generate_targeted_inputs
from src.core.invalid_input_generator import generate_invalid_inputs
from src.core.fuzz_generator import generate_fuzz_inputs
from src.languages.python.adapter import PythonAdapter
from src.coverage.coverage_analyzer import analyze_branch_coverage
from src.coverage.unsupported_syntax import find_unsupported_constructs


def _describe_unsupported(unsupported: list[dict[str, Any]]) -> str | None:
    """Build a user-facing note about constructs coverage ignores."""
    if not unsupported:
        return None

    parts: list[str] = []
    for item in unsupported:
        text = f"{item['construct']} (line {item['line']})"
        if text not in parts:
            parts.append(text)

    return (
        "Branch coverage does not track: "
        + "; ".join(parts)
        + ". The percentage covers only if/elif and while conditions."
    )


def _join_messages(*messages: str | None) -> str | None:
    """Join the non-empty messages, or return None if there are none."""
    present = [message for message in messages if message]
    return " ".join(present) if present else None


def run_python_test_suite(
    source_code: str,
    max_cases: int = 100,
    include_invalid_inputs: bool = False,
    include_fuzz_inputs: bool = False,
) -> dict[str, Any]:
    """Generate and execute targeted, invalid-input, and fuzz tests."""

    if max_cases < 1:
        raise ValueError("max_cases must be at least 1")

    adapter = PythonAdapter()
    adapter.parse(source_code)
    conditions = adapter.analyze(source_code)
    unsupported = find_unsupported_constructs(source_code)
    unsupported_note = _describe_unsupported(unsupported)

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
                "covered": 0,
                "total": 0,
                "percentage": 0.0,
                "success": True,
                "error": None,
                "branches": [],
                "branch_coverage_percent": 0.0,
                "unsupported": unsupported,
            },
            "message": _join_messages(
                "No supported conditions were detected; "
                "no targeted tests were generated.",
                unsupported_note,
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

    targeted_cases = generate_targeted_inputs(
        condition_data,
        max_cases=max_cases,
    )

    input_cases: list[TestCase] = [
        TestCase(
            inputs=inputs,
            description="Boundary/targeted test",
        )
        for inputs in targeted_cases
    ]

    variable_names = list(
        dict.fromkeys(condition.variable for condition in conditions)
    )

    if include_invalid_inputs:
        remaining = max_cases - len(input_cases)

        if remaining > 0:
            invalid_cases = generate_invalid_inputs(
                variable_names,
                max_cases=remaining,
            )

            input_cases.extend(
                TestCase(
                    inputs=case,
                    description="Invalid-input candidate",
                )
                for case in invalid_cases
            )

    if include_fuzz_inputs:
        remaining = max_cases - len(input_cases)

        if remaining > 0:
            fuzz_cases = generate_fuzz_inputs(
                variable_names,
                max_cases=remaining,
            )

            input_cases.extend(
                TestCase(
                    inputs=case,
                    description="Fuzz test candidate",
                )
                for case in fuzz_cases
            )

    results: list[TestResult] = [
        adapter.execute(source_code, test_case)
        for test_case in input_cases
    ]

    coverage = analyze_branch_coverage(
        source_code,
        [test_case.inputs for test_case in input_cases],
    )
    coverage["unsupported"] = unsupported

    if not input_cases:
        base_message = (
            "No usable test inputs could be generated. "
            "Supported conditions or input variables may be required."
        )
    else:
        base_message = None

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
        "message": _join_messages(base_message, unsupported_note),
    }