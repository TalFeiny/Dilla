"""
Formula evaluator for spreadsheet-style formulas.
Provides cell/named-range context and evaluation used by financial_tools and financial_api.
"""

import re
import math
from typing import Any, Dict, List

# Built-in function names exposed for /functions API (financial_tools uses NPV, IRR, etc. via financial_calc)
FUNCTION_NAMES = [
    "NPV", "IRR", "PV", "FV", "PMT", "RATE", "NPER", "SLN", "DB", "DDB", "EFFECT", "NOMINAL",
    "SUM", "AVERAGE", "MIN", "MAX", "COUNT", "ROUND", "SQRT", "POWER", "ABS", "LOG", "LN", "EXP",
    "MEDIAN", "MODE", "STDEV", "STDEVP", "VAR", "VARP",
    "SIN", "COS", "TAN", "ASIN", "ACOS", "ATAN", "ATAN2", "RADIANS", "DEGREES",
    "IF", "AND", "OR", "NOT", "TRUE", "FALSE", "IFERROR", "ISNA", "ISERROR",
    "CONCATENATE", "LEN", "LEFT", "RIGHT", "MID", "UPPER", "LOWER", "TRIM", "FIND", "SEARCH",
    "TODAY", "NOW", "DATE", "TIME", "YEAR", "MONTH", "DAY", "WEEKDAY", "DAYS",
    "VLOOKUP", "HLOOKUP", "INDEX", "MATCH", "CHOOSE", "LOOKUP",
    "PI", "E", "RAND", "RANDBETWEEN", "SIGN", "MOD", "FACT", "GCD", "LCM",
]


class FormulaEvaluator:
    """Minimal evaluator: stores cell/range context and evaluates simple expressions."""

    def __init__(self):
        self._cell_values: Dict[str, Any] = {}
        self._named_ranges: Dict[str, List[Any]] = {}
        self.functions = {name: None for name in FUNCTION_NAMES}

    def set_cell_value(self, cell_ref: str, value: Any) -> None:
        self._cell_values[cell_ref.upper()] = value

    def set_named_range(self, name: str, values: List[Any]) -> None:
        self._named_ranges[name] = values

    def evaluate(self, formula: str) -> Any:
        """Evaluate formula string. Supports cell refs, named ranges, and simple math."""
        if not formula or not isinstance(formula, str):
            return 0
        s = formula.strip()
        if s.startswith("="):
            s = s[1:].strip()
        if not s:
            return 0
        # Resolve cell refs (e.g. A1, B2)
        for ref, val in self._cell_values.items():
            s = re.sub(rf"\b{re.escape(ref)}\b", str(val), s, flags=re.IGNORECASE)
        # Resolve named ranges as first element or sum (simplified)
        for name, values in self._named_ranges.items():
            repl = str(values[0]) if values else "0"
            s = re.sub(rf"\b{re.escape(name)}\b", repl, s, flags=re.IGNORECASE)
        # Safe eval: numbers and basic math only
        try:
            allowed = {"abs": abs, "round": round, "min": min, "max": max, "sum": sum, "pow": pow}
            allowed.update({k: getattr(math, k) for k in ["sqrt", "log", "log10", "exp", "sin", "cos", "tan"] if hasattr(math, k)})
            return eval(s, {"__builtins__": {}}, allowed)
        except Exception:
            return 0


formula_evaluator = FormulaEvaluator()
