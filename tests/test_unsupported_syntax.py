from src.core.test_runner import run_python_test_suite
from src.coverage.unsupported_syntax import find_unsupported_constructs

MATCH = (
    "match cmd:\n"
    "    case 1:\n"
    "        print('one')\n"
    "    case _:\n"
    "        print('other')\n"
)


def _constructs(source):
    return [
        (item["line"], item["construct"])
        for item in find_unsupported_constructs(source)
    ]


def test_match_statement_detected():
    assert _constructs(MATCH) == [(1, "match/case statement")]


def test_for_loop_detected():
    assert _constructs("for i in range(3):\n    print(i)\n") == [
        (1, "for loop")
    ]


def test_conditional_expression_detected():
    assert _constructs("y = 1 if x > 0 else 2\n") == [
        (1, "conditional expression")
    ]


def test_comprehension_filter_detected():
    source = "ys = [v for v in xs if v > 0]\n"
    assert _constructs(source) == [(1, "comprehension filter")]


def test_plain_if_and_while_not_flagged():
    source = "if a > 0:\n    pass\nwhile b > 0:\n    b -= 1\n"
    assert _constructs(source) == []


# Cases of `match name:` are analyzed (see test_switch_cases.py), so a
# subject that is an expression keeps this program untestable.
MATCH_ON_EXPRESSION = MATCH.replace("match cmd:", "match cmd.lower():")


def test_match_program_reports_unsupported_and_keeps_old_keys():
    result = run_python_test_suite(MATCH_ON_EXPRESSION, max_cases=20)

    assert result["total_tests"] == 0
    assert result["results"] == []
    assert "match/case" in result["message"]

    coverage = result["coverage"]
    for key in ("covered", "total", "percentage"):
        assert key in coverage
    assert coverage["unsupported"][0]["construct"] == "match/case statement"


def test_mixed_program_mentions_unsupported_in_message():
    source = (
        "if x > 5:\n"
        "    print('big')\n"
        "for i in range(3):\n"
        "    print(i)\n"
    )
    result = run_python_test_suite(source, max_cases=20)

    assert len(result["coverage"]["branches"]) == 1
    assert "for loop" in result["message"]
    assert result["coverage"]["unsupported"][0]["line"] == 3


def test_supported_program_has_no_message():
    source = "if x > 5:\n    print('big')\n"
    result = run_python_test_suite(source, max_cases=20)

    assert result["message"] is None
    assert result["coverage"]["unsupported"] == []