"""A tiny calculator module — the thing this PR is 'reviewing'.

Has a genuine lint issue: an unused import. Real pyflakes will flag this,
not a scripted pass/fail.
"""
import math


def add(a: float, b: float) -> float:
    return a + b


def subtract(a: float, b: float) -> float:
    return a - b


def sqrt(x: float) -> float:
    return math.sqrt(x)

