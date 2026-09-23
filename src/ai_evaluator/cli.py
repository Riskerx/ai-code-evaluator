"""The command-line interface; run `python -m ai_evaluator --help`."""

import argparse
import json
from pathlib import Path

from .analysis import analyze, read_source
from .evaluator import evaluate, prepare
from .generator import render_suite
from .problems import PROBLEMS


def write_output(path: Path, content: str, protected: Path):
    if path.resolve() == protected.resolve():
        raise ValueError("Output path must not overwrite the submission")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate small Python submissions and generate Pytest tests.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="List problem contracts")
    for name in ("analyze", "evaluate", "generate"):
        command = commands.add_parser(name)
        command.add_argument("problem", choices=PROBLEMS)
        command.add_argument("submission", type=Path)
        if name != "analyze":
            command.add_argument("--seed", type=int, default=42)
            command.add_argument("--random-cases", type=int, default=12)
            command.add_argument("--timeout", type=float, default=1.0, help="Seconds per case, including process startup")
            command.add_argument("--memory-mb", type=int, default=256, help="Worker address-space cap; Linux only")
        if name == "evaluate":
            command.add_argument("--report", type=Path, help="Write a JSON grading report")
        if name == "generate":
            command.add_argument("--output", type=Path, required=True, help="Output test_*.py file (reveals test cases)")
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            for problem in PROBLEMS.values():
                print(f"{problem.key}: {problem.function}({', '.join(problem.parameters)})")
                print(f"  {problem.description}")
            return 0
        problem = PROBLEMS[args.problem]
        if args.command == "analyze":
            findings = analyze(read_source(args.submission), problem.function, len(problem.parameters))
            print_findings(findings)
            return int(any(item["severity"] == "error" for item in findings))
        options = dict(seed=args.seed, random_cases=args.random_cases,
                       timeout=args.timeout, memory_mb=args.memory_mb)
        if args.command == "generate":
            problem, source, findings, cases = prepare(args.problem, args.submission, **options)
            print_findings(findings)
            if any(item["severity"] == "error" for item in findings):
                return 1
            if args.output.suffix != ".py" or not args.output.name.startswith("test_"):
                raise ValueError("Generated test filenames must start with test_ and end in .py")
            write_output(args.output, render_suite(source, problem.function, cases, args.timeout, args.memory_mb), args.submission)
            print(f"Generated {len(cases)} cases: {args.output}")
            print("This file exposes inputs and expected answers, and contains a snapshot of the submission.")
            return 0
        if args.report and args.report.resolve() == args.submission.resolve():
            raise ValueError("Report path must not overwrite the submission")
        report = evaluate(args.problem, args.submission, **options)
        print(f"{report['status'].upper()} | {report['score']:.2f}/100 | {report['passed']}/{report['total']} tests passed")
        print(f"Executed: {report['executed']} | Duration: {report['duration_ms']:.0f} ms | Seed: {report['seed']}")
        print_findings(report["findings"])
        if not report["memory_limit_supported"]:
            print("Platform: memory cap unavailable here; per-case wall timeout is active.")
        for category, counts in report.get("categories", {}).items():
            print(f"  {category}: {counts['passed']}/{counts['total']}")
        failures = [item for item in report["results"] if item["status"] != "passed"]
        for item in failures[:8]:
            print(f"  {item['id']} [{item['status']}]: {item['message']}")
        if len(failures) > 8:
            print(f"  ... and {len(failures) - 8} more failures (see JSON report)")
        if "error" in report:
            print(f"Error: {report['error']}")
        if args.report:
            write_output(args.report, json.dumps(report, indent=2) + "\n", args.submission)
            print(f"Report: {args.report}")
        return 2 if report["status"] == "engine_error" else int(report["status"] != "passed")
    except (OSError, ValueError, UnicodeError) as exc:
        print(f"Error: {exc}")
        return 2


def print_findings(findings):
    if not findings:
        print("AST: no findings (not a proof of correctness).")
    for item in findings:
        location = f"line {item['line']}" if item["line"] else "module"
        print(f"  {item['severity'].upper()} {location} [{item['code']}]: {item['message']}")

