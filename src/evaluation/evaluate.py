"""Compare AST-targeted test generation with random testing.

For each program, BranchLab's targeted suite (max_cases = BUDGET) and
random suites of the same size (uniform integers in [-1000, 1000], one
per seed) are measured on:

    branch coverage, statement coverage, mutation score (fault
    detection), number of tests and generation time.

Run from the repository root:

    python -m src.evaluation.evaluate

It writes docs/evaluation/results.md and results.json.
"""

import json
import statistics
import time
from pathlib import Path
from typing import Any

from src.core.models import TestCase
from src.core.targeted_generator import generate_targeted_inputs
from src.coverage.coverage_analyzer import analyze_branch_coverage
from src.evaluation.mutation import mutation_scores
from src.evaluation.random_baseline import RANDOM_HIGH, RANDOM_LOW, random_inputs
from src.languages.c.adapter import CAdapter
from src.languages.java.adapter import JavaAdapter
from src.languages.python.adapter import PythonAdapter

BUDGET = 20
SEEDS = (1, 2, 3)

ROOT = Path(__file__).resolve().parents[2]
PROGRAMS = [
    ("examples/python/grade.py", "python"),
    ("examples/python/thermostat.py", "python"),
    ("examples/python/countdown.py", "python"),
    ("examples/python/nested_login.py", "python"),
    ("examples/java/Grade.java", "java"),
    ("examples/java/Thermostat.java", "java"),
    ("examples/c/grade.c", "c"),
    ("examples/c/countdown.c", "c"),
    ("examples/c/bank.c", "c"),
    # Benchmarks: common lab exercises, including forms the tool cannot
    # target (sums of variables, x % 4, values computed from inputs).
    ("benchmarks/python/shipping.py", "python"),
    ("benchmarks/python/leap_year.py", "python"),
    ("benchmarks/java/TaxSlab.java", "java"),
    ("benchmarks/java/Calculator.java", "java"),
    ("benchmarks/c/electricity_bill.c", "c"),
    ("benchmarks/c/triangle.c", "c"),
]

ADAPTERS = {"python": PythonAdapter, "java": JavaAdapter, "c": CAdapter}


def measure_coverage(source: str, language: str, inputs: list[dict]) -> dict[str, Any]:
    """Branch and statement coverage reached by exactly these inputs."""
    if language == "python":
        coverage = analyze_branch_coverage(source, inputs)
    else:
        with ADAPTERS[language]().compile(source) as program:
            hits: set = set()
            for row in inputs:
                hits |= program.run(TestCase(inputs=row))[1]
            coverage = program.coverage(hits)
    return {
        "branch": coverage["branch_coverage_percent"],
        "statement": coverage["statement_coverage_percent"],
    }


def _targeted(source: str, language: str):
    """AST analysis + boundary generation, timed together."""
    started = time.perf_counter()
    adapter = ADAPTERS[language]()
    conditions = adapter.analyze(source)
    inputs = generate_targeted_inputs(
        [
            {
                "variable": condition.variable,
                "operator": condition.operator,
                "constant": condition.value,
                "line": condition.line,
            }
            for condition in conditions
        ],
        max_cases=BUDGET,
    )
    elapsed = (time.perf_counter() - started) * 1000
    names = list(dict.fromkeys(condition.variable for condition in conditions))
    return inputs, names, len(conditions), elapsed


def evaluate_program(path: str, language: str, seeds=SEEDS) -> dict[str, Any]:
    source = (ROOT / path).read_text(encoding="utf-8")
    ast_inputs, names, condition_count, ast_ms = _targeted(source, language)

    random_suites = {}
    random_ms = []
    for seed in seeds:
        started = time.perf_counter()
        random_suites[f"random-{seed}"] = random_inputs(names, len(ast_inputs), seed)
        random_ms.append((time.perf_counter() - started) * 1000)

    mutation = mutation_scores(source, language, {"ast": ast_inputs, **random_suites})

    ast_coverage = measure_coverage(source, language, ast_inputs)
    per_seed = []
    for name, inputs in random_suites.items():
        coverage = measure_coverage(source, language, inputs)
        per_seed.append(
            {
                "seed": name,
                **coverage,
                "mutation": mutation["suites"][name]["score"],
            }
        )

    def mean(key):
        values = [row[key] for row in per_seed if row[key] is not None]
        return round(statistics.mean(values), 2) if values else None

    return {
        "program": path,
        "language": language,
        "conditions": condition_count,
        "tests": len(ast_inputs),
        "mutants": mutation["total"],
        "stillborn": mutation["stillborn"],
        "ast": {
            **ast_coverage,
            "mutation": mutation["suites"]["ast"]["score"],
            "generation_ms": round(ast_ms, 2),
        },
        "random": {
            "branch": mean("branch"),
            "statement": mean("statement"),
            "mutation": mean("mutation"),
            "generation_ms": round(statistics.mean(random_ms), 2),
            "per_seed": per_seed,
        },
    }


def _fmt(value, suffix="%"):
    return "n/a" if value is None else f"{value:.1f}{suffix}"


def write_report(results: list[dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    def average(side, key):
        values = [row[side][key] for row in results if row[side][key] is not None]
        return statistics.mean(values) if values else None

    lines = [
        "# Evaluation: AST-targeted vs random test generation",
        "",
        "Generated by `python -m src.evaluation.evaluate`; raw numbers are in",
        "`results.json`.",
        "",
        "## Setup",
        "",
        f"- **AST-targeted:** BranchLab's boundary values, at most {BUDGET} tests per program.",
        f"- **Random:** the same input variables and the **same number of tests**, uniform",
        f"  integers in [{RANDOM_LOW}, {RANDOM_HIGH}]; mean of {len(SEEDS)} fixed seeds ({', '.join(map(str, SEEDS))}).",
        "- **Branch coverage:** share of true/false outcomes of if/while conditions that ran.",
        "- **Statement coverage:** share of statements that ran at least once.",
        "- **Mutation score (fault detection):** three boundary bugs per comparison",
        "  (operator off by one, constant + 1, constant - 1); a mutant is caught when",
        "  any test's output, exit status or error differs from the original's.",
        "- **Generation time:** analysis + input generation only (execution excluded).",
        "",
        "## Results",
        "",
        "| Program | Tests | Branch AST | Branch random | Statement AST | Statement random | Mutation AST | Mutation random | Mutants | Gen. time AST |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in results:
        lines.append(
            f"| `{row['program']}` | {row['tests']} | "
            f"{_fmt(row['ast']['branch'])} | {_fmt(row['random']['branch'])} | "
            f"{_fmt(row['ast']['statement'])} | {_fmt(row['random']['statement'])} | "
            f"{_fmt(row['ast']['mutation'])} | {_fmt(row['random']['mutation'])} | "
            f"{row['mutants']} | {row['ast']['generation_ms']:.1f} ms |"
        )
    lines += [
        f"| **Average** | | **{_fmt(average('ast', 'branch'))}** | **{_fmt(average('random', 'branch'))}** | "
        f"**{_fmt(average('ast', 'statement'))}** | **{_fmt(average('random', 'statement'))}** | "
        f"**{_fmt(average('ast', 'mutation'))}** | **{_fmt(average('random', 'mutation'))}** | | |",
        "",
        "## Notes",
        "",
        "- Some mutants can be *equivalent* (no input can tell them apart from the",
        "  original), so a mutation score below 100% is not always a missed fault.",
        "- Random inputs share the targeted suite's size, so neither side gets more tests.",
        "- `bank.c` needs several menu actions in one run for some branches; neither",
        "  approach generates such sequences (see README limitations).",
        "- `benchmarks/` holds lab exercises with conditions the tool cannot target",
        "  directly: `a + b <= c` (triangle), `year % 400 == 0` (leap year) and",
        "  `bill > 1000`, where `bill` is computed from the input (electricity bill).",
        "",
    ]
    (out_dir / "results.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    results = []
    for path, language in PROGRAMS:
        print(f"evaluating {path} ...", flush=True)
        results.append(evaluate_program(path, language))
    write_report(results, ROOT / "docs" / "evaluation")
    print((ROOT / "docs" / "evaluation" / "results.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
