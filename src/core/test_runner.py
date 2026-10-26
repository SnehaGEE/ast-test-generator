from typing import Any

from src.core.models import TestCase, TestResult
from src.core.targeted_generator import generate_targeted_inputs
from src.core.invalid_input_generator import generate_invalid_inputs
from src.core.fuzz_generator import generate_fuzz_inputs
from src.languages.python.adapter import PythonAdapter
from src.coverage.coverage_analyzer import (
    analyze_branch_coverage,
    suggest_missing_branch_tests,
)
from src.coverage.unsupported_syntax import find_unsupported_constructs

# When invalid-input or fuzz tests are requested, each one reserves this
# share of max_cases so the boundary tests cannot use every slot.
EXTRA_SHARE_PERCENT = 20


def _describe_unsupported(unsupported: list[dict[str, Any]]) -> str | None:
    """Build a user-facing note about constructs coverage ignores."""
    if not unsupported:
        return None

    parts: list[str] = []
    for item in unsupported:
        text = f"{item['construct']} (line {item['line']})"
        if text not in parts:
            parts.append(text)

    return (
        "Branch coverage does not track: "
        + "; ".join(parts)
        + ". The percentage covers only if/elif and while conditions."
    )


def _join_messages(*messages: str | None) -> str | None:
    """Join the non-empty messages, or return None if there are none."""
    present = [message for message in messages if message]
    return " ".join(present) if present else None


def _inputs_key(inputs: dict[str, Any]) -> str:
    """Return a hashable key identifying one set of test inputs."""
    return repr(sorted(inputs.items(), key=lambda item: item[0]))


def _base_row(
    variable_names: list[str],
    targeted_cases: list[dict[str, Any]],
) -> dict[str, Any]:
    """Pick one valid-looking value for each variable.

    Invalid and fuzz cases change one variable at a time. The other
    variables are filled from this row so the program does not fail
    on an undefined name before reaching the value being tested.
    Candidate values are listed in a condition's own order, and the
    second one satisfies that condition for every supported operator.
    """
    base: dict[str, Any] = {}

    for name in variable_names:
        values = list(
            dict.fromkeys(
                row[name] for row in targeted_cases if name in row
            )
        )
        if values:
            base[name] = values[1] if len(values) > 1 else values[0]

    return base


def _verified_suggestions(
    source_code: str,
    coverage: dict[str, Any],
    base: dict[str, Any],
) -> list[dict[str, Any]]:
    """Suggest inputs for missing branch outcomes and check each one.

    A suggestion changes one variable; the others come from the base
    row. It is run once and marked verified only if it really reaches
    the missing outcome, since other conditions can make it unreachable.
    """
    if not coverage.get("success"):
        return []

    suggestions = []
    for suggestion in suggest_missing_branch_tests(source_code, coverage):
        inputs = {**base, **suggestion["inputs"]}
        check = analyze_branch_coverage(source_code, [inputs])
        target = f"{suggestion['target_outcome']}_covered"
        verified = any(
            branch["line"] == suggestion["line"] and branch[target]
            for branch in check.get("branches", [])
        )
        suggestions.append({**suggestion, "inputs": inputs, "verified": verified})

    return suggestions


def _generate_invalid_spread(
    variable_names: list[str],
    limit: int,
) -> list[dict[str, Any]]:
    """Generate invalid inputs that rotate through the variables.

    generate_invalid_inputs fills one variable completely before moving
    to the next, so a small limit would only ever test the first one.
    """
    pools = [
        generate_invalid_inputs([name], max_cases=limit)
        for name in variable_names
    ]

    spread: list[dict[str, Any]] = []
    position = 0

    while len(spread) < limit and any(position < len(p) for p in pools):
        for pool in pools:
            if position < len(pool) and len(spread) < limit:
                spread.append(pool[position])
        position += 1

    return spread


def run_python_test_suite(
    source_code: str,
    max_cases: int = 100,
    include_invalid_inputs: bool = False,
    include_fuzz_inputs: bool = False,
) -> dict[str, Any]:
    """Generate and execute targeted, invalid-input, and fuzz tests."""

    if max_cases < 1:
        raise ValueError("max_cases must be at least 1")

    adapter = PythonAdapter()
    adapter.parse(source_code)
    conditions = adapter.analyze(source_code)
    unsupported = find_unsupported_constructs(source_code)
    unsupported_note = _describe_unsupported(unsupported)

    if (
        not conditions
        and not include_invalid_inputs
        and not include_fuzz_inputs
    ):
        return {
            "results": [],
            "total_tests": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "coverage": {
                "covered": 0,
                "total": 0,
                "percentage": 0.0,
                "success": True,
                "error": None,
                "branches": [],
                # None means "not measured", which is not the same as 0%.
                "branch_coverage_percent": None,
                "unsupported": unsupported,
                "suggestions": [],
            },
            "message": _join_messages(
                "No supported conditions were detected; "
                "no targeted tests were generated.",
                unsupported_note,
            ),
        }

    condition_data = [
        {
            "variable": condition.variable,
            "operator": condition.operator,
            "constant": condition.value,
            "line": condition.line,
        }
        for condition in conditions
    ]

    # (label, category, description) for each extra strategy requested.
    extras: list[tuple[str, str, str]] = []
    if include_invalid_inputs:
        extras.append(
            ("Invalid-input", "invalid", "Invalid-input candidate")
        )
    if include_fuzz_inputs:
        extras.append(("Fuzz", "fuzz", "Fuzz test candidate"))

    targeted_budget = max_cases
    if extras:
        reserve = max(1, max_cases * EXTRA_SHARE_PERCENT // 100)
        targeted_budget = max(1, max_cases - reserve * len(extras))

    targeted_cases = generate_targeted_inputs(
        condition_data,
        max_cases=targeted_budget,
    )

    planned: list[tuple[TestCase, str]] = [
        (
            TestCase(inputs=inputs, description="Boundary/targeted test"),
            "targeted",
        )
        for inputs in targeted_cases
    ]
    seen_inputs = {_inputs_key(case.inputs) for case, _ in planned}

    variable_names = list(
        dict.fromkeys(condition.variable for condition in conditions)
    )
    base = _base_row(variable_names, targeted_cases)

    not_generated: list[str] = []

    for position, (label, category, description) in enumerate(extras):
        # Split what is left fairly; the last strategy gets the rest.
        share = (max_cases - len(planned)) // (len(extras) - position)
        added = 0

        if share > 0:
            if category == "invalid":
                candidates = _generate_invalid_spread(variable_names, share)
            else:
                candidates = generate_fuzz_inputs(
                    variable_names,
                    max_cases=share,
                )

            for candidate in candidates:
                inputs = {**base, **candidate}
                key = _inputs_key(inputs)

                if key in seen_inputs:
                    continue

                seen_inputs.add(key)
                planned.append(
                    (TestCase(inputs=inputs, description=description),
                     category)
                )
                added += 1

        if added == 0:
            not_generated.append(label)

    extras_note = None
    if not_generated:
        names = " and ".join(not_generated)
        if not variable_names:
            reason = (
                "no input variables were found in supported conditions"
            )
        else:
            reason = (
                f"the limit of {max_cases} test cases left no room; "
                "raise the maximum to include them"
            )
        extras_note = f"{names} tests were requested but not generated: {reason}."

    results: list[TestResult] = []
    for case, category in planned:
        result = adapter.execute(source_code, case)
        result.category = category
        results.append(result)

    coverage = analyze_branch_coverage(
        source_code,
        [case.inputs for case, _ in planned],
    )
    coverage["unsupported"] = unsupported
    coverage["suggestions"] = _verified_suggestions(
        source_code, coverage, base
    )

    if not planned:
        base_message = (
            "No usable test inputs could be generated. "
            "Supported conditions or input variables may be required."
        )
    else:
        base_message = None

    return {
        "results": results,
        "total_tests": len(results),
        "successful_executions": sum(
            result.executed for result in results
        ),
        "failed_executions": sum(
            not result.executed for result in results
        ),
        "coverage": coverage,
        "message": _join_messages(
            base_message,
            extras_note,
            unsupported_note,
        ),
    }