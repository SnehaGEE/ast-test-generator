"""Decide which generated value a program receives in which position.

Generated inputs are keyed by variable name, but programs read values by
position: the n-th input() / scanf / Scanner call, or argv[n]. These
helpers put values in the order the program actually reads them, and give
a placeholder to reads that no condition mentions (a name, an id), so the
values after them still reach the right variable.
"""

import ast
from typing import Any

# Placeholder answer for a read whose variable has no generated value.
FILLERS = {"int": "1", "float": "1.0", "str": "test", "bool": "true"}


def answer_inputs(
    inputs: dict[str, Any],
    read_order: list[str],
    kinds: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Return one answer per read, in read order.

    Variables the program reads come first, in that order; a read with no
    generated value gets a placeholder of its kind. Generated values the
    program was not seen reading follow in their original order.
    """
    kinds = kinds or {}
    answers: dict[str, Any] = {}

    for name in read_order:
        if name in inputs:
            answers[name] = inputs[name]
        else:
            answers[name] = FILLERS.get(kinds.get(name, "int"), FILLERS["int"])

    for name, value in inputs.items():
        if name not in answers:
            answers[name] = value

    return answers


def _input_call(node: ast.AST) -> ast.Call | None:
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "input"
        ):
            return child
    return None


def _python_kind(value: ast.AST) -> str:
    """int(input()) -> "int", float(input()) -> "float", else "str"."""
    if (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id in {"int", "float"}
    ):
        return value.func.id
    return "str"


def python_reads(source_code: str) -> tuple[list[str], dict[str, str]]:
    """Names assigned from input() calls, in source order, and their kinds."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return [], {}

    found: list[tuple[int, int, str, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        else:
            continue

        if _input_call(node.value) is None:
            continue

        for target in targets:
            if isinstance(target, ast.Name):
                found.append(
                    (
                        node.lineno,
                        node.col_offset,
                        target.id,
                        _python_kind(node.value),
                    )
                )

    order: list[str] = []
    kinds: dict[str, str] = {}
    for _, _, name, kind in sorted(found):
        if name not in kinds:
            order.append(name)
            kinds[name] = kind
    return order, kinds


def python_answers(source_code: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """The values a Python program's input() calls receive, in order."""
    order, kinds = python_reads(source_code)
    return answer_inputs(inputs, order, kinds)
