# Review III – demo script and viva preparation

Review III is marked on: **project completion and demo (3)**, **individual
contribution and technical understanding (3)** and **project outcome, the
research manuscript (4)**. This guide covers the first two; the manuscript is the Overleaf project
`BranchLab_Manuscript_Overleaf.zip` in this folder. For the basic concept questions
(AST, coverage, mutation testing), see
[`../review2/QA_Preparation.md`](../review2/QA_Preparation.md); everything
there still applies.

Numbers come from [`../evaluation/results.md`](../evaluation/results.md)
(15 programs). Re-run `python -m src.evaluation.evaluate` if the code changes.

## Before the review

- [ ] Open https://branchlab-ggon.onrender.com **two minutes early**. The free
      server sleeps after 15 minutes idle and takes about a minute to wake.
      Check that the sidebar says **Backend connected**.
- [ ] Have these files open in a text editor, ready to paste:
      `examples/c/bank.c`, `examples/python/nested_login.py`,
      `benchmarks/c/triangle.c`.
- [ ] Backup if the network fails: in the project folder run
      `.\.venv\Scripts\python -m uvicorn api:app`, and in `frontend/`
      run `npm run dev`; open http://localhost:5173.
- [ ] Compile the manuscript on Overleaf and read the PDF once before submitting it.

## Demo script (about 5 minutes)

| # | Do this | Point out |
|---|---|---|
| 1 | Python tab, starter program, **Run analysis** | Tests 17, 18, 19 come from `age >= 18`; outputs Minor / Adult / Adult; 100% branch and statement coverage. |
| 2 | C tab, paste `bank.c`, 20 tests, **Run analysis** | Every menu option runs; each test gets only the inputs its own path reads (read map). Coverage tab: missed lines and suggestions marked *not reached*, because they need a sequence of actions. |
| 3 | Python, paste `nested_login.py`, set **Maximum test cases** to 1 | One suggestion is *verified* (it was run and really reached the outcome); one is *not reached*. The tool never offers a fix it has not checked. |
| 4 | C, paste `triangle.c` | An honest limit: `a + b <= c` compares variables, so no targeted values are generated for it. Same result as random. |

Say while it runs: *"Every test comes from a condition in the syntax tree.
There is no solver, no search and no language model, so generating a suite takes
about 4 milliseconds."*

## Individual contribution: what to say

- **"I am the only team member."** I designed and built the analysis,
  generation, read map, probes, coverage, interface, evaluation, deployment
  and manuscript. The Git history shows 52 commits from 6 to 28 October.
- **Hardest problem:** delivering inputs. Programs read by position, but values
  are generated per variable. A menu option that reads `no, name, amount` must not
  receive what another option reads. The read map follows each test's own path
  through the AST.
- **Most satisfying bug:** the crash on the bank program's large `switch`.
  I cut it down to a small reproduction, traced it to memory corruption in
  Tree-sitter 0.26.0, pinned 0.25.2, and added a regression test that runs the
  parser in a separate process.
- **How I know it works:** 252 automated tests, written test-first. They
  compare real program outputs with reference implementations and recompute
  expected branch outcomes, instead of trusting a coverage number.

## Viva questions

### Compiler concepts

**Which compiler phases does the project use?**
The front end: lexical and syntax analysis build the tree (Python's `ast`;
Tree-sitter for C and Java). Then a small static analysis on the tree (finding
conditions and input reads), and a source-to-source transformation (inserting
probes) before the real compiler (`gcc`, `javac`) runs.

**Why Tree-sitter for C and Java instead of writing a parser?**
It provides tested grammars for both languages through one interface, and it
keeps working on code with errors. Writing full C and Java parsers was outside
the scope of the project. The analysis on top of the tree is the project's own work.

**What is a concrete syntax tree vs an abstract syntax tree?**
A concrete (parse) tree keeps every token: parentheses, semicolons, keywords.
An AST keeps only the structure that matters, such as *comparison of `age` with
18*. Tree-sitter returns a concrete tree, and the analyzer reads the relevant
nodes from it as an AST.

**What does `#line 1` do?**
It is a preprocessor directive. It tells the compiler to number the following
lines from 1, so after the probe helpers are inserted at the top, error messages
still point at the user's original line numbers.

**Isn't inserting probes changing the program?**
The probe returns the condition's own value unchanged, so control flow is
identical. The only extra effect is writing one line to a file the first time
each outcome happens.

### Method

**Why c−1, c and c+1?**
A wrong operator (`>` instead of `>=`) or a constant off by one changes the
result only at the boundary. Each of those faults gives a different output for
one of the three values.

**What if a variable appears in several conditions?**
It gets the union of their boundary values. If all combinations of variables
exceed the budget, rows are picked in priority order: diagonal rows first, then
one variable changed at a time, then evenly spaced rows of the full product.

**What can it not handle?**
Comparisons between variables (`a + b <= c`), arithmetic in conditions
(`year % 4 == 0`), values computed from inputs (`bill > 1000`), and behaviour
that needs several actions in one run. `for` loops, `switch` cases and `?:` are
not yet counted in branch coverage. The benchmark includes programs with each of
these on purpose.

**How would you extend it?**
Generate input sequences from the read map (for menus), add light constraint
handling for `x > y` and `x % n == 0`, and propagate boundaries back through
assignments like `bill = units * 1.5`.

### Evaluation and manuscript

**Summarise the results.**
Across 15 programs with the same number of tests: branch coverage 90.0% vs
57.6%, statement coverage 93.4% vs 70.1%, boundary faults detected
91.0% vs 14.1%.

**Why is the fault-detection gap bigger than the coverage gap?**
Covering a branch is not enough to catch a boundary fault. A random suite can
run both sides of `age >= 18` with ages like 412 and −87, and never test 17, 18
or 19. The mutant `age > 18` then survives.

**What is the Wilcoxon signed-rank test, and why use it?**
It is a non-parametric test for paired samples: here, each program's AST score
paired with its random score. It doesn't assume the differences are normally
distributed, which matters with only 15 programs. The exact version enumerates
every sign assignment instead of using an approximation. Branch coverage:
higher on 12 programs, equal on 3, lower on 0 (p < 0.001). Fault detection: higher on 13 programs, equal on 2, lower on 0 (p < 0.001).

**Isn't the mutation comparison biased towards your method?**
Yes, and the manuscript says so under threats to validity. The mutants are
boundary faults, the kind the method targets. Scores for other fault types would
be lower and closer together. That is why coverage is reported as well.

**Is the random baseline fair?**
It uses the same variables, the same number of tests, three fixed seeds averaged,
and the same measurement. The range [−1000, 1000] crosses every constant in the
benchmark programs. A wider range would make random testing worse, not better.

**Where did random testing win?**
Statement coverage on `electricity_bill.c` (93.0% vs 89.5%): the surcharge
depends on `bill`, which is computed from the input, and large random readings
trigger it. The boundary values for `units` stay near 100–300.

**Who wrote the benchmark programs?**
All 15 were written for this project: nine examples, plus six common lab
exercises. Three of those six were chosen because the method fails on them. This
is a threat to external validity, and the manuscript states it.

### Deployment

**How is it deployed?**
A Docker image builds the React interface and serves it from the FastAPI back
end, with GCC and a JDK installed. Render builds it from the `dev` branch on
every push.

**Is running visitors' code safe?**
Not fully. Each test runs in its own process with a time limit, as an
unprivileged user, with a 50,000-character size limit. But process isolation is
not a security sandbox, so the link is shared only with reviewers. A container
sandbox would be needed for a public service.
