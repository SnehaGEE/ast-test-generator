"""Fault detection by mutation testing.

At every `variable op number` comparison in an if/while/do condition,
three boundary bugs are injected, one per mutant:

    the operator off by one   >  <->  >=,   <  <->  <=,   ==  <->  !=
    the constant plus one     age >= 18  ->  age >= 19
    the constant minus one    age >= 18  ->  age >= 17

A test suite kills a mutant when some test's result (whether it ran
cleanly, its output, the first line of any error) differs from the
original program's. The mutation score is killed / mutants, the share of
injected faults the suite detects. switch/match case labels are not
mutated: changing one can duplicate another label.
"""

import ast
from dataclasses import dataclass
from typing import Any

from src.core.models import TestCase
from src.languages.input_plan import node_text
from src.languages.tree_sitter_conditions import CONDITION_STATEMENTS
from src.parser.analyzer.condition_analyzer import OPERATOR_SYMBOLS, _as_constant

OFF_BY_ONE = {">": ">=", ">=": ">", "<": "<=", "<=": "<", "==": "!=", "!=": "=="}


@dataclass
class Mutant:
    description: str
    line: int
    source: str


@dataclass
class _Site:
    """A comparison's operator and constant, as byte spans."""

    line: int
    operator: str
    operator_start: int
    operator_end: int
    value: Any
    constant_start: int
    constant_end: int


def _numeric(node: ast.expr):
    node = _as_constant(node)
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ):
        return node.value
    return None


def _python_sites(source_bytes: bytes) -> list[_Site]:
    line_starts = [0]
    for line in source_bytes.splitlines(keepends=True):
        line_starts.append(line_starts[-1] + len(line))

    def offset(line: int, column: int) -> int:  # ast columns are UTF-8 bytes
        return line_starts[line - 1] + column

    sites = []
    for statement in ast.walk(ast.parse(source_bytes)):
        if not isinstance(statement, (ast.If, ast.While)):
            continue
        for node in ast.walk(statement.test):
            if not isinstance(node, ast.Compare) or len(node.ops) != 1:
                continue
            operator = OPERATOR_SYMBOLS.get(type(node.ops[0]))
            left, right = node.left, node.comparators[0]
            if operator not in OFF_BY_ONE:
                continue
            if isinstance(left, ast.Name) and _numeric(right) is not None:
                constant = right
            elif isinstance(right, ast.Name) and _numeric(left) is not None:
                constant = left
            else:
                continue

            between_start = offset(left.end_lineno, left.end_col_offset)
            between_end = offset(right.lineno, right.col_offset)
            found = source_bytes.find(operator.encode(), between_start, between_end)
            if found < 0:
                continue
            sites.append(
                _Site(
                    statement.lineno,
                    operator,
                    found,
                    found + len(operator),
                    _numeric(constant),
                    offset(constant.lineno, constant.col_offset),
                    offset(constant.end_lineno, constant.end_col_offset),
                )
            )
    return sites


def _tree_sitter_sites(source_bytes: bytes, language: str) -> list[_Site]:
    if language == "c":
        from src.languages.c.adapter import CAdapter, _numeric_value

        parser = CAdapter().parser
    else:
        from src.languages.java.adapter import JavaAdapter, _numeric_value

        parser = JavaAdapter().parser

    sites = []

    def comparisons(node, line):
        if node.type == "binary_expression":
            operator_node = node.child_by_field_name("operator")
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if operator_node is not None and left is not None and right is not None:
                operator = node_text(operator_node, source_bytes)
                constant = None
                if operator in OFF_BY_ONE:
                    if left.type == "identifier" and _numeric_value(right, source_bytes) is not None:
                        constant = right
                    elif right.type == "identifier" and _numeric_value(left, source_bytes) is not None:
                        constant = left
                if constant is not None:
                    sites.append(
                        _Site(
                            line,
                            operator,
                            operator_node.start_byte,
                            operator_node.end_byte,
                            _numeric_value(constant, source_bytes),
                            constant.start_byte,
                            constant.end_byte,
                        )
                    )
                    return
        for child in node.named_children:
            comparisons(child, line)

    def visit(node):
        if node.type in CONDITION_STATEMENTS:
            condition = node.child_by_field_name("condition")
            if condition is not None:
                comparisons(condition, node.start_point.row + 1)
        for child in node.children:
            visit(child)

    visit(parser.parse(source_bytes).root_node)
    return sites


def _replace(source_bytes: bytes, start: int, end: int, text: str) -> str:
    return (source_bytes[:start] + text.encode() + source_bytes[end:]).decode("utf-8")


def _number_text(value) -> str:
    return str(value) if isinstance(value, int) else repr(float(value))


def generate_mutants(source_code: str, language: str) -> list[Mutant]:
    """Three boundary mutants per comparison, in source order."""
    source_bytes = source_code.encode("utf-8")
    sites = (
        _python_sites(source_bytes)
        if language == "python"
        else _tree_sitter_sites(source_bytes, language)
    )
    sites.sort(key=lambda site: site.operator_start)

    mutants = []
    for site in sites:
        swapped = OFF_BY_ONE[site.operator]
        mutants.append(
            Mutant(
                f"line {site.line}: {site.operator} -> {swapped}",
                site.line,
                _replace(source_bytes, site.operator_start, site.operator_end, swapped),
            )
        )
        for delta in (1, -1):
            new_value = site.value + delta
            mutants.append(
                Mutant(
                    f"line {site.line}: {site.value} -> {new_value}",
                    site.line,
                    _replace(
                        source_bytes,
                        site.constant_start,
                        site.constant_end,
                        _number_text(new_value),
                    ),
                )
            )
    return mutants


def _key(inputs: dict[str, Any]) -> str:
    return repr(sorted(inputs.items(), key=lambda item: item[0]))


def _signature(result) -> tuple:
    error = (result.error or "").strip()
    return (
        result.executed,
        (result.output or "").strip(),
        error.splitlines()[0] if error else "",
    )


def _run_all(source_code: str, language: str, inputs: list[dict[str, Any]]):
    """Signature per input key, or None if the program does not build."""
    cases = [TestCase(inputs=row) for row in inputs]
    if language == "python":
        from src.languages.python.adapter import PythonAdapter

        adapter = PythonAdapter()
        return {_key(case.inputs): _signature(adapter.execute(source_code, case)) for case in cases}

    if language == "c":
        from src.languages.c.adapter import CAdapter as Adapter
    else:
        from src.languages.java.adapter import JavaAdapter as Adapter

    with Adapter().compile(source_code) as program:
        if program.error is not None:
            return None
        return {_key(case.inputs): _signature(program.run(case)[0]) for case in cases}


def mutation_scores(
    source_code: str,
    language: str,
    suites: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Run every mutant on every suite's inputs; count kills per suite.

    Each mutant is built once and runs the union of all suites' inputs.
    Mutants that do not compile ("stillborn") are reported, not scored.
    """
    unique = {}
    for rows in suites.values():
        for row in rows:
            unique.setdefault(_key(row), row)
    all_inputs = list(unique.values())

    original = _run_all(source_code, language, all_inputs)
    if original is None:
        raise ValueError("The original program does not build.")

    mutants = generate_mutants(source_code, language)
    killed = {name: 0 for name in suites}
    details = []
    stillborn = 0

    for mutant in mutants:
        observed = _run_all(mutant.source, language, all_inputs)
        if observed is None:
            stillborn += 1
            details.append({"mutant": mutant.description, "stillborn": True})
            continue
        killed_by = []
        for name, rows in suites.items():
            if any(observed[_key(row)] != original[_key(row)] for row in rows):
                killed[name] += 1
                killed_by.append(name)
        details.append({"mutant": mutant.description, "killed_by": killed_by})

    total = len(mutants) - stillborn
    return {
        "total": total,
        "stillborn": stillborn,
        "mutants": details,
        "suites": {
            name: {
                "killed": killed[name],
                "score": round(killed[name] / total * 100, 2) if total else None,
            }
            for name in suites
        },
    }
