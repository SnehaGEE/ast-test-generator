
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from src.core.interfaces import LanguageAdapter
from src.core.models import Condition, TestCase, TestResult


class JavaAdapter(LanguageAdapter):
    """Basic Java adapter for simple numeric if conditions."""

    CONDITION_PATTERN = re.compile(
        r"\bif\s*\(\s*([A-Za-z_]\w*)\s*"
        r"(>=|<=|==|!=|>|<)\s*(-?\d+(?:\.\d+)?)\s*\)"
    )

    def parse(self, source_code: str) -> str:
        """Return Java source after checking that it is non-empty."""
        if not source_code.strip():
            raise ValueError("Java source code is empty.")
        return source_code

    def analyze(self, source_code: str) -> list[Condition]:
        """Detect simple variable-to-numeric-constant conditions."""
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
                    language="java",
                )
            )

        return conditions

    def execute(
        self,
        source_code: str,
        test_case: TestCase,
    ) -> TestResult:
        """Compile and execute a Java class using supplied variable inputs."""
        if shutil.which("javac") is None or shutil.which("java") is None:
            return TestResult(
                inputs=test_case.inputs,
                executed=False,
                error="Java JDK tools javac and java must be available on PATH.",
            )

        class_match = re.search(
            r"\bpublic\s+class\s+([A-Za-z_]\w*)",
            source_code,
        )
        if not class_match:
            return TestResult(
                inputs=test_case.inputs,
                executed=False,
                error="Java source must declare a public class.",
            )

        class_name = class_match.group(1)

        try:
            with tempfile.TemporaryDirectory(prefix="ast_test_java_") as temp_dir:
                source_path = Path(temp_dir) / f"{class_name}.java"
                source_path.write_text(source_code, encoding="utf-8")

                compile_result = subprocess.run(
                    ["javac", str(source_path)],
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
                        or "Java compilation failed.",
                    )

                # This first adapter version supplies inputs as JVM system
                # properties. Java programs must read them explicitly.
                properties = [
                    f"-D{key}={value}"
                    for key, value in test_case.inputs.items()
                ]

                run_result = subprocess.run(
                    ["java", *properties, "-cp", temp_dir, class_name],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=temp_dir,
                )

                return TestResult(
                    inputs=test_case.inputs,
                    executed=(run_result.returncode == 0),
                    output=run_result.stdout,
                    error=run_result.stderr.strip() or (
                        None if run_result.returncode == 0
                        else f"Java exited with code {run_result.returncode}."
                    ),
                )

        except subprocess.TimeoutExpired:
            return TestResult(
                inputs=test_case.inputs,
                executed=False,
                error="Java compilation or execution timed out.",
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
        """Execute a Java test case and verify its output."""
        from src.core.result_verifier import verify_output

        result = self.execute(source_code, test_case)
        return verify_output(result, expected_output)