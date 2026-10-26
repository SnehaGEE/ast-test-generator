# tests/test_coverage_suggestions.py
from src.core.test_runner import run_python_test_suite
from src.coverage.coverage_analyzer import analyze_branch_coverage

TWO_IFS = (
    "if age >= 18:\n"
    "    print('Adult')\n"
    "if score < 40:\n"
    "    print('Fail')\n"
)

NESTED = (
    "if age >= 18:\n"
    "    if score < 40:\n"
    "        print('Fail')\n"
)


def _outcome(source, inputs, line, target):
    coverage = analyze_branch_coverage(source, [inputs])
    branch = next(b for b in coverage["branches"] if b["line"] == line)
    return branch[f"{target}_covered"]


def test_missing_branches_get_complete_verified_suggestions():
    result = run_python_test_suite(TWO_IFS, max_cases=1)
    coverage = result["coverage"]
    assert coverage["branch_coverage_percent"] < 100

    suggestions = coverage["suggestions"]
    assert {(s["line"], s["target_outcome"]) for s in suggestions} == {
        (b["line"], target)
        for b in coverage["branches"]
        for target in b["missing"]
    }

    for suggestion in suggestions:
        # Every suggestion is a full input set, not one variable.
        assert set(suggestion["inputs"]) == {"age", "score"}
        # "verified" must match what really happens when it runs.
        assert suggestion["verified"] == _outcome(
            TWO_IFS,
            suggestion["inputs"],
            suggestion["line"],
            suggestion["target_outcome"],
        )
    assert all(s["verified"] for s in suggestions)


def test_full_coverage_has_no_suggestions():
    result = run_python_test_suite(TWO_IFS, max_cases=20)
    assert result["coverage"]["branch_coverage_percent"] == 100
    assert result["coverage"]["suggestions"] == []


def test_unreachable_suggestion_is_not_marked_verified():
    # One test with age < 18 never reaches the inner if, so its
    # outcomes cannot be covered by changing score alone.
    result = run_python_test_suite(NESTED, max_cases=1)
    for suggestion in result["coverage"]["suggestions"]:
        assert suggestion["verified"] == _outcome(
            NESTED,
            suggestion["inputs"],
            suggestion["line"],
            suggestion["target_outcome"],
        )
