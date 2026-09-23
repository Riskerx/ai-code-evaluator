def binary_search(numbers, target):
    if type(numbers) is not list or any(type(number) is not int for number in numbers):
        raise TypeError("Expected a list of integers")
    if type(target) is not int:
        raise TypeError("Expected an integer target")
    if any(numbers[i] > numbers[i + 1] for i in range(len(numbers) - 1)):
        raise ValueError("Input must be sorted")
    left, right = 0, len(numbers)
    while left < right:
        middle = (left + right) // 2
        if numbers[middle] < target:
            left = middle + 1
        else:
            right = middle
    if left < len(numbers) and numbers[left] == target:
        return left
    return -1

