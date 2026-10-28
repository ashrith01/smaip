"""Arithmetic-only expression sandbox.

Names, calls, attributes, and imports are rejected before evaluation.
The evaluator never opens a socket and never calls the builtin eval.
"""

import ast
import math
import operator
import re

from smaip.errors import SandboxError

_ALLOWED_CHARS = re.compile(r"[0-9+\-*/%.()\s]+")
_MAX_ABS = 10**12
_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
}


def evaluate(expression: str) -> int | float:
    if not isinstance(expression, str) or not expression.strip():
        raise SandboxError("expression rejected")
    if len(expression) > 100 or _ALLOWED_CHARS.fullmatch(expression) is None:
        raise SandboxError("expression rejected")
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise SandboxError("expression rejected") from exc
    value = _eval(tree.body)
    if isinstance(value, float) and not math.isfinite(value):
        raise SandboxError("expression rejected")
    if abs(value) > _MAX_ABS:
        raise SandboxError("expression rejected")
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _eval(node: ast.AST) -> int | float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise SandboxError("expression rejected")
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _eval(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        left = _eval(node.left)
        right = _eval(node.right)
        if type(node.op) in {ast.Div, ast.Mod} and right == 0:
            raise SandboxError("division by zero")
        return _BINOPS[type(node.op)](left, right)
    raise SandboxError("expression rejected")
