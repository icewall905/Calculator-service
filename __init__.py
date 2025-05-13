"""Calculator Service integration."""

import ast
import operator as op
import math
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.config_entries import ConfigEntry
import voluptuous as vol

DOMAIN = "calc_service"

# safe operators
OPS = {
    ast.Add: op.add, ast.Sub: op.sub,
    ast.Mult: op.mul, ast.Div: op.truediv,
    ast.Pow: op.pow, ast.Mod: op.mod,
    ast.USub: op.neg,
}

# allowed math names
MATH = {name: getattr(math, name) for name in (
    "pi","e","tau",
    "sin","cos","tan",
    "asin","acos","atan",
    "sqrt","log","log10","log2","exp",
)}

def _eval(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Num):
        return node.n
    if isinstance(node, ast.BinOp):
        return OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp):
        return OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name):
        if node.id in MATH:
            return MATH[node.id]
        raise NameError(f"Use of name '{node.id}' is not allowed")
    if isinstance(node, ast.Call):
        func = _eval(node.func)
        args = [_eval(a) for a in node.args]
        return func(*args)
    raise ValueError(f"Unsupported expression node: {ast.dump(node)}")

def safe_eval(expr: str):
    """Parse & evaluate an expression in a restricted AST."""
    tree = ast.parse(expr, mode="eval")
    result = _eval(tree.body)
    # tidy floats that are whole numbers
    if isinstance(result, float) and result.is_integer():
        return int(result)
    return result

# calc_service/__init__.py  (snippet)
def handle_calculate(call):
    expr = call.data["expression"]
    try:
        res = safe_eval(expr)
        call.hass.states.async_set("input_text.calculator_result", str(res))
        return {"result": res}     # still useful in dev‑tools
    except Exception as e:
        call.hass.states.async_set("input_text.calculator_result", f"error: {e}")
        return {"error": str(e)}


def setup(hass: HomeAssistant, config: dict):
    """Register the calc_service.calculate service."""
    schema = vol.Schema({vol.Required("expression"): str})

    # ✅ flag that this service RETURNS DATA
    hass.services.register(
        DOMAIN,
        "calculate",
        handle_calculate,
        schema=schema,
        supports_response=True,
    )
    return True
