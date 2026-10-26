import shutil

from src.core.models import TestCase
from src.languages.c.adapter import CAdapter

PROGRAM = r"""#include <stdio.h>
#include <stdlib.h>

int main(int argc, char *argv[]) {
    if (argc < 2) {
        return 1;
    }

    int age = atoi(argv[1]);

    if (age >= 18) {
        printf("Adult\n");
    } else {
        printf("Minor\n");
    }

    return 0;
}
"""

COUNT_ARGS = r"""#include <stdio.h>

int main(int argc, char *argv[]) {
    printf("%d", argc);
    return 0;
}
"""


def _run(source, inputs):
    return CAdapter().execute(source, TestCase(inputs=inputs))


def _needs_gcc():
    return shutil.which("gcc") is None


def test_argc_one_runs_the_missing_argument_guard():
    if _needs_gcc():
        return
    result = _run(PROGRAM, {"argc": 1, "age": 18})
    assert result.executed is False
    assert "exited with code 1" in result.error
    assert result.output.strip() == ""


def test_argc_two_passes_the_age_argument():
    if _needs_gcc():
        return
    adult = _run(PROGRAM, {"argc": 2, "age": 18})
    minor = _run(PROGRAM, {"argc": 2, "age": 17})
    assert adult.executed and adult.output.strip() == "Adult"
    assert minor.executed and minor.output.strip() == "Minor"


def test_larger_argc_pads_with_extra_arguments():
    if _needs_gcc():
        return
    result = _run(PROGRAM, {"argc": 3, "age": 19})
    assert result.executed is True
    assert result.output.strip() == "Adult"


def test_program_sees_exactly_the_requested_argc():
    if _needs_gcc():
        return
    for argc in (1, 2, 3, 5):
        result = _run(COUNT_ARGS, {"argc": argc, "age": 7})
        assert result.output == str(argc), argc


def test_programs_without_argc_input_behave_as_before():
    if _needs_gcc():
        return
    result = _run(PROGRAM, {"age": 21})
    assert result.executed is True
    assert result.output.strip() == "Adult"