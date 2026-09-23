"""Generate real, directly runnable Pytest source from a known problem contract."""

import json


def render_suite(source: str, function: str, cases: list[dict], timeout: float,
                 memory_mb: int) -> str:
    return f'''"""Generated evaluator tests. Inputs and expected answers are visible in this file.
Submission source is a snapshot: regenerate after editing the original submission.
"""
import json
import pytest
from ai_evaluator.runtime import run_case

SOURCE = {source!r}
FUNCTION = {function!r}
CASES = json.loads({json.dumps(cases, ensure_ascii=True)!r})


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_submission(case, record_property):
    result = run_case(SOURCE, FUNCTION, case, timeout={timeout!r}, memory_mb={memory_mb!r})
    record_property("evaluation", json.dumps(result))
    assert result["status"] == "passed", result["message"]
'''

