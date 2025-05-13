"""Calculator & Kitchen‑Conversion Service integration."""

import ast, operator as op, math, re
from typing import Dict
from homeassistant.core import HomeAssistant, ServiceCall
import voluptuous as vol

DOMAIN = "calc_service"

# -------------------- math evaluation --------------------
OPS = {
    ast.Add: op.add, ast.Sub: op.sub,
    ast.Mult: op.mul, ast.Div: op.truediv,
    ast.Pow: op.pow,  ast.Mod: op.mod,
    ast.USub: op.neg,
}

MATH_FUNCS = {name: getattr(math, name) for name in (
    "pi","e","tau",
    "sin","cos","tan",
    "asin","acos","atan",
    "sqrt","log","log10","log2","exp",
)}

# -------------------- kitchen units ----------------------
VOL_ML: Dict[str, float] = {  # volume → millilitres
    "ml": 1, "milliliter": 1, "milliliters": 1,
    "l": 1000, "liter": 1000, "liters": 1000,
    "cup": 236.588, "cups": 236.588,                # :contentReference[oaicite:6]{index=6}
    "tbsp": 15, "tablespoon": 15, "tablespoons": 15, # :contentReference[oaicite:7]{index=7}
    "tsp": 5, "teaspoon": 5, "teaspoons": 5,         # :contentReference[oaicite:8]{index=8}
    "fl_oz": 29.5735, "floz": 29.5735, "fl‑oz": 29.5735, "fluidounce": 29.5735, # :contentReference[oaicite:9]{index=9}
}

MASS_G: Dict[str, float] = {  # mass → grams
    "g": 1, "gram": 1, "grams": 1,
    "kg": 1000, "kilogram": 1000, "kilograms": 1000,
    "oz": 28.3495, "ounce": 28.3495, "ounces": 28.3495,           # :contentReference[oaicite:10]{index=10}
    "lb": 453.592, "lbs": 453.592, "pound": 453.592, "pounds": 453.592, # :contentReference[oaicite:11]{index=11}
}

def _convert(val: float, from_u: str, to_u: str) -> float:
    """Convert between supported units."""
    fu, tu = from_u.lower(), to_u.lower()
    if fu in VOL_ML and tu in VOL_ML:            # volume→volume
        return val * VOL_ML[fu] / VOL_ML[tu]
    if fu in MASS_G and tu in MASS_G:            # mass→mass
        return val * MASS_G[fu] / MASS_G[tu]
    raise ValueError(f"Can't convert '{from_u}' to '{to_u}'")

# expose to expressions
MATH_FUNCS["convert"] = _convert

# -------------------- expression helpers -----------------
# 1) pattern like "2.5 cups to ml"
CONV_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*([a-zA-Z_]+)\s*(?:to|in|→|>)\s*([a-zA-Z_]+)\s*$"
)

def try_unit_conversion(expr: str):
    m = CONV_RE.match(expr)
    if not m:
        return None
    val, u_from, u_to = float(m.group(1)), m.group(2), m.group(3)
    return _convert(val, u_from, u_to)

def _eval(node):
    if isinstance(node, ast.Constant): return node.value
    if isinstance(node, ast.Num):      return node.n               # Py<3.8
    if isinstance(node, ast.BinOp):    return OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp):  return OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Name):
        if node.id in MATH_FUNCS:      return MATH_FUNCS[node.id]
        raise NameError(node.id)
    if isinstance(node, ast.Call):
        func = _eval(node.func)
        args = [_eval(a) for a in node.args]
        return func(*args)
    raise ValueError(f"Unsupported node: {ast.dump(node)}")

def safe_eval(expr: str):
    """Evaluate arithmetic or convert units."""
    # quick path for "<value> unit to unit"
    maybe = try_unit_conversion(expr)
    if maybe is not None:
        return maybe

    tree = ast.parse(expr, mode="eval")
    result = _eval(tree.body)
    # tidy floats that are whole numbers
    if isinstance(result, float) and result.is_integer():
        return int(result)
    return result

# -------------------- HA service -------------------------
def handle_calculate(call: ServiceCall):
    expr = call.data["expression"]
    try:
        res = safe_eval(expr)
        call.hass.states.async_set("input_text.calculator_result", str(res))
        return {"result": res}
    except Exception as err:
        call.hass.states.async_set("input_text.calculator_result", f"error: {err}")
        return {"error": str(err)}

def setup(hass: HomeAssistant, config: dict):
    """Register calc_service.calculate (supports_response=True)."""
    hass.services.register(
        DOMAIN,
        "calculate",
        handle_calculate,
        schema=vol.Schema({vol.Required("expression"): str}),
        supports_response=True,
    )
    return True
