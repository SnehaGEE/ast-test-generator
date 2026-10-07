from analyzer.condition_analyzer import analyze_source
from analyzer.generator.test_generator import generate_boundary_tests


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

conditions = analyze_source(source_code)

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
            print(f"  {test_case}")

        print()