from src.core.models import TestCase, TestResult
from src.core.targeted_generator import generate_targeted_inputs
from src.languages.c.adapter import CAdapter


def run_c_test_suite(
    source_code: str,
    max_cases: int = 100,
) -> list[TestResult]:
    """Generate boundary tests and execute them against C source."""

    adapter = CAdapter()
    conditions = adapter.analyze(source_code)

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
            description="AST-derived C boundary test",
        )
        for inputs in input_cases
    ]

    return adapter.execute_many(source_code, test_cases)
