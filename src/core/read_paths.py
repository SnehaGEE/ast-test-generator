"""Which input reads a run makes, depending on the path its values take.

A language builder turns a program into a small read map:

    Read(name, kind)            one input read (name None if unassigned)
    Branch(var, op, value, ...)  if/else on `var op number`
    Switch(var, cases)           switch/match on `var`

For one test, resolve() follows the branches its generated values decide
and returns the reads on that path, so each read gets the right answer.
A branch that cannot be decided (unknown variable, non-numeric value)
keeps the reads of every side, in source order.
"""

from dataclasses import dataclass, field
from typing import Any

# Placeholder answer for a read whose variable has no generated value.
FILLERS = {"int": "1", "float": "1.0", "str": "test", "bool": "true"}


@dataclass
class Read:
    """One input read.

    token: a Scanner-style token read (nextInt, next) that leaves the rest
    of its line unread. rest_of_line: a Scanner nextLine, which after a
    token read returns that remainder and needs no answer of its own.
    """

    name: str | None
    kind: str = "int"
    token: bool = False
    rest_of_line: bool = False


@dataclass
class Branch:
    variable: str
    operator: str
    value: Any
    then: list = field(default_factory=list)
    otherwise: list = field(default_factory=list)


@dataclass
class Case:
    values: list[Any] | None  # None marks default / `case _`
    body: list = field(default_factory=list)
    falls_through: bool = False


@dataclass
class Switch:
    variable: str
    cases: list[Case] = field(default_factory=list)


_COMPARE = {
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


def _number(inputs: dict[str, Any], name: str):
    value = inputs.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def resolve(items: list, inputs: dict[str, Any]) -> list[Read]:
    """The reads one run makes, following branches its values decide."""
    reads: list[Read] = []

    for item in items:
        if isinstance(item, Read):
            reads.append(item)

        elif isinstance(item, Branch):
            value = _number(inputs, item.variable)
            compare = _COMPARE.get(item.operator)
            if value is None or compare is None:
                reads += resolve(item.then, inputs)
                reads += resolve(item.otherwise, inputs)
            elif compare(value, item.value):
                reads += resolve(item.then, inputs)
            else:
                reads += resolve(item.otherwise, inputs)

        elif isinstance(item, Switch):
            value = _number(inputs, item.variable)
            if value is None:
                for case in item.cases:
                    reads += resolve(case.body, inputs)
                continue

            start = next(
                (
                    index
                    for index, case in enumerate(item.cases)
                    if case.values is not None and value in case.values
                ),
                None,
            )
            if start is None:
                start = next(
                    (
                        index
                        for index, case in enumerate(item.cases)
                        if case.values is None
                    ),
                    None,
                )
            if start is None:
                continue

            for case in item.cases[start:]:
                reads += resolve(case.body, inputs)
                if not case.falls_through:
                    break

    return reads


def _all_names(items: list) -> set[str]:
    """Every variable read anywhere in a read map, on any path."""
    names: set[str] = set()
    for item in items:
        if isinstance(item, Read):
            if item.name is not None:
                names.add(item.name)
        elif isinstance(item, Branch):
            names |= _all_names(item.then) | _all_names(item.otherwise)
        elif isinstance(item, Switch):
            for case in item.cases:
                names |= _all_names(case.body)
    return names


def answers(items: list, inputs: dict[str, Any]) -> list[str]:
    """One answer per read on this run's path, then never-read values.

    A read with a generated value gets it; any other read gets a
    placeholder of its kind. Generated values for variables the program
    is never seen reading follow, as a fallback for reads that were not
    recognised. Values read only on other paths are left out: a menu loop
    would otherwise take them as its next choice.
    """
    result: list[str] = []
    read_anywhere = _all_names(items)
    mid_line = False  # a token read left the rest of its line unread

    for read in resolve(items, inputs):
        if read.rest_of_line and mid_line:
            mid_line = False
            continue
        mid_line = read.token

        if read.name is not None and read.name in inputs:
            result.append(str(inputs[read.name]))
        else:
            result.append(FILLERS.get(read.kind, FILLERS["int"]))

    result += [
        str(value) for name, value in inputs.items() if name not in read_anywhere
    ]
    return result


def name_single_read(items: list, name: str | None) -> list:
    """Give `name` to the one unnamed read in items, for `x = helper()`."""
    if name is None:
        return items
    unnamed = [item for item in items if isinstance(item, Read) and item.name is None]
    if len(unnamed) == 1 and len(items) == 1:
        unnamed[0].name = name
    return items
