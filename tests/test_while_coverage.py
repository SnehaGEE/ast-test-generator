from src.coverage.coverage_analyzer import analyze_branch_coverage

LOOP = "total = 0\nwhile n > 0:\n    total += n\n    n -= 1\n"


def _while_branch(result):
    return next(b for b in result["branches"] if b["kind"] == "while")


def test_loop_is_counted_as_a_branch():
    result = analyze_branch_coverage(LOOP, [{"n": 3}])
    assert len(result["branches"]) == 1
    assert _while_branch(result)["line"] == 2


def test_zero_iterations_covers_only_false():
    result = analyze_branch_coverage(LOOP, [{"n": 0}])
    branch = _while_branch(result)
    assert branch["true_covered"] is False
    assert branch["false_covered"] is True
    assert branch["missing"] == ["true"]
    assert result["branch_coverage_percent"] == 50.0


def test_multiple_iterations_cover_both_outcomes():
    result = analyze_branch_coverage(LOOP, [{"n": 3}])
    branch = _while_branch(result)
    assert branch["true_covered"] is True
    assert branch["false_covered"] is True
    assert result["branch_coverage_percent"] == 100.0


def test_separate_tests_combine():
    result = analyze_branch_coverage(LOOP, [{"n": 0}, {"n": 2}])
    assert result["branch_coverage_percent"] == 100.0


def test_break_does_not_record_false():
    source = "while True:\n    break\n"
    result = analyze_branch_coverage(source, [{}])
    branch = _while_branch(result)
    assert branch["true_covered"] is True
    assert branch["false_covered"] is False
    assert result["branch_coverage_percent"] == 50.0


def test_infinite_loop_terminates_and_keeps_partial_result():
    source = "while n > 0:\n    pass\n"
    result = analyze_branch_coverage(source, [{"n": 1}])
    branch = _while_branch(result)
    assert branch["true_covered"] is True
    assert branch["false_covered"] is False


def test_nested_if_inside_while_is_counted_separately():
    source = (
        "while n > 0:\n"
        "    if n % 2 == 0:\n"
        "        pass\n"
        "    n -= 1\n"
    )
    result = analyze_branch_coverage(source, [{"n": 1}])
    kinds = {b["kind"]: b for b in result["branches"]}
    assert kinds["while"]["missing"] == []
    assert kinds["if"]["true_covered"] is False
    assert kinds["if"]["false_covered"] is True
    assert result["branch_coverage_percent"] == 75.0

    full = analyze_branch_coverage(source, [{"n": 2}])
    assert full["branch_coverage_percent"] == 100.0


def test_if_only_behaviour_unchanged():
    source = "if x > 5:\n    y = 1\nelse:\n    y = 0\n"
    result = analyze_branch_coverage(source, [{"x": 10}])
    assert result["branches"][0]["kind"] == "if"
    assert result["branch_coverage_percent"] == 50.0