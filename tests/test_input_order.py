# tests/test_input_order.py
"""Programs must receive each generated value in the variable it belongs to.

Every test checks real program output, which echoes the values it read,
against the inputs the generator intended.
"""
import shutil
import time

import pytest

from src.core.multi_language_runner import run_test_suite

needs_java = pytest.mark.skipif(
    not (shutil.which("javac") and shutil.which("java")),
    reason="Java JDK is not installed",
)
needs_gcc = pytest.mark.skipif(
    not shutil.which("gcc"), reason="GCC is not installed"
)


def _echoed(result):
    """Map each executed test's inputs to the 'a=.. b=..' line it printed."""
    rows = []
    for test in result["results"]:
        assert test.executed, (test.inputs, test.error)
        last = test.output.strip().splitlines()[-1]
        rows.append((test.inputs, last))
    assert rows
    return rows


def _assert_echo(result):
    for inputs, line in _echoed(result):
        assert line == f"a={inputs['a']} b={inputs['b']}", inputs


# Conditions mention b before a, but the program reads a first.

PY_INPUT = (
    "a = int(input())\n"
    "b = int(input())\n"
    "if b > 0:\n"
    "    if a > 100:\n"
    "        print('both')\n"
    "print(f'a={a} b={b}')\n"
)


def test_python_input_calls_get_values_in_read_order():
    _assert_echo(run_test_suite(PY_INPUT, language="python", max_cases=6))


def test_python_coverage_uses_the_same_order():
    # b > 0 and a > 100 both true needs a=101, b=1; with swapped values
    # the inner print would be reached for the wrong reason.
    result = run_test_suite(PY_INPUT, language="python", max_cases=20)
    for test in result["results"]:
        reached = "both" in test.output
        assert reached == (test.inputs["b"] > 0 and test.inputs["a"] > 100)


C_SCANF = r"""
#include <stdio.h>
int main(void) {
    int a, b;
    scanf("%d", &a);
    scanf("%d", &b);
    if (b > 0) {
        if (a > 100) {
            printf("both\n");
        }
    }
    printf("a=%d b=%d\n", a, b);
    return 0;
}
"""

C_ARGV = r"""
#include <stdio.h>
#include <stdlib.h>
int main(int argc, char *argv[]) {
    int b = atoi(argv[1]);
    int a = atoi(argv[2]);
    if (a > 100 && b > 0) {
        printf("both\n");
    }
    printf("a=%d b=%d\n", a, b);
    return 0;
}
"""

JAVA_SCANNER = """
import java.util.Scanner;
public class Order {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in);
        int a = in.nextInt();
        int b = in.nextInt();
        if (b > 0) {
            if (a > 100) {
                System.out.println("both");
            }
        }
        System.out.println("a=" + a + " b=" + b);
    }
}
"""

JAVA_READER = """
import java.io.BufferedReader;
import java.io.InputStreamReader;
public class Reader {
    public static void main(String[] args) throws Exception {
        BufferedReader in = new BufferedReader(new InputStreamReader(System.in));
        int a = Integer.parseInt(in.readLine().trim());
        int b = Integer.parseInt(in.readLine().trim());
        if (b > 0 && a > 100) {
            System.out.println("both");
        }
        System.out.println("a=" + a + " b=" + b);
    }
}
"""

JAVA_ARGS = """
public class Args {
    public static void main(String[] args) {
        int b = Integer.parseInt(args[0]);
        int a = Integer.parseInt(args[1]);
        if (a > 100 && b > 0) {
            System.out.println("both");
        }
        System.out.println("a=" + a + " b=" + b);
    }
}
"""


@needs_gcc
def test_c_scanf_gets_values_in_read_order():
    _assert_echo(run_test_suite(C_SCANF, language="c", max_cases=6))


@needs_gcc
def test_c_argv_positions_follow_the_source():
    _assert_echo(run_test_suite(C_ARGV, language="c", max_cases=6))


@needs_java
def test_java_scanner_gets_values_in_read_order():
    started = time.monotonic()
    result = run_test_suite(JAVA_SCANNER, language="java", max_cases=4)
    _assert_echo(result)
    # Each run used to hang until the 10 s timeout waiting on stdin.
    assert time.monotonic() - started < 30


@needs_java
def test_java_buffered_reader_gets_values():
    _assert_echo(run_test_suite(JAVA_READER, language="java", max_cases=4))


@needs_java
def test_java_args_positions_follow_the_source():
    _assert_echo(run_test_suite(JAVA_ARGS, language="java", max_cases=4))
