# tests/test_statement_coverage.py
"""Statement coverage: the share of a program's statements that ran.

The same program in each language, run with one known input (x = 5), so
the executed statements can be worked out by hand.
"""
import shutil

import pytest

from src.core.models import TestCase
from src.core.multi_language_runner import run_test_suite
from src.coverage.coverage_analyzer import analyze_branch_coverage
from src.languages.c.adapter import CAdapter
from src.languages.java.adapter import JavaAdapter

needs_java = pytest.mark.skipif(
    not (shutil.which("javac") and shutil.which("java")),
    reason="Java JDK is not installed",
)
needs_gcc = pytest.mark.skipif(
    not shutil.which("gcc"), reason="GCC is not installed"
)

PYTHON = '''def classify(n):
    """Docstrings and global declarations are not statements that run."""
    global LAST
    if n > 10:
        return 1
    return 0

x = int(input())
print(classify(x))
if x < 0:
    print("negative")
'''
# Statements: 1 def, 4 if, 5 return, 6 return, 8 x=, 9 print, 10 if, 11 print
# x = 5 runs 1, 8, 9, 4, 6, 10 -> missed 5 and 11.


def test_python_statement_coverage_counts_function_bodies():
    coverage = analyze_branch_coverage(PYTHON, [{"x": 5}])
    statements = coverage["statements"]
    assert statements["total"] == 8
    assert statements["covered"] == 6
    assert statements["missed_lines"] == [5, 11]
    assert coverage["statement_coverage_percent"] == 75.0


def test_python_more_inputs_cover_more_statements():
    coverage = analyze_branch_coverage(PYTHON, [{"x": 5}, {"x": 11}, {"x": -1}])
    assert coverage["statements"]["missed_lines"] == []
    assert coverage["statement_coverage_percent"] == 100.0


C_PROGRAM = r"""#include <stdio.h>
int classify(int n) {
    if (n > 10)
        return 1;
    return 0;
}
int main(void) {
    int x;
    scanf("%d", &x);
    printf("%d\n", classify(x));
    if (x < 0) {
        printf("negative\n");
    }
    return 0;
}
"""
# Statements: 3 if, 4 return (unbraced), 5 return, 8 int x, 9 scanf,
# 10 printf, 11 if, 12 printf, 14 return
# x = 5 runs 8, 9, 10, 3, 5, 11, 14 -> missed 4 and 12.

JAVA_PROGRAM = """import java.util.Scanner;
public class Classify {
    static int classify(int n) {
        if (n > 10)
            return 1;
        return 0;
    }
    public static void main(String[] args) {
        int x = new Scanner(System.in).nextInt();
        System.out.println(classify(x));
        if (x < 0) {
            System.out.println("negative");
        }
    }
}
"""
# Statements: 4 if, 5 return (unbraced), 6 return, 9 int x, 10 println,
# 11 if, 12 println
# x = 5 runs 9, 10, 4, 6, 11 -> missed 5 and 12.


def _compiled_coverage(adapter, source, x):
    with adapter.compile(source) as program:
        result, hits = program.run(TestCase(inputs={"x": x}))
        return result, program.coverage(hits)


@needs_gcc
def test_c_statement_coverage_and_unchanged_output():
    result, coverage = _compiled_coverage(CAdapter(), C_PROGRAM, 5)
    assert result.executed and result.output.strip() == "0"
    assert coverage["statements"] == {"covered": 7, "total": 9, "missed_lines": [4, 12]}
    assert coverage["statement_coverage_percent"] == 77.78


@needs_java
def test_java_statement_coverage_and_unchanged_output():
    result, coverage = _compiled_coverage(JavaAdapter(), JAVA_PROGRAM, 5)
    assert result.executed and result.output.strip() == "0"
    assert coverage["statements"] == {"covered": 5, "total": 7, "missed_lines": [5, 12]}
    assert coverage["statement_coverage_percent"] == 71.43


@pytest.mark.parametrize(
    "language, source",
    [
        pytest.param("python", PYTHON),
        pytest.param("c", C_PROGRAM, marks=needs_gcc),
        pytest.param("java", JAVA_PROGRAM, marks=needs_java),
    ],
)
def test_runs_report_statement_coverage(language, source):
    coverage = run_test_suite(source, language=language, max_cases=20)["coverage"]
    assert coverage["success"] is True
    assert 0 < coverage["statement_coverage_percent"] <= 100
    assert coverage["statements"]["covered"] <= coverage["statements"]["total"]
