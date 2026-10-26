# tests/test_api.py
import pytest
from fastapi import HTTPException

import api

PROGRAM = (
    "if age >= 18:\n"
    "    print('Adult')\n"
    "else:\n"
    "    print('Minor')\n"
)


def _run(**fields):
    return api.run_tests(api.TestRequest(**fields))


def test_python_run_returns_labelled_results_and_coverage():
    response = _run(
        source_code=PROGRAM,
        language="Python",
        max_cases=20,
        include_invalid_inputs=True,
        include_fuzz_inputs=True,
    )

    assert response["language"] == "python"
    assert response["total_tests"] == len(response["results"])
    categories = {row["category"] for row in response["results"]}
    assert {"targeted", "invalid", "fuzz"} <= categories

    targeted = {
        row["inputs"]["age"]: row["output"].strip()
        for row in response["results"]
        if row["category"] == "targeted" and row["executed"]
    }
    assert targeted, "no targeted test executed"
    for age, output in targeted.items():
        assert output == ("Adult" if age >= 18 else "Minor"), age

    assert response["coverage"]["branch_coverage_percent"] == 100


def test_unknown_language_is_rejected():
    with pytest.raises(HTTPException) as error:
        _run(source_code=PROGRAM, language="ruby")
    assert error.value.status_code == 400


def test_python_syntax_error_is_a_400():
    with pytest.raises(HTTPException) as error:
        _run(source_code="if x >:\n    pass\n", language="python")
    assert error.value.status_code == 400
