
import random
import string
from typing import Any


def generate_fuzz_inputs(
    variable_names: list[str],
    max_cases: int = 20,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Generate reproducible unusual inputs for basic fuzz testing."""

    if max_cases < 1:
        raise ValueError("max_cases must be at least 1")

    if not variable_names:
        return []

    rng = random.Random(seed)
    candidates: list[Any] = [
        0,
        -1,
        1,
        10**100,
        -10**100,
        "",
        " ",
        "null",
        "None",
        "true",
        "false",
        "@#$%",
        "A" * 256,
    ]

    cases: list[dict[str, Any]] = []

    for _ in range(max_cases):
        variable = rng.choice(variable_names)

        if rng.random() < 0.7:
            value = rng.choice(candidates)
        else:
            value = "".join(
                rng.choice(string.printable)
                for _ in range(rng.randint(1, 32))
            )

        cases.append({variable: value})

    return cases
