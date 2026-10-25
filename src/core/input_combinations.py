from itertools import product
from math import prod
from typing import Any


def _decode(index: int, sizes: list[int]) -> tuple[int, ...]:
    """Turn a product-order index into one position per variable."""
    digits = []
    for size in reversed(sizes):
        index, digit = divmod(index, size)
        digits.append(digit)
    return tuple(reversed(digits))


def _select_rows(
    sizes: list[int],
    max_cases: int,
) -> list[tuple[int, ...]]:
    """Choose up to max_cases rows from a product too large to enumerate.

    Plain product order changes only the last variable first, so a small
    cap would leave the first variables stuck at their first value.
    Rows are chosen in this priority order instead:

    1. Diagonal rows: every variable at its k-th value.
    2. One-variable-at-a-time rows from each diagonal row. The second
       diagonal comes first because the boundary generator lists a value
       that satisfies the condition second for every operator, so that
       row reaches nested branches and each variation flips one of them.
    3. Evenly spaced rows from the full product for any remaining slots.
    """
    selected: list[tuple[int, ...]] = []
    seen: set[tuple[int, ...]] = set()

    def add(row: tuple[int, ...]) -> bool:
        """Add a row; return True while there is still room for more."""
        if row not in seen and len(selected) < max_cases:
            seen.add(row)
            selected.append(row)
        return len(selected) < max_cases

    width = max(sizes)

    for k in range(width):
        if not add(tuple(k % size for size in sizes)):
            return selected

    base_order = [1, 0] + list(range(2, width)) if width > 1 else [0]

    for k in base_order:
        base = tuple(k % size for size in sizes)
        for position, size in enumerate(sizes):
            for alternative in range(size):
                if alternative == base[position]:
                    continue
                row = (
                    base[:position]
                    + (alternative,)
                    + base[position + 1:]
                )
                if not add(row):
                    return selected

    total = prod(sizes)

    for slot in range(max_cases):
        if not add(_decode(slot * total // max_cases, sizes)):
            return selected

    # Evenly spaced rows can collide with earlier ones; fill the rest
    # in product order. total > max_cases, so this always completes.
    for index in range(total):
        if not add(_decode(index, sizes)):
            return selected

    return selected


def generate_input_combinations(
    variable_values: dict[str, list[Any]],
    max_cases: int = 100,
) -> list[dict[str, Any]]:
    """Generate bounded combinations of candidate values for each variable.

    If every combination fits within max_cases, all of them are returned
    in product order. Otherwise a spread of rows is chosen so that no
    variable is stuck at its first value (see _select_rows).
    """

    if max_cases < 1:
        raise ValueError("max_cases must be at least 1")

    if not variable_values:
        return [{}]

    variables = list(variable_values)
    value_lists = [list(dict.fromkeys(variable_values[name])) for name in variables]

    if any(not values for values in value_lists):
        return []

    sizes = [len(values) for values in value_lists]

    if prod(sizes) <= max_cases:
        return [
            dict(zip(variables, values))
            for values in product(*value_lists)
        ]

    return [
        {
            name: value_lists[position][digit]
            for position, (name, digit) in enumerate(zip(variables, row))
        }
        for row in _select_rows(sizes, max_cases)
    ]