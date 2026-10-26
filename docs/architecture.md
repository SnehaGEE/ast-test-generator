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
   │
   ├── python ─► run_python_test_suite (src/core/test_runner.py)
   │               ├── PythonAdapter.analyze ─► condition_analyzer.py
   │               ├── plan_test_cases ─► targeted + invalid + fuzz cases
   │               ├── PythonAdapter.execute ─► test_executor.py ─► sandbox_worker.py
   │               ├── analyze_branch_coverage (line tracer)
   │               └── verified suggestions
   │
   └── java / c ─► _run_compiled_test_suite
                   ├── JavaAdapter / CAdapter.analyze (Tree-sitter)
                   ├── plan_test_cases (same planner as Python)
                   ├── adapter.compile ─► probed build, compiled once
                   │      └── program.run(case) ─► result + outcomes reached
                   ├── coverage from probe outcomes
                   └── verified suggestions (re-run on the same build)
```

## 1. Language adapters

Every language implements `LanguageAdapter` (`src/core/interfaces.py`):
`parse`, `analyze` (returns `Condition(variable, operator, value, line,
language)`), `execute` and `execute_many`.

- **Python** (`src/languages/python/adapter.py`) uses the built-in `ast`
  module through `ConditionAnalyzer`. It visits `If` and `While` nodes,
  descends into `and`/`or`/`not`, normalises reversed comparisons
  (`10 <= x` becomes `x >= 10`) and folds signed literals (`-5`).
- **Java** and **C** (`src/languages/java`, `src/languages/c`) parse with
  Tree-sitter and share `tree_sitter_conditions.extract_conditions`. It
  visits `if`, `while` and `do` conditions, descends into `&&`/`||`/`!`,
  and normalises reversed comparisons. Each language only supplies its
  literal parser: Java reads hex, octal, binary and `L`/`f`/`d` suffixes;
  C reads hex, octal and `u`/`l`/`f` suffixes.

Java and C also derive from `CompiledLanguageAdapter`
(`src/languages/compiled.py`), which provides compile-once execution and
coverage. Each subclass supplies its build command, run command and probe
code.

## 2. Test planning

`plan_test_cases` (`src/core/test_runner.py`) is shared by all languages:

1. `generate_targeted_inputs` turns each condition into boundary values:
   the constant and its neighbours (adjacent integers, or the nearest
   floats). The values are ordered so the second always satisfies the
   condition. `generate_input_combinations` combines variables within the
   budget: diagonal rows first, then rows that change one variable at a
   time, then evenly spaced rows.
2. If invalid-input or fuzz tests are enabled, each reserves about 20% of
   `max_cases`. These cases change one variable and fill the rest from a
   *base row* of valid values, so the program reaches the value under test.
3. Duplicate input sets are dropped. Every case keeps a category:
   `targeted`, `invalid` or `fuzz`.

## 3. Delivering inputs

Generated inputs are keyed by name, but programs read by position. The
adapters find the read positions in the AST (`src/core/input_order.py`,
`src/languages/input_plan.py`):

| Language | Read order | Command-line positions |
| --- | --- | --- |
| Python | assignments from `input()` | none |
| Java | variables assigned from `Scanner`/`BufferedReader` reads | `args[n]` |
| C | `&name` arguments of `scanf` | `argv[n]` |

Values go to standard input one per line in read order, and to the
command line at the detected indexes. Java also receives every value as a
system property, and Python as a global variable. Standard input is always
supplied, so a program waiting for input never hangs on the server's own
stdin.

## 4. Execution

- **Python**: `execute_test_case` starts `sandbox_worker.py` in a new
  `python -I` process and sends the program and inputs as JSON. The worker
  answers `input()` calls, caps output at 100,000 characters and returns
  output or the error. The parent kills the process on timeout. This
  contains hangs and crashes; it does not restrict what the program can
  access.
- **Java and C**: `CompiledLanguageAdapter.compile` builds the program once
  in a temporary directory (`javac`, or `gcc`), and `CompiledProgram.run`
  executes it per test with a 10 s limit. A compile error is reported on
  every test; timeouts are recorded per test.

## 5. Branch coverage

Every language reports the same shape: for each `if`/`while` condition,
its line, kind, whether the **true** and **false** outcomes were observed,
and which are missing. For a `while`, *true* means the body ran and
*false* means the loop exited through its condition. The percentage is
observed outcomes divided by total outcomes.

- **Python** (`src/coverage/coverage_analyzer.py`) runs each input under a
  line tracer and rewrites conditions to record their value.
- **Java and C** (`src/languages/branch_probes.py`) cannot be traced, so
  the source is instrumented instead. Each condition is wrapped in a probe
  call, `if (x > 5)` becoming `if (__probe(3, (x > 5)))`. The probe records
  the outcome and returns the value unchanged. Each new outcome is
  appended to a file named by the `BRANCHLAB_PROBE_FILE` environment
  variable, so outcomes reached before `exit()`, a crash or a timeout are
  kept. In C the probe function is prepended and followed by `#line 1`, so
  compiler messages keep the original line numbers; in Java a helper class
  is appended after the program. If the probed copy fails to compile, the
  original is rebuilt: its own compile errors are reported, or the tests
  run with coverage marked as not measured.

Constructs that run but are not counted (`for`, `do`-`while`,
`switch`/`match`, conditional expressions, comprehension filters) are
listed in `coverage.unsupported` and shown in the interface.

## 6. Coverage suggestions

`suggest_missing_branch_tests` proposes a boundary value for each missing
outcome of a simple numeric condition. `verified_suggestions` completes it
with the base row and runs it once (a coverage run for Python, the same
probed build for Java and C). It is marked `verified` only if the missing
outcome really occurred, so a nested condition that the base row never
reaches is shown as *not reached* rather than presented as a fix.

## 7. Frontend

`frontend/src/App.jsx` is a single React component:

- Monaco editor with Python, Java and C starter programs.
- Settings for max cases (1-100) and the invalid-input and fuzz strategies.
- Result tabs: generated tests (category, inputs, status, output, error),
  execution output, and coverage (per-branch table, verified suggestions,
  untracked constructs).
- A backend status light that polls `GET /api/health` every 15 s.
- A 3-minute request timeout and a cancel button.

## 8. Tests

| File | Covers |
| --- | --- |
| `test_condition_analyzer.py`, `test_negative_constants.py`, `test_membership_conditions.py` | Python condition extraction |
| `test_java_c_conditions.py`, `test_java_numeric_literals.py`, `test_java_adapter.py`, `test_c_adapter.py`, `test_c_argc.py` | Java and C analysis and execution |
| `test_input_order.py` | Each value reaching its variable, in all three languages |
| `test_input_combinations.py`, `test_boundary_generator.py`, `test_test_runner_allocation.py` | Input generation and budget allocation |
| `test_coverage_analyzer.py`, `test_while_coverage.py`, `test_java_c_coverage.py` | Coverage, recomputed from the real inputs |
| `test_coverage_suggestions.py`, `test_java_c_strategies.py` | Suggestions, invalid-input and fuzz tests |
| `test_executor_sandbox.py`, `test_time_limits.py`, `test_compile_once.py` | Process isolation, time limits, one build per run |
| `test_api.py`, `test_run_test_suite_delegation.py` | API and runner wiring |
| `test_examples.py` | Every demo program, checked output by output |
