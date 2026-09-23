import pytest

from ai_evaluator.runtime import run_case, validate_limits


def case(expected=0, **kwargs):
    return {"id": "unit", "category": "boundary", "args": [[]], "expected": expected, **kwargs}


def test_boolean_does_not_pass_as_integer():
    result = run_case("def sum_even(numbers):\n return True", "sum_even", case(1))
    assert result["status"] == "failed"


def test_prints_do_not_corrupt_protocol():
    result = run_case("def sum_even(numbers):\n print('debug info')\n return 0", "sum_even", case())
    assert result["status"] == "passed"


def test_infinite_print_loop_is_stopped():
    result = run_case("def sum_even(numbers):\n while True:\n  print('noise')", "sum_even", case(), timeout=0.15)
    assert result["status"] == "timeout"
    assert result["duration_ms"] < 3000


def test_expected_exception_is_checked_exactly():
    result = run_case("def sum_even(numbers):\n raise ValueError('wrong')", "sum_even", case(raises="TypeError"))
    assert result["status"] == "failed"
    result = run_case("def sum_even(numbers):\n raise TypeError('right')", "sum_even", case(raises="TypeError"))
    assert result["status"] == "passed"


def test_runtime_error_is_reported():
    result = run_case("def sum_even(numbers):\n return 1 / 0", "sum_even", case())
    assert result["status"] == "runtime_error"
    assert result["message"] == "Unexpected ZeroDivisionError"


def test_cases_do_not_share_mutated_arguments():
    original = case(1)
    source = "def sum_even(numbers):\n numbers.append(9)\n return len(numbers)"
    assert run_case(source, "sum_even", original)["status"] == "passed"
    assert run_case(source, "sum_even", original)["status"] == "passed"
    assert original["args"] == [[]]


@pytest.mark.parametrize("value", ["[1, 2]", "'x' * 10001", "2 ** 10000", "float('nan')"])
def test_unsupported_or_large_returns_fail(value):
    assert run_case(f"def sum_even(numbers):\n return {value}", "sum_even", case())["status"] == "failed"


@pytest.mark.parametrize("timeout,memory", [(0, 256), (float("nan"), 256), (float("inf"), 256), (1, 1)])
def test_invalid_limits_are_rejected(timeout, memory):
    with pytest.raises(ValueError):
        validate_limits(timeout, memory)

