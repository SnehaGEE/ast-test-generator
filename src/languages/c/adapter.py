

import shutil
import subprocess
import tempfile
from pathlib import Path

import tree_sitter
import tree_sitter_c

from src.core.input_order import reorder
from src.core.interfaces import LanguageAdapter
from src.languages.input_plan import (
    InputPlan,
    assigned_name,
    node_text,
    stdin_text,
)
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

    def input_plan(self, source_code: str) -> InputPlan:
        """Find scanf targets and argv[n] positions in the source."""
        source_bytes = source_code.encode("utf-8")
        tree = self.parser.parse(source_bytes)
        plan = InputPlan()
        reads: list[tuple[int, str]] = []

        def visit(node):
            if node.type == "call_expression":
                function = node.child_by_field_name("function")
                arguments = node.child_by_field_name("arguments")

                if (
                    function is not None
                    and arguments is not None
                    and node_text(function, source_bytes) == "scanf"
                ):
                    # Skip the format string; collect &name arguments.
                    for argument in arguments.named_children[1:]:
                        target = argument.child_by_field_name("argument")
                        if (
                            argument.type == "pointer_expression"
                            and target is not None
                            and target.type == "identifier"
                        ):
                            reads.append(
                                (
                                    argument.start_byte,
                                    node_text(target, source_bytes),
                                )
                            )

            elif node.type == "subscript_expression":
                array = node.child_by_field_name("argument")
                index = node.child_by_field_name("index")

                if (
                    array is not None
                    and index is not None
                    and node_text(array, source_bytes) == "argv"
                    and index.type == "number_literal"
                ):
                    name = assigned_name(node, source_bytes)
                    try:
                        position = int(node_text(index, source_bytes), 0)
                    except ValueError:
                        position = None
                    if name and position:
                        plan.positions.setdefault(name, position)

            for child in node.children:
                visit(child)

        visit(tree.root_node)
        plan.read_order = list(dict.fromkeys(name for _, name in sorted(reads)))
        return plan

    def execute(self, source_code: str, test_case: TestCase) -> TestResult:
        """Compile and execute C source with test inputs as command-line arguments."""
        return self.execute_many(source_code, [test_case])[0]

    def execute_many(
        self,
        source_code: str,
        test_cases: list[TestCase],
    ) -> list[TestResult]:
        """Compile C source once, then run every test case against it."""

        def fail_all(error: str) -> list[TestResult]:
            return [
                TestResult(inputs=case.inputs, executed=False, error=error)
                for case in test_cases
            ]

        if shutil.which("gcc") is None:
            return fail_all("GCC must be available on PATH.")

        try:
            with tempfile.TemporaryDirectory(prefix="ast_test_c_") as temp_dir:
                source_path = Path(temp_dir) / "program.c"
                executable_path = Path(temp_dir) / "program.exe"

                source_path.write_text(source_code, encoding="utf-8")

                try:
                    compile_result = subprocess.run(
                        ["gcc", str(source_path), "-o", str(executable_path)],
                        capture_output=True,
                        text=True,
                        timeout=15,
                        cwd=temp_dir,
                    )
                except subprocess.TimeoutExpired:
                    return fail_all("C compilation timed out.")

                if compile_result.returncode != 0:
                    return fail_all(
                        compile_result.stderr.strip()
                        or compile_result.stdout.strip()
                        or "C compilation failed."
                    )

                plan = self.input_plan(source_code)
                return [
                    self._run_case(executable_path, temp_dir, case, plan)
                    for case in test_cases
                ]

        except OSError as error:
            return fail_all(f"{type(error).__name__}: {error}")

    def _run_case(
        self,
        executable_path: Path,
        temp_dir: str,
        test_case: TestCase,
        plan: InputPlan,
    ) -> TestResult:
        """Run an already compiled C program for one test case."""
        # argc is not an argument; it is the argument count plus
        # the program name.
        values = {
            key: value
            for key, value in test_case.inputs.items()
            if key != "argc"
        }

        if plan.positions:
            # Put each value at the argv index the program reads it from.
            arguments = ["0"] * max(plan.positions.values())
            for name, position in plan.positions.items():
                if name in values:
                    arguments[position - 1] = str(values[name])
        else:
            # Unknown layout: pass values in alphabetical order.
            arguments = [str(value) for _, value in sorted(values.items())]

        argc = test_case.inputs.get("argc")

        if isinstance(argc, int) and not isinstance(argc, bool):
            # Make the program see exactly this argc: drop extra
            # arguments, or pad with "0" when more are needed.
            wanted = max(argc - 1, 0)
            arguments = arguments[:wanted] + [
                "0"
            ] * (wanted - len(arguments))

        try:
            run_result = subprocess.run(
                [str(executable_path), *arguments],
                input=stdin_text(
                    reorder(values, plan.read_order).values()
                ),
                capture_output=True,
                text=True,
                timeout=10,
                cwd=temp_dir,
            )
        except subprocess.TimeoutExpired:
            return TestResult(
                inputs=test_case.inputs,
                executed=False,
                error="C program execution timed out.",
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