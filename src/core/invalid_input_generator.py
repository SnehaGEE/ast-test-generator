
from typing import Any


def generate_invalid_inputs(
    variable_names: list[str],
    max_cases: int = 20,
) -> list[dict[str, Any]]:
    """Generate candidate invalid inputs for robustness testing."""

    if max_cases < 1:
        raise ValueError("max_cases must be at least 1")

    candidates: list[Any] = [
        "garbage",
        "",
        "@#$%",
        " ",
        None,
        "999999999999999999999999999999999999",
    ]

    cases: list[dict[str, Any]] = []

    for variable in variable_names:
        for value in candidates:
            cases.append({variable: value})

            if len(cases) >= max_cases:
                return cases

    return cases
