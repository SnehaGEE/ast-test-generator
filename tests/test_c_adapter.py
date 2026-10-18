
import unittest

from src.core.models import TestCase
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

    def test_executes_c_program(self):
        source = """
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char *argv[]) {
    if (argc < 2) {
        return 1;
    }

    int age = atoi(argv[1]);

    if (age >= 18) {
        printf("Adult\\n");
    } else {
        printf("Minor\\n");
    }

    return 0;
}
"""
        test_case = TestCase(inputs={"age": 18})
        result = self.adapter.execute(source, test_case)

        self.assertTrue(result.executed, result.error)
        self.assertEqual(result.output.strip(), "Adult")


if __name__ == "__main__":
    unittest.main()
