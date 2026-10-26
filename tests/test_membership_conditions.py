# tests/test_membership_conditions.py
from src.parser.analyzer.condition_analyzer import analyze_source


def _triples(source):
    return [
        (c["variable"], c["operator"], c["constant"])
        for c in analyze_source(source)
    ]


def test_constant_in_variable_is_not_reversed():
    # `3 in xs` tests membership in xs; it is not `xs not in 3`.
    assert _triples("if 3 in xs:\n    pass\n") == []
    assert _triples("if 3 not in xs:\n    pass\n") == []


def test_variable_in_constant_is_kept():
    assert _triples("if x in 'abc':\n    pass\n") == [("x", "in", "abc")]


def test_reversed_identity_and_order_comparisons_still_work():
    assert _triples("if None is x:\n    pass\n") == [("x", "is", None)]
    assert _triples("if 10 <= x:\n    pass\n") == [("x", ">=", 10)]
