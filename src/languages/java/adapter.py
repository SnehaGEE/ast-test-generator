
import re
import shutil
import subprocess
from pathlib import Path

import tree_sitter
import tree_sitter_java

from src.core.read_paths import Read, answers
from src.languages.branch_probes import Branch, insert_probes
from src.languages.compiled import (
    COMPILE_TIMEOUT_SECONDS,
    CompiledLanguageAdapter,
)
from src.languages.input_plan import (
    InputPlan,
    assigned_name,
    node_text,
    stdin_text,
)
from src.languages.tree_sitter_conditions import extract_conditions
from src.languages.tree_sitter_reads import ReadMapBuilder
from src.core.models import Condition, TestCase


# Records each condition outcome the first time it happens, so outcomes
# reached before System.exit(), an exception or a timeout are kept.
PROBE_CLASS = r"""

final class __BranchLabProbe {
    private static final boolean[][] SEEN = new boolean[BRANCH_COUNT][2];

    static synchronized boolean hit(int id, boolean value) {
        int outcome = value ? 1 : 0;
        if (!SEEN[id][outcome]) {
            SEEN[id][outcome] = true;
            String path = System.getenv("BRANCHLAB_PROBE_FILE");
            if (path != null) {
                try (java.io.FileWriter out = new java.io.FileWriter(path, true)) {
                    out.write(id + " " + outcome + "\n");
                } catch (java.io.IOException ignored) {
                }
            }
        }
        return value;
    }
}
"""

# What a read method returns, before any parse call around it.
READ_KINDS = {
    "nextInt": "int",
    "nextLong": "int",
    "nextShort": "int",
    "nextByte": "int",
    "nextDouble": "float",
    "nextFloat": "float",
    "nextBoolean": "bool",
}

# Parse calls that turn a line of text into a value.
PARSE_KINDS = {
    "parseInt": "int",
    "parseLong": "int",
    "parseShort": "int",
    "parseByte": "int",
    "parseDouble": "float",
    "parseFloat": "float",
    "parseBoolean": "bool",
}

# Scanner and BufferedReader methods that consume one value from stdin.
READ_METHODS = {
    "next",
    "nextInt",
    "nextLong",
    "nextShort",
    "nextByte",
    "nextDouble",
    "nextFloat",
    "nextBoolean",
    "nextLine",
    "readLine",
}

INTEGER_LITERALS = {
    "decimal_integer_literal",
    "hex_integer_literal",
    "octal_integer_literal",
    "binary_integer_literal",
}


def _numeric_value(node, source_bytes: bytes):
    """Return the value of a numeric literal such as -5, 0x1F, 5L or 2.5f.

    Returns None when the node is not a supported numeric literal.
    """
    sign = 1

    if node.type == "unary_expression" and len(node.children) == 2:
        operator, operand = node.children
        if operator.type not in {"-", "+"}:
            return None
        sign = -1 if operator.type == "-" else 1
        node = operand

    text = node_text(node, source_bytes).replace("_", "")

    try:
        if node.type == "decimal_floating_point_literal":
            return sign * float(text.rstrip("fFdD"))
        if node.type == "octal_integer_literal":
            return sign * int(text.rstrip("lL"), 8)
        if node.type in INTEGER_LITERALS:
            # base 0 reads 0x.. and 0b.. prefixes.
            return sign * int(text.rstrip("lL"), 0)
    except ValueError:
        return None

    return None


def _read_kind(node, source_bytes: bytes) -> str:
    """Kind of value a read call expects.

    in.nextInt() -> "int"; Integer.parseInt(in.readLine()) -> "int";
    in.next() or in.readLine() on their own -> "str".
    """
    current = node
    while current is not None and current.type == "method_invocation":
        method = current.child_by_field_name("name")
        name = node_text(method, source_bytes) if method is not None else ""
        if name in PARSE_KINDS:
            return PARSE_KINDS[name]
        if current is node and name in READ_KINDS:
            return READ_KINDS[name]
        # Step out through .trim() and through being a call's argument.
        parent = current.parent
        if parent is not None and parent.type == "argument_list":
            parent = parent.parent
        current = parent
    return "str"


# Scanner methods that read one token and leave the rest of the line.
TOKEN_METHODS = {
    "next",
    "nextInt",
    "nextLong",
    "nextShort",
    "nextByte",
    "nextDouble",
    "nextFloat",
    "nextBoolean",
}


def _java_reads(node, source_bytes: bytes):
    """The read a Scanner/BufferedReader call makes, or None."""
    if node.type != "method_invocation":
        return None
    method = node.child_by_field_name("name")
    name = node_text(method, source_bytes) if method is not None else ""
    if name not in READ_METHODS:
        return None
    return [
        Read(
            None,
            _read_kind(node, source_bytes),
            token=name in TOKEN_METHODS,
            rest_of_line=name == "nextLine",
        )
    ]


def _java_callee(node, source_bytes: bytes):
    """Name of a method of this class called as name(...) or this.name(...)."""
    if node.type != "method_invocation":
        return None
    target = node.child_by_field_name("object")
    if target is not None and node_text(target, source_bytes) != "this":
        return None
    method = node.child_by_field_name("name")
    return node_text(method, source_bytes) if method is not None else None


def _java_definition(node, source_bytes: bytes):
    name = node.child_by_field_name("name")
    body = node.child_by_field_name("body")
    if name is None or body is None:
        return None
    return node_text(name, source_bytes), body


class JavaAdapter(CompiledLanguageAdapter):
    """Java adapter using Tree-sitter for syntax parsing."""

    display_name = "Java"
    exit_label = "Java"
    timeout_message = "Java execution timed out."
    temp_prefix = "ast_test_java_"

    def __init__(self):
        self.language = tree_sitter.Language(tree_sitter_java.language())
        self.parser = tree_sitter.Parser(self.language)

    def parse(self, source_code: str):
        """Parse Java source into a Tree-sitter syntax tree."""
        if not source_code.strip():
            raise ValueError("Java source code is empty.")

        tree = self.parser.parse(source_code.encode("utf-8"))

        if tree.root_node.has_error:
            raise ValueError("Java source contains syntax errors.")

        return tree

    def analyze(self, source_code: str) -> list[Condition]:
        """Extract numeric comparisons from if, while and do conditions."""
        tree = self.parse(source_code)
        source_bytes = source_code.encode("utf-8")
        return extract_conditions(
            tree.root_node,
            source_bytes,
            "java",
            lambda node: _numeric_value(node, source_bytes),
        )

    def input_plan(self, source_code: str) -> InputPlan:
        """Find stdin reads and args[n] positions in the source."""
        source_bytes = source_code.encode("utf-8")
        tree = self.parser.parse(source_bytes)
        plan = InputPlan()
        args_name = "args"

        def find_args_name(node):
            nonlocal args_name
            if node.type == "method_declaration":
                name = node.child_by_field_name("name")
                parameters = node.child_by_field_name("parameters")
                if (
                    name is not None
                    and parameters is not None
                    and node_text(name, source_bytes) == "main"
                ):
                    for parameter in parameters.named_children:
                        parameter_name = parameter.child_by_field_name("name")
                        if parameter_name is not None:
                            args_name = node_text(parameter_name, source_bytes)
                            return
            for child in node.children:
                find_args_name(child)

        def visit(node):
            if node.type == "array_access":
                array = node.child_by_field_name("array")
                index = node.child_by_field_name("index")
                if (
                    array is not None
                    and index is not None
                    and node_text(array, source_bytes) == args_name
                    and index.type == "decimal_integer_literal"
                ):
                    name = assigned_name(node, source_bytes)
                    if name:
                        plan.positions.setdefault(
                            name, int(node_text(index, source_bytes))
                        )

            for child in node.children:
                visit(child)

        find_args_name(tree.root_node)
        visit(tree.root_node)
        plan.read_map = ReadMapBuilder(
            source_bytes,
            reads=lambda node: _java_reads(node, source_bytes),
            callee=lambda node: _java_callee(node, source_bytes),
            definition=lambda node: _java_definition(node, source_bytes),
            numeric_value=lambda node: _numeric_value(node, source_bytes),
        ).build(tree.root_node)
        return plan

    def missing_tools(self) -> str | None:
        if shutil.which("javac") is None or shutil.which("java") is None:
            return "Java JDK tools javac and java must be available on PATH."
        return None

    def build(self, temp_dir: str, source_code: str):
        class_match = re.search(
            r"\bpublic\s+class\s+([A-Za-z_]\w*)",
            source_code,
        )
        if not class_match:
            return None, "Java source must declare a public class."

        class_name = class_match.group(1)
        source_path = Path(temp_dir) / f"{class_name}.java"
        source_path.write_text(source_code, encoding="utf-8")

        compile_result = subprocess.run(
            ["javac", str(source_path)],
            capture_output=True,
            text=True,
            timeout=COMPILE_TIMEOUT_SECONDS,
            cwd=temp_dir,
        )

        if compile_result.returncode != 0:
            return None, (
                compile_result.stderr.strip()
                or compile_result.stdout.strip()
                or "Java compilation failed."
            )
        return class_name, None

    def add_probes(self, source_bytes: bytes, branches: list[Branch]) -> str:
        """Wrap every condition and append the probe class.

        The class goes after the program so line numbers do not change.
        """
        body = insert_probes(
            source_bytes,
            branches,
            lambda branch_id, condition: (
                f"__BranchLabProbe.hit({branch_id}, ({condition}))"
            ),
        )
        return body + PROBE_CLASS.replace("BRANCH_COUNT", str(len(branches)))

    def run_command(
        self,
        target,
        temp_dir: str,
        test_case: TestCase,
        plan: InputPlan,
    ) -> tuple[list[str], str]:
        """Offer each value three ways.

        As a system property, at the args index the program reads it
        from, and on standard input.
        """
        properties = [
            f"-D{key}={value}"
            for key, value in test_case.inputs.items()
        ]

        arguments: list[str] = []
        if plan.positions:
            arguments = ["0"] * (max(plan.positions.values()) + 1)
            for name, position in plan.positions.items():
                if name in test_case.inputs:
                    arguments[position] = str(test_case.inputs[name])

        stdin = stdin_text(answers(plan.read_map, test_case.inputs))
        return ["java", *properties, "-cp", temp_dir, target, *arguments], stdin
