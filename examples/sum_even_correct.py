def sum_even(numbers):
    if type(numbers) is not list or any(type(number) is not int for number in numbers):
        raise TypeError("Expected a list of integers; bool is not accepted")
    return sum(number for number in numbers if number % 2 == 0)

