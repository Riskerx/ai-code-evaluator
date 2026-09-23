import pytest

from ai_evaluator.problems import PROBLEMS, generate_cases, reference


@pytest.mark.parametrize("problem", PROBLEMS)
def test_generation_is_repeatable_and_varied(problem):
    first = generate_cases(problem, seed=42)
    assert first == generate_cases(problem, seed=42)
    assert first != generate_cases(problem, seed=43)
    assert len({case["id"] for case in first}) == len(first)
    assert {case["category"] for case in first} == {"normal", "boundary", "malformed", "stress", "random"}
    assert all(("expected" in case) != ("raises" in case) for case in first)


@pytest.mark.parametrize("problem,args,expected", [
    ("sum-even", [[-4, 0, 2, 3]], -2),
    ("sum-even", [[]], 0),
    ("palindrome", ["A man, a plan, a canal: Panama!"], True),
    ("palindrome", ["Été"], True),
    ("palindrome", ["İxİ"], False),  # lower() expands this character into two code points.
    ("binary-search", [[1, 2, 2, 2, 3], 2], 1),
    ("binary-search", [[], 1], -1),
])
def test_oracle_against_handwritten_answers(problem, args, expected):
    assert reference(problem, args) == expected


@pytest.mark.parametrize("problem,args,error", [
    ("sum-even", [[True]], TypeError),
    ("sum-even", [[2.0]], TypeError),
    ("palindrome", [None], TypeError),
    ("binary-search", [[1], True], TypeError),
    ("binary-search", [[2, 1], 1], ValueError),
])
def test_malformed_inputs_have_explicit_contracts(problem, args, error):
    with pytest.raises(error):
        reference(problem, args)

