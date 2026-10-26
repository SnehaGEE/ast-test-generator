# tests/test_switch_cases.py
"""switch / match cases are conditions too: `case 2:` means `choice == 2`."""
import shutil

import pytest

from src.core.multi_language_runner import run_test_suite
from src.languages.c.adapter import CAdapter
from src.languages.java.adapter import JavaAdapter
from src.parser.analyzer.condition_analyzer import analyze_source

needs_java = pytest.mark.skipif(
    not (shutil.which("javac") and shutil.which("java")),
    reason="Java JDK is not installed",
)
needs_gcc = pytest.mark.skipif(
    not shutil.which("gcc"), reason="GCC is not installed"
)


def _c(body):
    return [(c.variable, c.operator, c.value) for c in CAdapter().analyze(
        "void f(int c, int x) { " + body + " }"
    )]


def _java(body):
    return [(c.variable, c.operator, c.value) for c in JavaAdapter().analyze(
        "public class A { static int f(int c, int x) { " + body + " return 0; } }"
    )]


def test_c_switch_cases():
    body = "switch (c) { case 1: break; case -2: case 0x3: break; default: break; }"
    assert _c(body) == [("c", "==", 1), ("c", "==", -2), ("c", "==", 3)]


def test_java_switch_statement_and_arrow_cases():
    body = (
        "switch (c) { case 1: break; case -2: break; default: } "
        "int r = switch (x) { case 4, 5 -> 1; default -> 0; };"
    )
    assert _java(body) == [
        ("c", "==", 1), ("c", "==", -2), ("x", "==", 4), ("x", "==", 5),
    ]


def test_python_match_cases():
    source = (
        "match c:\n"
        "    case 1:\n"
        "        pass\n"
        "    case 2 | -3:\n"
        "        pass\n"
        "    case _:\n"
        "        pass\n"
    )
    assert [(c["variable"], c["operator"], c["constant"]) for c in analyze_source(source)] == [
        ("c", "==", 1), ("c", "==", 2), ("c", "==", -3),
    ]


def test_switch_on_an_expression_is_ignored():
    assert _c("switch (c + 1) { case 1: break; }") == []


C_MENU = r"""
#include <stdio.h>
int main(void) {
    int choice;
    scanf("%d", &choice);
    switch (choice) {
    case 1: printf("create\n"); break;
    case 2: printf("deposit\n"); break;
    case 3: printf("withdraw\n"); break;
    case 0: printf("exit\n"); break;
    default: printf("invalid\n");
    }
    return 0;
}
"""

JAVA_MENU = """
import java.util.Scanner;
public class Menu {
    public static void main(String[] args) {
        int choice = new Scanner(System.in).nextInt();
        switch (choice) {
            case 1 -> System.out.println("create");
            case 2 -> System.out.println("deposit");
            case 3 -> System.out.println("withdraw");
            case 0 -> System.out.println("exit");
            default -> System.out.println("invalid");
        }
    }
}
"""

PY_MENU = (
    "choice = int(input())\n"
    "match choice:\n"
    "    case 1:\n"
    "        print('create')\n"
    "    case 2:\n"
    "        print('deposit')\n"
    "    case 3:\n"
    "        print('withdraw')\n"
    "    case 0:\n"
    "        print('exit')\n"
    "    case _:\n"
    "        print('invalid')\n"
)

EXPECTED = {1: "create", 2: "deposit", 3: "withdraw", 0: "exit"}


@pytest.mark.parametrize(
    "language, source",
    [
        pytest.param("c", C_MENU, marks=needs_gcc),
        pytest.param("java", JAVA_MENU, marks=needs_java),
        pytest.param("python", PY_MENU),
    ],
)
def test_every_menu_option_runs(language, source):
    result = run_test_suite(source, language=language, max_cases=20)

    seen = set()
    for test in result["results"]:
        choice = test.inputs["choice"]
        output = test.output.strip()
        assert output == EXPECTED.get(choice, "invalid"), (choice, output)
        seen.add(output)

    assert seen == {"create", "deposit", "withdraw", "exit", "invalid"}
