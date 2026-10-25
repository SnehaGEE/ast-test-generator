import time
from itertools import product

import pytest

from src.core.input_combinations import generate_input_combinations
from src.core.test_runner import run_python_test_suite

FIVE_VARS = {name: [0, 1, -1] for name in "abcde"}

DEEP = (
    "if a > 0:\n"
    "    if b > 0:\n"
    "        if c > 0:\n"
    "            if d > 0:\n"
    "                if e > 0:\n"
    "                    print('deepest')\n"
)


def test_small_product_keeps_original_rows_and_order():
    rows = generate_input_combinations(
        {"a": [0, 1], "b": [2, 3]}, max_cases=100
    )
    assert rows == [
        {"a": 0, "b": 2},
        {"a": 0, "b": 3},
        {"a": 1, "b": 2},
        {"a": 1, "b": 3},
    ]


def test_truncation_respects_cap_and_has_no_duplicates():
    rows = generate_input_combinations(FIVE_VARS, max_cases=20)
    assert len(rows) == 20
    assert len({tuple(row.items()) for row in rows}) == 20


def test_truncation_keeps_every_value_of_every_variable():
    rows = generate_input_combinations(FIVE_VARS, max_cases=20)
    for name, values in FIVE_VARS.items():
        assert {row[name] for row in rows} == set(values), name


def test_truncation_includes_the_all_second_values_row():
    rows = generate_input_combinations(FIVE_VARS, max_cases=20)
    assert {name: 1 for name in "abcde"} in rows


def test_huge_product_is_bounded_and_fast():
    variables = {f"v{i}": [0, 1, 2] for i in range(20)}  # 3**20 rows
    start = time.perf_counter()
    rows = generate_input_combinations(variables, max_cases=10)
    assert time.perf_counter() - start < 1.0
    assert len(rows) == 10
    assert len({tuple(row.items()) for row in rows}) == 10


def test_cap_of_one_keeps_the_first_product_row():
    assert generate_input_combinations({"a": [0, 1, 2]}, max_cases=1) == [
        {"a": 0}
    ]


def test_empty_inputs_and_validation_unchanged():
    assert generate_input_combinations({}, max_cases=5) == [{}]
    assert generate_input_combinations({"a": []}, max_cases=5) == []
    with pytest.raises(ValueError):
        generate_input_combinations({"a": [1]}, max_cases=0)


def test_deep_nesting_reaches_full_branch_coverage():
    result = run_python_test_suite(DEEP, max_cases=20)
    coverage = result["coverage"]

    assert result["total_tests"] == 20
    for branch in coverage["branches"]:
        assert branch["missing"] == [], branch
    assert coverage["branch_coverage_percent"] == 100.0