"""Shared helpers for finding how Java and C programs read their inputs."""

from dataclasses import dataclass, field

_ASSIGNMENT_NODES = {
    "init_declarator": "declarator",      # C: int a = ...
    "variable_declarator": "name",        # Java: int a = ...
    "assignment_expression": "left",      # both: a = ...
}

_STOP_NODES = {"compound_statement", "block", "translation_unit", "program"}


@dataclass
class InputPlan:
    """Where a program reads each variable from.

    read_order: variables read from standard input, in source order.
    kinds: what each stdin read expects: "int", "float", "str" or "bool".
    positions: command-line index per variable (argv[1] -> 1, args[0] -> 0).
    """

    read_order: list[str] = field(default_factory=list)
    kinds: dict[str, str] = field(default_factory=dict)
    positions: dict[str, int] = field(default_factory=dict)


def node_text(node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8")


def assigned_name(node, source_bytes: bytes) -> str | None:
    """Name of the variable that the expression containing node is stored in.

    For `int age = atoi(argv[1]);` and the argv[1] node, returns "age".
    """
    current = node.parent

    while current is not None and current.type not in _STOP_NODES:
        field_name = _ASSIGNMENT_NODES.get(current.type)

        if field_name is not None:
            target = current.child_by_field_name(field_name)
            if target is not None and target.type == "identifier":
                return node_text(target, source_bytes)
            return None

        current = current.parent

    return None


def stdin_text(values) -> str:
    """One value per line, as typed at a terminal."""
    return "".join(f"{value}\n" for value in values)
