# tests/test_benchmarks.py
"""Run every program in benchmarks/ and check each real output.

As in test_examples.py, coverage is not trusted on its own: every executed
test's output is compared with a reference implementation of the program.
"""
import shutil
from pathlib import Path

import pytest

from src.core.multi_language_runner import run_test_suite

BENCHMARKS = Path(__file__).resolve().parent.parent / "benchmarks"

needs_java = pytest.mark.skipif(
    not (shutil.which("javac") and shutil.which("java")),
    reason="Java JDK is not installed",
)
needs_gcc = pytest.mark.skipif(not shutil.which("gcc"), reason="GCC is not installed")

# Prompts are written to stdout, as in a terminal.
PROMPTS = (
    "Parcel weight (kg): ",
    "Distance (km): ",
    "Year: ",
    "Annual income (in thousands): ",
    "Age: ",
    "1. Add  2. Subtract  3. Multiply  4. Divide\n",
    "Choice: ",
    "Two numbers: ",
    "Enter units consumed: ",
    "Enter three sides: ",
)


def _shipping(weight, distance, **_):
    if weight <= 0 or distance <= 0:
        return "Invalid parcel"
    cost = 40 if weight <= 2 else 80 if weight <= 10 else 150
    if distance > 500:
        cost += 60
    elif distance > 100:
        cost += 25
    return f"Cost: {cost}"


def _leap_year(year, **_):
    if year < 1:
        return "Invalid year"
    leap = year % 400 == 0 or (year % 100 != 0 and year % 4 == 0)
    return "Leap year" if leap else "Not a leap year"


def _tax(income, age, **_):
    if income < 0 or age < 0:
        return "Invalid input"
    if income <= 300:
        rate = 0
    elif income <= 700:
        rate = 0.05
    elif income <= 1000:
        rate = 0.10
    elif income <= 1200:
        rate = 0.15
    else:
        rate = 0.20
    lines = []
    if age >= 60 and income > 300:
        rate = rate - 0.05
        lines.append("Senior citizen relief")
    lines.append(f"Tax: {income * rate:.2f}")
    return "\n".join(lines)


def _calculator(choice, b, a=1, **_):
    # `a` is read but appears in no condition, so it gets the placeholder 1.
    if choice == 1:
        return f"Sum: {a + b}"
    if choice == 2:
        return f"Difference: {a - b}"
    if choice == 3:
        return f"Product: {a * b}"
    if choice == 4:
        return "Cannot divide by zero" if b == 0 else f"Quotient: {int(a / b)}"
    return "Invalid choice"


def _electricity(units, **_):
    if units < 0:
        return "Invalid reading"
    if units <= 100:
        bill = units * 1.5
    elif units <= 200:
        bill = 150 + (units - 100) * 2.5
    elif units <= 300:
        bill = 400 + (units - 200) * 4.0
    else:
        bill = 800 + (units - 300) * 6.0
    lines = []
    if bill > 1000:
        bill *= 1.05
        lines.append("Surcharge applied")
    lines.append(f"Bill: {bill:.2f}")
    return "\n".join(lines)


def _triangle(a, b, c, **_):
    if a <= 0 or b <= 0 or c <= 0:
        return "Invalid side"
    if a + b <= c or a + c <= b or b + c <= a:
        return "Not a triangle"
    if a == b == c:
        return "Equilateral"
    if a == b or b == c or a == c:
        return "Isosceles"
    return "Scalene"


def _check(path, language, reference):
    source = (BENCHMARKS / path).read_text(encoding="utf-8")
    result = run_test_suite(source, language=language, max_cases=20)
    assert any(test.executed for test in result["results"]), "no generated test executed"
    for test in result["results"]:
        # The C programs exit with 1 on invalid input; nothing else may fail.
        assert test.executed or test.error == "C program exited with code 1.", (test.inputs, test.error)
        output = test.output
        for prompt in PROMPTS:
            output = output.replace(prompt, "")
        assert output.strip() == reference(**test.inputs), test.inputs
    return result


def test_shipping():
    result = _check("python/shipping.py", "python", _shipping)
    assert result["coverage"]["branch_coverage_percent"] == 100


def test_leap_year_remainder_conditions_are_not_targeted():
    result = _check("python/leap_year.py", "python", _leap_year)
    years = {test.inputs["year"] for test in result["results"]}
    assert years == {0, 1, 2}  # only year < 1 yields boundary values


@needs_java
def test_tax_slab():
    result = _check("java/TaxSlab.java", "java", _tax)
    assert result["coverage"]["branch_coverage_percent"] == 100


@needs_java
def test_calculator():
    result = _check("java/Calculator.java", "java", _calculator)
    choices = {test.inputs["choice"] for test in result["results"]}
    assert {1, 2, 3, 4} <= choices


@needs_gcc
def test_electricity_bill():
    _check("c/electricity_bill.c", "c", _electricity)


@needs_gcc
def test_triangle():
    result = _check("c/triangle.c", "c", _triangle)
    outputs = {test.output.strip() for test in result["results"]}
    assert not any("Scalene" in output for output in outputs)
