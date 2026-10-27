"""Random test generation: the baseline BranchLab is compared against."""

import random
from typing import Any

RANDOM_LOW = -1000
RANDOM_HIGH = 1000


def random_inputs(
    variable_names: list[str],
    count: int,
    seed: int,
    low: int = RANDOM_LOW,
    high: int = RANDOM_HIGH,
) -> list[dict[str, Any]]:
    """count input rows of uniform random integers, reproducible per seed.

    It knows the same input variables as the AST-targeted generator, but
    not the conditions they are compared against.
    """
    rng = random.Random(seed)
    return [
        {name: rng.randint(low, high) for name in variable_names}
        for _ in range(count)
    ]
