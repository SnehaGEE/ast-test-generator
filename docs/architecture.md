# BranchLab architecture

This document explains how a request moves through BranchLab and where
each part lives in the code.

## Overview

```
React UI (frontend/src/App.jsx)
   │  POST /api/run {source_code, language, max_cases, include_*}
   ▼
FastAPI (api.py)
   │
   ▼
run_test_suite (src/core/multi_language_runner.py)
   ├── python ──► run_python_test_suite (src/core/test_runner.py)
   │                ├── PythonAdapter.analyze ──► condition_analyzer.py
   │                ├── generate_targeted_inputs ──► boundary values + combinations
   │                ├── invalid / fuzz generators (optional)
   │                ├── PythonAdapter.execute ──► test_executor.py ──► sandbox_worker.py
   │                ├── analyze_branch_coverage (src/coverage/coverage_analyzer.py)
   │                └── verified suggestions for missing outcomes
   └── java / c ──► JavaAdapter / CAdapter
                    ├── analyze (Tree-sitter)
                    ├── generate_targeted_inputs
                    └── execute_many: compile once, run each case
```

## 1. Language adapters

Every language implements `LanguageAdapter` (`src/core/interfaces.py`):

| Method | Purpose |
| --- | --- |
| `parse(source)` | Build the syntax tree; reject empty or invalid source with `ValueError`/`SyntaxError`. |
| `analyze(source)` | Return `Condition(variable, operator, value, line, language)` objects. |
| `execute(source, case)` | Run one test case and return a `TestResult`. |
| `execute_many(source, cases)` | Run several cases. The default loops over `execute`; Java and C override it to compile once. |

- **Python** (`src/languages/python/adapter.py`) uses the built-in `ast`
  module through `ConditionAnalyzer`. It visits `If` and `While` nodes,
  descends into `and`/`or`, normalises reversed comparisons (`10 <= x`
  becomes `x >= 10`) and folds signed literals (`-5`).
- **Java** and **C** use Tree-sitter grammars. They walk `if_statement`
  nodes and accept `identifier <op> numeric literal`, including signed
  literals. Java also accepts suffixed literals (`5L`, `2.5f`).

## 2. Test input generation

`generate_targeted_inputs` (`src/core/targeted_generator.py`):

1. For each condition, `generate_boundary_tests` returns the constant and
   its neighbours: adjacent integers, or the nearest representable floats
   for float constants. The values are ordered so that the second one
   always satisfies the condition.
2. `generate_input_combinations` combines values across variables. When
   the full product is larger than `max_cases`, it picks diagonal rows
   first, then rows that change one variable at a time, then evenly spaced
   rows, so a small budget still varies every variable.

For Python, `run_python_test_suite` can add **invalid-input** and **fuzz**
cases. Each enabled strategy reserves about 20% of `max_cases`. These
cases change one variable and fill the others from a "base row" of valid
values, so the program reaches the value under test instead of failing
early on an undefined name. Duplicate input sets are removed.

Every result carries a `category`: `targeted`, `invalid` or `fuzz`.

## 3. Execution

- **Python**: `execute_test_case` starts `sandbox_worker.py` in a new
  `python -I` process and sends the program and inputs as JSON. The worker
  injects inputs as globals and as answers to `input()`, caps output at
  100,000 characters, and returns output or the error. The parent kills
  the process when it exceeds the time limit. This isolates hangs and
  crashes; it does not restrict what the program can access.
- **Java**: writes `<PublicClass>.java` to a temporary directory, runs
  `javac` once, then `java -D<name>=<value> ...` for each case.
- **C**: runs `gcc` once, then the executable for each case with values as
  arguments in alphabetical key order (`argc` sets the argument count).

A compile error is reported on every test result. Timeouts are recorded
per test, so one hanging input does not fail the others.

## 4. Branch coverage (Python)

`analyze_branch_coverage` runs each test input under a line tracer and
records, for every `if`/`elif`/`while` condition, whether its **true** and
**false** outcomes were actually observed:

- For an `if`, the outcome is the value of the condition.
- For a `while`, *true* means the body ran at least once and *false* means
  the condition was evaluated false and the loop exited normally.

The percentage is observed outcomes divided by total outcomes.
`find_unsupported_constructs` lists `for` loops, `match`/`case`,
conditional expressions and comprehension filters, which are excluded
from the percentage; the UI shows them next to the number.

Java and C report `branch_coverage_percent: null` ("not measured").

## 5. Coverage suggestions

`suggest_missing_branch_tests` proposes a boundary value for each missing
outcome of a simple numeric condition. `_verified_suggestions` in
`test_runner.py` completes it with the base row, runs it once, and sets
`verified` only if the missing outcome really occurred. A nested condition
that the base row never reaches is therefore shown as *not reached*
instead of being presented as a fix.

## 6. Frontend

`frontend/src/App.jsx` is a single React component:

- Monaco editor with Python, Java and C starter programs.
- Settings for max cases (1-100) and the Python-only strategies.
- Result tabs: generated tests (category, inputs, status, output, error),
  execution output, and coverage (per-branch table, suggestions,
  unsupported constructs).
- A backend status light that polls `GET /api/health` every 15 s.
- A 3-minute request timeout and a cancel button.

## 7. Tests

`tests/` holds the pytest suite. Notable files:

| File | Covers |
| --- | --- |
| `test_condition_analyzer.py`, `test_negative_constants.py`, `test_membership_conditions.py` | Python condition extraction |
| `test_java_adapter.py`, `test_java_numeric_literals.py`, `test_c_adapter.py`, `test_c_argc.py` | Java and C analysis and execution |
| `test_input_combinations.py`, `test_boundary_generator.py`, `test_test_runner_allocation.py` | Input generation and budget allocation |
| `test_coverage_analyzer.py`, `test_while_coverage.py`, `test_coverage_suggestions.py` | Coverage and suggestions |
| `test_executor_sandbox.py`, `test_time_limits.py` | Process isolation and time limits |
| `test_compile_once.py` | One compiler call per Java/C run |
| `test_api.py`, `test_run_test_suite_delegation.py` | API and runner wiring |
| `test_examples.py` | Every demo program, checked output by output |
