"""Compile-once execution with branch probes, shared by Java and C."""

import os
import subprocess
import tempfile
from abc import abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from src.core.interfaces import LanguageAdapter
from src.core.models import TestCase, TestResult
from src.languages.branch_probes import (
    PROBE_FILE_VARIABLE,
    Branch,
    find_branches,
    find_untracked,
    insert_probes,
    read_probe_hits,
    summarize_coverage,
)
from src.languages.input_plan import InputPlan

COMPILE_TIMEOUT_SECONDS = 15
RUN_TIMEOUT_SECONDS = 10

PROBE_BUILD_FAILED = (
    "The branch probes could not be compiled into this program, so "
    "coverage was not measured. The tests ran on the unmodified program."
)


class CompiledProgram:
    """A program built once in a temporary directory, run per test case."""

    def __init__(
        self,
        adapter: "CompiledLanguageAdapter",
        temp_dir: str | None = None,
        target: Any = None,
        plan: InputPlan | None = None,
        branches: list[Branch] | None = None,
        error: str | None = None,
        coverage_error: str | None = None,
    ) -> None:
        self.adapter = adapter
        self.temp_dir = temp_dir
        self.target = target
        self.plan = plan or InputPlan()
        self.branches = branches or []
        self.error = error
        self.coverage_error = coverage_error
        self._runs = 0

    def run(self, test_case: TestCase) -> tuple[TestResult, set[tuple[int, bool]]]:
        """Run one test case; return its result and the outcomes it reached."""
        if self.error is not None:
            return (
                TestResult(
                    inputs=test_case.inputs,
                    executed=False,
                    error=self.error,
                ),
                set(),
            )

        self._runs += 1
        probe_path = Path(self.temp_dir) / f"probe_{self._runs}.txt"
        command, stdin = self.adapter.run_command(
            self.target, self.temp_dir, test_case, self.plan
        )

        try:
            completed = subprocess.run(
                command,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=RUN_TIMEOUT_SECONDS,
                cwd=self.temp_dir,
                env={**os.environ, PROBE_FILE_VARIABLE: str(probe_path)},
            )
        except subprocess.TimeoutExpired:
            result = TestResult(
                inputs=test_case.inputs,
                executed=False,
                error=self.adapter.timeout_message,
            )
        except OSError as error:
            result = TestResult(
                inputs=test_case.inputs,
                executed=False,
                error=f"{type(error).__name__}: {error}",
            )
        else:
            result = TestResult(
                inputs=test_case.inputs,
                executed=completed.returncode == 0,
                output=completed.stdout,
                error=completed.stderr.strip()
                or (
                    None
                    if completed.returncode == 0
                    else f"{self.adapter.exit_label} exited with code "
                    f"{completed.returncode}."
                ),
            )

        return result, read_probe_hits(probe_path)

    def coverage(self, hits: set[tuple[int, bool]]) -> dict[str, Any]:
        """Coverage report for the outcomes reached by all runs."""
        if self.error is not None or self.coverage_error is not None:
            return {
                "success": False,
                "error": self.coverage_error
                or "The program did not compile, so coverage was not measured.",
                "branches": [],
                "branch_coverage_percent": None,
            }
        return summarize_coverage(self.branches, hits)


class CompiledLanguageAdapter(LanguageAdapter):
    """Base for languages that are compiled once and then run per test.

    Subclasses provide the parser, the build and run commands, and the
    probe code for their language.
    """

    display_name = ""
    exit_label = ""
    timeout_message = ""
    temp_prefix = "ast_test_"

    @abstractmethod
    def missing_tools(self) -> str | None:
        """Return an error message when the compiler is unavailable."""

    @abstractmethod
    def build(self, temp_dir: str, source_code: str) -> tuple[Any, str | None]:
        """Compile source in temp_dir; return (run target, error or None)."""

    @abstractmethod
    def run_command(
        self,
        target: Any,
        temp_dir: str,
        test_case: TestCase,
        plan: InputPlan,
    ) -> tuple[list[str], str]:
        """Return the command line and stdin text for one test case."""

    @abstractmethod
    def add_probes(self, source_bytes: bytes, branches: list[Branch]) -> str:
        """Return the source with every branch condition probed."""

    @abstractmethod
    def input_plan(self, source_code: str) -> InputPlan:
        """Find where the program reads each variable from."""

    def instrument(self, source_code: str) -> tuple[str, list[Branch]]:
        """Return probed source and the branches it tracks."""
        source_bytes = source_code.encode("utf-8")
        branches = find_branches(self.parser.parse(source_bytes).root_node)
        if not branches:
            return source_code, []
        return self.add_probes(source_bytes, branches), branches

    def untracked(self, source_code: str) -> list[dict[str, Any]]:
        """Constructs that run normally but are not counted in coverage."""
        tree = self.parser.parse(source_code.encode("utf-8"))
        return find_untracked(tree.root_node)

    @contextmanager
    def compile(self, source_code: str) -> Iterator[CompiledProgram]:
        """Build the probed program once; fall back to the plain program."""
        tools_error = self.missing_tools()
        if tools_error is not None:
            yield CompiledProgram(self, error=tools_error)
            return

        plan = self.input_plan(source_code)

        with tempfile.TemporaryDirectory(prefix=self.temp_prefix) as temp_dir:
            coverage_error = None
            try:
                probed, branches = self.instrument(source_code)
                target, error = self.build(temp_dir, probed)

                if error is not None and branches:
                    # Rebuild without probes. If the program itself is
                    # broken, this reports its own errors, not the
                    # probed text; otherwise the tests still run.
                    target, error = self.build(temp_dir, source_code)
                    branches = []
                    coverage_error = PROBE_BUILD_FAILED
            except subprocess.TimeoutExpired:
                yield CompiledProgram(
                    self, error=f"{self.display_name} compilation timed out."
                )
                return
            except OSError as error:
                yield CompiledProgram(
                    self, error=f"{type(error).__name__}: {error}"
                )
                return

            yield CompiledProgram(
                self,
                temp_dir=temp_dir,
                target=target,
                plan=plan,
                branches=branches,
                error=error,
                coverage_error=coverage_error,
            )

    def execute_many(
        self,
        source_code: str,
        test_cases: list[TestCase],
    ) -> list[TestResult]:
        """Compile once, then run every test case against that build."""
        with self.compile(source_code) as program:
            return [program.run(case)[0] for case in test_cases]

    def execute(self, source_code: str, test_case: TestCase) -> TestResult:
        return self.execute_many(source_code, [test_case])[0]

    def execute_and_verify(
        self,
        source_code: str,
        test_case: TestCase,
        expected_output: str,
    ) -> TestResult:
        """Execute a test case and verify its output."""
        from src.core.result_verifier import verify_output

        return verify_output(
            self.execute(source_code, test_case), expected_output
        )
