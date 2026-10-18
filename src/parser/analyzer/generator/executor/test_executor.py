
import ast
import contextlib
import io
import signal
import threading
from unittest.mock import patch


def execute_test_case(source_code, variable_values, timeout=3):
    """Execute trusted Python source with supplied test inputs."""

    try:
        tree = ast.parse(source_code)
    except SyntaxError as error:
        return {
            "success": False,
            "error": f"Invalid Python syntax: {error.msg}",
            "output": "",
            "input": variable_values,
        }

    namespace = {"__name__": "__main__"}
    namespace.update(variable_values)
    output = io.StringIO()

    # Provide input() values from the generated test inputs.
    input_values = iter(str(value) for value in variable_values.values())

    def mock_input(prompt=""):
        print(prompt, end="", file=output)
        try:
            return next(input_values)
        except StopIteration:
            raise EOFError("No more generated input values available")

    # Use a daemon thread so a timed-out execution cannot hold up the test process.
    result = {}

    def run_program():
        try:
            with patch("builtins.input", mock_input):
                with contextlib.redirect_stdout(output):
                    exec(compile(tree, "<user_program>", "exec"), namespace)
            result["success"] = True
            result["error"] = None
        except Exception as error:
            result["success"] = False
            result["error"] = f"{type(error).__name__}: {error}"

    worker = threading.Thread(target=run_program, daemon=True)
    worker.start()
    worker.join(timeout)

    if worker.is_alive():
        return {
            "success": False,
            "input": variable_values,
            "output": output.getvalue(),
            "error": f"Execution timed out after {timeout} seconds",
        }

    return {
        "success": result.get("success", False),
        "input": variable_values,
        "output": output.getvalue(),
        "error": result.get("error"),
    }
