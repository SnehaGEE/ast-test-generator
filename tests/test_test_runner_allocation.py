from collections import Counter

from src.core.test_runner import run_python_test_suite

ONE_VAR = "age = int(input())\nif age >= 18:\n    print('adult')\n"
TWO_VARS = "if a > 0:\n    if b > 0:\n        print('both')\n"
THREE_VARS = (
    "if a > 0:\n"
    "    if b > 0:\n"
    "        if c > 0:\n"
    "            print('all')\n"
)
FIVE_VARS = (
    "if a > 0:\n"
    "    if b > 0:\n"
    "        if c > 0:\n"
    "            if d > 0:\n"
    "                if e > 0:\n"
    "                    print('deepest')\n"
)


def _run(source, cap=20, invalid=True, fuzz=True):
    return run_python_test_suite(
        source,
        max_cases=cap,
        include_invalid_inputs=invalid,
        include_fuzz_inputs=fuzz,
    )


def _counts(result):
    return Counter(test.category for test in result["results"])


def test_every_result_has_a_known_category():
    result = _run(TWO_VARS)
    assert result["total_tests"] > 0
    assert set(_counts(result)) <= {"targeted", "invalid", "fuzz"}
    assert sum(_counts(result).values()) == result["total_tests"]


def test_ticked_strategies_produce_tests_for_two_variables():
    result = _run(TWO_VARS)
    counts = _counts(result)
    assert counts["targeted"] == 9
    assert counts["invalid"] >= 1
    assert counts["fuzz"] >= 1
    assert result["total_tests"] <= 20


def test_ticked_strategies_produce_tests_for_three_variables():
    result = _run(THREE_VARS)
    counts = _counts(result)
    assert counts["targeted"] >= 1
    assert counts["invalid"] >= 1
    assert counts["fuzz"] >= 1
    assert result["total_tests"] <= 20


def test_single_variable_program_still_gets_all_three_kinds():
    counts = _counts(_run(ONE_VAR))
    assert counts["targeted"] == 3
    assert counts["invalid"] >= 1
    assert counts["fuzz"] >= 1


def test_invalid_cases_cover_every_variable():
    result = _run(TWO_VARS, fuzz=False)
    changed = set()
    for test in result["results"]:
        if test.category != "invalid":
            continue
        non_int = [
            name for name, value in test.inputs.items()
            if not isinstance(value, int)
        ]
        assert len(non_int) == 1, test.inputs
        assert set(test.inputs) == {"a", "b"}, test.inputs
        changed.add(non_int[0])
    assert changed == {"a", "b"}


def test_fuzz_and_invalid_cases_do_not_leave_variables_undefined():
    result = _run(THREE_VARS)
    for test in result["results"]:
        assert set(test.inputs) == {"a", "b", "c"}, test.inputs
        assert "NameError" not in (test.error or ""), test.inputs


def test_no_duplicate_inputs():
    result = _run(TWO_VARS)
    keys = [repr(sorted(test.inputs.items())) for test in result["results"]]
    assert len(keys) == len(set(keys))


def test_without_extras_all_slots_go_to_targeted_tests():
    result = _run(FIVE_VARS, cap=20, invalid=False, fuzz=False)
    assert _counts(result) == Counter({"targeted": 20})


def test_deep_nesting_with_extras_still_reaches_full_coverage():
    result = _run(FIVE_VARS, cap=20)
    coverage = result["coverage"]
    assert _counts(result)["targeted"] >= 11
    assert coverage["branch_coverage_percent"] == 100.0
    assert result["total_tests"] <= 20


def test_cap_is_never_exceeded():
    for cap in (1, 2, 3, 5, 10, 20, 50):
        result = _run(THREE_VARS, cap=cap)
        assert 1 <= result["total_tests"] <= cap, cap


def test_tiny_cap_explains_missing_strategies():
    result = _run(TWO_VARS, cap=1)
    assert result["total_tests"] == 1
    assert "Invalid-input and Fuzz tests were requested" in result["message"]


def test_no_message_when_everything_was_generated():
    result = _run(TWO_VARS)
    assert result["message"] is None


def test_requested_strategies_without_variables_are_explained():
    result = _run("print('hello')\n")
    assert "no input variables" in result["message"]


def test_unticked_extras_do_not_add_a_message():
    result = _run(TWO_VARS, invalid=False, fuzz=False)
    assert result["message"] is None


def test_no_conditions_reports_not_measured_instead_of_zero():
    result = run_python_test_suite("print('hello')\n", max_cases=20)
    coverage = result["coverage"]
    assert coverage["branch_coverage_percent"] is None
    assert coverage["branches"] == []
    assert coverage["percentage"] == 0.0
    assert result["message"]


def test_invalid_input_candidate_still_rejected_by_int_parsing():
    result = run_python_test_suite(
        "age = int(input('Enter age: '))\n"
        "if age >= 18:\n    print('Adult')\nelse:\n    print('Minor')\n",
        max_cases=20,
        include_invalid_inputs=True,
    )
    assert result["total_tests"] <= 20
    assert any(
        test.error and "ValueError" in test.error
        for test in result["results"]
    )


def test_boundary_inputs_still_produce_different_outputs():
    result = run_python_test_suite(
        "age = int(input('Enter age: '))\n"
        "if age >= 18:\n    print('Adult')\nelse:\n    print('Minor')\n"
    )
    outputs = {
        item.output.strip().split()[-1]
        for item in result["results"]
        if item.executed and item.output.strip()
    }
    assert {"Adult", "Minor"} <= outputs