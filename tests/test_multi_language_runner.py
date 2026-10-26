import shutil
import unittest

from src.core.multi_language_runner import run_test_suite
from src.core.models import TestResult
from src.core.result_verifier import classify_execution, verify_output


class TestMultiLanguageRunner(unittest.TestCase):

    def test_rejects_unsupported_language(self):
        with self.assertRaises(ValueError):
            run_test_suite("print('hello')", language="ruby")

    def test_rejects_invalid_max_cases(self):
        with self.assertRaises(ValueError):
            run_test_suite("print('hello')", max_cases=0)

    def test_python_runner_executes(self):
        source = """
age = int(input("Age: "))
if age >= 18:
    print("Adult")
else:
    print("Minor")
"""
        result = run_test_suite(source, language="python")

        self.assertGreater(result["total_tests"], 0)
        self.assertEqual(result["failed_executions"], 0)

        outputs = {
            line.strip().split()[-1]
            for test in result["results"]
            if test.executed
            for line in test.output.strip().splitlines()
            if line.strip()
        }

        self.assertIn("Adult", outputs)
        self.assertIn("Minor", outputs)

    def test_python_runner_reports_branch_coverage(self):
        source = """
age = int(input("Age: "))
if age >= 18:
    print("Adult")
else:
    print("Minor")
"""
        result = run_test_suite(source, language="python")
        coverage = result["coverage"]

        self.assertTrue(coverage["success"])
        self.assertIn("branch_coverage_percent", coverage)
        self.assertGreaterEqual(
            coverage["branch_coverage_percent"], 0
        )
        self.assertLessEqual(
            coverage["branch_coverage_percent"], 100
        )
        self.assertTrue(coverage["branches"])

        branch = coverage["branches"][0]
        self.assertTrue(branch["true_covered"])
        self.assertTrue(branch["false_covered"])

    @unittest.skipUnless(
        shutil.which("javac") and shutil.which("java"),
        "Java JDK is not installed",
    )
    def test_java_runner_executes(self):
        source = """
public class AgeCheck {
    public static void main(String[] args) {
        int age = Integer.parseInt(
            System.getProperty("age", "0")
        );

        if (age >= 18) {
            System.out.println("Adult");
        } else {
            System.out.println("Minor");
        }
    }
}
"""
        result = run_test_suite(source, language="java")

        self.assertGreater(result["total_tests"], 0)
        self.assertEqual(result["failed_executions"], 0)

        outputs = {
            test.output.strip()
            for test in result["results"]
            if test.executed and test.output.strip()
        }

        self.assertIn("Adult", outputs)
        self.assertIn("Minor", outputs)

    @unittest.skipUnless(
        shutil.which("gcc"),
        "GCC is not installed",
    )
    def test_c_runner_executes(self):
        source = r"""
#include <stdio.h>
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
        result = run_test_suite(source, language="c")

        self.assertGreater(result["total_tests"], 0)

        # argc = 1 runs the program's missing-argument guard, which
        # exits with code 1; every other run should succeed.
        for test in result["results"]:
            if test.inputs.get("argc") == 1:
                self.assertFalse(test.executed, test.inputs)
                self.assertIn("exited with code 1", test.error)
            else:
                self.assertTrue(test.executed, test.inputs)

        outputs = {
            test.output.strip()
            for test in result["results"]
            if test.executed and test.output.strip()
        }

        self.assertIn("Adult", outputs)
        self.assertIn("Minor", outputs)

    def test_execution_error_classification(self):
        cases = [
            ("ValueError: invalid literal", "invalid_input_error"),
            ("EOFError: No more input", "missing_input_error"),
            ("Execution timed out after 3 seconds", "timeout"),
            ("Invalid Python syntax: invalid syntax", "syntax_error"),
            ("RuntimeError: unexpected failure", "execution_error"),
        ]

        for error, expected in cases:
            with self.subTest(error=error):
                result = TestResult(
                    inputs={},
                    executed=False,
                    error=error,
                )
                self.assertEqual(
                    classify_execution(result),
                    expected,
                )

    def test_output_verification_preserves_pass_fail_behavior(self):
        passing = TestResult(
            inputs={},
            executed=True,
            output="Adult\n",
        )
        failing = TestResult(
            inputs={},
            executed=True,
            output="Minor\n",
        )

        self.assertEqual(
            verify_output(passing, "Adult").correctness,
            "passed",
        )
        self.assertEqual(
            verify_output(failing, "Adult").correctness,
            "failed",
        )


if __name__ == "__main__":
    unittest.main()