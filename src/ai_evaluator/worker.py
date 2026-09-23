"""One-use submission process. Called by runtime.py, never imported for grading."""

import __future__
import builtins
import contextlib
import json
import math
import os
import sys


def apply_limits(timeout: float, memory_mb: int) -> dict:
    applied = {"cpu_seconds": None, "memory_mb": None, "core_dump_disabled": False}
    try:
        import resource
    except ImportError:
        return applied  # Windows: parent still enforces the wall-clock timeout.

    def cap(kind, requested):
        _, inherited_hard = resource.getrlimit(kind)
        value = requested if inherited_hard == resource.RLIM_INFINITY else min(requested, inherited_hard)
        resource.setrlimit(kind, (value, value))
        return value

    if hasattr(resource, "RLIMIT_CPU"):
        applied["cpu_seconds"] = cap(resource.RLIMIT_CPU, max(1, math.ceil(timeout) + 1))
    if hasattr(resource, "RLIMIT_CORE"):
        cap(resource.RLIMIT_CORE, 0)
        applied["core_dump_disabled"] = True
    if sys.platform.startswith("linux"):
        applied["memory_mb"] = cap(resource.RLIMIT_AS, memory_mb * 1024 * 1024) / (1024 * 1024)
    return applied


def main():
    request = json.loads(sys.stdin.read())
    try:
        limits = apply_limits(request["timeout"], request["memory_mb"])
    except (OSError, ValueError) as exc:
        print(json.dumps({"kind": "environment_error", "message": f"Cannot apply limits: {type(exc).__name__}"}))
        return

    names = (
        "abs all any bool dict divmod enumerate filter float frozenset int isinstance "
        "issubclass iter len list map max min next pow print range repr reversed round "
        "set slice sorted str sum tuple type zip Exception ValueError TypeError IndexError "
        "KeyError ZeroDivisionError RuntimeError AssertionError StopIteration"
    ).split()
    namespace = {"__builtins__": {name: getattr(builtins, name) for name in names},
                 "__name__": "submission"}
    try:
        # Output from the submission is intentionally discarded, even in a printing loop.
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            code = compile(request["source"], "<submission>", "exec",
                           flags=__future__.annotations.compiler_flag, dont_inherit=True)
            exec(code, namespace)
            value = namespace[request["function"]](*request["args"])
        if (type(value) not in (int, bool, float, str, type(None))
                or (type(value) is str and len(value) > 10000)
                or (type(value) is int and value.bit_length() > 4096)
                or (type(value) is float and not math.isfinite(value))):
            result = {"kind": "invalid_return"}
        else:
            result = {"kind": "returned", "value": value}
    except MemoryError:
        result = {"kind": "memory_error"}
    except BaseException as exc:
        # Return just the type, never user-controlled exception messages or tracebacks.
        result = {"kind": "raised", "exception": type(exc).__name__}
    result["limits"] = limits
    print(json.dumps(result, allow_nan=False))


if __name__ == "__main__":
    main()

