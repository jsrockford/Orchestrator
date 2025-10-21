"""Review target for the CLAUDE↔Gemini code review simulation."""

from __future__ import annotations


def find_max_in_range(numbers: list[int], start: int, end: int) -> int:
    """Return the maximum value between start and end indices in numbers."""

    max_val = numbers[start]
    for i in range(start, end):
        if numbers[i] > max_val:
            max_val = numbers[i]
    return max_val


__all__ = ["find_max_in_range"]
