# tests/test_path_inputs.py
"""Different branches read different values. Each test must answer the
reads on the path its own values take: in a menu, option 1 may read
(no, name, amount) while option 2 reads (no, amount).

Every program echoes what it read, so the tests check real outputs.
"""
import shutil
from pathlib import Path

import pytest

from src.core.multi_language_runner import run_test_suite

ROOT = Path(__file__).resolve().parent.parent

needs_java = pytest.mark.skipif(
    not (shutil.which("javac") and shutil.which("java")),
    reason="Java JDK is not installed",
)
needs_gcc = pytest.mark.skipif(
    not shutil.which("gcc"), reason="GCC is not installed"
)


def _last_lines(result):
    rows = []
    for test in result["results"]:
        if test.category != "targeted":
            continue
        assert test.executed, (test.inputs, test.error)
        rows.append((test.inputs, test.output.strip().splitlines()[-1]))
    assert rows
    return rows


def _expected_menu(inputs):
    choice, amount = inputs["choice"], inputs["amount"]
    if choice == 1:
        return "open amount=%d" % amount
    if choice == 2:
        return "deposit amount=%d" % amount
    return "bye"


C_MENU = r"""
#include <stdio.h>
int main(void) {
    int choice, no;
    char name[30];
    float amount;
    scanf("%d", &choice);
    switch (choice) {
    case 1:
        scanf("%d", &no);
        scanf(" %29[^\n]", name);
        scanf("%f", &amount);
        if (amount < 0) { printf("negative\n"); }
        printf("open amount=%.0f\n", amount);
        break;
    case 2:
        scanf("%d %f", &no, &amount);
        if (amount <= 0) { printf("invalid\n"); }
        printf("deposit amount=%.0f\n", amount);
        break;
    default:
        printf("bye\n");
    }
    return 0;
}
"""


@needs_gcc
def test_c_each_menu_option_gets_its_own_reads():
    result = run_test_suite(C_MENU, language="c", max_cases=30)
    for inputs, line in _last_lines(result):
        assert line == _expected_menu(inputs), (inputs, line)


C_FALLTHROUGH = r"""
#include <stdio.h>
int main(void) {
    int mode, a = 0, b = 0;
    scanf("%d", &mode);
    switch (mode) {
    case 1:
        scanf("%d", &a);
    case 2:
        scanf("%d", &b);
        break;
    }
    if (b > 5) { printf("big\n"); }
    printf("a=%d b=%d\n", a, b);
    return 0;
}
"""


@needs_gcc
def test_c_case_without_break_falls_through_to_the_next_reads():
    result = run_test_suite(C_FALLTHROUGH, language="c", max_cases=20)
    for inputs, line in _last_lines(result):
        b = inputs["b"] if inputs["mode"] in (1, 2) else 0
        a = 1 if inputs["mode"] == 1 else 0  # a has no condition: placeholder 1
        assert line == f"a={a} b={b}", (inputs, line)


JAVA_MENU = """
import java.util.Scanner;
public class Bank {
    static double readAmount(Scanner in) {
        return in.nextDouble();
    }
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in);
        int choice = in.nextInt();
        in.nextLine();
        if (choice == 1) {
            String name = in.nextLine();
            double amount = readAmount(in);
            if (amount < 0) { System.out.println("negative"); }
            System.out.println("open amount=" + (int) amount);
        } else if (choice == 2) {
            int no = in.nextInt();
            double amount = in.nextDouble();
            if (amount <= 0) { System.out.println("invalid"); }
            System.out.println("deposit amount=" + (int) amount);
        } else {
            System.out.println("bye");
        }
    }
}
"""


@needs_java
def test_java_if_chain_skip_line_and_helper_method():
    result = run_test_suite(JAVA_MENU, language="java", max_cases=30)
    for inputs, line in _last_lines(result):
        assert line == _expected_menu(inputs), (inputs, line)


PY_MENU = (
    "def read_amount():\n"
    "    return float(input('Amount: '))\n"
    "\n"
    "choice = int(input('Choice: '))\n"
    "match choice:\n"
    "    case 1:\n"
    "        name = input('Name: ')\n"
    "        amount = read_amount()\n"
    "        if amount < 0:\n"
    "            print('negative')\n"
    "        print('open amount=%d' % amount)\n"
    "    case 2:\n"
    "        no = int(input('No: '))\n"
    "        amount = float(input('Amount: '))\n"
    "        if amount <= 0:\n"
    "            print('invalid')\n"
    "        print('deposit amount=%d' % amount)\n"
    "    case _:\n"
    "        print('bye')\n"
)


def test_python_match_branches_and_helper_function():
    result = run_test_suite(PY_MENU, language="python", max_cases=30)
    for inputs, line in _last_lines(result):
        line = line.split(": ")[-1]  # input() prompts share the line
        assert line == _expected_menu(inputs), (inputs, line)


@needs_gcc
def test_bank_deposit_and_withdraw_read_number_and_amount():
    source = (ROOT / "examples" / "c" / "bank.c").read_text(encoding="utf-8")
    result = run_test_suite(source, language="c", max_cases=40)
    for test in result["results"]:
        if test.inputs.get("choice") in (2, 3):
            # The amount is read as a number now. With no accounts yet,
            # the program correctly answers "Account not found!".
            assert "Account not found!" in test.output, test.inputs
            assert "Account number and amount: Invalid input!" not in test.output


@needs_gcc
def test_values_from_other_paths_are_not_fed_to_the_next_menu_round():
    # Option 4 never reads `amount`. Its generated value must not be left
    # on stdin, where the menu loop would read it as the next choice and
    # start option 1 inside a "Check Balance" test. Only option 1 asks
    # for the account holder's name.
    source = (ROOT / "examples" / "c" / "bank.c").read_text(encoding="utf-8")
    result = run_test_suite(source, language="c", max_cases=40)
    checked = 0
    for test in result["results"]:
        if test.category == "targeted" and test.inputs["choice"] in (4, 5, 6, 7):
            assert "Account holder name:" not in test.output, test.inputs
            checked += 1
    assert checked
