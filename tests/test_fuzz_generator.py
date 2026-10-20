
import unittest

from src.core.fuzz_generator import generate_fuzz_inputs


class TestFuzzGenerator(unittest.TestCase):
    def test_generates_requested_number_of_cases(self):
        cases = generate_fuzz_inputs(["age"], max_cases=10)

        self.assertEqual(len(cases), 10)
        self.assertTrue(all("age" in case for case in cases))

    def test_results_are_reproducible_with_same_seed(self):
        first = generate_fuzz_inputs(["age", "name"], max_cases=10, seed=42)
        second = generate_fuzz_inputs(["age", "name"], max_cases=10, seed=42)

        self.assertEqual(first, second)

    def test_respects_max_cases(self):
        cases = generate_fuzz_inputs(["age"], max_cases=3)

        self.assertEqual(len(cases), 3)

    def test_rejects_invalid_max_cases(self):
        with self.assertRaises(ValueError):
            generate_fuzz_inputs(["age"], max_cases=0)

    def test_empty_variable_list_returns_no_cases(self):
        cases = generate_fuzz_inputs([])

        self.assertEqual(cases, [])


if __name__ == "__main__":
    unittest.main()
