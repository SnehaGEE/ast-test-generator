
import ast
from typing import Any


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

REVERSED_OPERATORS = {
    ">": "<",
    ">=": "<=",
    "<": ">",
    "<=": ">=",
    "==": "==",
    "!=": "!=",
    "is": "is",
    "is not": "is not",
    "in": "not in",
    "not in": "in",
}


class ConditionAnalyzer(ast.NodeVisitor):
    """Find supported variable-to-constant comparisons in Python."""

    def __init__(self) -> None:
        self.conditions: list[dict[str, Any]] = []
        self._seen: set[tuple[Any, ...]] = set()

    def visit_If(self, node: ast.If) -> None:
        self._extract_comparisons(node.test, node.lineno)
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self._extract_comparisons(node.test, node.lineno)
        self.generic_visit(node)

    def _add_condition(
        self,
        variable: str,
        operator: str,
        constant: Any,
        line: int,
    ) -> None:
        key = (variable, operator, repr(constant), line)

        if key in self._seen:
            return

        self._seen.add(key)
        self.conditions.append(
            {
                "variable": variable,
                "operator": operator,
                "constant": constant,
                "line": line,
            }
        )

    def _extract_comparisons(
        self,
        expression: ast.expr,
        line: int,
    ) -> None:
        """Extract supported comparisons, including reversed operands."""

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
                self._add_condition(
                    left.id, operator, right.value, line
                )

            elif (
                isinstance(left, ast.Constant)
                and isinstance(right, ast.Name)
            ):
                reversed_operator = REVERSED_OPERATORS.get(operator)

                if reversed_operator is not None:
                    self._add_condition(
                        right.id,
                        reversed_operator,
                        left.value,
                        line,
                    )

            left = right


def analyze_source(source_code: str) -> list[dict[str, Any]]:
    """Parse Python source and return detected conditions."""
    tree = ast.parse(source_code)
    analyzer = ConditionAnalyzer()
    analyzer.visit(tree)
    return analyzer.conditions
