# tests/test_java_c_coverage.py
"""Java and C branch coverage, checked against the real test inputs.

For each program, the expected true/false outcomes are worked out from
the generated inputs with a reference model, and must equal what the
probes reported. A coverage number is never accepted on its own.
"""
import shutil
from pathlib import Path

import pytest

from src.core.multi_language_runner import run_test_suite

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"

needs_java = pytest.mark.skipif(
    not (shutil.which("javac") and shutil.which("java")),
    reason="Java JDK is not installed",
)
needs_gcc = pytest.mark.skipif(
    not shutil.which("gcc"), reason="GCC is not installed"
)

LANGUAGES = pytest.mark.parametrize(
    "language, path",
    [
        pytest.param("java", "java/Grade.java", marks=needs_java),
        pytest.param("c", "c/grade.c", marks=needs_gcc),
    ],
)


def _if_lines(source):
    return [
        number
        for number, text in enumerate(source.splitlines(), start=1)
        if "if (" in text
    ]


def _grade_outcomes(score, lines):
    """(line, outcome) pairs the grade if/else-if chain evaluates."""
    checks = [
        score < 0 or score > 100,
        score >= 90,
        score >= 75,
        score >= 40,
    ]
    seen = set()
    for line, result in zip(lines, checks):
        seen.add((line, result))
        if result:
            break
    return seen


def _observed(coverage):
    seen = set()
    for branch in coverage["branches"]:
        if branch["true_covered"]:
            seen.add((branch["line"], True))
        if branch["false_covered"]:
            seen.add((branch["line"], False))
    return seen


@LANGUAGES
@pytest.mark.parametrize("max_cases", [1, 3, 50])
def test_grade_coverage_matches_inputs(language, path, max_cases):
    source = (EXAMPLES / path).read_text(encoding="utf-8")
    lines = _if_lines(source)
    result = run_test_suite(source, language=language, max_cases=max_cases)
    coverage = result["coverage"]

    assert coverage["success"] is True, coverage.get("error")
    assert [b["line"] for b in coverage["branches"]] == lines
    assert all(b["kind"] == "if" for b in coverage["branches"])

    expected = set()
    for test in result["results"]:
        expected |= _grade_outcomes(test.inputs["score"], lines)
    assert _observed(coverage) == expected

    percent = round(len(expected) / (2 * len(lines)) * 100, 2)
    assert coverage["branch_coverage_percent"] == percent
    for branch in coverage["branches"]:
        assert branch["missing"] == [
            label
            for label, flag in (("true", True), ("false", False))
            if (branch["line"], flag) not in expected
        ]


C_LOOP_AND_EXIT = r"""
#include <stdio.h>
#include <stdlib.h>
int main(void) {
    int n, stop;
    scanf("%d", &n);
    scanf("%d", &stop);
    while (n > 2) {
        n--;
    }
    if (stop == 7) {
        exit(3);
    }
    printf("done\n");
    return 0;
}
"""

JAVA_LOOP_AND_EXIT = """
import java.util.Scanner;
public class LoopExit {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in);
        int n = in.nextInt();
        int stop = in.nextInt();
        while (n > 2) {
            n--;
        }
        if (stop == 7) {
            System.exit(3);
        }
        System.out.println("done");
    }
}
"""


@pytest.mark.parametrize(
    "language, source",
    [
        pytest.param("c", C_LOOP_AND_EXIT, marks=needs_gcc),
        pytest.param("java", JAVA_LOOP_AND_EXIT, marks=needs_java),
    ],
)
def test_while_and_early_exit(language, source):
    result = run_test_suite(source, language=language, max_cases=20)
    coverage = result["coverage"]
    assert coverage["success"] is True, coverage.get("error")

    loop, check = coverage["branches"]
    assert loop["kind"] == "while" and check["kind"] == "if"

    ns = [t.inputs["n"] for t in result["results"]]
    stops = [t.inputs["stop"] for t in result["results"]]
    # The body runs when n > 2; the loop always exits through its condition.
    assert loop["true_covered"] == any(n > 2 for n in ns)
    assert loop["false_covered"] is True
    # exit(3) must not lose the outcome recorded just before it.
    assert check["true_covered"] == (7 in stops)
    assert check["false_covered"] == any(s != 7 for s in stops)

    for test in result["results"]:
        if test.inputs["stop"] == 7:
            assert test.executed is False and "code 3" in test.error
        else:
            assert test.output.strip() == "done"


C_UNTRACKED = r"""
#include <stdio.h>
int main(void) {
    int x;
    scanf("%d", &x);
    for (int i = 0; i < x; i++) { }
    switch (x) { case 1: break; default: break; }
    int y = x > 5 ? 1 : 0;
    do { x--; } while (x > 100);
    if (x > 3) { printf("big\n"); }
    return y;
}
"""


@needs_gcc
def test_c_untracked_constructs_are_reported():
    result = run_test_suite(C_UNTRACKED, language="c", max_cases=10)
    coverage = result["coverage"]
    constructs = {item["construct"] for item in coverage["unsupported"]}
    assert constructs == {
        "for loop",
        "switch statement",
        "conditional expression",
        "do-while loop",
    }
    assert [b["kind"] for b in coverage["branches"]] == ["if"]
    assert "for loop" in result["message"]
