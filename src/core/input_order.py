"""Decide which generated value a program receives in which position.

Generated inputs are keyed by variable name, but programs read values by
position: the n-th input() / scanf / Scanner call, or argv[n]. These
helpers put values in the order the program actually reads them.
"""

import ast
from typing import Any


def reorder(inputs: dict[str, Any], read_order: list[str]) -> dict[str, Any]:
    """Return inputs with the names in read_order first, in that order.

    Names the program was not seen reading keep their original order
    after the others.
    """
    names = [name for name in read_order if name in inputs]
    names += [name for name in inputs if name not in names]
    return {name: inputs[name] for name in names}


def _calls_input(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == "input"
        for child in ast.walk(node)
    )


def python_read_order(source_code: str) -> list[str]:
    """Names assigned from input() calls, in source order."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    found: list[tuple[int, int, str]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        else:
            continue

        if not _calls_input(node.value):
            continue

        for target in targets:
            if isinstance(target, ast.Name):
                found.append((node.lineno, node.col_offset, target.id))

    return list(dict.fromkeys(name for _, _, name in sorted(found)))
