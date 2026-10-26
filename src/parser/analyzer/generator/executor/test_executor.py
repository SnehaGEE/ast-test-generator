import ast
import json
import subprocess
import sys
from pathlib import Path

_WORKER_PATH = Path(__file__).with_name("sandbox_worker.py")


def _failure(message, variable_values, output=""):
    return {
        "success": False,
        "input": variable_values,
        "output": output,
        "error": message,
    }


def _last_line(text):
    """Return the last non-empty line of text, shortened for display."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1][:300] if lines else ""


def execute_test_case(source_code, variable_values, timeout=3, answers=None):
    """Execute Python source with supplied test inputs in a child process.

    The program runs in a separate Python process so that a program which
    never finishes can be killed when the timeout expires. Returns a dict
    with success, input, output and error. answers, if given, are what
    each input() call returns, in order.
    """

    try:
        ast.parse(source_code)
    except SyntaxError as error:
        return _failure(f"Invalid Python syntax: {error.msg}", variable_values)

    if not _WORKER_PATH.is_file():
        return _failure(
            f"Sandbox worker script not found: {_WORKER_PATH}",
            variable_values,
        )

    try:
        request = {"source": source_code, "inputs": variable_values}
        if answers is not None:
            request["answers"] = [str(answer) for answer in answers]
        payload = json.dumps(request)
    except (TypeError, ValueError) as error:
        return _failure(
            f"Test inputs could not be passed to the sandbox: {error}",
            variable_values,
        )

    try:
        completed = subprocess.run(
            [sys.executable, "-I", str(_WORKER_PATH)],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return _failure(
            f"Execution timed out after {timeout} seconds",
            variable_values,
        )
    except OSError as error:
        return _failure(
            f"Could not start the test process: {error}",
            variable_values,
        )

    try:
        result = json.loads(completed.stdout)
    except ValueError:
        detail = _last_line(completed.stderr)
        message = (
            "Test process ended without a result "
            f"(exit code {completed.returncode})"
        )
        if detail:
            message += f": {detail}"
        return _failure(message, variable_values)

    return {
        "success": bool(result.get("success", False)),
        "input": variable_values,
        "output": result.get("output", ""),
        "error": result.get("error"),
    }