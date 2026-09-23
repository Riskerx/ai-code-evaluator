"""Preflight -> test generation -> isolated Pytest run -> structured grade."""

from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

from .analysis import analyze, read_source
from . import __version__
from .generator import render_suite
from .problems import PROBLEMS, generate_cases
from .runtime import clean_environment, stop_process, validate_limits


def prepare(problem_key, submission, seed=42, random_cases=12, timeout=1.0, memory_mb=256):
    validate_limits(timeout, memory_mb)
    if problem_key not in PROBLEMS:
        raise ValueError(f"Unknown problem: {problem_key}")
    problem = PROBLEMS[problem_key]
    source = read_source(Path(submission))
    findings = analyze(source, problem.function, len(problem.parameters))
    cases = generate_cases(problem_key, seed, random_cases)
    return problem, source, findings, cases


def evaluate(problem_key: str, submission: Path, *, seed: int = 42, random_cases: int = 12,
             timeout: float = 1.0, memory_mb: int = 256) -> dict:
    started = time.perf_counter()
    problem, source, findings, cases = prepare(problem_key, submission, seed, random_cases, timeout, memory_mb)
    report = {
        "problem": problem.key, "submission": Path(submission).name, "seed": seed,
        "evaluator_version": __version__, "random_cases": random_cases,
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "status": "rejected", "score": 0.0, "passed": 0, "total": len(cases), "executed": 0,
        "findings": findings, "results": [],
        "requested_limits": {"wall_seconds_per_case": timeout, "memory_mb": memory_mb},
        "platform": sys.platform,
        "memory_limit_supported": sys.platform.startswith("linux"),
    }

    def finish():
        report["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
        return report

    if any(item["severity"] == "error" for item in findings):
        return finish()

    with tempfile.TemporaryDirectory(prefix="ai-evaluation-") as directory:
        root = Path(directory)
        suite, junit = root / "test_submission.py", root / "results.xml"
        suite.write_text(render_suite(source, problem.function, cases, timeout, memory_mb), encoding="utf-8")
        config = root / "pytest.ini"
        config.write_text("[pytest]\njunit_family = xunit1\n", encoding="utf-8")
        process = subprocess.Popen(
            [sys.executable, "-I", "-B", "-m", "pytest", str(suite), "-q", "--tb=no",
             "-c", str(config), "--noconftest", "-p", "no:cacheprovider", f"--junitxml={junit}"],
            cwd=root, env=clean_environment(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", start_new_session=sys.platform != "win32",
        )
        try:
            output, _ = process.communicate(timeout=len(cases) * (timeout + 1) + 15)
        except subprocess.TimeoutExpired:
            stop_process(process)
            process.communicate()
            report.update(status="engine_error", error="Pytest exceeded the whole-evaluation deadline")
            return finish()
        except BaseException:
            stop_process(process)
            process.communicate()
            raise
        if process.returncode not in (0, 1) or not junit.exists():
            report.update(status="engine_error", error="Pytest could not complete the evaluation",
                          engine_output=output[-4000:])
            return finish()
        try:
            results = []
            for node in ET.parse(junit).getroot().iter("testcase"):
                prop = node.find("./properties/property[@name='evaluation']")
                if prop is None or node.find("error") is not None or node.find("skipped") is not None:
                    raise ValueError("A test did not produce a valid result")
                result = json.loads(prop.attrib["value"])
                pytest_passed = node.find("failure") is None
                if pytest_passed != (result["status"] == "passed"):
                    raise ValueError("Pytest verdict does not match case result")
                results.append(result)
            if Counter(item["id"] for item in results) != Counter(case["id"] for case in cases):
                raise ValueError("Pytest results do not cover every generated case exactly once")
        except (ET.ParseError, OSError, ValueError, KeyError, TypeError) as exc:
            report.update(status="engine_error", error=f"Invalid Pytest results: {exc}")
            return finish()

    passed = sum(item["status"] == "passed" for item in results)
    report.update(status="passed" if passed == len(cases) else "failed", passed=passed,
                  score=round(100 * passed / len(cases), 2), executed=len(results), results=results)
    if any(item["status"] == "environment_error" for item in results):
        report.update(status="engine_error", error="Worker resource limits could not be configured")
    report["categories"] = {
        category: {"passed": sum(item["status"] == "passed" for item in results if item["category"] == category),
                   "total": sum(item["category"] == category for item in results)}
        for category in sorted({case["category"] for case in cases})
    }
    return finish()
