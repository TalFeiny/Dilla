"""
Driver Narration Helper

Structures branch execution results into agent-readable narration:
- What changed (drivers with overrides)
- Ripple trace (downstream P&L impact chain)
- Headline summary
- Base vs branch comparison
- Capital raising analysis (if runway is short)

The agent uses this structured output to compose its NL response
without hallucinating numbers — everything comes from actual computation.
"""

from typing import Any, Dict, List, Optional


def narrate_branch_result(
    branch_result: Dict[str, Any],
    resolved_drivers: Dict[str, Any],
    base_forecast: Optional[List[Dict[str, Any]]] = None,
    branch_forecast: Optional[List[Dict[str, Any]]] = None,
    capital_raising: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build structured narration from a branch execution result.

    Args:
        branch_result: output from execute_branch()
        resolved_drivers: output from resolve_drivers()
        base_forecast: base case P&L (optional, pulled from branch_result if absent)
        branch_forecast: branch P&L (optional, pulled from branch_result if absent)
        capital_raising: output from analyze_capital_needs() (optional)

    Returns structured dict the agent uses to compose its response.
    """
    if base_forecast is None:
        base_forecast = branch_result.get("base_forecast", [])
    if branch_forecast is None:
        branch_forecast = branch_result.get("forecast", [])

    changes = _extract_changes(resolved_drivers)
    ripple = _build_ripple_trace(base_forecast, branch_forecast)
    comparison = _build_comparison(base_forecast, branch_forecast)
    headline = _build_headline(changes, comparison, capital_raising)

    return {
        "changes": changes,
        "ripple_trace": ripple,
        "headline": headline,
        "comparison": comparison,
        "capital_raising": capital_raising,
    }


def _extract_changes(resolved: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract drivers that have been overridden from base."""
    changes = []
    for did, info in resolved.items():
        if isinstance(info, dict) and info.get("source") == "branch":
            changes.append({
                "driver": did,
                "label": info.get("label", did),
                "from": info.get("base"),
                "to": info.get("effective"),
                "override": info.get("override"),
                "how": info.get("how"),
                "unit": info.get("unit"),
                "impact_summary": _describe_change(info),
            })
    return changes


def _describe_change(info: Dict[str, Any]) -> str:
    """One-line description of a single driver change."""
    label = info.get("label", "")
    base = info.get("base")
    effective = info.get("effective")
    unit = info.get("unit", "")
    how = info.get("how", "set")

    if effective is None:
        return f"{label}: set"

    if unit == "%":
        if how == "scale":
            override = info.get("override", 0)
            direction = "increase" if override > 0 else "decrease"
            return f"{label}: {direction} by {abs(override)*100:.0f}%"
        return f"{label}: {_fmt(base, '%')} -> {_fmt(effective, '%')}"
    elif unit == "$":
        return f"{label}: {_fmt_dollars(base)} -> {_fmt_dollars(effective)}"
    elif unit == "headcount":
        delta = (effective or 0) - (base or 0)
        sign = "+" if delta > 0 else ""
        return f"{label}: {sign}{delta:.0f} heads"
    else:
        return f"{label}: {base} -> {effective}"


def _build_ripple_trace(
    base: List[Dict[str, Any]],
    branch: List[Dict[str, Any]],
) -> List[str]:
    """Build human-readable ripple trace showing cascading P&L impact."""
    if not base or not branch:
        return []

    b_last = base[-1] if base else {}
    s_last = branch[-1] if branch else {}
    traces = []

    metrics = [
        ("revenue", "Revenue", "$"),
        ("gross_profit", "Gross Profit", "$"),
        ("total_opex", "Total OpEx", "$"),
        ("ebitda", "EBITDA", "$"),
        ("free_cash_flow", "Free Cash Flow", "$"),
        ("cash_balance", "Cash Balance", "$"),
        ("runway_months", "Runway", "mo"),
    ]

    for key, label, unit in metrics:
        bv = b_last.get(key, 0) or 0
        sv = s_last.get(key, 0) or 0
        diff = sv - bv

        if abs(diff) < 0.01 and key != "runway_months":
            continue
        if abs(diff) < 0.1 and key == "runway_months":
            continue

        if unit == "$":
            traces.append(
                f"{label}: {_fmt_dollars(bv)} -> {_fmt_dollars(sv)} "
                f"({'+' if diff >= 0 else ''}{_fmt_dollars(diff)})"
            )
        else:
            traces.append(
                f"{label}: {bv:.1f}{unit} -> {sv:.1f}{unit} "
                f"({'+' if diff >= 0 else ''}{diff:.1f}{unit})"
            )

    return traces


def _build_comparison(
    base: List[Dict[str, Any]],
    branch: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """12-month cumulative comparison of key metrics."""
    if not base or not branch:
        return {}

    horizon = min(12, len(base), len(branch))

    def _sum(forecast, key):
        return sum(m.get(key, 0) or 0 for m in forecast[:horizon])

    base_rev = _sum(base, "revenue")
    branch_rev = _sum(branch, "revenue")
    base_cash_end = base[horizon - 1].get("cash_balance", 0) if len(base) >= horizon else 0
    branch_cash_end = branch[horizon - 1].get("cash_balance", 0) if len(branch) >= horizon else 0
    base_runway = base[horizon - 1].get("runway_months", 0) if len(base) >= horizon else 0
    branch_runway = branch[horizon - 1].get("runway_months", 0) if len(branch) >= horizon else 0

    return {
        "revenue_impact_12mo": round(branch_rev - base_rev, 2),
        "cash_impact_12mo": round(branch_cash_end - base_cash_end, 2),
        "runway_impact": round(branch_runway - base_runway, 1),
    }


def _build_headline(
    changes: List[Dict[str, Any]],
    comparison: Dict[str, Any],
    capital_raising: Optional[Dict[str, Any]],
) -> str:
    """Generate a one-sentence headline summarizing the scenario."""
    parts = []

    # Describe what changed
    if len(changes) == 1:
        parts.append(changes[0]["impact_summary"])
    elif len(changes) <= 3:
        labels = [c["label"] for c in changes]
        parts.append(f"Changes to {', '.join(labels)}")
    elif changes:
        parts.append(f"{len(changes)} driver changes")

    # Key outcome
    runway_delta = comparison.get("runway_impact", 0)
    cash_delta = comparison.get("cash_impact_12mo", 0)

    if runway_delta > 0:
        parts.append(f"extends runway by {runway_delta:.0f} months")
    elif runway_delta < 0:
        parts.append(f"shortens runway by {abs(runway_delta):.0f} months")

    if abs(cash_delta) > 10_000:
        direction = "adds" if cash_delta > 0 else "reduces cash by"
        parts.append(f"{direction} {_fmt_dollars(abs(cash_delta))} over 12 months")

    # Funding need
    if capital_raising and capital_raising.get("needs_funding"):
        gap = capital_raising.get("funding_gap", 0)
        parts.append(f"funding gap of {_fmt_dollars(gap)}")
    elif capital_raising is None and runway_delta > 6:
        parts.append("may eliminate need for bridge funding")

    return ". ".join(p.capitalize() if i == 0 else p for i, p in enumerate(parts)) + "." if parts else "Scenario applied."


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt(value: Any, unit: str) -> str:
    if value is None:
        return "N/A"
    if unit == "%":
        return f"{value * 100:.1f}%"
    return str(value)


def _fmt_dollars(value: Any) -> str:
    if value is None:
        return "N/A"
    v = float(value)
    if abs(v) >= 1e9:
        return f"${v/1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v/1e6:.1f}M"
    if abs(v) >= 1e3:
        return f"${v/1e3:.0f}K"
    return f"${v:,.0f}"
