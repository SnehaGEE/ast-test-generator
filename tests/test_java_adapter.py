
import unittest

from src.languages.java.adapter import JavaAdapter


class TestJavaAdapter(unittest.TestCase):

    def setUp(self):
        self.adapter = JavaAdapter()

    def test_detects_numeric_condition(self):
        source = """
public class AgeCheck {
    void check() {
        if (age >= 18) {
            System.out.println("Adult");
        }
    }
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
            ("age", ">=", 18, "java"),
        )

    def test_detects_multiple_conditions(self):
        source = """
public class Eligibility {
    void check() {
        if (age >= 18 && score < 50) {
            System.out.println("Eligible");
        }
    }
}
"""
        conditions = self.adapter.analyze(source)

        self.assertEqual(
            [
                (c.variable, c.operator, c.value)
                for c in conditions
            ],
            [("age", ">=", 18), ("score", "<", 50)],
        )

    def test_rejects_invalid_java_syntax(self):
        source = """
public class Broken {
    void check() {
        if (age >= ) {
        }
    }
}
"""
        with self.assertRaises(ValueError):
            self.adapter.analyze(source)

    def test_rejects_empty_source(self):
        with self.assertRaises(ValueError):
            self.adapter.parse("   ")


if __name__ == "__main__":
    unittest.main()
