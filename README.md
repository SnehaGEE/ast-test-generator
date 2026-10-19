# AST-Based Targeted Test Case Generator

A lightweight, multi-language framework for targeted automatic test case generation using **Abstract Syntax Tree (AST) analysis** and program analysis.

The project analyzes source code to identify supported conditional expressions, generates boundary-focused test inputs, and executes the generated test cases to observe program behavior.

Currently supported languages: Python, Java, and C.

## Key Features

- AST-Based Analysis: Identifies supported conditional expressions in source code.
- Targeted Test Generation: Generates boundary-focused inputs for numeric conditions.
- Multi-Language Support: Supports Python, Java, and C.
- Test Execution: Runs generated test cases and records outputs and errors.
- Condition Analysis: Extracts supported comparison operators and constants.
- Input Validation: Handles empty source code, invalid syntax, and unsupported languages.
- Automated Testing: Includes regression tests for analysis, generation, and execution.

## Installation

### Prerequisites

- Python 3.13 or a compatible Python version.
- GCC compiler for C execution.
- Java JDK for Java execution.

### Setup on Windows
1. Clone the repository
git clone https://github.com/SnehaGEE/ast-test-generator.git
cd ast-test-generator

2. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

3. Install the dependencies
powershell
python -m pip install -r requirements.txt
4. Run the test suite

python -m unittest discover -s tests -v