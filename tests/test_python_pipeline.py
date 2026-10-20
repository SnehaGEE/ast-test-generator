
import unittest

from src.core.test_runner import run_python_test_suite


class TestPythonPipeline(unittest.TestCase):

    def test_pipeline_generates_and_executes_targeted_tests(self):
        source_code = """
age = int(input("Enter age: "))
if age >= 18:
    print("Adult")
else:
    print("Minor")
"""

        result = run_python_test_suite(source_code)

        self.assertGreater(result["total_tests"], 0)
        self.assertEqual(
            result["total_tests"],
            result["successful_executions"] + result["failed_executions"],
        )
        self.assertIn("coverage", result)

    def test_pipeline_handles_source_without_conditions(self):
        source_code = 'print("Hello")'

        result = run_python_test_suite(source_code)

        self.assertEqual(result["total_tests"], 0)
        self.assertIn("message", result)

    def test_generated_inputs_produce_different_outputs(self):
        source_code = """
age = int(input("Enter age: "))
if age >= 18:
    print("Adult")
else:
    print("Minor")
"""

        result = run_python_test_suite(source_code)

        outputs = {
            item.output.strip().split()[-1]
            for item in result["results"]
            if item.executed and item.output.strip()
        }

        self.assertIn("Adult", outputs)
        self.assertIn("Minor", outputs)

    def test_runner_can_include_invalid_input_candidates(self):
        source_code = """
age = int(input("Enter age: "))
if age >= 18:
    print("Adult")
else:
    print("Minor")
"""

        result = run_python_test_suite(
            source_code,
            max_cases=20,
            include_invalid_inputs=True,
        )

        self.assertGreater(result["total_tests"], 0)
        self.assertLessEqual(result["total_tests"], 20)
        self.assertTrue(
            any(
                item.error and "ValueError" in item.error
                for item in result["results"]
            )
        )

    def test_runner_can_include_fuzz_inputs(self):
        source_code = """
age = int(input("Enter age: "))
if age >= 18:
    print("Adult")
else:
    print("Minor")
"""

        result = run_python_test_suite(
            source_code,
            max_cases=20,
            include_fuzz_inputs=True,
        )

        self.assertGreater(result["total_tests"], 0)
        self.assertLessEqual(result["total_tests"], 20)

        # TestResult stores inputs, output, and execution status,
        # but does not store the original TestCase description.
        self.assertTrue(
            any(item.inputs for item in result["results"])
        )


if __name__ == "__main__":
    unittest.main()
