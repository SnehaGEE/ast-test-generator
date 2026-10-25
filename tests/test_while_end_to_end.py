# tests/test_while_end_to_end.py
from src.core.test_runner import run_python_test_suite

LOOP = (
    "total = 0\n"
    "while n > 0:\n"
    "    total += n\n"
    "    n -= 1\n"
    "print(total)\n"
)


def test_while_coverage_matches_generated_inputs():
    result = run_python_test_suite(LOOP, max_cases=20)

    values = [
        test.inputs["n"]
        for test in result["results"]
        if isinstance(test.inputs.get("n"), int)
        and not isinstance(test.inputs.get("n"), bool)
    ]
    assert values, "generator produced no integer inputs for n"

    coverage = result["coverage"]
    assert coverage["success"] is True

    loops = [b for b in coverage["branches"] if b["kind"] == "while"]
    assert len(loops) == 1

    assert loops[0]["true_covered"] == any(v > 0 for v in values)
    assert loops[0]["false_covered"] == any(v <= 0 for v in values)
    assert coverage["branch_coverage_percent"] > 0