# tests/test_api.py
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

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


def test_oversized_source_is_rejected():
    with pytest.raises(ValidationError):
        api.TestRequest(source_code="x = 1\n" * 20000)


def test_built_frontend_is_served_beside_the_api(tmp_path):
    (tmp_path / "index.html").write_text("<p>BranchLab</p>", encoding="utf-8")
    app = FastAPI()
    app.get("/api/health")(api.health)
    api.serve_frontend(app, tmp_path)
    client = TestClient(app)

    assert "BranchLab" in client.get("/").text
    assert client.get("/api/health").json() == {"status": "ok"}


def test_missing_frontend_build_is_skipped(tmp_path):
    app = FastAPI()
    api.serve_frontend(app, tmp_path / "dist")
    assert TestClient(app).get("/").status_code == 404
