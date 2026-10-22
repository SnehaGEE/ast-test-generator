
import unittest

from src.coverage.coverage_analyzer import (
    analyze_branch_coverage,
    measure_line_coverage,
)


class TestCoverageAnalyzer(unittest.TestCase):

    def test_branch_coverage_detects_true_and_false(self):
        source = """
age = int(input("Age: "))
if age >= 18:
    print("Adult")
else:
    print("Minor")
"""
        result = analyze_branch_coverage(
            source,
            [{"age": 20}, {"age": 16}],
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["branch_coverage_percent"], 100.0)
        self.assertTrue(result["branches"][0]["true_covered"])
        self.assertTrue(result["branches"][0]["false_covered"])

    def test_branch_coverage_reports_missing_outcome(self):
        source = """
age = int(input("Age: "))
if age >= 18:
    print("Adult")
else:
    print("Minor")
"""
        result = analyze_branch_coverage(source, [{"age": 20}])

        self.assertTrue(result["success"])
        self.assertEqual(result["branch_coverage_percent"], 50.0)
        self.assertEqual(result["branches"][0]["missing"], ["false"])

    def test_invalid_python_syntax_is_reported(self):
        result = analyze_branch_coverage("if :", [{"age": 20}])

        self.assertFalse(result["success"])
        self.assertIn("Invalid Python syntax", result["error"])

    def test_line_coverage_returns_executed_lines(self):
        source = """
value = 10
if value > 5:
    result = "high"
else:
    result = "low"
"""
        result = measure_line_coverage(source, {})

        self.assertTrue(result["success"])
        self.assertGreater(result["line_coverage_percent"], 0)
        self.assertTrue(result["executed_lines"])

    def test_branch_not_counted_when_execution_fails_before_if(self):
        source = """
value = 1 / 0
if value > 5:
    print("high")
else:
    print("low")
"""
        result = analyze_branch_coverage(source, [{}])

        self.assertTrue(result["success"])
        self.assertEqual(result["branch_coverage_percent"], 0.0)
        self.assertEqual(
            result["branches"][0]["missing"],
            ["true", "false"],
        )

    def test_unreachable_branch_is_not_reported_as_covered(self):
        source = """
if flag:
    print("enabled")
else:
    print("disabled")
"""
        result = analyze_branch_coverage(source, [{"flag": True}])

        self.assertTrue(result["success"])
        self.assertEqual(result["branch_coverage_percent"], 50.0)
        self.assertEqual(
            result["branches"][0]["missing"],
            ["false"],
        )


if __name__ == "__main__":
    unittest.main()
