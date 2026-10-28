# tests/test_evaluation.py
"""Mutation testing (fault detection) and the random-testing baseline."""
import shutil

import pytest

from src.evaluation.mutation import generate_mutants, mutation_scores
from src.evaluation.random_baseline import random_inputs

needs_java = pytest.mark.skipif(
    not (shutil.which("javac") and shutil.which("java")),
    reason="Java JDK is not installed",
)
needs_gcc = pytest.mark.skipif(
    not shutil.which("gcc"), reason="GCC is not installed"
)

PY = "age = int(input())\nif age >= 18:\n    print('Adult')\nelse:\n    print('Minor')\n"


def _changed_lines(source, mutants):
    original = source.splitlines()
    result = []
    for mutant in mutants:
        lines = mutant.source.splitlines()
        [changed] = [new for old, new in zip(original, lines) if old != new]
        result.append(changed.strip())
    return result


def test_python_boundary_mutants():
    assert _changed_lines(PY, generate_mutants(PY, "python")) == [
        "if age > 18:",
        "if age >= 19:",
        "if age >= 17:",
    ]


def test_c_mutants_handle_negative_constants():
    source = "int main(void) {\n    int x = 0;\n    if (x > -5) { return 1; }\n    return 0;\n}\n"
    assert _changed_lines(source, generate_mutants(source, "c")) == [
        "if (x >= -5) { return 1; }",
        "if (x > -4) { return 1; }",
        "if (x > -6) { return 1; }",
    ]


def test_java_mutants_keep_reversed_operands_and_skip_switch_cases():
    source = (
        "public class A {\n"
        "    static int f(int x) {\n"
        "        if (5 < x) { return 1; }\n"
        "        switch (x) { case 2: return 2; }\n"
        "        return 0;\n"
        "    }\n"
        "}\n"
    )
    assert _changed_lines(source, generate_mutants(source, "java")) == [
        "if (5 <= x) { return 1; }",
        "if (6 < x) { return 1; }",
        "if (4 < x) { return 1; }",
    ]


def test_boundary_tests_kill_boundary_mutants_and_far_values_do_not():
    scores = mutation_scores(
        PY,
        "python",
        {
            "boundary": [{"age": 17}, {"age": 18}, {"age": 19}],
            "far": [{"age": 500}, {"age": -300}],
        },
    )
    assert scores["total"] == 3
    assert scores["suites"]["boundary"]["killed"] == 3
    assert scores["suites"]["far"]["killed"] == 0
    assert scores["suites"]["boundary"]["score"] == 100.0
    assert scores["suites"]["far"]["score"] == 0.0


C_GRADE = r"""#include <stdio.h>
int main(void) {
    int score;
    scanf("%d", &score);
    if (score >= 40) { printf("pass\n"); } else { printf("fail\n"); }
    return 0;
}
"""


@needs_gcc
def test_c_mutants_are_compiled_and_judged_by_output():
    scores = mutation_scores(
        C_GRADE, "c", {"edge": [{"score": 39}, {"score": 40}, {"score": 41}], "far": [{"score": 900}]}
    )
    assert scores["total"] == 3
    assert scores["suites"]["edge"]["killed"] == 3
    assert scores["suites"]["far"]["killed"] == 0


JAVA_GRADE = """import java.util.Scanner;
public class G {
    public static void main(String[] args) {
        int score = new Scanner(System.in).nextInt();
        if (score >= 40) { System.out.println("pass"); } else { System.out.println("fail"); }
    }
}
"""


@needs_java
def test_java_mutants_are_compiled_and_judged_by_output():
    scores = mutation_scores(
        JAVA_GRADE, "java", {"edge": [{"score": 39}, {"score": 40}, {"score": 41}], "far": [{"score": 900}]}
    )
    assert scores["total"] == 3
    assert scores["suites"]["edge"]["killed"] == 3
    assert scores["suites"]["far"]["killed"] == 0


def test_evaluate_program_compares_ast_with_random():
    from src.evaluation.evaluate import evaluate_program

    row = evaluate_program("examples/python/thermostat.py", "python", seeds=(1,))
    assert row["tests"] > 0 and row["mutants"] > 0
    assert row["ast"]["branch"] == 100.0
    assert row["ast"]["mutation"] == 100.0
    # Same number of tests, but random values miss the boundaries.
    assert row["random"]["mutation"] < row["ast"]["mutation"]
    assert row["random"]["per_seed"][0]["seed"] == "random-1"


def test_random_inputs_are_reproducible_and_in_range():
    first = random_inputs(["a", "b"], count=50, seed=7)
    assert first == random_inputs(["a", "b"], count=50, seed=7)
    assert first != random_inputs(["a", "b"], count=50, seed=8)
    assert len(first) == 50
    for row in first:
        assert set(row) == {"a", "b"}
        assert all(-1000 <= value <= 1000 for value in row.values())


def test_evaluation_covers_every_example_and_benchmark():
    from src.evaluation.evaluate import PROGRAMS, ROOT

    listed = {path for path, _ in PROGRAMS}
    on_disk = {
        path.relative_to(ROOT).as_posix()
        for folder in ("examples", "benchmarks")
        for path in (ROOT / folder).rglob("*")
        if path.suffix in {".py", ".java", ".c"}
    }
    assert listed == on_disk
