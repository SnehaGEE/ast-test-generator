
import random
import string
from typing import Any


def generate_fuzz_inputs(
    variable_names: list[str],
    max_cases: int = 20,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Generate reproducible, varied fuzz inputs with minimal duplicates."""

    if max_cases < 1:
        raise ValueError("max_cases must be at least 1")

    if not variable_names:
        return []

    rng = random.Random(seed)

    candidates: list[Any] = [
        0,
        -1,
        1,
        10,
        -10,
        10**100,
        -(10**100),
        "",
        " ",
        "null",
        "None",
        "true",
        "false",
        "@#$%",
        "A" * 256,
        "\n",
        "\r",
        "0",
        "1.5",
        "-999999",
    ]

    cases: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    # Shuffle candidate values to keep runs reproducible but varied.
    rng.shuffle(candidates)

    # Try candidate values first, avoiding duplicate variable/value pairs.
    for value in candidates:
        if len(cases) >= max_cases:
            break

        variable = rng.choice(variable_names)
        key = (variable, repr(value))

        if key in seen:
            continue

        seen.add(key)
        cases.append({variable: value})

    # Fill remaining slots with random printable strings.
    attempts = 0
    max_attempts = max_cases * 20

    while len(cases) < max_cases and attempts < max_attempts:
        attempts += 1
        variable = rng.choice(variable_names)

        value = "".join(
            rng.choice(string.printable)
            for _ in range(rng.randint(1, 32))
        )

        key = (variable, repr(value))

        if key in seen:
            continue

        seen.add(key)
        cases.append({variable: value})

    return cases
