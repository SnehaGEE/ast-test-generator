import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from src.core.interfaces import LanguageAdapter
from src.core.models import Condition, TestCase, TestResult


class CAdapter(LanguageAdapter):
    """Basic C adapter for simple numeric if conditions."""

    CONDITION_PATTERN = re.compile(
        r"\bif\s*\(\s*([A-Za-z_]\w*)\s*"
        r"(>=|<=|==|!=|>|<)\s*(-?\d+(?:\.\d+)?)\s*\)"
    )

    def parse(self, source_code: str) -> str:
        """Check that C source code is not empty."""
        if not source_code.strip():
            raise ValueError("C source code is empty.")
        return source_code

    def analyze(self, source_code: str) -> list[Condition]:
        """Detect simple variable-to-numeric-constant if conditions."""
        conditions = []

        for match in self.CONDITION_PATTERN.finditer(source_code):
            variable, operator, raw_value = match.groups()
            value = float(raw_value) if "." in raw_value else int(raw_value)
            line = source_code.count("\n", 0, match.start()) + 1

            conditions.append(
                Condition(
                    variable=variable,
                    operator=operator,
                    value=value,
                    line=line,
                    language="c",
                )
            )

        return conditions

    def execute(self, source_code: str, test_case: TestCase) -> TestResult:
        """Compile and execute C source with test inputs passed as arguments."""
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
                        error=compile_result.stderr.strip()
                        or compile_result.stdout.strip()
                        or "C compilation failed.",
                    )

                arguments = [
                    str(value) for value in test_case.inputs.values()
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
                    executed=(run_result.returncode == 0),
                    output=run_result.stdout,
                    error=run_result.stderr.strip()
                    or (
                        None
                        if run_result.returncode == 0
                        else f"C program exited with code {run_result.returncode}."
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