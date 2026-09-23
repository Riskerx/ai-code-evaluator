import json
import subprocess
import sys

import pytest

from ai_evaluator.cli import main
from ai_evaluator.evaluator import evaluate


@pytest.mark.parametrize("problem,filename", [
    ("sum-even", "sum_even_correct.py"),
    ("palindrome", "palindrome_correct.py"),
    ("binary-search", "binary_search_correct.py"),
])
def test_correct_submissions_pass_real_pytest(problem, filename, examples):
    report = evaluate(problem, examples / filename, random_cases=2)
    assert report["status"] == "passed", report
    assert report["score"] == 100
    assert report["executed"] == report["total"]
    assert all(item["limits"].get("memory_mb") for item in report["results"]) == sys.platform.startswith("linux")
    assert all("args" not in item and "expected" not in item for item in report["results"])


@pytest.mark.parametrize("problem,filename", [
    ("sum-even", "sum_even_buggy.py"),
    ("binary-search", "binary_search_buggy.py"),
])
def test_plausible_but_wrong_submissions_lose_points(problem, filename, examples):
    report = evaluate(problem, examples / filename, random_cases=2)
    assert report["status"] == "failed"
    assert 0 < report["score"] < 100
    assert report["categories"]["boundary"]["passed"] < report["categories"]["boundary"]["total"]


def test_rejected_source_never_executes(tmp_path):
    marker = tmp_path / "marker.txt"
    source = tmp_path / "submission.py"
    source.write_text(f"open({str(marker)!r}, 'w').write('bad')\ndef sum_even(numbers):\n return 0")
    report = evaluate("sum-even", source)
    assert report["status"] == "rejected"
    assert report["executed"] == 0
    assert not marker.exists()


def test_timeouts_are_counted_and_grading_continues(examples):
    report = evaluate("sum-even", examples / "sum_even_infinite.py", random_cases=0, timeout=0.1)
    assert report["status"] == "failed"
    assert report["executed"] == report["total"]
    assert report["score"] == 0
    assert all(item["status"] == "timeout" for item in report["results"])


def test_generated_file_runs_with_pytest(examples, tmp_path):
    output = tmp_path / "test_generated.py"
    assert main(["generate", "sum-even", str(examples / "sum_even_correct.py"),
                 "--output", str(output), "--random-cases", "0"]) == 0
    process = subprocess.run([sys.executable, "-m", "pytest", str(output), "-q", "--noconftest"],
                             capture_output=True, text=True, timeout=60)
    assert process.returncode == 0, process.stdout + process.stderr
    assert "14 passed" in process.stdout


def test_cli_writes_json_report(examples, tmp_path):
    output = tmp_path / "report.json"
    assert main(["evaluate", "sum-even", str(examples / "sum_even_correct.py"),
                 "--report", str(output), "--random-cases", "0"]) == 0
    assert json.loads(output.read_text())["score"] == 100


def test_output_cannot_replace_submission(examples, tmp_path):
    path = tmp_path / "test_submission.py"
    original = (examples / "sum_even_correct.py").read_text()
    path.write_text(original)
    assert main(["generate", "sum-even", str(path), "--output", str(path)]) == 2
    assert main(["evaluate", "sum-even", str(path), "--report", str(path)]) == 2
    assert path.read_text() == original

