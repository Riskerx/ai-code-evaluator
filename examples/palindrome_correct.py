def is_palindrome(text):
    if type(text) is not str:
        raise TypeError("Expected a string")
    normalized = "".join(character.lower() for character in text if character.isalnum())
    left, right = 0, len(normalized) - 1
    while left < right:
        if normalized[left] != normalized[right]:
            return False
        left += 1
        right -= 1
    return True

