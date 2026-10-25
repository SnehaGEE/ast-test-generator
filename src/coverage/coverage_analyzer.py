import ast
import contextlib
import io
import sys
import time
from typing import Any

# Guards against generated inputs that make a while loop run forever.
MAX_LOOP_EVALUATIONS = 100_000

# Wall-clock limit for one program run during coverage measurement.
DEFAULT_TIME_LIMIT_SECONDS = 2.0


class _LimitExceeded(BaseException):
    """Raised when a program exceeds a loop or time limit.

    This derives from BaseException on purpose: a tested program's own
    `except Exception:` must not be able to swallow the limit and keep
    running.
    """


def _make_input(inputs: dict[str, Any]):
    """Provide input() values from supplied test variables."""
    values = iter(str(value) for value in inputs.values())

    def fake_input(prompt: str = "") -> str:
        return next(values, "")

    return fake_input


def _make_deadline_tracer(filename: str, time_limit: float, on_line=None):
    """Build a trace function that stops the program after time_limit.

    Python calls the trace function on every line of traced code, so
    ordinary loops are interrupted. A single long C-level call, such as
    time.sleep(1000) or 10**10**10, cannot be interrupted this way.
    """
    deadline = time.monotonic() + time_limit

    def tracer(frame, event, arg):
        if frame.f_code.co_filename != filename:
            return None
        if time.monotonic() > deadline:
            raise _LimitExceeded("time limit exceeded")
        if event == "line" and on_line is not None:
            on_line(frame.f_lineno)
        return tracer

    return tracer


def measure_line_coverage(
    source_code: str,
    inputs: dict[str, Any],
    time_limit: float = DEFAULT_TIME_LIMIT_SECONDS,
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

    # Line 0 is the compiler's function-entry marker, not a source line.
    executable_lines = {
        line
        for start, end, line in compiled.co_lines()
        if line is not None and line > 0 and start < end
    }

    trace_lines = _make_deadline_tracer(
        filename,
        time_limit,
        on_line=executed_lines.add,
    )

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
    except _LimitExceeded:
        error_message = f"Time limit of {time_limit} seconds exceeded"
    except SystemExit as exit_request:
        if exit_request.code not in (None, 0):
            error_message = f"SystemExit: {exit_request.code}"
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


def _collect_branch_nodes(tree: ast.AST) -> list[ast.AST]:
    """Return if/while nodes in a deterministic order.

    ast.walk order is the same for any parse of the same source, so the
    index in this list is a stable branch ID across separate parses.
    """
    return [
        node for node in ast.walk(tree)
        if isinstance(node, (ast.If, ast.While))
    ]


def analyze_branch_coverage(
    source_code: str,
    test_inputs: list[dict[str, Any]],
    time_limit: float = DEFAULT_TIME_LIMIT_SECONDS,
) -> dict[str, Any]:
    """Measure true/false outcomes of executed Python if/while conditions.

    For an if statement, true/false is the value of its condition.
    For a while loop, true means the condition was true at least once
    (the body ran) and false means the condition was evaluated false
    (the loop exited normally). Leaving a loop through break, return or
    an exception does not record a false outcome.

    Each test input runs for at most time_limit seconds; outcomes reached
    before a program is stopped are kept.
    """

    try:
        tree = ast.parse(source_code)
    except SyntaxError as error:
        return {
            "success": False,
            "error": f"Invalid Python syntax: {error.msg}",
            "branches": [],
            "branch_coverage_percent": 0.0,
        }

    conditions = _collect_branch_nodes(tree)

    # Use IDs internally so multiple conditions on one line
    # are counted separately.
    outcomes: dict[int, set[bool]] = {
        index: set() for index in range(len(conditions))
    }

    for test_index, inputs in enumerate(test_inputs):
        filename = f"<branch_coverage_{test_index}>"

        # Assign IDs on a fresh tree using the same ordering as above.
        test_tree = ast.parse(source_code)
        test_nodes = _collect_branch_nodes(test_tree)
        for branch_id, branch_node in enumerate(test_nodes):
            branch_node._branch_id = branch_id

        while_ids = {
            branch_id
            for branch_id, branch_node in enumerate(test_nodes)
            if isinstance(branch_node, ast.While)
        }
        while_evaluations: dict[int, int] = {}

        class BranchTracer(ast.NodeTransformer):
            def _wrap_test(self, node, branch_id: int):
                node.test = ast.copy_location(
                    ast.Call(
                        func=ast.Name(
                            id="__record_branch",
                            ctx=ast.Load(),
                        ),
                        args=[
                            ast.Constant(value=branch_id),
                            node.test,
                        ],
                        keywords=[],
                    ),
                    node.test,
                )

            def visit_If(self, node: ast.If):
                branch_id = node._branch_id
                node.test = self.visit(node.test)
                self._wrap_test(node, branch_id)

                node.body = [
                    self.visit(child) for child in node.body
                ]
                node.orelse = [
                    self.visit(child) for child in node.orelse
                ]
                return node

            def visit_While(self, node: ast.While):
                branch_id = node._branch_id
                # Visit the body and else-clause first so nested
                # if/while statements are instrumented too.
                self.generic_visit(node)
                self._wrap_test(node, branch_id)
                return node

        def record_branch(branch_id: int, value: Any) -> bool:
            if branch_id in while_ids:
                count = while_evaluations.get(branch_id, 0) + 1
                while_evaluations[branch_id] = count
                if count > MAX_LOOP_EVALUATIONS:
                    raise _LimitExceeded(
                        "while loop exceeded evaluation limit"
                    )
            result = bool(value)
            outcomes[branch_id].add(result)
            return result

        namespace = {
            "__name__": "__main__",
            **inputs,
            "input": _make_input(inputs),
            "__record_branch": record_branch,
        }

        previous_trace = sys.gettrace()

        try:
            instrumented = BranchTracer().visit(test_tree)
            ast.fix_missing_locations(instrumented)
            compiled = compile(instrumented, filename, "exec")

            with contextlib.redirect_stdout(io.StringIO()):
                sys.settrace(
                    _make_deadline_tracer(filename, time_limit)
                )
                try:
                    exec(compiled, namespace)
                finally:
                    sys.settrace(previous_trace)
        except (Exception, SystemExit, _LimitExceeded):
            # Preserve outcomes reached before a runtime error, an
            # exit request, or a limit being hit.
            continue
        finally:
            sys.settrace(previous_trace)

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
            "kind": "while" if isinstance(node, ast.While) else "if",
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