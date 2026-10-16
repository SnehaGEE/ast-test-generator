
from dataclasses import dataclass
from typing import Any


@dataclass
class Condition:
    """A language-independent representation of a program condition."""

    variable: str
    operator: str
    value: Any
    line: int
    language: str


@dataclass
class TestCase:
    """A generated test case for a program."""

    inputs: dict[str, Any]
    description: str = ""


@dataclass
class TestResult:
    """The outcome of executing and checking a test case."""

    inputs: dict[str, Any]
    executed: bool
    output: str = ""
    error: str | None = None
    expected_output: str | None = None
    correctness: str = "unknown"
