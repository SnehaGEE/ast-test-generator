
import ast

from src.core.input_order import python_answers
from src.core.interfaces import LanguageAdapter
from src.core.models import Condition, TestCase, TestResult
from src.parser.analyzer.condition_analyzer import analyze_source
from src.parser.analyzer.generator.executor.test_executor import (
    execute_test_case,
)


class PythonAdapter(LanguageAdapter):
    """Connect existing Python modules to the shared framework."""

    def parse(self, source_code: str) -> ast.AST:
        """Parse Python source into an AST."""
        return ast.parse(source_code)

    def analyze(self, source_code: str) -> list[Condition]:
        """Convert detected conditions into shared models."""
        detected = analyze_source(source_code)

        return [
            Condition(
                variable=item["variable"],
                operator=item["operator"],
                value=item["constant"],
                line=item["line"],
                language="python",
            )
            for item in detected
        ]

    def execute(
        self,
        source_code: str,
        test_case: TestCase,
    ) -> TestResult:
        """Execute a test case and normalize its result."""
        result = execute_test_case(
            source_code,
            test_case.inputs,
            answers=python_answers(source_code, test_case.inputs),
        )

        return TestResult(
            inputs=test_case.inputs,
            executed=result["success"],
            output=result.get("output", ""),
            error=result.get("error"),
        )
    
    def execute_and_verify(
        self,
        source_code: str,
        test_case: TestCase,
        expected_output: str,
    ) -> TestResult:
        """Execute a test case and verify its expected output."""

        from src.core.result_verifier import verify_output

        result = self.execute(source_code, test_case)

        return verify_output(result, expected_output)
