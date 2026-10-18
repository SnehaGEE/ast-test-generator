import unittest

from src.parser.analyzer.generator.test_generator import (
    generate_boundary_tests,
)


class TestBoundaryGenerator(unittest.TestCase):
    def test_greater_than_boundary(self):
        values = generate_boundary_tests({
            "constant": 10,
            "operator": ">",
        })

        self.assertEqual(values, [10, 11, 9])

    def test_equality_boundary(self):
        values = generate_boundary_tests({
            "constant": 50,
            "operator": "==",
        })

        self.assertEqual(values, [49, 50, 51])

    def test_unsupported_operator_returns_no_candidates(self):
        values = generate_boundary_tests({
            "constant": 10,
            "operator": "contains",
        })

        self.assertEqual(values, [])

    def test_boolean_is_not_treated_as_numeric(self):
        values = generate_boundary_tests({
            "constant": True,
            "operator": "==",
        })

        self.assertEqual(values, [])

    def test_float_boundary_candidates_are_distinct(self):
        values = generate_boundary_tests({
            "constant": 1.5,
            "operator": ">=",
        })

        self.assertEqual(len(values), 3)
        self.assertEqual(len(set(values)), 3)
        self.assertIn(1.5, values)


    def test_greater_than_or_equal_covers_both_sides(self):
        values = generate_boundary_tests({
            "variable": "age",
            "operator": ">=",
            "constant": 18,
        })

        self.assertEqual(values, [17, 18, 19])
        self.assertLess(values[0], 18)
        self.assertIn(18, values)
        self.assertGreater(values[2], 18)


if __name__ == "__main__":
    unittest.main()