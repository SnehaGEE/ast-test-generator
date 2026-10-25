import builtins
import sys
import threading
import time

from src.parser.analyzer.generator.executor.test_executor import (
    execute_test_case,
)


def test_normal_program_returns_output():
    result = execute_test_case("print(n + 1)", {"n": 4})
    assert result["success"] is True
    assert result["output"] == "5\n"
    assert result["error"] is None
    assert result["input"] == {"n": 4}


def test_input_function_uses_generated_values():
    source = "value = input('? ')\nprint(int(value) * 2)"
    result = execute_test_case(source, {"a": 21})
    assert result["success"] is True
    assert result["output"] == "? 42\n"


def test_input_runs_out_of_values():
    result = execute_test_case("input()\ninput()", {"a": 1})
    assert result["success"] is False
    assert result["error"].startswith("EOFError")


def test_runtime_error_is_reported():
    result = execute_test_case("1 / 0", {})
    assert result["success"] is False
    assert result["error"] == "ZeroDivisionError: division by zero"


def test_syntax_error_is_reported():
    result = execute_test_case("def (", {})
    assert result["success"] is False
    assert result["error"].startswith("Invalid Python syntax")


def test_exit_zero_is_success_and_nonzero_is_failure():
    ok = execute_test_case("import sys\nsys.exit(0)", {})
    bad = execute_test_case("import sys\nsys.exit(3)", {})
    assert ok["success"] is True
    assert bad["success"] is False
    assert bad["error"] == "SystemExit: 3"


def test_hard_exit_without_result_is_reported():
    result = execute_test_case("import os\nos._exit(7)", {})
    assert result["success"] is False
    assert "exit code 7" in result["error"]


def test_huge_integer_input_round_trips():
    result = execute_test_case("print(n > 10**99)", {"n": 10**100})
    assert result["success"] is True
    assert result["output"] == "True\n"


def test_non_ascii_and_none_inputs():
    result = execute_test_case(
        "print(s, type(a).__name__)", {"s": "h\u00e9llo \u2603", "a": None}
    )
    assert result["success"] is True
    assert result["output"] == "h\u00e9llo \u2603 NoneType\n"


def test_unserialisable_input_is_reported_not_raised():
    result = execute_test_case("pass", {"a": object()})
    assert result["success"] is False
    assert "could not be passed" in result["error"]


def test_runaway_output_is_capped():
    result = execute_test_case("print('x' * 1_000_000)", {})
    assert result["success"] is True
    assert len(result["output"]) < 100_100
    assert result["output"].endswith("[output truncated]")


def test_timeout_reports_error_quickly():
    start = time.perf_counter()
    result = execute_test_case("while True:\n    pass", {}, timeout=1)
    assert result["success"] is False
    assert result["error"] == "Execution timed out after 1 seconds"
    assert time.perf_counter() - start < 3


def test_timeout_does_not_leak_threads_or_global_state():
    stdout_before = sys.stdout
    input_before = builtins.input
    threads_before = threading.active_count()

    execute_test_case("while n > 0:\n    pass", {"n": 1}, timeout=1)

    assert sys.stdout is stdout_before
    assert builtins.input is input_before
    assert threading.active_count() == threads_before


def test_timed_out_program_stops_using_cpu():
    execute_test_case("while True:\n    pass", {}, timeout=1)
    start = time.process_time()
    time.sleep(0.5)
    assert time.process_time() - start < 0.25