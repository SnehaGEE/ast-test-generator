# tests/test_examples.py
"""Run every demo in examples/ and check each real output.

Coverage percentages are not trusted on their own: every executed test's
output is compared with a reference implementation of the program.
"""
import shutil
from pathlib import Path

import pytest

from src.core.multi_language_runner import run_test_suite

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _grade(score):
    if score < 0 or score > 100:
        return "Invalid score"
    if score >= 90:
        return "Grade A"
    if score >= 75:
        return "Grade B"
    if score >= 40:
        return "Grade C"
    return "Fail"


def _thermostat(temp):
    if temp < -10:
        return "Freezing"
    return "Comfortable" if temp <= 25 else "Hot"


def _countdown(n):
    return "\n".join([str(i) for i in range(n, 0, -1)] + ["Lift-off"])


def _login(attempts, age):
    if attempts >= 3:
        return "Locked"
    return "Login allowed" if age >= 30 else "New account: verify email"


def _run(path, language, max_cases=50):
    source = (EXAMPLES / path).read_text(encoding="utf-8")
    return run_test_suite(source, language=language, max_cases=max_cases)


# input() prompts are written to stdout, as in a terminal.
PROMPTS = (
    "Score: ",
    "Temperature: ",
    "Count down from: ",
    "Failed attempts: ",
    "Account age (days): ",
)


def _check_outputs(result, reference):
    executed = [test for test in result["results"] if test.executed]
    assert executed, "no generated test executed"
    for test in executed:
        output = test.output
        for prompt in PROMPTS:
            output = output.replace(prompt, "")
        assert output.strip() == reference(**test.inputs), test.inputs


@pytest.mark.parametrize(
    "path, reference, variables",
    [
        ("python/grade.py", _grade, {"score"}),
        ("python/thermostat.py", _thermostat, {"temp"}),
        ("python/countdown.py", _countdown, {"n"}),
        ("python/nested_login.py", _login, {"attempts", "age"}),
    ],
)
def test_python_examples(path, reference, variables):
    result = _run(path, "python")

    assert result["failed_executions"] == 0
    for test in result["results"]:
        assert set(test.inputs) == variables
    _check_outputs(
        result,
        lambda **inputs: reference(**{k: inputs[k] for k in variables}),
    )
    assert result["coverage"]["branch_coverage_percent"] == 100


def test_thermostat_covers_negative_boundary():
    result = _run("python/thermostat.py", "python")
    temps = {test.inputs["temp"] for test in result["results"]}
    assert {-11, -10, -9} <= temps


def test_nested_example_shows_unverified_suggestion():
    result = _run("python/nested_login.py", "python", max_cases=1)
    suggestions = result["coverage"]["suggestions"]
    assert suggestions
    assert any(not s["verified"] for s in suggestions)


@pytest.mark.skipif(
    not (shutil.which("javac") and shutil.which("java")),
    reason="Java JDK is not installed",
)
def test_java_example():
    result = _run("java/Grade.java", "java")
    assert result["failed_executions"] == 0
    _check_outputs(result, _grade)


@pytest.mark.skipif(not shutil.which("gcc"), reason="GCC is not installed")
def test_c_example():
    result = _run("c/grade.c", "c")
    assert result["failed_executions"] == 0
    _check_outputs(result, _grade)
