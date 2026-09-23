"""Run one input in a fresh child and compare its answer in the trusted parent."""

import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

WORKER = Path(__file__).with_name("worker.py")


def validate_limits(timeout: float, memory_mb: int):
    if not math.isfinite(timeout) or not 0.05 <= timeout <= 30:
        raise ValueError("timeout must be between 0.05 and 30 seconds")
    if not 64 <= memory_mb <= 2048:
        raise ValueError("memory_mb must be between 64 and 2048")


def clean_environment() -> dict:
    # Do not pass API keys, cloud credentials, PYTHONPATH, or user plugin settings.
    environment = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR") if key in os.environ}
    environment.update({"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONIOENCODING": "utf-8"})
    return environment


def stop_process(process):
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        process.kill()


def run_case(source: str, function: str, case: dict, timeout: float = 1.0,
             memory_mb: int = 256) -> dict:
    """Internal API: source must have passed analysis.analyze before calling."""
    validate_limits(timeout, memory_mb)
    started = time.perf_counter()
    result = {"id": case["id"], "category": case["category"], "status": "runtime_error",
              "message": "Worker did not return a valid result", "limits": {}}
    # Expected answers and other test cases are NOT sent to the child.
    request = {"source": source, "function": function, "args": case["args"],
               "timeout": timeout, "memory_mb": memory_mb}
    payload = json.dumps(request)
    with tempfile.TemporaryDirectory(prefix="ai-case-") as directory:
        process = subprocess.Popen(
            [sys.executable, "-I", "-B", "-S", str(WORKER)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", cwd=directory, env=clean_environment(),
            start_new_session=os.name == "posix",
        )
        try:
            output, _ = process.communicate(payload, timeout=timeout)
        except subprocess.TimeoutExpired:
            stop_process(process)
            process.communicate()
            result.update(status="timeout", message=f"Exceeded {timeout:g}s wall-clock limit")
        except BaseException:
            stop_process(process)
            process.communicate()
            raise
        else:
            if process.returncode != 0:
                result["message"] = f"Worker exited with code {process.returncode}; it may have hit a resource limit"
            else:
                try:
                    observed = json.loads(output)
                    result["limits"] = observed.get("limits", {})
                    kind = observed["kind"]
                    if kind == "environment_error":
                        result.update(status="environment_error", message=observed["message"])
                    elif kind == "memory_error":
                        result.update(status="memory_error", message="Submission exhausted available memory")
                    elif "raises" in case:
                        passed = kind == "raised" and observed.get("exception") == case["raises"]
                        result.update(status="passed" if passed else "failed",
                                      message="Expected exception raised" if passed else "Expected exception type was not raised")
                    elif kind == "returned":
                        value = observed["value"]
                        passed = type(value) is type(case["expected"]) and value == case["expected"]
                        result.update(status="passed" if passed else "failed",
                                      message="Correct value and type" if passed else "Returned an incorrect value or type")
                    elif kind == "raised":
                        result.update(status="runtime_error", message=f"Unexpected {observed['exception']}")
                    else:
                        result.update(status="failed", message="Return value is unsupported or exceeds the output limit")
                except (ValueError, KeyError, TypeError, AttributeError):
                    result.update(status="runtime_error", message="Invalid worker response")
    result["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return result
