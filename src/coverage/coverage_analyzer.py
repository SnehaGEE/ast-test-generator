
import sys
from typing import Any


def measure_line_coverage(
    source_code: str,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    """Measure executed source lines for a trusted Python program."""

    import contextlib
    import io

    filename = "<coverage_target>"
    executed_lines = set()
    output = io.StringIO()
    namespace = {"__name__": "__main__", **inputs}

    def trace_lines(frame, event, arg):
        if frame.f_code.co_filename == filename and event == "line":
            executed_lines.add(frame.f_lineno)
        return trace_lines

    try:
        compiled = compile(source_code, filename, "exec")
    except SyntaxError as error:
        return {
            "success": False,
            "error": f"Invalid Python syntax: {error.msg}",
            "executed_lines": [],
            "executable_lines": [],
            "line_coverage_percent": 0.0,
            "output": "",
        }

    # Approximate executable lines using Python's bytecode line metadata.
    executable_lines = {
    line
    for start, end, line in compiled.co_lines()
    if line is not None and start < end
}

    try:
        with contextlib.redirect_stdout(output):
            previous_trace = sys.gettrace()
            try:
                sys.settrace(trace_lines)
                exec(compiled, namespace)
            finally:
                sys.settrace(previous_trace)

        covered = executed_lines & executable_lines
        percentage = (
            len(covered) / len(executable_lines) * 100
            if executable_lines else 100.0
        )

        return {
            "success": True,
            "error": None,
            "executed_lines": sorted(covered),
            "executable_lines": sorted(executable_lines),
            "line_coverage_percent": round(percentage, 2),
            "output": output.getvalue(),
        }

    except Exception as error:
        covered = executed_lines & executable_lines
        percentage = (
            len(covered) / len(executable_lines) * 100
            if executable_lines else 100.0
        )

        return {
            "success": False,
            "error": f"{type(error).__name__}: {error}",
            "executed_lines": sorted(covered),
            "executable_lines": sorted(executable_lines),
            "line_coverage_percent": round(percentage, 2),
            "output": output.getvalue(),
        }

def analyze_branch_coverage(
    source_code: str,
    test_inputs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Measure observed true/false outcomes for supported Python if conditions."""

    import ast

    branch_outcomes = {}

    try:
        tree = ast.parse(source_code)
    except SyntaxError as error:
        return {
            "success": False,
            "error": f"Invalid Python syntax: {error.msg}",
            "branches": [],
            "branch_coverage_percent": 0.0,
        }

    conditions = []

    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            conditions.append(node)

    for node in conditions:
        branch_outcomes[node.lineno] = set()

    for inputs in test_inputs:
        namespace = {"__name__": "__main__", **inputs}

        for node in conditions:
            try:
                condition_code = compile(
                    ast.Expression(body=node.test),
                    "<branch_condition>",
                    "eval",
                )
                outcome = bool(eval(condition_code, namespace))
                branch_outcomes[node.lineno].add(outcome)
            except Exception:
                # This condition could not be evaluated with these inputs.
                continue

    branches = []
    covered_outcomes = 0
    total_outcomes = len(conditions) * 2

    for node in conditions:
        outcomes = branch_outcomes[node.lineno]
        covered_outcomes += len(outcomes)

        branches.append({
            "line": node.lineno,
            "true_covered": True in outcomes,
            "false_covered": False in outcomes,
            "missing": [
                name
                for name, value in (
                    ("true", True),
                    ("false", False),
                )
                if value not in outcomes
            ],
        })

    percentage = (
        covered_outcomes / total_outcomes * 100
        if total_outcomes else 100.0
    )

    return {
        "success": True,
        "error": None,
        "branches": branches,
        "branch_coverage_percent": round(percentage, 2),
    }

def suggest_missing_branch_tests(
    source_code: str,
    coverage_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """Suggest inputs for missing outcomes of supported simple conditions."""

    from src.parser.analyzer.condition_analyzer import analyze_source

    conditions = analyze_source(source_code)
    suggestions = []

    missing_by_line = {
        branch["line"]: branch["missing"]
        for branch in coverage_result.get("branches", [])
    }

    for condition in conditions:
        missing = missing_by_line.get(condition["line"], [])
        variable = condition["variable"]
        operator = condition["operator"]
        constant = condition["constant"]

        if (
            isinstance(constant, bool)
            or not isinstance(constant, (int, float))
        ):
            continue

        if not missing:
            continue

        if "true" in missing:
            target_outcome = True
        elif "false" in missing:
            target_outcome = False
        else:
            continue

        # Find a nearby value that should make the condition true/false.
        candidates = [
            constant,
            constant - 1,
            constant + 1,
        ]

        operator_functions = {
            ">": lambda x: x > constant,
            ">=": lambda x: x >= constant,
            "<": lambda x: x < constant,
            "<=": lambda x: x <= constant,
            "==": lambda x: x == constant,
            "!=": lambda x: x != constant,
        }

        predicate = operator_functions.get(operator)
        if predicate is None:
            continue

        for candidate in candidates:
            if predicate(candidate) == target_outcome:
                suggestions.append({
                    "line": condition["line"],
                    "target_outcome": (
                        "true" if target_outcome else "false"
                    ),
                    "inputs": {variable: candidate},
                })
                break

    return suggestions
