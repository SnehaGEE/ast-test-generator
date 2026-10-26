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

# C: switch_statement; Java: switch_expression (statement or expression).
SWITCH_STATEMENTS = {"switch_statement", "switch_expression"}


def _case_values(body):
    """The value nodes of a switch body's case labels, in order.

    C: `case 2:` (case_statement.value). Java: `case 2:` and `case 4, 5 ->`
    (switch_label children). `default` has no value. Nested switches are
    left to their own visit.
    """
    for child in body.named_children:
        if child.type == "case_statement":
            value = child.child_by_field_name("value")
            if value is not None:
                yield value
        elif child.type in {"switch_block_statement_group", "switch_rule"}:
            for label in child.named_children:
                if label.type == "switch_label":
                    yield from label.named_children


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

    def add(name_node, operator, value, line):
        conditions.append(
            Condition(
                variable=node_text(name_node, source_bytes),
                operator=operator,
                value=value,
                line=line,
                language=language,
            )
        )

    def comparisons(node, line):
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
                            add(left, operator, value, line)
                            return
                    elif right.type == "identifier":
                        value = numeric_value(left)
                        if value is not None:
                            add(right, REVERSED_OPERATORS[operator], value, line)
                            return

        # &&, ||, !, parentheses: look inside for more comparisons.
        for child in node.named_children:
            comparisons(child, line)

    def switch_cases(node):
        # `switch (choice) { case 2: ... }` means `choice == 2`.
        condition = node.child_by_field_name("condition")
        body = node.child_by_field_name("body")
        subjects = [
            child
            for child in (condition.named_children if condition else [])
            if child.type != "comment"
        ]
        if body is None or len(subjects) != 1 or subjects[0].type != "identifier":
            return

        for value_node in _case_values(body):
            value = numeric_value(value_node)
            if value is not None:
                add(subjects[0], "==", value, value_node.start_point.row + 1)

    def visit(node):
        if node.type in CONDITION_STATEMENTS:
            condition = node.child_by_field_name("condition")
            if condition is not None:
                # Like Python, report the statement's line, which is
                # also the line its branch coverage is reported on.
                comparisons(condition, node.start_point.row + 1)
        elif node.type in SWITCH_STATEMENTS:
            switch_cases(node)

        for child in node.children:
            visit(child)

    visit(root)
    return conditions
