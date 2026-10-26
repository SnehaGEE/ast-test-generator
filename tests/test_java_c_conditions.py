# tests/test_java_c_conditions.py
"""Java and C condition analysis should find what Python's analyzer finds."""
import pytest

from src.languages.c.adapter import CAdapter
from src.languages.java.adapter import JavaAdapter
from src.parser.analyzer.condition_analyzer import analyze_source


def _java(body):
    source = "public class A { static void f(int x, int y) { " + body + " } }"
    return [(c.variable, c.operator, c.value) for c in JavaAdapter().analyze(source)]


def _c(body):
    source = "void f(int x, int y) { " + body + " }"
    return [(c.variable, c.operator, c.value) for c in CAdapter().analyze(source)]


BOTH = pytest.mark.parametrize("analyze", [_java, _c], ids=["java", "c"])


@BOTH
def test_while_condition(analyze):
    assert analyze("while (x > 0) { x--; }") == [("x", ">", 0)]


@BOTH
def test_do_while_condition(analyze):
    assert analyze("do { x--; } while (x >= 3);") == [("x", ">=", 3)]


@BOTH
@pytest.mark.parametrize(
    "condition, expected",
    [
        ("5 < x", ("x", ">", 5)),
        ("5 <= x", ("x", ">=", 5)),
        ("5 > x", ("x", "<", 5)),
        ("5 >= x", ("x", "<=", 5)),
        ("5 == x", ("x", "==", 5)),
        ("5 != x", ("x", "!=", 5)),
        ("-5 < x", ("x", ">", -5)),
    ],
)
def test_reversed_operands(analyze, condition, expected):
    assert analyze(f"if ({condition}) {{ }}") == [expected]


@BOTH
def test_two_variables_are_not_a_constant_condition(analyze):
    assert analyze("if (x > y) { }") == []


@pytest.mark.parametrize(
    "literal, value",
    [("0x10", 16), ("0b101", 5), ("017", 15), ("0x1F", 31), ("10L", 10)],
)
def test_java_integer_literal_forms(literal, value):
    assert _java(f"if (x > {literal}) {{ }}") == [("x", ">", value)]


@pytest.mark.parametrize(
    "literal, value",
    [("0x10", 16), ("017", 15), ("5u", 5), ("5UL", 5), ("2.5f", 2.5), ("0x1F", 31)],
)
def test_c_integer_literal_forms(literal, value):
    assert _c(f"if (x > {literal}) {{ }}") == [("x", ">", value)]


def test_python_not_is_analyzed():
    conditions = analyze_source("if not x > 5:\n    pass\n")
    assert [(c["variable"], c["operator"], c["constant"]) for c in conditions] == [
        ("x", ">", 5)
    ]
