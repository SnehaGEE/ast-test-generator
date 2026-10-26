
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
    # "constant in name" tests membership in name, so it has no reversed
    # form; it is left out on purpose.
}


def _as_constant(node: ast.expr) -> ast.expr:
    """Fold a signed numeric literal such as -5 into an ast.Constant."""
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.USub, ast.UAdd))
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, (int, float))
        and not isinstance(node.operand.value, bool)
    ):
        value = node.operand.value
        return ast.Constant(-value if isinstance(node.op, ast.USub) else value)

    return node


def _match_values(pattern: ast.pattern) -> list[ast.expr]:
    """Literal values a case pattern compares against: `case 2 | 3:`."""
    if isinstance(pattern, ast.MatchValue):
        return [pattern.value]
    if isinstance(pattern, ast.MatchOr):
        return [
            value
            for option in pattern.patterns
            for value in _match_values(option)
        ]
    return []


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

    def visit_Match(self, node: ast.Match) -> None:
        # `match choice: case 2:` means `choice == 2`.
        if isinstance(node.subject, ast.Name):
            for case in node.cases:
                for value in _match_values(case.pattern):
                    constant = _as_constant(value)
                    if isinstance(constant, ast.Constant):
                        self._add_condition(
                            node.subject.id,
                            "==",
                            constant.value,
                            case.pattern.lineno,
                        )
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

        if isinstance(expression, ast.UnaryOp) and isinstance(
            expression.op, ast.Not
        ):
            self._extract_comparisons(expression.operand, line)
            return

        if not isinstance(expression, ast.Compare):
            return

        left = _as_constant(expression.left)

        for operator_node, right in zip(
            expression.ops, expression.comparators
        ):
            right = _as_constant(right)
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
