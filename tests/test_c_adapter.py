
import unittest

from src.languages.c.adapter import CAdapter


class TestCAdapter(unittest.TestCase):

    def setUp(self):
        self.adapter = CAdapter()

    def test_detects_numeric_condition(self):
        source = """
int main(void) {
    int age = 18;
    if (age >= 18) {
        return 1;
    }
    return 0;
}
"""
        conditions = self.adapter.analyze(source)

        self.assertEqual(len(conditions), 1)
        self.assertEqual(
            (
                conditions[0].variable,
                conditions[0].operator,
                conditions[0].value,
                conditions[0].language,
            ),
            ("age", ">=", 18, "c"),
        )

    def test_detects_multiple_conditions(self):
        source = """
int main(void) {
    int age = 18;
    if (age >= 18 && age < 65) {
        return 1;
    }
    return 0;
}
"""
        conditions = self.adapter.analyze(source)

        self.assertEqual(
            [
                (c.variable, c.operator, c.value)
                for c in conditions
            ],
            [("age", ">=", 18), ("age", "<", 65)],
        )

    def test_rejects_invalid_c_syntax(self):
        source = """
int main(void) {
    if (age >= ) {
        return 1;
    }
    return 0;
}
"""
        with self.assertRaises(ValueError):
            self.adapter.analyze(source)

    def test_rejects_empty_source(self):
        with self.assertRaises(ValueError):
            self.adapter.parse("   ")


if __name__ == "__main__":
    unittest.main()
