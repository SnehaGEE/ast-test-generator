
import shutil
import unittest

from src.core.multi_language_runner import run_test_suite


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
        self.assertEqual(result["failed_executions"], 0)

        outputs = {
            test.output.strip()
            for test in result["results"]
            if test.executed and test.output.strip()
        }

        self.assertIn("Adult", outputs)
        self.assertIn("Minor", outputs)


if __name__ == "__main__":
    unittest.main()
