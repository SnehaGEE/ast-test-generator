"""Condition extraction shared by the Tree-sitter (Java and C) adapters."""

from typing import Any, Callable

from src.core.models import Condition
from src.languages.input_plan import node_text

SUPPORTED_OPERATORS = {">", ">=", "<", "<=", "==", "!="}

# `5 < x` means `x > 5`.
REVERSED_OPERATORS = {
    ">": "<",
    ">=": "<=",
    "<": ">",
    "<=": ">=",
    "==": "==",
    "!=": "!=",
}

# Statements whose condition decides a branch. Both grammars name the
# condition field "condition".
CONDITION_STATEMENTS = {"if_statement", "while_statement", "do_statement"}


def extract_conditions(
    root,
    source_bytes: bytes,
    language: str,
    numeric_value: Callable[[Any], Any],
) -> list[Condition]:
    """Find `name <op> number` and `number <op> name` comparisons.

    numeric_value(node) returns the literal's value, or None when the node
    is not a supported numeric literal.
    """
    conditions: list[Condition] = []

    def add(name_node, operator, value, node):
        conditions.append(
            Condition(
                variable=node_text(name_node, source_bytes),
                operator=operator,
                value=value,
                line=node.start_point.row + 1,
                language=language,
            )
        )

    def comparisons(node):
        if node.type == "binary_expression":
            operator_node = node.child_by_field_name("operator")
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")

            if operator_node is not None and left is not None and right is not None:
                operator = node_text(operator_node, source_bytes)

                if operator in SUPPORTED_OPERATORS:
                    if left.type == "identifier":
                        value = numeric_value(right)
                        if value is not None:
                            add(left, operator, value, node)
                            return
                    elif right.type == "identifier":
                        value = numeric_value(left)
                        if value is not None:
                            add(right, REVERSED_OPERATORS[operator], value, node)
                            return

        # &&, ||, !, parentheses: look inside for more comparisons.
        for child in node.named_children:
            comparisons(child)

    def visit(node):
        if node.type in CONDITION_STATEMENTS:
            condition = node.child_by_field_name("condition")
            if condition is not None:
                comparisons(condition)

        for child in node.children:
            visit(child)

    visit(root)
    return conditions
