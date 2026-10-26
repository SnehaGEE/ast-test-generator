"""Read maps for the Tree-sitter languages (Java and C).

The walk starts at `main` when the program has one. Function bodies are
read only where they are called, if/else on `name op number` becomes a
Branch, and switch on a name becomes a Switch whose cases fall through
when they do not end in break/return. Each language supplies a few hooks.
"""

from typing import Callable

from src.core.read_paths import Branch, Case, Read, Switch, name_single_read
from src.languages.input_plan import node_text
from src.languages.tree_sitter_conditions import REVERSED_OPERATORS, SUPPORTED_OPERATORS

DEFINITIONS = {"function_definition", "method_declaration"}
SWITCHES = {"switch_statement", "switch_expression"}
LOOPS = {"while_statement", "do_statement", "for_statement", "enhanced_for_statement"}
EXITS = {"break_statement", "return_statement", "continue_statement", "yield_statement"}
ASSIGNMENTS = {
    "init_declarator": "declarator",
    "variable_declarator": "name",
    "assignment_expression": "left",
}


class ReadMapBuilder:
    """Turn a Tree-sitter tree into a read map.

    reads(node): the Reads a node performs itself, or None if it is not a
        read call (C: scanf; Java: Scanner/BufferedReader methods).
    callee(node): name of a function in this file that node calls, or None.
    definition(node): (name, body) for a function/method definition.
    numeric_value(node): value of a numeric literal, or None.
    """

    def __init__(
        self,
        source_bytes: bytes,
        reads: Callable,
        callee: Callable,
        definition: Callable,
        numeric_value: Callable,
    ) -> None:
        self.source_bytes = source_bytes
        self.reads = reads
        self.callee = callee
        self.definition = definition
        self.numeric_value = numeric_value
        self.functions: dict = {}

    def build(self, root) -> list:
        self._collect(root)
        main = self.functions.get("main")
        if main is not None:
            return self.items(main, frozenset({"main"}))
        # No main: read the file top to bottom, function bodies included.
        self.functions = {}
        return self.items(root, frozenset())

    def _collect(self, node) -> None:
        found = self.definition(node) if node.type in DEFINITIONS else None
        if found is not None:
            name, body = found
            self.functions.setdefault(name, body)
        for child in node.children:
            self._collect(child)

    def text(self, node) -> str:
        return node_text(node, self.source_bytes)

    # ---- node handlers ----

    def items(self, node, stack) -> list:
        if node.type in DEFINITIONS and self.functions:
            return []  # runs only where it is called

        own_reads = self.reads(node)
        if own_reads is not None:
            return own_reads

        if node.type == "if_statement":
            return self._if(node, stack)
        if node.type in SWITCHES:
            return self._switch(node, stack)
        if node.type in ASSIGNMENTS:
            return self._assignment(node, stack)

        items = self.children(node, stack)
        name = self.callee(node)
        if name is not None and name in self.functions and name not in stack:
            items += self.items(self.functions[name], stack | {name})
        return items

    def children(self, node, stack) -> list:
        items: list = []
        for child in node.named_children:
            items += self.items(child, stack)
        return items

    def _assignment(self, node, stack) -> list:
        target = node.child_by_field_name(ASSIGNMENTS[node.type])
        name = self.text(target) if target is not None and target.type == "identifier" else None
        return name_single_read(self.children(node, stack), name)

    def _comparison(self, condition):
        """(name, operator, number) for a condition `(name op number)`."""
        node = condition
        while node is not None and node.type == "parenthesized_expression":
            inner = [c for c in node.named_children if c.type != "comment"]
            node = inner[0] if len(inner) == 1 else None
        if node is None or node.type != "binary_expression":
            return None

        operator_node = node.child_by_field_name("operator")
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if operator_node is None or left is None or right is None:
            return None
        operator = self.text(operator_node)
        if operator not in SUPPORTED_OPERATORS:
            return None

        if left.type == "identifier":
            value = self.numeric_value(right)
            if value is not None:
                return self.text(left), operator, value
        if right.type == "identifier":
            value = self.numeric_value(left)
            if value is not None:
                return self.text(right), REVERSED_OPERATORS[operator], value
        return None

    def _if(self, node, stack) -> list:
        condition = node.child_by_field_name("condition")
        consequence = node.child_by_field_name("consequence")
        alternative = node.child_by_field_name("alternative")

        items = self.items(condition, stack) if condition is not None else []
        then = self.items(consequence, stack) if consequence is not None else []
        otherwise = self.items(alternative, stack) if alternative is not None else []

        simple = self._comparison(condition) if condition is not None else None
        if simple is None:
            return items + then + otherwise
        return items + [Branch(*simple, then, otherwise)]

    def _switch(self, node, stack) -> list:
        condition = node.child_by_field_name("condition")
        body = node.child_by_field_name("body")
        items = self.items(condition, stack) if condition is not None else []
        if body is None:
            return items

        subjects = [
            child
            for child in (condition.named_children if condition is not None else [])
            if child.type != "comment"
        ]
        cases = list(self._cases(body, stack))
        if len(subjects) != 1 or subjects[0].type != "identifier":
            return items + [item for case in cases for item in case.body]
        return items + [Switch(self.text(subjects[0]), cases)]

    def _cases(self, body, stack):
        for child in body.named_children:
            if child.type == "case_statement":  # C
                value_node = child.child_by_field_name("value")
                statements = [
                    part
                    for part in child.named_children
                    if part is not value_node and part.type != "comment"
                ]
                values = None if value_node is None else self._values([value_node])
                yield Case(
                    values,
                    [item for part in statements for item in self.items(part, stack)],
                    not _ends_case(statements),
                )
            elif child.type in {"switch_block_statement_group", "switch_rule"}:  # Java
                labels = [part for part in child.named_children if part.type == "switch_label"]
                statements = [
                    part
                    for part in child.named_children
                    if part.type != "switch_label" and part.type != "comment"
                ]
                is_default = any(not label.named_children for label in labels)
                values = None if is_default else self._values(
                    [value for label in labels for value in label.named_children]
                )
                yield Case(
                    values,
                    [item for part in statements for item in self.items(part, stack)],
                    child.type == "switch_block_statement_group"
                    and not _ends_case(statements),
                )

    def _values(self, nodes) -> list:
        return [
            value
            for value in (self.numeric_value(node) for node in nodes)
            if value is not None
        ]


def _ends_case(statements) -> bool:
    """True if a case body ends with break/return (directly or in a block)."""
    for statement in statements:
        if statement.type in EXITS:
            return True
        if statement.type in {"compound_statement", "block"} and any(
            part.type in EXITS for part in statement.named_children
        ):
            return True
    return False
