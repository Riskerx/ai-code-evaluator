"""Problem contracts, independent reference answers, and reproducible test data."""

from dataclasses import dataclass
import random


@dataclass(frozen=True)
class Problem:
    key: str
    function: str
    parameters: tuple[str, ...]
    description: str


PROBLEMS = {
    "sum-even": Problem("sum-even", "sum_even", ("numbers",),
        "Sum even integers in a list. Reject non-lists, non-integers, and booleans with TypeError."),
    "palindrome": Problem("palindrome", "is_palindrome", ("text",),
        "Ignore non-alphanumeric characters and case (str.lower); return a bool. Non-strings raise TypeError."),
    "binary-search": Problem("binary-search", "binary_search", ("numbers", "target"),
        "Return the FIRST index of target in a sorted integer list, or -1. Invalid types raise TypeError; unsorted lists raise ValueError."),
}


def reference(problem: str, args: list):
    """These trusted oracles never run inside the submission process."""
    if problem == "palindrome":
        text, = args
        if type(text) is not str:
            raise TypeError("text must be a string")
        letters = "".join(char.lower() for char in text if char.isalnum())
        return letters == letters[::-1]

    numbers = args[0]
    if type(numbers) is not list or any(type(n) is not int for n in numbers):
        raise TypeError("numbers must be a list of integers, excluding bool")
    if problem == "sum-even":
        total = 0
        for number in numbers:
            if number % 2 == 0:
                total += number
        return total
    if problem != "binary-search":
        raise ValueError(f"Unknown problem: {problem}")
    target = args[1]
    if type(target) is not int:
        raise TypeError("target must be an integer, excluding bool")
    if any(a > b for a, b in zip(numbers, numbers[1:])):
        raise ValueError("numbers must be sorted")
    # A linear oracle is deliberately independent of the submitted search algorithm.
    return next((i for i, value in enumerate(numbers) if value == target), -1)


def generate_cases(problem: str, seed: int = 42, random_cases: int = 12) -> list[dict]:
    """Fixed boundaries/malformed inputs plus seeded random valid inputs."""
    if problem not in PROBLEMS:
        raise ValueError(f"Unknown problem: {problem}")
    if not 0 <= random_cases <= 100:
        raise ValueError("random_cases must be between 0 and 100")
    rng = random.Random(seed)
    if problem == "sum-even":
        fixed = [
            ("normal", [[1, 2, 3, 4]]), ("boundary", [[]]),
            ("boundary", [[0]]), ("boundary", [[-6, -3, -2]]),
            ("boundary", [[1, 3, 5]]), ("boundary", [[2, 2, 2]]),
            ("boundary", [[10**30, -(10**30), 4]]),
            ("stress", [list(range(-1000, 1001))]),
            ("malformed", [None]), ("malformed", ["123"]),
            ("malformed", [[1, "2"]]), ("malformed", [[2.0]]),
            ("malformed", [[True]]), ("malformed", [[[]]]),
        ]
        random_args = [[[rng.randint(-10000, 10000) for _ in range(rng.randint(0, 100))]]
                       for _ in range(random_cases)]
    elif problem == "palindrome":
        fixed = [
            ("normal", ["racecar"]), ("normal", ["hello"]),
            ("boundary", [""]), ("boundary", ["!"]),
            ("boundary", ["A man, a plan, a canal: Panama!"]),
            ("boundary", ["0P"]), ("boundary", ["Été"]),
            ("boundary", ["ab"]), ("boundary", ["a"]),
            ("boundary", ["12321"]), ("boundary", ["İxİ"]),
            ("stress", ["a" * 4000 + "b" + "a" * 4000]),
            ("malformed", [None]), ("malformed", [123]),
            ("malformed", [["a"]]), ("malformed", [True]),
        ]
        random_args = []
        for index in range(random_cases):
            half = "".join(rng.choice("abC019") for _ in range(rng.randint(0, 40)))
            random_args.append([half + "!" + half[::-1] if index % 2 == 0 else half + "xy"])
    else:
        fixed = [
            ("normal", [[1, 3, 5, 7], 5]), ("boundary", [[], 1]),
            ("boundary", [[7], 7]), ("boundary", [[7], 8]),
            ("boundary", [[1, 2, 2, 2, 3], 2]),
            ("boundary", [[-5, -2, 0], -5]),
            ("boundary", [[1, 2, 3], 3]), ("boundary", [[1, 3], 2]),
            ("boundary", [[-(10**30), 10**30], 10**30]),
            ("stress", [list(range(5000)), 4999]),
            ("malformed", [None, 1]), ("malformed", [["1"], 1]),
            ("malformed", [[True], 1]), ("malformed", [[1], True]),
            ("malformed", [[1], 1.0]), ("malformed", [[3, 1, 2], 2]),
        ]
        random_args = []
        for index in range(random_cases):
            numbers = sorted(rng.randint(-50, 50) for _ in range(rng.randint(0, 100)))
            target = rng.choice(numbers) if numbers and index % 2 == 0 else rng.randint(-60, 60)
            random_args.append([numbers, target])

    cases = []
    for index, (category, args) in enumerate(fixed + [("random", args) for args in random_args]):
        case = {"id": f"case-{index + 1:03}", "category": category, "args": args}
        try:
            case["expected"] = reference(problem, args)
        except (TypeError, ValueError) as exc:
            case["raises"] = type(exc).__name__
        cases.append(case)
    return cases
