# Review II – Q&A preparation

Likely questions with short answers. Numbers come from
[`docs/evaluation/results.md`](../evaluation/results.md); re-run
`python -m src.evaluation.evaluate` if the code changes.

## Concepts

**What is an AST, and why use it instead of the source text?**
An Abstract Syntax Tree is the compiler's structured view of a program:
each `if`, comparison, variable and constant is a node. Working on the
tree means `if (age >= 18)` is found as *a comparison of the variable `age`
with the constant 18*, wherever it appears and however it is formatted,
instead of guessing with text patterns.

**Which compiler phase does the project use?**
The front end: lexical and syntax analysis produce the tree (Python's
`ast` module; Tree-sitter grammars for C and Java). The project then does
a small static analysis on that tree (finding conditions and reads), and
for coverage it performs a source-to-source transformation (inserting
probes) before the real compiler (`gcc`, `javac`) builds the program.

**What is branch coverage vs statement coverage?**
Statement coverage: the share of statements that ran at least once.
Branch coverage: every condition has two outcomes (true and false); the
share of those outcomes that actually happened. Branch coverage is
stronger: `if (x > 5) y = 1;` can have 100% statement coverage with only
`x = 6`, but 50% branch coverage, because the false outcome never ran.

**What is boundary value analysis, and why c-1, c, c+1?**
Off-by-one faults (`>=` written as `>`, 18 written as 19) change the
program's behaviour only at the edge. For `age >= 18`: 17 must give false,
18 and 19 must give true. Any wrong operator or constant near the edge
changes the result for one of those three values.

**What is mutation testing, and why use it for fault detection?**
We plant small, realistic bugs (mutants) one at a time and check whether
the test suite notices: a mutant is "killed" if any test's output differs
from the original program's. The mutation score (killed / total) measures
how many faults the tests would have caught. Our operators are the
boundary bugs above: operator off by one, constant ±1.

**What is an equivalent mutant?**
A change that does not alter behaviour for any input (for example when a
value can never reach the boundary). No test can kill it, so mutation
scores below 100% are not always missed faults.

## Design decisions

**How does it measure coverage for C and Java, which cannot be traced like Python?**
By instrumentation. Before compiling, each condition is wrapped:
`if (x > 5)` becomes `if (__probe(3, (x > 5)))`. The probe records whether
condition 3 was true or false and returns the same value, so behaviour is
unchanged. Each statement gets a `__line(n);` call before it. Outcomes are
written to a file the moment they first happen, so they survive `exit()`,
crashes and timeouts. In C, `#line 1` after the inserted helper keeps
compiler error messages on the original line numbers.

**Why compile once per run?**
Compiling is the slow part (about a second for `javac`). The program is
built once with probes, then run once per test. A test's own timeout or
crash does not affect the others.

**How do generated values reach the program?**
Values are keyed by variable name, but programs read by position (the
first `scanf`, the next `Scanner` call). BranchLab builds a *read map* from
the AST (reads in order plus the branches that decide them) and, for each
test, follows the path its values take. Option 1 of a menu that reads
`no, name, amount` gets exactly those three answers; option 2 that reads
`no, amount` gets two. Values no condition uses get a typed placeholder
(`1`, `1.0`, `test`).

**How are tests chosen when there are too many combinations?**
Within the maximum test count, rows are picked by priority: diagonal rows
(all variables at their k-th value), then rows changing one variable at a
time, then evenly spaced rows. The second boundary value always satisfies
its condition, so these rows can reach nested branches.

**What are the "verified" suggestions?**
For each missing outcome the tool proposes an input, then runs it once.
It is marked *verified* only if it really produces that outcome; one that
cannot reach a nested condition is marked *not reached* instead of being
offered as a fix.

## Comparison and novelty

**How is this different from KLEE, CUTE or EvoSuite?**
Those use symbolic execution with constraint solvers, or evolutionary
search: powerful, but heavy (path explosion, solver cost, many
iterations). BranchLab reads the conditions directly from the AST and
picks boundary values: no solver, no search, no language model. Each test
is explainable (it comes from a named condition on a known line), and it
runs in milliseconds.

**Why compare with random testing?**
Random testing is the standard lightweight baseline and was named in the
Review I objectives. Both suites get the same number of tests, so the
difference comes from *which* values are chosen, not from how many.

**Is the comparison fair?**
Same input variables, same test count, three fixed seeds averaged, and
the same coverage and mutation measurement for both. Random values are
uniform integers in [-1000, 1000]; a wider range would make random
testing worse at hitting small boundaries, not better.

**What is novel?**
Structure-derived, explainable tests; one pipeline for C, Java and Python;
probe-based coverage for compiled languages; path-aware input delivery;
verified suggestions; and honest reporting of what is not measured.

## Limitations (say them before they are asked)

- Each test is one run with one set of values: behaviour needing several
  actions (create an account, *then* deposit) is not generated.
- Only `variable op number` comparisons produce targeted values;
  `x > y` or `strlen(s) > 5` do not.
- `for` loops, `switch` and `?:` run normally but are not counted in
  branch coverage; the interface lists them.
- Process isolation contains hangs and crashes but is not a security
  sandbox.

## Demo checklist

1. `.\.venv\Scripts\python -m uvicorn api:app --reload` and, in
   `frontend/`, `npm run dev`; open http://localhost:5173 and check
   **Backend connected**.
2. Python starter: tests 17 / 18 / 19, 100% branch and statement coverage.
3. Paste `examples/c/bank.c` (C tab): every menu option runs; open the
   Coverage tab for statement coverage, missed lines and *not reached*
   suggestions.
4. Set **Maximum test cases** to 1 on `examples/python/nested_login.py`
   to show a verified and a not-reached suggestion.
5. Show `docs/evaluation/results.md` for the AST vs random comparison.
