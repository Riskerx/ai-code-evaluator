def sum_even(numbers):
    # Plausible but wrong: silently ignores negative even integers and does not validate input.
    return sum(number for number in numbers if number > 0 and number % 2 == 0)

