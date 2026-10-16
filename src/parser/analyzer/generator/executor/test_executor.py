import ast
import contextlib
import io


def execute_test_case(source_code, variable_values):
    """Execute trusted Python source with supplied test inputs."""

    try:
        tree = ast.parse(source_code)
    except SyntaxError as error:
        return {
            "success": False,
            "error": f"Invalid Python syntax: {error.msg}"
        }

    namespace = {"__name__": "__main__"}
    namespace.update(variable_values)
    output = io.StringIO()

    try:
        with contextlib.redirect_stdout(output):
            exec(compile(tree, "<user_program>", "exec"), namespace)

        return {
            "success": True,
            "input": variable_values,
            "output": output.getvalue(),
            "error": None
        }

    except Exception as error:
        return {
            "success": False,
            "input": variable_values,
            "output": output.getvalue(),
            "error": f"{type(error).__name__}: {error}"
        }
