"""Run one generated test case in its own child process.

The parent (test_executor.py) starts this script, sends the program and the
test inputs as JSON on stdin, and reads one JSON result from stdout. Running
the program in a separate process means a timed-out program can actually be
killed, and nothing it does (redirecting stdout, replacing input()) can leak
into the API server.

This file must stay standard-library only: it runs with `python -I`.
"""

import builtins
import io
import json
import sys

MAX_OUTPUT_CHARS = 100_000
TRUNCATION_NOTE = "\n...[output truncated]"


class _CappedOutput(io.TextIOBase):
    """Collect program output, keeping at most MAX_OUTPUT_CHARS."""

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._size = 0
        self._truncated = False

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        room = MAX_OUTPUT_CHARS - self._size
        if room > 0:
            kept = text[:room]
            self._parts.append(kept)
            self._size += len(kept)
            if len(kept) < len(text):
                self._truncated = True
        else:
            self._truncated = True
        return len(text)

    def getvalue(self) -> str:
        text = "".join(self._parts)
        return text + TRUNCATION_NOTE if self._truncated else text


def main() -> None:
    real_stdout = sys.stdout
    request = json.loads(sys.stdin.read())
    source = request["source"]
    values = request["inputs"]

    output = _CappedOutput()
    # "answers" lists what each input() call returns, in order; without
    # it the values are handed out in dict order.
    answers = request.get("answers")
    if answers is None:
        answers = [str(value) for value in values.values()]
    input_values = iter(answers)

    def mock_input(prompt=""):
        output.write(str(prompt))
        try:
            return next(input_values)
        except StopIteration:
            raise EOFError("No more generated input values available")

    builtins.input = mock_input

    namespace = {"__name__": "__main__"}
    namespace.update(values)

    success = False
    error = None
    sys.stdout = output

    try:
        exec(compile(source, "<user_program>", "exec"), namespace)
        success = True
    except SystemExit as exit_request:
        if exit_request.code in (None, 0):
            success = True
        else:
            error = f"SystemExit: {exit_request.code}"
    except BaseException as failure:
        error = f"{type(failure).__name__}: {failure}"
    finally:
        sys.stdout = real_stdout

    real_stdout.write(
        json.dumps(
            {
                "success": success,
                "error": error,
                "output": output.getvalue(),
            }
        )
    )
    real_stdout.flush()


if __name__ == "__main__":
    main()