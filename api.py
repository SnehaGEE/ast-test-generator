
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from src.core.multi_language_runner import run_test_suite
from src.core.test_runner import run_python_test_suite


app = FastAPI(
    title="AST Test Generator API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TestRequest(BaseModel):
    source_code: str = Field(min_length=1)
    language: str = "python"
    max_cases: int = Field(default=20, ge=1, le=100)
    include_invalid_inputs: bool = False
    include_fuzz_inputs: bool = False


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/run")
def run_tests(request: TestRequest) -> dict[str, Any]:
    language = request.language.strip().lower()

    if language not in {"python", "java", "c"}:
        raise HTTPException(
            status_code=400,
            detail="Choose Python, Java, or C.",
        )

    try:
        if language == "python":
            result = run_python_test_suite(
                source_code=request.source_code,
                max_cases=request.max_cases,
                include_invalid_inputs=request.include_invalid_inputs,
                include_fuzz_inputs=request.include_fuzz_inputs,
            )
        else:
            result = run_test_suite(
                source_code=request.source_code,
                language=language,
                max_cases=request.max_cases,
            )

        return {
            "language": language,
            "total_tests": result["total_tests"],
            "successful_executions": result["successful_executions"],
            "failed_executions": result["failed_executions"],
            "coverage": result["coverage"],
            "message": result.get("message"),
            "results": [
                {
                    "inputs": test.inputs,
                    "executed": test.executed,
                    "output": test.output,
                    "error": test.error,
                    "expected_output": test.expected_output,
                    "correctness": test.correctness,
                }
                for test in result["results"]
            ],
        }

    except (SyntaxError, ValueError) as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Test generation failed: {error}",
        ) from error
