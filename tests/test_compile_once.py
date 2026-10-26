# tests/test_compile_once.py
import shutil
import subprocess

import pytest

from src.core.multi_language_runner import run_test_suite

JAVA_PROGRAM = """
public class AgeCheck {
    public static void main(String[] args) {
        int age = Integer.parseInt(System.getProperty("age", "0"));
        if (age >= 18) {
            System.out.println("Adult");
        } else {
            System.out.println("Minor");
        }
    }
}
"""

C_PROGRAM = r"""
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char *argv[]) {
    int age = argc > 1 ? atoi(argv[1]) : 0;
    if (age >= 18) {
        printf("Adult\n");
    } else {
        printf("Minor\n");
    }
    return 0;
}
"""

C_BROKEN = r"""
int main(int argc, char *argv[]) {
    int age = 0;
    if (age >= 18) {
        return undefined_name;
    }
    return 0;
}
"""


@pytest.fixture
def compiler_calls(monkeypatch):
    calls = []
    real_run = subprocess.run

    def counting_run(command, *args, **kwargs):
        calls.append(command[0])
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", counting_run)
    return calls


needs_java = pytest.mark.skipif(
    not (shutil.which("javac") and shutil.which("java")),
    reason="Java JDK is not installed",
)
needs_gcc = pytest.mark.skipif(
    not shutil.which("gcc"), reason="GCC is not installed"
)


@needs_java
def test_java_compiles_once_per_run(compiler_calls):
    result = run_test_suite(JAVA_PROGRAM, language="java", max_cases=20)

    assert result["total_tests"] > 1
    assert compiler_calls.count("javac") == 1
    assert compiler_calls.count("java") == result["total_tests"]

    outputs = {
        test.inputs["age"]: test.output.strip()
        for test in result["results"]
        if test.executed
    }
    assert outputs, "no Java test executed"
    for age, output in outputs.items():
        assert output == ("Adult" if age >= 18 else "Minor"), age


@needs_gcc
def test_c_compiles_once_per_run(compiler_calls):
    result = run_test_suite(C_PROGRAM, language="c", max_cases=20)

    assert result["total_tests"] > 1
    assert compiler_calls.count("gcc") == 1

    outputs = {
        test.inputs["age"]: test.output.strip()
        for test in result["results"]
        if test.executed
    }
    assert outputs, "no C test executed"
    for age, output in outputs.items():
        assert output == ("Adult" if age >= 18 else "Minor"), age


@needs_gcc
def test_c_compile_error_is_reported_on_every_test(compiler_calls):
    result = run_test_suite(C_BROKEN, language="c", max_cases=20)

    assert result["total_tests"] > 1
    assert compiler_calls.count("gcc") == 1
    for test in result["results"]:
        assert test.executed is False
        assert "undefined_name" in test.error
