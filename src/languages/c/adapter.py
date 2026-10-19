
import shutil
import subprocess
import tempfile
from pathlib import Path

import tree_sitter
import tree_sitter_c

from src.core.interfaces import LanguageAdapter
from src.core.models import Condition, TestCase, TestResult


class CAdapter(LanguageAdapter):
    """C adapter using Tree-sitter for syntax parsing."""

    def __init__(self):
        self.language = tree_sitter.Language(tree_sitter_c.language())
        self.parser = tree_sitter.Parser(self.language)

    def parse(self, source_code: str):
        """Parse C source and reject empty or syntactically invalid input."""
        if not source_code.strip():
            raise ValueError("C source code is empty.")

        tree = self.parser.parse(source_code.encode("utf-8"))

        if tree.root_node.has_error:
            raise ValueError("C source contains syntax errors.")

        return tree

    def analyze(self, source_code: str) -> list[Condition]:
        """Extract supported variable-to-numeric-constant comparisons."""
        tree = self.parse(source_code)
        source_bytes = source_code.encode("utf-8")
        conditions = []

        supported_operators = {">", ">=", "<", "<=", "==", "!="}

        def extract_comparisons(node):
            if node.type == "parenthesized_expression":
                for child in node.named_children:
                    extract_comparisons(child)
                return

            if node.type == "binary_expression":
                left_node = node.child_by_field_name("left")
                right_node = node.child_by_field_name("right")

                operator_node = next(
                    (
                        child
                        for child in node.children
                        if child.type in {
                            ">", ">=", "<", "<=", "==", "!=",
                            "+", "-", "*", "/", "%", "&&", "||",
                        }
                    ),
                    None,
                )

                if left_node and right_node and operator_node:
                    operator = source_bytes[
                        operator_node.start_byte:operator_node.end_byte
                    ].decode("utf-8")

                    left_text = source_bytes[
                        left_node.start_byte:left_node.end_byte
                    ].decode("utf-8")

                    right_text = source_bytes[
                        right_node.start_byte:right_node.end_byte
                    ].decode("utf-8")

                    if (
                        operator in supported_operators
                        and left_node.type == "identifier"
                        and right_node.type == "number_literal"
                    ):
                        try:
                            value = (
                                float(right_text)
                                if any(char in right_text for char in ".eE")
                                else int(right_text, 0)
                            )
                        except ValueError:
                            return

                        conditions.append(
                            Condition(
                                variable=left_text,
                                operator=operator,
                                value=value,
                                line=node.start_point.row + 1,
                                language="c",
                            )
                        )
                        return

                # Handle nested conditions, e.g.:
                # age >= 18 && score < 50
                for child in node.named_children:
                    extract_comparisons(child)
                return

            for child in node.named_children:
                extract_comparisons(child)

        def visit(node):
            if node.type == "if_statement":
                condition_node = node.child_by_field_name("condition")

                if condition_node is not None:
                    extract_comparisons(condition_node)

            for child in node.children:
                visit(child)

        visit(tree.root_node)
        return conditions

    def execute(self, source_code: str, test_case: TestCase) -> TestResult:
        """Compile and execute C source with test inputs as command-line arguments."""
        if shutil.which("gcc") is None:
            return TestResult(
                inputs=test_case.inputs,
                executed=False,
                error="GCC must be available on PATH.",
            )

        try:
            with tempfile.TemporaryDirectory(prefix="ast_test_c_") as temp_dir:
                source_path = Path(temp_dir) / "program.c"
                executable_path = Path(temp_dir) / "program.exe"

                source_path.write_text(source_code, encoding="utf-8")

                compile_result = subprocess.run(
                    ["gcc", str(source_path), "-o", str(executable_path)],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    cwd=temp_dir,
                )

                if compile_result.returncode != 0:
                    return TestResult(
                        inputs=test_case.inputs,
                        executed=False,
                        error=(
                            compile_result.stderr.strip()
                            or compile_result.stdout.strip()
                            or "C compilation failed."
                        ),
                    )

                # Exclude argc: it is metadata, not a program input.
                # Sort keys so arguments are passed in a predictable order.
                arguments = [
                    str(value)
                    for key, value in sorted(test_case.inputs.items())
                    if key != "argc"
                ]

                run_result = subprocess.run(
                    [str(executable_path), *arguments],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=temp_dir,
                )

                return TestResult(
                    inputs=test_case.inputs,
                    executed=run_result.returncode == 0,
                    output=run_result.stdout,
                    error=(
                        run_result.stderr.strip()
                        or (
                            None
                            if run_result.returncode == 0
                            else (
                                "C program exited with code "
                                f"{run_result.returncode}."
                            )
                        )
                    ),
                )

        except subprocess.TimeoutExpired:
            return TestResult(
                inputs=test_case.inputs,
                executed=False,
                error="C compilation or execution timed out.",
            )
        except OSError as error:
            return TestResult(
                inputs=test_case.inputs,
                executed=False,
                error=f"{type(error).__name__}: {error}",
            )

    def execute_and_verify(
        self,
        source_code: str,
        test_case: TestCase,
        expected_output: str,
    ) -> TestResult:
        """Execute a C test case and verify its output."""
        from src.core.result_verifier import verify_output

        result = self.execute(source_code, test_case)
        return verify_output(result, expected_output)
