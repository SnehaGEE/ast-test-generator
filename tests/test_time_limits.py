import sys
import time

from src.coverage.coverage_analyzer import (
    analyze_branch_coverage,
    measure_line_coverage,
)

HUGE_FOR = "if n > 0:\n    for i in range(n):\n        pass\n"

SWALLOWING_FOR = (
    "if n > 0:\n"
    "    for i in range(n):\n"
    "        try:\n"
    "            pass\n"
    "        except Exception:\n"
    "            pass\n"
)


def test_huge_for_loop_is_stopped_and_keeps_earlier_outcomes():
    start = time.perf_counter()
    result = analyze_branch_coverage(
        HUGE_FOR, [{"n": 10**100}], time_limit=0.5
    )
    assert time.perf_counter() - start < 5

    branch = result["branches"][0]
    assert branch["true_covered"] is True
    assert branch["false_covered"] is False


def test_program_cannot_swallow_the_time_limit():
    start = time.perf_counter()
    result = analyze_branch_coverage(
        SWALLOWING_FOR, [{"n": 10**100}], time_limit=0.5
    )
    assert time.perf_counter() - start < 5
    assert result["branches"][0]["true_covered"] is True


def test_exit_request_in_program_does_not_escape():
    source = "if n > 0:\n    raise SystemExit(1)\n"
    result = analyze_branch_coverage(source, [{"n": 1}])
    assert result["success"] is True
    assert result["branches"][0]["true_covered"] is True


def test_one_slow_input_does_not_block_the_others():
    start = time.perf_counter()
    result = analyze_branch_coverage(
        HUGE_FOR, [{"n": 10**100}, {"n": 0}], time_limit=0.5
    )
    assert time.perf_counter() - start < 5
    assert result["branches"][0]["missing"] == []


def test_tracer_is_restored_after_a_timeout():
    before = sys.gettrace()
    analyze_branch_coverage(HUGE_FOR, [{"n": 10**100}], time_limit=0.3)
    assert sys.gettrace() is before


def test_line_coverage_stops_infinite_loop():
    start = time.perf_counter()
    result = measure_line_coverage(
        "while True:\n    pass\n", {}, time_limit=0.5
    )
    assert time.perf_counter() - start < 5
    assert result["success"] is False
    assert "Time limit" in result["error"]


def test_line_coverage_reaches_100_when_every_line_runs():
    result = measure_line_coverage("x = 1\nif x:\n    y = 2\n", {})
    assert result["success"] is True
    assert 0 not in result["executable_lines"]
    assert result["line_coverage_percent"] == 100.0


def test_line_coverage_reports_unrun_lines():
    result = measure_line_coverage("x = 0\nif x:\n    y = 2\n", {})
    assert result["line_coverage_percent"] == 66.67
    assert result["executed_lines"] == [1, 2]