# tests/test_java_numeric_literals.py
import pytest

from src.languages.java.adapter import JavaAdapter


def _conditions(condition):
    source = (
        "public class A { static void f(int x) { if ("
        + condition
        + ") { } } }"
    )
    return [
        (c.variable, c.operator, c.value)
        for c in JavaAdapter().analyze(source)
    ]


@pytest.mark.parametrize(
    "condition, expected",
    [
        ("x > -5", ("x", ">", -5)),
        ("x <= -2.5", ("x", "<=", -2.5)),
        ("x == +3", ("x", "==", 3)),
        ("x > 5L", ("x", ">", 5)),
        ("x < 2.5f", ("x", "<", 2.5)),
        ("x >= 1_000", ("x", ">=", 1000)),
    ],
)
def test_signed_and_suffixed_literals(condition, expected):
    assert _conditions(condition) == [expected]


def test_negated_variable_is_ignored():
    assert _conditions("x > -y") == []
