def generate_boundary_tests(condition):
    """Generate test values around a detected boundary."""

    constant = condition["constant"]
    operator = condition["operator"]

    if not isinstance(constant, (int, float)):
        return []

    if operator in ["Gt", "GtE", "Lt", "LtE", "Eq", "NotEq"]:
        return [constant - 1, constant, constant + 1]

    return []


if __name__ == "__main__":
    condition = {
        "variable": "age",
        "operator": "GtE",
        "constant": 18,
        "line": 3
    }

    tests = generate_boundary_tests(condition)

    print("Generated test cases:")

    for test in tests:
        print(test)