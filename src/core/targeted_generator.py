
from typing import Any

from src.core.input_combinations import generate_input_combinations
from src.parser.analyzer.generator.test_generator import generate_boundary_tests


def generate_targeted_inputs(
    conditions: list[dict[str, Any]],
    max_cases: int = 100,
) -> list[dict[str, Any]]:
    """Generate bounded combinations of values derived from conditions."""

    variable_values: dict[str, list[Any]] = {}

    for condition in conditions:
        variable = condition["variable"]
        candidates = generate_boundary_tests(condition)

        if not candidates:
            continue

        existing = variable_values.setdefault(variable, [])

        for candidate in candidates:
            if candidate not in existing:
                existing.append(candidate)

    return generate_input_combinations(variable_values, max_cases)
