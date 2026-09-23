import pytest

from ai_evaluator.analysis import analyze


@pytest.mark.parametrize("source,code", [
    ("def sum_even(:\n pass", "syntax"),
    ("def sum_even(numbers):\n break", "syntax"),
    ("def other(numbers):\n return 0", "entrypoint"),
    ("def sum_even(a, b):\n return 0", "signature"),
    ("def sum_even(numbers):\n import os\n return 0", "import"),
    ("def sum_even(numbers):\n fn = open\n return 0", "restricted-name"),
    ("def sum_even(numbers):\n return numbers.__class__", "restricted-attribute"),
    ("print('should not run')\ndef sum_even(numbers):\n return 0", "top-level"),
    ("@print\ndef sum_even(numbers):\n return 0", "function-definition"),
    ("def sum_even(numbers=list()):\n return 0", "default-expression"),
    ("def sum_even(numbers):\n yield 1", "unsupported"),
    ("def sum_even(a):\n return 1\ndef sum_even(b):\n return 2", "entrypoint"),
])
def test_rejects_invalid_contracts_without_execution(source, code):
    assert any(item["severity"] == "error" and item["code"] == code for item in analyze(source, "sum_even", 1))


def test_patterns_are_warnings_not_claims_of_incorrectness():
    findings = analyze("def sum_even(numbers):\n while True:\n  break\n return sum_even(numbers)", "sum_even", 1)
    assert {item["code"] for item in findings} == {"constant-loop", "recursion"}
    assert all(item["severity"] == "warning" for item in findings)


@pytest.mark.parametrize("body", [
    " for a in numbers:\n  for b in numbers:\n   pass\n return 0",
    " return sum(a * b for a in numbers for b in numbers)",
])
def test_warns_on_nested_loops_and_comprehensions(body):
    assert any(item["code"] == "nested-loop" for item in analyze("def sum_even(numbers):\n" + body, "sum_even", 1))


def test_correct_examples_have_no_ast_errors(examples):
    for filename, function, arity in [
        ("sum_even_correct.py", "sum_even", 1),
        ("palindrome_correct.py", "is_palindrome", 1),
        ("binary_search_correct.py", "binary_search", 2),
    ]:
        assert not analyze((examples / filename).read_text(), function, arity)


def test_deep_expression_is_rejected_without_crashing():
    source = "def sum_even(numbers):\n return " + "+".join(["1"] * 1500)
    assert any(item["severity"] == "error" for item in analyze(source, "sum_even", 1))
