def generate_boundary_tests(condition):
    """Generate test values around a detected numeric boundary."""

    constant = condition["constant"]

    if isinstance(constant, bool) or not isinstance(constant, (int, float)):
        return []

    return [constant - 1, constant, constant + 1]