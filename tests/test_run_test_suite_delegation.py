# tests/test_run_test_suite_delegation.py
import shutil

import pytest

from src.core.multi_language_runner import run_test_suite
from src.core.test_runner import run_python_test_suite

PROGRAM = (
    "if age >= 18:\n"
    "    print('Adult')\n"
    "else:\n"
    "    print('Minor')\n"
)

MIXED = (
    "if age >= 18:\n"
    "    print('Adult')\n"
    "for i in range(2):\n"
    "    print(i)\n"
)


def _summary(result):
    return (
        result["total_tests"],
        [(t.inputs, t.output, t.category) for t in result["results"]],
        result["coverage"]["branch_coverage_percent"],
        result["message"],
    )


def test_python_path_matches_run_python_test_suite():
    expected = run_python_test_suite(
        PROGRAM,
        max_cases=20,
        include_invalid_inputs=True,
        include_fuzz_inputs=True,
    )
    actual = run_test_suite(
        PROGRAM,
        language="python",
        max_cases=20,
        include_invalid_inputs=True,
        include_fuzz_inputs=True,
    )

    assert _summary(actual) == _summary(expected)
    categories = {t.category for t in actual["results"]}
    assert {"targeted", "invalid", "fuzz"} <= categories


def test_python_path_reports_unsupported_syntax():
    result = run_test_suite(MIXED, language="python", max_cases=20)

    assert "for loop" in result["message"]
    assert all(t.category == "targeted" for t in result["results"])


@pytest.mark.skipif(not shutil.which("gcc"), reason="GCC is not installed")
def test_c_path_says_invalid_and_fuzz_are_python_only():
    source = r"""
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char *argv[]) {
    int age = argc > 1 ? atoi(argv[1]) : 0;
    if (age >= 18) { printf("Adult\n"); }
    return 0;
}
"""
    result = run_test_suite(
        source,
        language="c",
        max_cases=10,
        include_invalid_inputs=True,
        include_fuzz_inputs=True,
    )

    assert "only available for Python" in result["message"]
    # C branch coverage is measured with probes (test_java_c_coverage.py).
    assert result["coverage"]["success"] is True
