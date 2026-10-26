# BranchLab: AST-Based Targeted Test Case Generation

BranchLab is an automated testing tool. It reads a program's
**Abstract Syntax Tree (AST)**, finds the conditions that decide which
branch runs, and generates test inputs aimed at both sides of each
condition. It then runs those tests, records outputs and runtime errors,
and measures **branch coverage**, so you can see which program paths were
tested and which were missed.

It supports **Python**, **Java** and **C**, and has a React web interface
backed by a FastAPI server.

## What it does

| Step | What happens |
| --- | --- |
| 1. Parse | Python uses the standard `ast` module; Java and C use Tree-sitter. |
| 2. Analyze | Finds `variable <op> constant` comparisons in `if`/`elif` (and Python `while`) conditions, including `and`/`or`, reversed operands (`10 <= x`, Python), and signed constants (`x > -5`). |
| 3. Generate | Picks boundary values for each comparison, e.g. `age >= 18` gives 17, 18, 19, and combines variables into at most *max cases* test inputs. |
| 4. Execute | Runs every test case and records output, errors, exit codes and timeouts. Java and C are compiled once per run. |
| 5. Measure | For Python, records which true/false outcome of each `if`/`while` condition really happened at runtime. |
| 6. Suggest | For each missing outcome, suggests an input set, runs it once, and marks it **verified** only if it actually reaches that outcome. |

Optional strategies (Python):

- **Invalid-input tests**: values such as `"garbage"`, `""`, `None` and
  very long numbers, to see how the program handles bad input.
- **Fuzz tests**: reproducible random and extreme values (seeded).

Each strategy you turn on reserves about 20% of the maximum test cases.

## Quick start (Windows)

Prerequisites: Python 3.11+, Node.js 20+, and optionally a JDK (`javac`,
`java`) and GCC on `PATH` for Java and C.

```powershell
git clone https://github.com/SnehaGEE/ast-test-generator.git
cd ast-test-generator

# Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn api:app --reload        # http://127.0.0.1:8000

# Frontend (second terminal)
cd frontend
npm install
npm run dev                               # http://localhost:5173
```

Open http://localhost:5173. The sidebar shows **Backend connected** when
the API is reachable. To use another API address, set `VITE_API_URL`
(for example in `frontend/.env.local`).

## Running the tests

```powershell
.\.venv\Scripts\python -m pytest -q
```

Java and C tests are skipped automatically when the JDK or GCC is
missing. `tests/test_examples.py` runs every program in `examples/` and
compares **each real output** with a reference implementation, so it
does not rely on the coverage percentage alone.

## How programs receive inputs

| Language | Inputs |
| --- | --- |
| Python | As global variables, and as answers to `input()` calls in order. |
| Java | As system properties: `System.getProperty("age")`. The source must declare a `public class`. |
| C | As command-line arguments in alphabetical order of variable name: `argv[1]`, `argv[2]` and so on. A variable named `argc` sets the argument count instead. |

See [`examples/`](examples/) for ready-to-paste programs in each language.

## API

`POST /api/run`

```json
{
  "source_code": "if age >= 18:\n    print('Adult')\n",
  "language": "python",
  "max_cases": 20,
  "include_invalid_inputs": false,
  "include_fuzz_inputs": false
}
```

The response contains `results` (inputs, output, error, category per test),
counts, a `message`, and `coverage`, which holds `branches`,
`branch_coverage_percent`, `unsupported` constructs and `suggestions`.
`GET /api/health` returns `{"status": "ok"}`.

## Limitations

- **Branch coverage is measured for Python only.** Java and C show
  "not measured" (`null`), never 0% or 100%.
- Only comparisons between a variable and a numeric constant produce
  targeted inputs. Comparisons between two variables (`x > y`) or with
  expressions (`x > n * 2`) are not analyzed.
- Python `for` loops, `match`/`case`, conditional expressions and
  comprehension filters run normally but are **not** counted in the
  coverage percentage; the interface lists them when present.
- Java and C analyze `if` conditions only (not `while`), and do not
  handle reversed operands such as `5 < x`.
- Invalid-input and fuzz tests are Python only.
- Time limits: about 2-3 s per Python test, 15 s to compile and 10 s per
  run for Java and C.
- Each Python test runs in its own child process so hangs and crashes
  are contained, but this is **not a security sandbox**. Only analyze
  code you trust, and keep the API on `127.0.0.1` (the default).

## Project layout

```
api.py                 FastAPI server (/api/run, /api/health)
frontend/              BranchLab React + Vite interface
src/core/              Runners, input generators, data models
src/languages/         Python, Java and C adapters (parse, analyze, execute)
src/parser/analyzer/   Python condition analyzer, boundary values, executor
src/coverage/          Python branch coverage and unsupported-syntax detection
examples/              Demo programs for each language
tests/                 pytest suite
docs/architecture.md   How the pieces fit together
```

See [docs/architecture.md](docs/architecture.md) for the design.
