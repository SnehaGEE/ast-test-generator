
import unittest

from src.core.invalid_input_generator import generate_invalid_inputs


class TestInvalidInputGenerator(unittest.TestCase):
    def test_generates_invalid_input_candidates(self):
        cases = generate_invalid_inputs(["age"])

        self.assertEqual(len(cases), 6)
        self.assertEqual(
            [case["age"] for case in cases],
            [
                "garbage",
                "",
                "@#$%",
                " ",
                None,
                "999999999999999999999999999999999999",
            ],
        )

    def test_generates_cases_for_multiple_variables(self):
        cases = generate_invalid_inputs(["age", "name"], max_cases=8)

        self.assertEqual(len(cases), 8)
        self.assertTrue(all(len(case) == 1 for case in cases))

    def test_respects_max_cases(self):
        cases = generate_invalid_inputs(["age"], max_cases=3)

        self.assertEqual(len(cases), 3)

    def test_rejects_invalid_max_cases(self):
        with self.assertRaises(ValueError):
            generate_invalid_inputs(["age"], max_cases=0)

    def test_empty_variable_list_returns_no_cases(self):
        cases = generate_invalid_inputs([])

        self.assertEqual(cases, [])


if __name__ == "__main__":
    unittest.main()
