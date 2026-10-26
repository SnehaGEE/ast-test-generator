# tests/test_java_c_strategies.py
"""Invalid-input tests, fuzz tests and coverage suggestions for Java and C."""
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


def _source(path):
    return (EXAMPLES / path).read_text(encoding="utf-8")


def _if_lines(source):
    return [
        number
        for number, text in enumerate(source.splitlines(), start=1)
        if "if (" in text
    ]


def _grade_outcomes(score, lines):
    checks = [score < 0 or score > 100, score >= 90, score >= 75, score >= 40]
    seen = set()
    for line, result in zip(lines, checks):
        seen.add((line, result))
        if result:
            break
    return seen


@LANGUAGES
def test_invalid_and_fuzz_tests_run(language, path):
    result = run_test_suite(
        _source(path),
        language=language,
        max_cases=20,
        include_invalid_inputs=True,
        include_fuzz_inputs=True,
    )

    categories = [test.category for test in result["results"]]
    assert {"targeted", "invalid", "fuzz"} <= set(categories)
    assert len(categories) <= 20
    assert "only available for Python" not in (result["message"] or "")

    inputs = [repr(sorted(test.inputs.items())) for test in result["results"]]
    assert len(inputs) == len(set(inputs)), "duplicate test inputs"

    garbage = [
        test for test in result["results"]
        if test.inputs.get("score") == "garbage"
    ]
    assert garbage, "no invalid-input case with a non-numeric value"
    if language == "java":
        # Integer.parseInt rejects it, and the run says so.
        assert garbage[0].executed is False
        assert "NumberFormatException" in garbage[0].error
    else:
        # atoi("garbage") quietly returns 0, which grades as Fail.
        assert garbage[0].output.strip() == "Fail"


@LANGUAGES
def test_suggestions_are_verified_against_reality(language, path):
    source = _source(path)
    lines = _if_lines(source)
    result = run_test_suite(source, language=language, max_cases=1)
    coverage = result["coverage"]
    assert coverage["branch_coverage_percent"] < 100

    suggestions = coverage["suggestions"]
    missing = {
        (b["line"], target)
        for b in coverage["branches"]
        for target in b["missing"]
    }
    assert suggestions
    for suggestion in suggestions:
        key = (suggestion["line"], suggestion["target_outcome"])
        assert key in missing
        reached = (
            suggestion["line"],
            suggestion["target_outcome"] == "true",
        ) in _grade_outcomes(suggestion["inputs"]["score"], lines)
        assert suggestion["verified"] == reached, suggestion


C_NESTED = r"""
#include <stdio.h>
int main(void) {
    int attempts, age;
    scanf("%d", &attempts);
    scanf("%d", &age);
    if (attempts < 3) {
        if (age >= 30) {
            printf("allowed\n");
        }
    }
    return 0;
}
"""


@needs_gcc
def test_unreachable_suggestion_is_not_verified():
    result = run_test_suite(C_NESTED, language="c", max_cases=1)
    [test] = result["results"]
    assert test.inputs["attempts"] >= 3, "expected the outer if to be false"

    inner = [s for s in result["coverage"]["suggestions"] if s["line"] == 8]
    assert inner, "expected suggestions for the unreached inner if"
    for suggestion in inner:
        assert suggestion["inputs"]["attempts"] >= 3
        assert suggestion["verified"] is False
