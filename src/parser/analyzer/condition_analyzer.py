
import ast


OPERATOR_SYMBOLS = {
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Eq: "==",
    ast.NotEq: "!=",
    ast.Is: "is",
    ast.IsNot: "is not",
    ast.In: "in",
    ast.NotIn: "not in",
}


class ConditionAnalyzer(ast.NodeVisitor):
    """Find comparison conditions in Python if statements."""

    def __init__(self):
        self.conditions = []

    def visit_If(self, node):
        self._extract_comparisons(node.test, node.lineno)
        self.generic_visit(node)

    def _extract_comparisons(self, expression, line):
        """Extract supported variable-to-constant comparisons."""
        if isinstance(expression, ast.BoolOp):
            for value in expression.values:
                self._extract_comparisons(value, line)
            return

        if not isinstance(expression, ast.Compare):
            return

        left = expression.left

        for operator_node, right in zip(
            expression.ops, expression.comparators
        ):
            operator = OPERATOR_SYMBOLS.get(type(operator_node))

            if operator is None:
                left = right
                continue

            if isinstance(left, ast.Name) and isinstance(right, ast.Constant):
                self.conditions.append({
                    "variable": left.id,
                    "operator": operator,
                    "constant": right.value,
                    "line": line,
                })

            left = right


def analyze_source(source_code):
    """Parse Python source and return detected conditions."""
    tree = ast.parse(source_code)
    analyzer = ConditionAnalyzer()
    analyzer.visit(tree)
    return analyzer.conditions
