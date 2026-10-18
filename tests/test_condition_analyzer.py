import unittest

from src.parser.analyzer.condition_analyzer import analyze_source


class TestConditionAnalyzer(unittest.TestCase):
    def test_detects_multiple_comparisons(self):
        source = """
if age >= 18 and score < 40:
    print("ok")
"""
        conditions = analyze_source(source)

        self.assertEqual(len(conditions), 2)
        self.assertEqual(
            [(c["variable"], c["operator"], c["constant"]) for c in conditions],
            [("age", ">=", 18), ("score", "<", 40)],
        )

    def test_returns_empty_list_when_no_comparison_is_supported(self):
        source = """
print("hello")
"""
        self.assertEqual(analyze_source(source), [])
    def test_detects_comparisons_in_or_expression(self):
        source = """
if age < 13 or age >= 65:
    print("eligible")
"""
        conditions = analyze_source(source)

        self.assertEqual(len(conditions), 2)
        self.assertEqual(
            [(c["variable"], c["operator"], c["constant"]) for c in conditions],
            [("age", "<", 13), ("age", ">=", 65)],
        )
        
if __name__ == "__main__":
    unittest.main()