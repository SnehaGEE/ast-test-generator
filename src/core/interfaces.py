
from abc import ABC, abstractmethod
from typing import Any

from src.core.models import Condition, TestCase, TestResult


class LanguageAdapter(ABC):
    """Common interface for supported programming languages."""

    @abstractmethod
    def parse(self, source_code: str) -> Any:
        """Parse source code into a language-specific representation."""
        pass

    @abstractmethod
    def analyze(self, source_code: str) -> list[Condition]:
        """Extract supported conditions from source code."""
        pass

    @abstractmethod
    def execute(
        self,
        source_code: str,
        test_case: TestCase
    ) -> TestResult:
        """Execute a test case and return its result."""
        pass

    def execute_many(
        self,
        source_code: str,
        test_cases: list[TestCase],
    ) -> list[TestResult]:
        """Execute several test cases; compiled languages build once."""
        return [
            self.execute(source_code, test_case)
            for test_case in test_cases
        ]
