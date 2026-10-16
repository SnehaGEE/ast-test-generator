from analyzer.condition_analyzer import analyze_source
from analyzer.generator.test_generator import generate_boundary_tests
from analyzer.generator.executor.test_executor import execute_test_case


print("========================================")
print(" AST-BASED TARGETED TEST GENERATOR")
print("========================================")
print()

print("Enter your Python program.")
print("Type END on a new line when finished.")
print()

lines = []

while True:
    line = input()

    if line.strip() == "END":
        break

    lines.append(line)

source_code = "\n".join(lines)

print()
print("Analyzing program...")
print()

try:
    conditions = analyze_source(source_code)
except SyntaxError as error:
    print("Invalid Python syntax!")
    print(f"Error on line {error.lineno}: {error.msg}")
    raise SystemExit(1)

if not conditions:
    print("No supported conditions were detected.")
else:
    for condition in conditions:
        print("Detected condition:")
        print(f"Variable : {condition['variable']}")
        print(f"Operator : {condition['operator']}")
        print(f"Boundary : {condition['constant']}")
        print(f"Line     : {condition['line']}")
        print()

        test_cases = generate_boundary_tests(condition)

        print("Generated targeted test cases:")

        for test_case in test_cases:
            variable_values = {}

            for detected_condition in conditions:
                variable = detected_condition["variable"]
                constant = detected_condition["constant"]

                if (
                    isinstance(constant, (int, float))
                    and not isinstance(constant, bool)
                ):
                    variable_values[variable] = constant

            variable_values[condition["variable"]] = test_case

            print(f"  Test inputs: {variable_values}")

            result = execute_test_case(source_code, variable_values)

            if result["success"]:
                print(f"  Program output: {result['output'].rstrip()}")
            else:
                print(f"  Execution error: {result['error']}")

        print()