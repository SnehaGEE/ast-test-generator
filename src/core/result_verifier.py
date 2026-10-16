
from src.core.models import TestResult


def verify_output(
    result: TestResult,
    expected_output: str,
) -> TestResult:
    """Compare actual program output with an expected output."""

    result.expected_output = expected_output

    if not result.executed:
        result.correctness = "execution_error"
    elif result.output.rstrip() == expected_output.rstrip():
        result.correctness = "passed"
    else:
        result.correctness = "failed"

    return result
