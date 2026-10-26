
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import tree_sitter
import tree_sitter_java

from src.core.interfaces import LanguageAdapter
from src.core.models import Condition, TestCase, TestResult


NUMERIC_LITERALS = {
    "decimal_integer_literal",
    "decimal_floating_point_literal",
}


def _numeric_value(node, source_bytes: bytes):
    """Return the value of a numeric literal such as -5, +3, 5L or 2.5f.

    Returns None when the node is not a supported numeric literal.
    """
    sign = 1

    if node.type == "unary_expression" and len(node.children) == 2:
        operator, operand = node.children
        if operator.type not in {"-", "+"}:
            return None
        sign = -1 if operator.type == "-" else 1
        node = operand

    if node.type not in NUMERIC_LITERALS:
        return None

    text = source_bytes[node.start_byte:node.end_byte].decode("utf-8")
    text = text.replace("_", "").rstrip("lLfFdD")

    try:
        if node.type == "decimal_floating_point_literal":
            return sign * float(text)
        return sign * int(text)
    except ValueError:
        return None


class JavaAdapter(LanguageAdapter):
    """Java adapter using Tree-sitter for syntax parsing."""

    def __init__(self):
        self.language = tree_sitter.Language(tree_sitter_java.language())
        self.parser = tree_sitter.Parser(self.language)

    def parse(self, source_code: str):
        """Parse Java source into a Tree-sitter syntax tree."""
        if not source_code.strip():
            raise ValueError("Java source code is empty.")

        tree = self.parser.parse(source_code.encode("utf-8"))

        if tree.root_node.has_error:
            raise ValueError("Java source contains syntax errors.")

        return tree

    def analyze(self, source_code: str) -> list[Condition]:
        """Extract supported numeric comparisons from Java if conditions."""
        tree = self.parse(source_code)
        source_bytes = source_code.encode("utf-8")
        conditions = []

        supported_operators = {
            ">": ">",
            ">=": ">=",
            "<": "<",
            "<=": "<=",
            "==": "==",
            "!=": "!=",
        }

        def visit(node):
            if node.type == "if_statement":
                condition_node = node.child_by_field_name("condition")

                if condition_node is not None:
                    extract_comparisons(condition_node)

            for child in node.children:
                visit(child)

        def extract_comparisons(node):
            if node.type == "parenthesized_expression":
                for child in node.named_children:
                    extract_comparisons(child)
                return

            if node.type == "binary_expression":
                operator_node = node.child_by_field_name("operator")
                left_node = node.child_by_field_name("left")
                right_node = node.child_by_field_name("right")

                if operator_node and left_node and right_node:
                    operator = source_bytes[
                        operator_node.start_byte:operator_node.end_byte
                    ].decode("utf-8")

                    left_text = source_bytes[
                        left_node.start_byte:left_node.end_byte
                    ].decode("utf-8")

                    value = _numeric_value(right_node, source_bytes)

                    if (
                        operator in supported_operators
                        and left_node.type == "identifier"
                        and value is not None
                    ):
                        conditions.append(
                            Condition(
                                variable=left_text,
                                operator=supported_operators[operator],
                                value=value,
                                line=node.start_point.row + 1,
                                language="java",
                            )
                        )
                        return

                # Also inspect nested comparisons in compound conditions.
                for child in node.named_children:
                    extract_comparisons(child)
                return

            for child in node.named_children:
                extract_comparisons(child)

        visit(tree.root_node)
        return conditions

    def execute(
        self,
        source_code: str,
        test_case: TestCase,
    ) -> TestResult:
        """Compile and execute Java source using JVM system properties."""
        return self.execute_many(source_code, [test_case])[0]

    def execute_many(
        self,
        source_code: str,
        test_cases: list[TestCase],
    ) -> list[TestResult]:
        """Compile Java source once, then run every test case against it."""

        def fail_all(error: str) -> list[TestResult]:
            return [
                TestResult(inputs=case.inputs, executed=False, error=error)
                for case in test_cases
            ]

        if shutil.which("javac") is None or shutil.which("java") is None:
            return fail_all(
                "Java JDK tools javac and java must be available on PATH."
            )

        class_match = re.search(
            r"\bpublic\s+class\s+([A-Za-z_]\w*)",
            source_code,
        )
        if not class_match:
            return fail_all("Java source must declare a public class.")

        class_name = class_match.group(1)

        try:
            with tempfile.TemporaryDirectory(prefix="ast_test_java_") as temp_dir:
                source_path = Path(temp_dir) / f"{class_name}.java"
                source_path.write_text(source_code, encoding="utf-8")

                try:
                    compile_result = subprocess.run(
                        ["javac", str(source_path)],
                        capture_output=True,
                        text=True,
                        timeout=15,
                        cwd=temp_dir,
                    )
                except subprocess.TimeoutExpired:
                    return fail_all("Java compilation timed out.")

                if compile_result.returncode != 0:
                    return fail_all(
                        compile_result.stderr.strip()
                        or compile_result.stdout.strip()
                        or "Java compilation failed."
                    )

                return [
                    self._run_case(class_name, temp_dir, case)
                    for case in test_cases
                ]

        except OSError as error:
            return fail_all(f"{type(error).__name__}: {error}")

    def _run_case(
        self,
        class_name: str,
        temp_dir: str,
        test_case: TestCase,
    ) -> TestResult:
        """Run an already compiled Java class for one test case."""
        properties = [
            f"-D{key}={value}"
            for key, value in test_case.inputs.items()
        ]

        try:
            run_result = subprocess.run(
                ["java", *properties, "-cp", temp_dir, class_name],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=temp_dir,
            )
        except subprocess.TimeoutExpired:
            return TestResult(
                inputs=test_case.inputs,
                executed=False,
                error="Java execution timed out.",
            )
        except OSError as error:
            return TestResult(
                inputs=test_case.inputs,
                executed=False,
                error=f"{type(error).__name__}: {error}",
            )

        return TestResult(
            inputs=test_case.inputs,
            executed=run_result.returncode == 0,
            output=run_result.stdout,
            error=run_result.stderr.strip()
            or (
                None
                if run_result.returncode == 0
                else f"Java exited with code {run_result.returncode}."
            ),
        )

    def execute_and_verify(
        self,
        source_code: str,
        test_case: TestCase,
        expected_output: str,
    ) -> TestResult:
        """Execute a Java test case and verify its output."""
        from src.core.result_verifier import verify_output

        result = self.execute(source_code, test_case)
        return verify_output(result, expected_output)
