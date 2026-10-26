# tests/test_tree_sitter_stability.py
"""tree-sitter 0.26.0 returned garbage nodes for examples/c/bank.c and then
crashed the whole process. Analysis runs in a child process here so a
native crash fails this test instead of killing the test run."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCRIPT = """
import json, sys
from src.languages.c.adapter import CAdapter
source = open(sys.argv[1], encoding="utf-8").read()
for _ in range(5):
    conditions = CAdapter().analyze(source)
print(json.dumps([[c.variable, c.operator, c.value, c.line] for c in conditions]))
"""


def test_bank_switch_is_analyzed_without_crashing():
    bank = ROOT / "examples" / "c" / "bank.c"
    done = subprocess.run(
        [sys.executable, "-c", SCRIPT, str(bank)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr[-2000:]

    lines = bank.read_text(encoding="utf-8").splitlines()
    case_lines = {
        number: int(text.strip().split()[1].rstrip(":"))
        for number, text in enumerate(lines, start=1)
        if text.strip().startswith("case ")
    }

    import json

    found = {
        line: value
        for variable, operator, value, line in json.loads(done.stdout)
        if variable == "choice" and operator == "=="
    }
    # Every case label, at its real line: no garbage nodes.
    assert found == case_lines
