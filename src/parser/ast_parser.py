import ast


def parse_source(source_code):
    """Parse Python source code into an Abstract Syntax Tree."""
    return ast.parse(source_code)


def print_ast(source_code):
    """Print the AST in a readable format."""
    tree = parse_source(source_code)
    print(ast.dump(tree, indent=4))


if __name__ == "__main__":
    sample_code = """
def check_age(age):
    if age >= 18:
        return "Adult"
    else:
        return "Minor"
"""

    print_ast(sample_code)