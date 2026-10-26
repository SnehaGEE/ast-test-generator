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


def insert_probes(
    source_bytes: bytes,
    branches: list[Branch],
    wrap: Callable[[int, str], str],
) -> str:
    """Replace each condition with wrap(branch_id, condition_text)."""
    result = source_bytes
    for branch in reversed(branches):
        inner = result[branch.start:branch.end].decode("utf-8")
        result = (
            result[:branch.start]
            + wrap(branch.id, inner).encode("utf-8")
            + result[branch.end:]
        )
    return result.decode("utf-8")


def read_probe_hits(path: Path) -> set[tuple[int, bool]]:
    """Read the (branch id, outcome) pairs a run recorded."""
    hits: set[tuple[int, bool]] = set()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return hits

    for line in text.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1] in {"0", "1"}:
            hits.add((int(parts[0]), parts[1] == "1"))
    return hits


def summarize_coverage(
    branches: list[Branch],
    hits: set[tuple[int, bool]],
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
    }
