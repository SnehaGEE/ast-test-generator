

import re
import shutil
import subprocess
from pathlib import Path

import tree_sitter
import tree_sitter_c

from src.core.read_paths import Read, answers
from src.languages.branch_probes import Branch, Statement, instrument_source
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
# reached before exit(), a crash or a timeout are kept.
PROBE_PRELUDE = r"""#include <stdio.h>
#include <stdlib.h>
static int __branchlab_seen[BRANCH_COUNT][2];
static int __branchlab_probe(int id, int outcome)
{
    if (!__branchlab_seen[id][outcome]) {
        const char *path = getenv("BRANCHLAB_PROBE_FILE");
        __branchlab_seen[id][outcome] = 1;
        if (path != NULL) {
            FILE *file = fopen(path, "a");
            if (file != NULL) {
                fprintf(file, "%d %d\n", id, outcome);
                fclose(file);
            }
        }
    }
    return outcome;
}
static char __branchlab_lines[LINE_COUNT];
static void __branchlab_line(int line)
{
    if (!__branchlab_lines[line]) {
        const char *path = getenv("BRANCHLAB_PROBE_FILE");
        __branchlab_lines[line] = 1;
        if (path != NULL) {
            FILE *file = fopen(path, "a");
            if (file != NULL) {
                fprintf(file, "L %d\n", line);
                fclose(file);
            }
        }
    }
}
#line 1
"""


# One scanf conversion: optional '*' (assignment suppressed), width,
# length modifier, then the conversion letter or a [set].
_SCANF_CONVERSION = re.compile(
    r"%(\*?)\d*(?:hh|h|ll|l|L|j|z|t)?([diouxXaAeEfFgGscp]|\[\^?\]?[^\]]*\])"
)


def _scanf_kinds(format_literal: str) -> list[str]:
    """Kinds of the values a scanf format reads: "%d %f" -> int, float."""
    kinds = []
    for suppressed, conversion in _SCANF_CONVERSION.findall(
        format_literal.replace("%%", "")
    ):
        if suppressed:
            continue
        if conversion in "diouxXp":
            kinds.append("int")
        elif conversion in "aAeEfFgG":
            kinds.append("float")
        else:
            kinds.append("str")
    return kinds


def _c_reads(node, source_bytes: bytes):
    """Reads a call makes: one per scanf conversion, or None if not a read.

    &name and char-array arguments name their read; other targets such as
    &list[i] still consume a value, with no name.
    """
    if node.type != "call_expression":
        return None
    function = node.child_by_field_name("function")
    arguments = node.child_by_field_name("arguments")
    if (
        function is None
        or arguments is None
        or node_text(function, source_bytes) != "scanf"
        or not arguments.named_children
    ):
        return None

    format_node, *targets = arguments.named_children
    reads = []
    for argument, kind in zip(targets, _scanf_kinds(node_text(format_node, source_bytes))):
        target = (
            argument.child_by_field_name("argument")
            if argument.type == "pointer_expression"
            else argument
        )
        name = (
            node_text(target, source_bytes)
            if target is not None and target.type == "identifier"
            else None
        )
        reads.append(Read(name, kind))
    return reads


def _c_callee(node, source_bytes: bytes):
    if node.type != "call_expression":
        return None
    function = node.child_by_field_name("function")
    if function is None or function.type != "identifier":
        return None
    return node_text(function, source_bytes)


def _c_definition(node, source_bytes: bytes):
    """(name, body) of a function definition, through pointer declarators."""
    declarator = node.child_by_field_name("declarator")
    while declarator is not None and declarator.type != "identifier":
        declarator = declarator.child_by_field_name("declarator")
    body = node.child_by_field_name("body")
    if declarator is None or body is None:
        return None
    return node_text(declarator, source_bytes), body


def _parse_c_number(text: str):
    """Parse a C number literal such as 42, -5, 0x1F, 017, 5u or 2.5f."""
    text = text.replace("'", "").lower()
    sign = -1 if text.startswith("-") else 1
    text = text.lstrip("+-")

    if text.startswith(("0x", "0b")):
        if "." in text or "p" in text:
            return None  # hexadecimal floats are not supported
        return sign * int(text.rstrip("ul"), 0)

    if "." in text or "e" in text:
        return sign * float(text.rstrip("fl"))

    text = text.rstrip("ul")
    if len(text) > 1 and text.startswith("0"):
        return sign * int(text, 8)
    return sign * int(text)


def _numeric_value(node, source_bytes: bytes):
    """Return a numeric literal's value, or None for anything else."""
    sign = 1

    if node.type == "unary_expression":
        operator = node.child_by_field_name("operator")
        argument = node.child_by_field_name("argument")
        if operator is None or argument is None:
            return None
        if operator.type not in {"-", "+"}:
            return None
        sign = -1 if operator.type == "-" else 1
        node = argument

    if node.type != "number_literal":
        return None

    try:
        value = _parse_c_number(node_text(node, source_bytes))
    except ValueError:
        return None

    return None if value is None else sign * value


class CAdapter(CompiledLanguageAdapter):
    """C adapter using Tree-sitter for syntax parsing."""

    display_name = "C"
    exit_label = "C program"
    timeout_message = "C program execution timed out."
    temp_prefix = "ast_test_c_"

    def __init__(self):
        self.language = tree_sitter.Language(tree_sitter_c.language())
        self.parser = tree_sitter.Parser(self.language)

    def parse(self, source_code: str):
        """Parse C source and reject empty or syntactically invalid input."""
        if not source_code.strip():
            raise ValueError("C source code is empty.")

        tree = self.parser.parse(source_code.encode("utf-8"))

        if tree.root_node.has_error:
            raise ValueError("C source contains syntax errors.")

        return tree

    def analyze(self, source_code: str) -> list[Condition]:
        """Extract numeric comparisons from if, while and do conditions."""
        tree = self.parse(source_code)
        source_bytes = source_code.encode("utf-8")
        return extract_conditions(
            tree.root_node,
            source_bytes,
            "c",
            lambda node: _numeric_value(node, source_bytes),
        )

    def input_plan(self, source_code: str) -> InputPlan:
        """Find the program's reads (as a read map) and argv[n] positions."""
        source_bytes = source_code.encode("utf-8")
        tree = self.parser.parse(source_bytes)
        plan = InputPlan()

        def visit(node):
            if node.type == "subscript_expression":
                array = node.child_by_field_name("argument")
                index = node.child_by_field_name("index")

                if (
                    array is not None
                    and index is not None
                    and node_text(array, source_bytes) == "argv"
                    and index.type == "number_literal"
                ):
                    name = assigned_name(node, source_bytes)
                    try:
                        position = int(node_text(index, source_bytes), 0)
                    except ValueError:
                        position = None
                    if name and position:
                        plan.positions.setdefault(name, position)

            for child in node.children:
                visit(child)

        visit(tree.root_node)
        plan.read_map = ReadMapBuilder(
            source_bytes,
            reads=lambda node: _c_reads(node, source_bytes),
            callee=lambda node: _c_callee(node, source_bytes),
            definition=lambda node: _c_definition(node, source_bytes),
            numeric_value=lambda node: _numeric_value(node, source_bytes),
        ).build(tree.root_node)
        return plan

    def missing_tools(self) -> str | None:
        if shutil.which("gcc") is None:
            return "GCC must be available on PATH."
        return None

    def build(self, temp_dir: str, source_code: str):
        source_path = Path(temp_dir) / "program.c"
        executable_path = Path(temp_dir) / "program.exe"
        source_path.write_text(source_code, encoding="utf-8")

        compile_result = subprocess.run(
            ["gcc", str(source_path), "-o", str(executable_path)],
            capture_output=True,
            text=True,
            timeout=COMPILE_TIMEOUT_SECONDS,
            cwd=temp_dir,
        )

        if compile_result.returncode != 0:
            return None, (
                compile_result.stderr.strip()
                or compile_result.stdout.strip()
                or "C compilation failed."
            )
        return executable_path, None

    def add_probes(
        self,
        source_bytes: bytes,
        branches: list[Branch],
        statements: list[Statement],
    ) -> str:
        """Prepend the probe functions; probe every condition and statement.

        `#line 1` makes compiler messages use the original line numbers.
        """
        prelude = PROBE_PRELUDE.replace(
            "BRANCH_COUNT", str(max(len(branches), 1))
        ).replace("LINE_COUNT", str(source_bytes.count(b"\n") + 2))
        body = instrument_source(
            source_bytes,
            branches,
            statements,
            lambda branch_id, condition: (
                f"__branchlab_probe({branch_id}, ({condition}) ? 1 : 0)"
            ),
            lambda line: f"__branchlab_line({line});",
        )
        return prelude + body

    def run_command(
        self,
        target,
        temp_dir: str,
        test_case: TestCase,
        plan: InputPlan,
    ) -> tuple[list[str], str]:
        """Pass values as argv entries and on stdin."""
        # argc is not an argument; it is the argument count plus
        # the program name.
        values = {
            key: value
            for key, value in test_case.inputs.items()
            if key != "argc"
        }

        if plan.positions:
            # Put each value at the argv index the program reads it from.
            arguments = ["0"] * max(plan.positions.values())
            for name, position in plan.positions.items():
                if name in values:
                    arguments[position - 1] = str(values[name])
        else:
            # Unknown layout: pass values in alphabetical order.
            arguments = [str(value) for _, value in sorted(values.items())]

        argc = test_case.inputs.get("argc")

        if isinstance(argc, int) and not isinstance(argc, bool):
            # Make the program see exactly this argc: drop extra
            # arguments, or pad with "0" when more are needed.
            wanted = max(argc - 1, 0)
            arguments = arguments[:wanted] + [
                "0"
            ] * (wanted - len(arguments))

        stdin = stdin_text(answers(plan.read_map, values))
        return [str(target), *arguments], stdin
