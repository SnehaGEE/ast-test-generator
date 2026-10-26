"""Which answers a Python program's input() calls receive.

Generated inputs are keyed by variable name, but input() hands out values
by position. The program is turned into a read map (src/core/read_paths)
so each test answers exactly the reads on the path its values take:
`match choice:` and `if choice == 2:` pick their branch, calls to
functions defined in the program contribute their reads at the call, and
reads with no generated value get a placeholder of their kind.
"""

import ast
from functools import lru_cache
from typing import Any

from src.core.read_paths import (
    Branch,
    Case,
    Read,
    Switch,
    answers,
    name_single_read,
)
from src.parser.analyzer.condition_analyzer import (
    OPERATOR_SYMBOLS,
    REVERSED_OPERATORS,
    _as_constant,
    _match_values,
)


def _is_input(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "input"
    )


def _number(node: ast.expr):
    node = _as_constant(node)
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ):
        return node.value
    return None


def _simple_comparison(test: ast.expr):
    """(name, operator, number) for `name op number` or `number op name`."""
    if not isinstance(test, ast.Compare) or len(test.ops) != 1:
        return None

    operator = OPERATOR_SYMBOLS.get(type(test.ops[0]))
    left, right = test.left, test.comparators[0]

    if isinstance(left, ast.Name) and _number(right) is not None:
        return left.id, operator, _number(right)
    if isinstance(right, ast.Name) and _number(left) is not None:
        return right.id, REVERSED_OPERATORS.get(operator), _number(left)
    return None


class _ReadMap:
    """Build the read map of a module, starting at its top-level code."""

    def __init__(self, tree: ast.Module) -> None:
        self.functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

    def block(self, statements, stack) -> list:
        items: list = []
        for statement in statements:
            items += self.statement(statement, stack)
        return items

    def statement(self, node: ast.stmt, stack) -> list:
        # Function and class bodies run only when called.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return []

        if isinstance(node, ast.If):
            condition = self.expression(node.test, stack)
            then = self.block(node.body, stack)
            otherwise = self.block(node.orelse, stack)
            simple = _simple_comparison(node.test)
            if simple is not None and simple[1] is not None:
                return condition + [Branch(*simple, then, otherwise)]
            return condition + then + otherwise

        if isinstance(node, ast.Match):
            subject = self.expression(node.subject, stack)
            if not isinstance(node.subject, ast.Name):
                return subject + [
                    item for case in node.cases for item in self.block(case.body, stack)
                ]
            cases = []
            for case in node.cases:
                pattern = case.pattern
                if isinstance(pattern, ast.MatchAs) and pattern.pattern is None:
                    values = None  # `case _:` or `case name:` matches anything
                else:
                    values = [
                        value
                        for value in map(_number, _match_values(pattern))
                        if value is not None
                    ]
                cases.append(Case(values, self.block(case.body, stack)))
            return subject + [Switch(node.subject.id, cases)]

        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            if node.value is None:
                return []
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            name = (
                targets[0].id
                if len(targets) == 1 and isinstance(targets[0], ast.Name)
                else None
            )
            return name_single_read(self.expression(node.value, stack), name)

        return self.children(node, stack)

    def expression(self, node: ast.AST, stack) -> list:
        if isinstance(node, ast.Call):
            # int(input()) / float(input()): one read of that kind.
            if (
                isinstance(node.func, ast.Name)
                and node.func.id in {"int", "float"}
                and len(node.args) == 1
                and _is_input(node.args[0])
            ):
                return self.children(node.args[0], stack) + [Read(None, node.func.id)]

            if _is_input(node):
                return self.children(node, stack) + [Read(None, "str")]

            items = self.children(node, stack)
            if (
                isinstance(node.func, ast.Name)
                and node.func.id in self.functions
                and node.func.id not in stack
            ):
                function = self.functions[node.func.id]
                items += self.block(function.body, stack | {node.func.id})
            return items

        return self.children(node, stack)

    def children(self, node: ast.AST, stack) -> list:
        items: list = []
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.stmt):
                items += self.statement(child, stack)
            else:
                items += self.expression(child, stack)
        return items


@lru_cache(maxsize=64)
def python_read_map(source_code: str) -> tuple:
    """The read map of a Python program (empty if it does not parse)."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return ()
    builder = _ReadMap(tree)
    return tuple(builder.block(tree.body, frozenset()))


def python_answers(source_code: str, inputs: dict[str, Any]) -> list[str]:
    """The answers a Python program's input() calls receive, in order."""
    return answers(list(python_read_map(source_code)), inputs)
