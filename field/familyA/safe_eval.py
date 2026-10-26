"""Sandboxed evaluation of model-produced rule expressions.

Model output is untrusted input. Nothing in this module calls ``eval`` or
``exec``: an expression is parsed with :mod:`ast` and run by a small recursive
evaluator that only accepts an explicit whitelist of node types, names, calls
and operators, with a step budget and a size bound.

The grammar a model is expected to produce::

    <expr>  := <const> | <name> | <expr> <op> <expr> | f(<expr>, ...)
             | <expr> if <expr> else <expr> | not <expr>
    <name>  := a | b | n

``a`` and ``b`` are the two inputs of a task instance; ``n`` is an optional
index, provided so that a model may write something like ``a % 2 if n == 0 else b``.
"""

from __future__ import annotations

import ast
from typing import Any, Callable, Dict, List, Sequence, Tuple

MAX_STEPS = 200_000
MAX_POW_EXPONENT = 64
MAX_POW_VALUE = 10 ** 12
MAX_EXPR_LEN = 400
MAX_SEQUENCE_LEN = 32

ALLOWED_NAMES = frozenset({"a", "b", "n"})
ALLOWED_CALLS = frozenset({"abs", "min", "max", "int", "round", "sum", "len"})

_BIN_OPS = {
    ast.Add: lambda x, y: x + y,
    ast.Sub: lambda x, y: x - y,
    ast.Mult: lambda x, y: x * y,
    ast.Div: lambda x, y: x / y,
    ast.FloorDiv: lambda x, y: x // y,
    ast.Mod: lambda x, y: x % y,
}

_CMP_OPS = {
    ast.Eq: lambda x, y: x == y,
    ast.NotEq: lambda x, y: x != y,
    ast.Lt: lambda x, y: x < y,
    ast.LtE: lambda x, y: x <= y,
    ast.Gt: lambda x, y: x > y,
    ast.GtE: lambda x, y: x >= y,
}

_CHAINED_CMP_OPS = tuple(_CMP_OPS)


class RuleError(Exception):
    """Raised when a rule expression is malformed or exceeds a sandbox bound."""


def _truthy(value: Any) -> bool:
    return bool(value)


def _eval(node: ast.AST, env: Dict[str, Any], state: Dict[str, int]) -> Any:
    state["steps"] += 1
    if state["steps"] > MAX_STEPS:
        raise RuleError("step budget exceeded")

    if isinstance(node, ast.Expression):
        return _eval(node.body, env, state)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (bool, int, float)):
            return node.value
        raise RuleError(f"unsupported constant: {node.value!r}")

    if isinstance(node, ast.Name):
        if node.id not in ALLOWED_NAMES:
            raise RuleError(f"unknown name: {node.id}")
        return env[node.id]

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        left = _eval(node.left, env, state)
        right = _eval(node.right, env, state)
        if op_type is ast.Pow:
            if not isinstance(right, (int, float)) or abs(right) > MAX_POW_EXPONENT:
                raise RuleError("exponent out of range")
            result = left ** right
            if abs(result) > MAX_POW_VALUE:
                raise RuleError("power result out of range")
            return result
        if op_type not in _BIN_OPS:
            raise RuleError(f"unsupported operator: {op_type.__name__}")
        try:
            return _BIN_OPS[op_type](left, right)
        except ZeroDivisionError as exc:
            raise RuleError("division by zero") from exc

    if isinstance(node, ast.UnaryOp):
        operand = _eval(node.operand, env, state)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.Not):
            return not operand
        raise RuleError(f"unsupported unary operator: {type(node.op).__name__}")

    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            for value in node.values:
                if not _truthy(_eval(value, env, state)):
                    return False
            return True
        for value in node.values:
            if _truthy(_eval(value, env, state)):
                return True
        return False

    if isinstance(node, ast.Compare):
        left = _eval(node.left, env, state)
        for op, comparator in zip(node.ops, node.comparators):
            op_type = type(op)
            if op_type not in _CMP_OPS:
                raise RuleError(f"unsupported comparison: {op_type.__name__}")
            right = _eval(comparator, env, state)
            if not _CMP_OPS[op_type](left, right):
                return False
            left = right
        return True

    if isinstance(node, ast.IfExp):
        if _truthy(_eval(node.test, env, state)):
            return _eval(node.body, env, state)
        return _eval(node.orelse, env, state)

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_CALLS:
            raise RuleError("call to a function that is not allowed")
        if node.keywords:
            raise RuleError("keyword arguments are not allowed")
        args = [_eval(arg, env, state) for arg in node.args]
        if node.func.id == "len":
            if len(args) != 1:
                raise RuleError("len() takes exactly one argument")
            try:
                return len(args[0])
            except TypeError as exc:
                raise RuleError("len() applied to a non-sequence") from exc
        if node.func.id == "min" or node.func.id == "max":
            if not args:
                raise RuleError("min()/max() need at least one argument")
            return min(args) if node.func.id == "min" else max(args)
        if node.func.id == "sum":
            if len(args) != 1:
                raise RuleError("sum() takes exactly one argument")
            try:
                return sum(args[0])
            except TypeError as exc:
                raise RuleError("sum() applied to a non-sequence") from exc
        if node.func.id == "round":
            if not 1 <= len(args) <= 2:
                raise RuleError("round() takes one or two arguments")
            return round(*args)
        if node.func.id == "int":
            if len(args) != 1:
                raise RuleError("int() takes exactly one argument")
            return int(args[0])
        if len(args) != 1:
            raise RuleError(f"{node.func.id}() takes exactly one argument")
        return abs(args[0])

    if isinstance(node, (ast.List, ast.Tuple)):
        if len(node.elts) > MAX_SEQUENCE_LEN:
            raise RuleError("sequence literal too long")
        items = [_eval(elt, env, state) for elt in node.elts]
        return items if isinstance(node, ast.List) else tuple(items)

    raise RuleError(f"unsupported syntax: {type(node).__name__}")


def _validate(node: ast.AST) -> None:
    """Static check of the expression tree, before anything is evaluated.

    Rejecting here (rather than at evaluation time) means an unsafe rule is
    refused with a precise reason instead of surfacing later as a mysterious
    failure on one input.
    """
    if isinstance(node, ast.Expression):
        _validate(node.body)
    elif isinstance(node, ast.Constant):
        if not isinstance(node.value, (bool, int, float)):
            raise RuleError(f"unsupported constant: {node.value!r}")
    elif isinstance(node, ast.Name):
        if node.id not in ALLOWED_NAMES:
            raise RuleError(f"unknown name: {node.id}")
    elif isinstance(node, ast.BinOp):
        if type(node.op) is not ast.Pow and type(node.op) not in _BIN_OPS:
            raise RuleError(f"unsupported operator: {type(node.op).__name__}")
        _validate(node.left)
        _validate(node.right)
    elif isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, (ast.UAdd, ast.USub, ast.Not)):
            raise RuleError(f"unsupported unary operator: {type(node.op).__name__}")
        _validate(node.operand)
    elif isinstance(node, ast.BoolOp):
        if not isinstance(node.op, (ast.And, ast.Or)):
            raise RuleError(f"unsupported boolean operator: {type(node.op).__name__}")
        for value in node.values:
            _validate(value)
    elif isinstance(node, ast.Compare):
        for op in node.ops:
            if type(op) not in _CMP_OPS:
                raise RuleError(f"unsupported comparison: {type(op).__name__}")
        _validate(node.left)
        for comparator in node.comparators:
            _validate(comparator)
    elif isinstance(node, ast.IfExp):
        _validate(node.test)
        _validate(node.body)
        _validate(node.orelse)
    elif isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_CALLS:
            raise RuleError("call to a function that is not allowed")
        if node.keywords:
            raise RuleError("keyword arguments are not allowed")
        for arg in node.args:
            _validate(arg)
    elif isinstance(node, (ast.List, ast.Tuple)):
        if len(node.elts) > MAX_SEQUENCE_LEN:
            raise RuleError("sequence literal too long")
        for elt in node.elts:
            _validate(elt)
    else:
        raise RuleError(f"unsupported syntax: {type(node).__name__}")


def compile_rule(expr: str) -> Callable[[int, int, int], Any]:
    """Parse, validate and return a callable for a model-produced rule.

    Raises :class:`RuleError` for anything the sandbox refuses.
    """
    if not isinstance(expr, str) or not expr.strip():
        raise RuleError("empty rule")
    if len(expr) > MAX_EXPR_LEN:
        raise RuleError("rule too long")
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as exc:
        raise RuleError(f"syntax error: {exc}") from exc
    _validate(tree)

    def run(a: int, b: int, n: int = 0) -> Any:
        return _eval(tree, {"a": a, "b": b, "n": n}, {"steps": 0})

    return run


def try_compile(expr: str):
    """Return ``(callable, None)`` or ``(None, error_message)``."""
    try:
        return compile_rule(expr), None
    except RuleError as exc:
        return None, str(exc)


def equivalent(
    f: Callable[[int, int, int], Any],
    g: Callable[[int, int, int], Any],
    points: Sequence[Tuple[int, int]],
) -> bool:
    """True when ``f`` and ``g`` agree on every point of ``points``."""
    for a, b in points:
        try:
            if f(a, b, 0) != g(a, b, 0):
                return False
        except RuleError:
            return False
    return True


def check_output_is_scalar(value: Any) -> None:
    """Reject rules that return something other than a number."""
    if isinstance(value, bool) or isinstance(value, (int, float)):
        return
    raise RuleError("rule must return a number")
