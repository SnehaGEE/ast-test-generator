"""Branch coverage for Java and C by source instrumentation.

Python coverage traces the running program. Java and C cannot be traced
that way, so each `if`/`while` condition is wrapped in a probe call:

    if (x > 5)   ->   if (probe(3, (x > 5)))

The probe records whether condition 3 was true or false and returns the
value unchanged, so the program behaves exactly as before. Each outcome
is appended to a file the first time it happens, which keeps outcomes
reached before a crash, exit() or timeout.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from src.coverage.coverage_analyzer import summarize_statements

PROBE_FILE_VARIABLE = "BRANCHLAB_PROBE_FILE"

TRACKED_STATEMENTS = {"if_statement": "if", "while_statement": "while"}

UNTRACKED_CONSTRUCTS = {
    "for_statement": "for loop",
    "enhanced_for_statement": "for loop",
    "do_statement": "do-while loop",
    "switch_statement": "switch statement",
    "switch_expression": "switch statement",
    "conditional_expression": "conditional expression",
    "ternary_expression": "conditional expression",
}


@dataclass
class Branch:
    """One probed condition: byte span of the text inside its parentheses."""

    id: int
    line: int
    kind: str
    start: int
    end: int


def find_branches(root) -> list[Branch]:
    """Find if/while conditions, in source order, that can be probed."""
    found: list[tuple[int, int, int, str]] = []

    def visit(node):
        kind = TRACKED_STATEMENTS.get(node.type)
        if kind is not None:
            condition = node.child_by_field_name("condition")
            if (
                condition is not None
                and condition.type == "parenthesized_expression"
            ):
                found.append(
                    (
                        condition.start_byte + 1,
                        condition.end_byte - 1,
                        node.start_point.row + 1,
                        kind,
                    )
                )
        for child in node.children:
            visit(child)

    visit(root)

    # A condition nested inside another condition (for example inside a
    # lambda) would overlap its span; leave the inner one unprobed.
    branches: list[Branch] = []
    last_end = -1
    for start, end, line, kind in sorted(found):
        if start >= last_end:
            branches.append(Branch(len(branches), line, kind, start, end))
            last_end = end

    return branches


def find_untracked(root) -> list[dict[str, Any]]:
    """List branch-like constructs that coverage does not measure."""
    found: list[dict[str, Any]] = []

    def visit(node):
        construct = UNTRACKED_CONSTRUCTS.get(node.type)
        if construct is not None:
            found.append(
                {"line": node.start_point.row + 1, "construct": construct}
            )
        for child in node.children:
            visit(child)

    visit(root)
    return found


@dataclass
class Statement:
    """A statement to count: a probe goes before it, or around it (wrap)."""

    line: int
    start: int
    end: int
    wrap: bool = False


BLOCKS = {"compound_statement", "block"}
CASE_BODIES = {"case_statement", "switch_block_statement_group"}
NOT_STATEMENTS = BLOCKS | {"case_statement"}
# Bodies that can be a single statement without braces: if (x) return 1;
BODY_FIELDS = {
    "if_statement": ("consequence", "alternative"),
    "while_statement": ("body",),
    "do_statement": ("body",),
    "for_statement": ("body",),
    "enhanced_for_statement": ("body",),
}


def _is_statement(node) -> bool:
    return node.type not in NOT_STATEMENTS and (
        node.type.endswith("_statement")
        or node.type in {"declaration", "local_variable_declaration"}
    )


def find_statements(root, source_bytes: bytes, branches: list[Branch]) -> list[Statement]:
    """Statements inside function bodies, in source order.

    Block members and case bodies get a probe before them. A single
    statement used as an if/else/loop body is wrapped in braces with its
    probe, so it can be counted without changing what runs. Constructor
    calls `this(...)`/`super(...)` must stay first in Java and are skipped,
    as is anything inside a probed condition (a lambda's body).
    """
    found: list[Statement] = []

    def inside_condition(node) -> bool:
        return any(b.start <= node.start_byte and node.end_byte <= b.end for b in branches)

    def add(node, wrap=False):
        if not inside_condition(node):
            found.append(
                Statement(node.start_point.row + 1, node.start_byte, node.end_byte, wrap)
            )

    def visit(node):
        if node.type in BLOCKS or node.type in CASE_BODIES:
            for child in node.named_children:
                if _is_statement(child) and not source_bytes[
                    child.start_byte:child.end_byte
                ].lstrip().startswith((b"this(", b"super(")):
                    add(child)

        for field in BODY_FIELDS.get(node.type, ()):
            body = node.child_by_field_name(field)
            if body is not None and body.type == "else_clause":  # C keeps else apart
                body = next((c for c in body.named_children if _is_statement(c) or c.type in BLOCKS), None)
            if body is not None and body.type not in BLOCKS and _is_statement(body):
                add(body, wrap=True)

        for child in node.children:
            visit(child)

    visit(root)
    found.sort(key=lambda statement: statement.start)
    return found


def instrument_source(
    source_bytes: bytes,
    branches: list[Branch],
    statements: list[Statement],
    wrap: Callable[[int, str], str],
    line_call: Callable[[int], str],
) -> str:
    """Apply every probe in one pass.

    Conditions are replaced by wrap(branch_id, text); each statement gets
    line_call(line) before it, or `{ line_call(line) stmt }` around it.
    """
    edits: list[tuple[int, int, str]] = []
    for branch in branches:
        inner = source_bytes[branch.start:branch.end].decode("utf-8")
        edits.append((branch.start, branch.end, wrap(branch.id, inner)))
    for statement in statements:
        if statement.wrap:
            edits.append((statement.start, statement.start, "{ " + line_call(statement.line) + " "))
            edits.append((statement.end, statement.end, " }"))
        else:
            edits.append((statement.start, statement.start, line_call(statement.line) + " "))

    result = source_bytes
    for start, end, text in sorted(edits, key=lambda edit: (edit[0], edit[1]), reverse=True):
        result = result[:start] + text.encode("utf-8") + result[end:]
    return result.decode("utf-8")


def read_probe_hits(path: Path) -> set[tuple]:
    """Read what a run recorded: (branch id, outcome) and ("line", n)."""
    hits: set[tuple] = set()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return hits

    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1] in {"0", "1"}:
            hits.add((int(parts[0]), parts[1] == "1"))
        elif len(parts) == 2 and parts[0] == "L" and parts[1].isdigit():
            hits.add(("line", int(parts[1])))
    return hits


def summarize_coverage(
    branches: list[Branch],
    hits: set[tuple],
    statement_lines: set[int] | None = None,
) -> dict[str, Any]:
    """Build the same coverage report shape as Python's analyzer."""
    report = []
    covered = 0

    for branch in branches:
        observed = {outcome for branch_id, outcome in hits if branch_id == branch.id}
        covered += len(observed)
        report.append(
            {
                "line": branch.line,
                "kind": branch.kind,
                "true_covered": True in observed,
                "false_covered": False in observed,
                "missing": [
                    label
                    for label, value in (("true", True), ("false", False))
                    if value not in observed
                ],
            }
        )

    total = len(branches) * 2
    return {
        "success": True,
        "error": None,
        "branches": report,
        "branch_coverage_percent": round(covered / total * 100, 2)
        if total
        else 0.0,
        **summarize_statements(
            statement_lines or set(),
            {hit[1] for hit in hits if hit[0] == "line"},
        ),
    }
