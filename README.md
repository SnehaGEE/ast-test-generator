# BranchLab: AST-Based Targeted Test Case Generation

BranchLab is an automated testing tool. It reads a program's
**Abstract Syntax Tree (AST)**, finds the conditions that decide which
branch runs, and generates test inputs aimed at both sides of each
condition. It then runs those tests, records outputs and runtime errors,
and measures **branch coverage**, so you can see which program paths were
tested and which were missed.

It supports **Python**, **Java** and **C** with the same features, and has
a React web interface backed by a FastAPI server.

## What it does

| Step | What happens |
| --- | --- |
| 1. Parse | Python uses the standard `ast` module; Java and C use Tree-sitter. |
| 2. Analyze | Finds `variable <op> constant` comparisons in `if`/`elif`/`else if` and `while` conditions (plus `do`-`while` in Java and C), including `and`/`or`/`not`, reversed operands (`10 <= x`) and signed or suffixed literals (`-5`, `0x1F`, `5L`, `2.5f`). Each `switch`/`match` case counts as `variable == value`, so every option of a menu gets tested. |
| 3. Generate | Picks boundary values for each comparison, e.g. `age >= 18` gives 17, 18, 19, and combines variables into at most *max cases* test inputs. |
| 4. Execute | Runs every test and records output, errors, exit codes and timeouts. Each value reaches the variable it belongs to (see below). Java and C are compiled once per run. |
| 5. Measure | Records which true/false outcome of each `if`/`while` condition really happened at runtime. |
| 6. Suggest | For each missing outcome, suggests an input set, runs it once, and marks it **verified** only if it actually reaches that outcome. |

Optional strategies, for all three languages:

- **Invalid-input tests**: values such as `"garbage"`, `""`, `None` and
  very long numbers, to see how the program handles bad input.
- **Fuzz tests**: reproducible random and extreme values (seeded).

Each strategy you turn on reserves about 20% of the maximum test cases.

## Quick start (Windows)

Prerequisites: Python 3.11+, Node.js 20+, and for Java and C a JDK
(`javac`, `java`) and GCC on `PATH`.

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
missing. The tests check real program outputs and recompute expected
coverage from the actual generated inputs; a coverage percentage is never
accepted on its own. `tests/test_examples.py` runs every program in
`examples/` and compares each output with a reference implementation.

## How programs receive inputs

Generated values are keyed by variable name. BranchLab reads the AST to
find *where* the program reads each variable and supplies the value there:

| Language | Standard input | Command line | Other |
| --- | --- | --- | --- |
| Python | `input()` calls, including `int(input())` and `float(input())` | | Also set as global variables. |
| Java | `Scanner` reads (`nextInt()`, `next()`, `nextLine()`...) and `BufferedReader.readLine()` | `args[0]`, `args[1]`... at the index the program uses | Also passed as system properties: `System.getProperty("x")`. The source must declare a `public class`. |
| C | `scanf` conversions (`%d`, `%f`, `%s`, `%[...]`...) | `argv[1]`, `argv[2]`... at the index the program uses (alphabetical order if none is found) | A variable named `argc` sets the argument count. |

Standard input gets one value per line, following the program's own path:

- **Every read gets an answer.** A read with no generated value (a name,
  an id) gets a placeholder of the right kind (`1`, `1.0`, `test`), so the
  values after it still reach the right variable.
- **Each branch gets its own reads.** If option 1 of a menu reads
  `no, name, amount` and option 2 reads `no, amount`, a test for option 2
  answers exactly those two. `switch`/`match` and `if (x == 2)` style
  branches are followed, including C/Java `case` fall-through.
- **Helper functions count.** Reads inside a function the program calls
  (`amount = read_amount()`) are answered where the call happens.
- **Java's `nextLine()` after `nextInt()`** returns the rest of the
  number's line, and is not given an answer of its own.

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

- Only comparisons between a variable and a numeric constant produce
  targeted inputs. Comparisons between two variables (`x > y`), with
  expressions (`x > n * 2`) or with characters (`c == 'a'`) are not
  analyzed.
- Coverage counts `if`/`elif`/`else if` and `while` conditions. `for`
  loops, `do`-`while` loops, `switch`/`match`, conditional expressions
  (`?:`, `a if c else b`) and comprehension filters run normally but are
  **not** counted; the interface lists them when present.
- **One run, one set of values.** Behaviour that needs several actions
  in a row (create an account, *then* deposit into it) is not generated;
  such branches show as missing, with suggestions marked *not reached*.
- Input positions are found from common patterns (see the table above).
  Reads through other APIs (`getchar`, `fgets`, `Console`), or branches
  decided by something other than `variable op number`, keep the reads of
  every side, which can misalign later values.
- Java and C coverage works by compiling a probed copy of the program.
  If that copy does not compile, the tests run on the original program
  and coverage is shown as not measured.
- Time limits: about 2-3 s per Python test, 15 s to compile and 10 s per
  run for Java and C.
- Tests run in separate processes so hangs and crashes are contained,
  but this is **not a security sandbox**. Only analyze code you trust,
  and keep the API on `127.0.0.1` (the default).

## Project layout

```
api.py                  FastAPI server (/api/run, /api/health)
frontend/               BranchLab React + Vite interface
src/core/               Runners, test planning, input generators, models
src/languages/          Python, Java and C adapters; shared Java/C engine,
                        branch probes and input-position detection
src/parser/analyzer/    Python condition analyzer, boundary values, executor
src/coverage/           Python branch coverage, unsupported-syntax detection,
                        coverage suggestions
examples/               Demo programs for each language
tests/                  pytest suite
docs/architecture.md    How the pieces fit together
```

See [docs/architecture.md](docs/architecture.md) for the design.
