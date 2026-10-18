
from itertools import product
from typing import Any


def generate_input_combinations(
    variable_values: dict[str, list[Any]],
    max_cases: int = 100,
) -> list[dict[str, Any]]:
    """Generate bounded combinations of candidate values for each variable."""

    if max_cases < 1:
        raise ValueError("max_cases must be at least 1")

    if not variable_values:
        return [{}]

    variables = list(variable_values)
    value_lists = [list(dict.fromkeys(variable_values[name])) for name in variables]

    if any(not values for values in value_lists):
        return []

    combinations = []

    for values in product(*value_lists):
        combinations.append(dict(zip(variables, values)))

        if len(combinations) >= max_cases:
            break

    return combinations
