
from src.core.models import TestResult


def classify_execution(result: TestResult) -> str:
    """Classify an execution outcome using its status and error message."""

    if result.executed:
        return "executed"

    error = (result.error or "").lower()

    if "timed out" in error or "timeout" in error:
        return "timeout"

    if "invalid python syntax" in error:
        return "syntax_error"

    if "valueerror" in error or "typeerror" in error:
        return "invalid_input_error"

    if "eoferror" in error:
        return "missing_input_error"

    if error:
        return "execution_error"

    return "unknown"


def verify_output(
    result: TestResult,
    expected_output: str,
) -> TestResult:
    """Compare actual program output with an expected output."""

    result.expected_output = expected_output

    if not result.executed:
        result.correctness = classify_execution(result)
    elif result.output.rstrip() == expected_output.rstrip():
        result.correctness = "passed"
    else:
        result.correctness = "failed"

    return result
