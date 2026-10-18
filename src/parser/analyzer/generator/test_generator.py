
import math


def generate_boundary_tests(condition):
    """Generate candidate values around a supported numeric condition."""

    constant = condition.get("constant")
    operator = condition.get("operator")

    # Booleans are integers in Python, but aren't numeric boundaries here.
    if isinstance(constant, bool) or not isinstance(constant, (int, float)):
        return []

    if isinstance(constant, float) and not math.isfinite(constant):
        return []

    if operator not in {">", ">=", "<", "<=", "==", "!="}:
        return []

    # Integer boundaries use adjacent integers.
    # Floating-point boundaries use the nearest representable values.
    if isinstance(constant, int):
        below = constant - 1
        above = constant + 1
    else:
        below = math.nextafter(constant, -math.inf)
        above = math.nextafter(constant, math.inf)

    candidates_by_operator = {
        ">": [constant, above, below],
        ">=": [below, constant, above],
        "<": [constant, below, above],
        "<=": [above, constant, below],
        "==": [below, constant, above],
        "!=": [constant, below, above],
    }

    # Preserve candidate order while removing duplicates.
    return list(dict.fromkeys(candidates_by_operator[operator]))
