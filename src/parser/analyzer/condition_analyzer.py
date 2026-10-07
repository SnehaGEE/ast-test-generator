import ast


class ConditionAnalyzer(ast.NodeVisitor):
    """Find conditional statements and extract their conditions."""

    def __init__(self):
        self.conditions = []

    def visit_If(self, node):
        condition = node.test

        if (
            isinstance(condition, ast.Compare)
            and isinstance(condition.left, ast.Name)
            and len(condition.ops) == 1
            and len(condition.comparators) == 1
            and isinstance(condition.comparators[0], ast.Constant)
        ):
            variable = condition.left.id
            operator = type(condition.ops[0]).__name__
            constant = condition.comparators[0].value

            self.conditions.append({
                "variable": variable,
                "operator": operator,
                "constant": constant,
                "line": node.lineno
            })

        self.generic_visit(node)


def analyze_source(source_code):
    """Parse Python source code and return detected conditions."""
    tree = ast.parse(source_code)

    analyzer = ConditionAnalyzer()
    analyzer.visit(tree)

    return analyzer.conditions


if __name__ == "__main__":
    sample_code = """
def check_age(age):
    if age >= 18:
        return "Adult"
    else:
        return "Minor"
"""

    conditions = analyze_source(sample_code)

    for condition in conditions:
        print(f"Variable : {condition['variable']}")
        print(f"Operator : {condition['operator']}")
        print(f"Constant : {condition['constant']}")
        print(f"Line     : {condition['line']}")