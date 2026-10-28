"""Arithmetic sandbox."""

import pytest

from smaip.errors import SandboxError
from smaip.gateway.sandbox import evaluate


def test_arithmetic_addition():
    assert evaluate("128 + 37") == 165


def test_arithmetic_precedence_and_parentheses():
    assert evaluate("(2 + 3) * 4") == 20
    assert evaluate("8 / 2") == 4


def test_rejects_import():
    with pytest.raises(SandboxError):
        evaluate("__import__('os')")


def test_rejects_names_and_calls():
    with pytest.raises(SandboxError):
        evaluate("abs(1)")


def test_rejects_pow():
    with pytest.raises(SandboxError):
        evaluate("2**3")


def test_division_by_zero():
    with pytest.raises(SandboxError, match="division by zero"):
        evaluate("1/0")
