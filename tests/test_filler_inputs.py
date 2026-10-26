# tests/test_filler_inputs.py
"""Programs often read values that no condition mentions (a name, an id).

Those reads still need an answer, or every later value shifts into the
wrong variable. Each program echoes what it received, so the tests check
that every generated value really reached its variable.
"""
import shutil

import pytest

from src.core.multi_language_runner import run_test_suite

needs_java = pytest.mark.skipif(
    not (shutil.which("javac") and shutil.which("java")),
    reason="Java JDK is not installed",
)
needs_gcc = pytest.mark.skipif(
    not shutil.which("gcc"), reason="GCC is not installed"
)


def _echo_lines(result, variable):
    """(generated value, last output line) for every targeted test."""
    rows = []
    for test in result["results"]:
        if test.category != "targeted":
            continue
        assert test.executed, (test.inputs, test.error)
        rows.append((test.inputs[variable], test.output.strip().splitlines()[-1]))
    assert rows
    return rows


PY_NAME_FIRST = (
    "name = input('Name: ')\n"
    "age = int(input('Age: '))\n"
    "if age >= 18:\n"
    "    print('adult')\n"
    "print(f'name={name} age={age}')\n"
)


def test_python_unconditioned_input_gets_a_filler():
    result = run_test_suite(PY_NAME_FIRST, language="python", max_cases=6)
    for age, line in _echo_lines(result, "age"):
        assert line.endswith(f"age={age}"), (age, line)
        assert "name=" in line


def test_python_coverage_sees_the_same_values():
    result = run_test_suite(PY_NAME_FIRST, language="python", max_cases=6)
    ages = [test.inputs["age"] for test in result["results"]]
    [branch] = result["coverage"]["branches"]
    assert branch["true_covered"] == any(age >= 18 for age in ages)
    assert branch["false_covered"] == any(age < 18 for age in ages)


C_ACCOUNT = r"""
#include <stdio.h>
int main(void) {
    int no;
    char name[50];
    float amount;
    printf("Account number: ");
    scanf("%d", &no);
    printf("Name: ");
    scanf(" %49[^\n]", name);
    printf("Initial deposit: ");
    if (scanf("%f", &amount) != 1) {
        printf("no amount\n");
        return 1;
    }
    if (amount < 0) {
        printf("Invalid amount!\n");
    }
    printf("\namount=%.0f\n", amount);
    return 0;
}
"""


@needs_gcc
def test_c_reads_before_the_condition_variable_get_fillers():
    result = run_test_suite(C_ACCOUNT, language="c", max_cases=6)
    for amount, line in _echo_lines(result, "amount"):
        assert line == f"amount={amount}", (amount, line)

    [_, check] = result["coverage"]["branches"]
    amounts = [test.inputs["amount"] for test in result["results"]]
    assert check["true_covered"] == any(a < 0 for a in amounts)
    assert check["false_covered"] == any(a >= 0 for a in amounts)


JAVA_NAME_FIRST = """
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.util.Scanner;
public class Person {
    public static void main(String[] args) throws Exception {
        Scanner in = new Scanner(System.in);
        String name = in.next();
        int id = in.nextInt();
        double age = in.nextDouble();
        if (age >= 18) {
            System.out.println("adult");
        }
        System.out.println("age=" + (int) age);
    }
}
"""


@needs_java
def test_java_reads_before_the_condition_variable_get_fillers():
    result = run_test_suite(JAVA_NAME_FIRST, language="java", max_cases=4)
    for age, line in _echo_lines(result, "age"):
        assert line == f"age={age}", (age, line)
