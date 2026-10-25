import ast
from typing import Any

_COMPREHENSIONS = (
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)


def find_unsupported_constructs(source_code: str) -> list[dict[str, Any]]:
    """List branch-like constructs that branch coverage does not track.

    Branch coverage currently measures only if/elif and while conditions.
    These constructs run normally but are excluded from the percentage.
    """
    tree = ast.parse(source_code)
    found: list[dict[str, Any]] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Match):
            construct = "match/case statement"
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            construct = "for loop"
        elif isinstance(node, ast.IfExp):
            construct = "conditional expression"
        elif isinstance(node, _COMPREHENSIONS) and any(
            generator.ifs for generator in node.generators
        ):
            construct = "comprehension filter"
        else:
            continue

        found.append({"line": node.lineno, "construct": construct})

    return sorted(found, key=lambda item: (item["line"], item["construct"]))