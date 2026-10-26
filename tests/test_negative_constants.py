# tests/test_negative_constants.py
from src.core.test_runner import run_python_test_suite
from src.parser.analyzer.condition_analyzer import analyze_source


def _triples(source):
    return [
        (c["variable"], c["operator"], c["constant"])
        for c in analyze_source(source)
    ]


def test_detects_negative_int_constant():
    assert _triples("if x > -5:\n    pass\n") == [("x", ">", -5)]


def test_detects_reversed_negative_constant():
    assert _triples("if -5 < x:\n    pass\n") == [("x", ">", -5)]


def test_detects_negative_float_constant():
    assert _triples("if x == -1.5:\n    pass\n") == [("x", "==", -1.5)]


def test_detects_explicit_positive_constant():
    assert _triples("if x <= +3:\n    pass\n") == [("x", "<=", 3)]


def test_ignores_negated_variable():
    assert _triples("if x > -y:\n    pass\n") == []


NEGATIVE_BRANCH = (
    "if x > -5:\n"
    "    print('above')\n"
    "else:\n"
    "    print('at or below')\n"
)


def test_negative_constant_generates_inputs_on_both_sides():
    result = run_python_test_suite(NEGATIVE_BRANCH, max_cases=20)

    values = [
        test.inputs["x"]
        for test in result["results"]
        if isinstance(test.inputs.get("x"), (int, float))
        and not isinstance(test.inputs.get("x"), bool)
    ]
    assert values, "generator produced no numeric inputs for x"

    # Check the real inputs, not just the coverage percentage.
    assert any(v > -5 for v in values)
    assert any(v <= -5 for v in values)
    assert -5 in values

    coverage = result["coverage"]
    assert coverage["success"] is True
    assert coverage["branch_coverage_percent"] == 100
