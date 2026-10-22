
import ast
import contextlib
import io
import sys
from typing import Any


def _make_input(inputs: dict[str, Any]):
    """Provide input() values from supplied test variables."""
    values = iter(str(value) for value in inputs.values())

    def fake_input(prompt: str = "") -> str:
        return next(values, "")

    return fake_input


def measure_line_coverage(
    source_code: str,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    """Measure executed source lines for a trusted Python program."""

    filename = "<coverage_target>"
    executed_lines: set[int] = set()
    output = io.StringIO()

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

    executable_lines = {
        line
        for start, end, line in compiled.co_lines()
        if line is not None and start < end
    }

    def trace_lines(frame, event, arg):
        if frame.f_code.co_filename == filename and event == "line":
            executed_lines.add(frame.f_lineno)
        return trace_lines

    namespace = {
        "__name__": "__main__",
        **inputs,
        "input": _make_input(inputs),
    }

    previous_trace = sys.gettrace()
    error_message = None

    try:
        with contextlib.redirect_stdout(output):
            sys.settrace(trace_lines)
            try:
                exec(compiled, namespace)
            finally:
                sys.settrace(previous_trace)
    except Exception as error:
        error_message = f"{type(error).__name__}: {error}"
    finally:
        sys.settrace(previous_trace)

    covered = executed_lines & executable_lines
    percentage = (
        len(covered) / len(executable_lines) * 100
        if executable_lines
        else 0.0
    )

    return {
        "success": error_message is None,
        "error": error_message,
        "executed_lines": sorted(covered),
        "executable_lines": sorted(executable_lines),
        "line_coverage_percent": round(percentage, 2),
        "output": output.getvalue(),
    }


def analyze_branch_coverage(
    source_code: str,
    test_inputs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Measure true/false outcomes of executed Python if conditions."""

    try:
        tree = ast.parse(source_code)
    except SyntaxError as error:
        return {
            "success": False,
            "error": f"Invalid Python syntax: {error.msg}",
            "branches": [],
            "branch_coverage_percent": 0.0,
        }

    conditions = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.If)
    ]

    # Assign stable IDs before the tree is transformed.
    condition_ids = {
        node.lineno: index
        for index, node in enumerate(conditions)
    }

    # Use IDs internally so multiple if statements on one line
    # are counted separately.
    outcomes: dict[int, set[bool]] = {
        index: set() for index in range(len(conditions))
    }

    for test_index, inputs in enumerate(test_inputs):
        filename = f"<branch_coverage_{test_index}>"

        class BranchTracer(ast.NodeTransformer):
            def visit_If(self, node: ast.If):
                branch_id = condition_ids[node.lineno]
                original_test = self.visit(node.test)
                node.test = ast.copy_location(
                    ast.Call(
                        func=ast.Name(
                            id="__record_branch",
                            ctx=ast.Load(),
                        ),
                        args=[
                            ast.Constant(value=branch_id),
                            original_test,
                        ],
                        keywords=[],
                    ),
                    node.test,
                )

                node.body = [
                    self.visit(child) for child in node.body
                ]
                node.orelse = [
                    self.visit(child) for child in node.orelse
                ]
                return node

        def record_branch(branch_id: int, value: Any) -> bool:
            result = bool(value)
            outcomes[branch_id].add(result)
            return result

        namespace = {
            "__name__": "__main__",
            **inputs,
            "input": _make_input(inputs),
            "__record_branch": record_branch,
        }

        try:
            instrumented = BranchTracer().visit(ast.parse(source_code))
            ast.fix_missing_locations(instrumented)
            compiled = compile(instrumented, filename, "exec")

            with contextlib.redirect_stdout(io.StringIO()):
                exec(compiled, namespace)
        except Exception:
            # Preserve outcomes reached before a runtime error.
            continue

    branches = []
    covered_outcomes = 0
    total_outcomes = len(conditions) * 2

    for index, node in enumerate(conditions):
        observed = outcomes[index]
        covered_outcomes += len(observed)

        missing = [
            label
            for label, value in (
                ("true", True),
                ("false", False),
            )
            if value not in observed
        ]

        branches.append({
            "line": node.lineno,
            "true_covered": True in observed,
            "false_covered": False in observed,
            "missing": missing,
        })

    percentage = (
        covered_outcomes / total_outcomes * 100
        if total_outcomes
        else 0.0
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
    """Suggest candidate inputs for missing outcomes of simple conditions."""

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
            or not missing
        ):
            continue

        predicates = {
            ">": lambda value: value > constant,
            ">=": lambda value: value >= constant,
            "<": lambda value: value < constant,
            "<=": lambda value: value <= constant,
            "==": lambda value: value == constant,
            "!=": lambda value: value != constant,
        }

        predicate = predicates.get(operator)
        if predicate is None:
            continue

        for target in missing:
            expected = target == "true"

            for candidate in (
                constant,
                constant - 1,
                constant + 1,
            ):
                if predicate(candidate) == expected:
                    suggestion = {
                        "line": condition["line"],
                        "target_outcome": target,
                        "inputs": {variable: candidate},
                    }
                    if suggestion not in suggestions:
                        suggestions.append(suggestion)
                    break

    return suggestions
