"""PE chart generators — adaptive chart functions for any deal type IC memos.

Each function takes pe_model_data (from PEModelIngestionService) and returns
a chart config dict ready for the frontend TableauLevelCharts renderer.

Charts self-select based on what data exists: LBO deals get debt paydown and
EBITDA bridges; structured equity gets capital stack and instrument mix;
all deal types get sources/uses and sensitivity when the data is present.
"""

import logging
from typing import Any, Dict, List, Optional

from app.services.chart_data_service import (
    format_waterfall_chart,
    format_heatmap_chart,
    format_stacked_bar_chart,
    format_bar_chart,
)
from app.services.data_validator import ensure_numeric

logger = logging.getLogger(__name__)


def _get_metric_values(om: Dict[str, Any], metric_name: str) -> List[float]:
    """Extract values array for a named metric from flexible operating_model."""
    metrics = om.get("metrics") or {}
    md = metrics.get(metric_name)
    if isinstance(md, dict):
        return md.get("values") or []
    return []


def format_primary_metric_bridge(pe_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Primary metric bridge waterfall: entry → value creation drivers → exit.

    Adapts to deal type: uses deal_profile.primary_metric (EBITDA, NOI, Revenue, etc.).
    Decomposes into revenue growth vs margin expansion when EBITDA is primary and
    Revenue + margin metrics exist. Otherwise: year-over-year deltas.
    """
    om = pe_data.get("operating_model") or {}
    dp = pe_data.get("deal_profile") or {}
    metrics = om.get("metrics") or {}

    primary = dp.get("primary_metric", "")
    if not primary or primary not in metrics:
        # Fall back to first dollar-format metric
        for name, md in metrics.items():
            if isinstance(md, dict) and md.get("format") == "dollar":
                primary = name
                break
    if not primary:
        return None

    series = _get_metric_values(om, primary)
    if len(series) < 2:
        return None

    entry_val = series[0]
    exit_val = series[-1]
    if not entry_val:
        return None

    items: List[Dict[str, Any]] = [
        {"name": f"Entry {primary}", "value": entry_val, "isSubtotal": True},
    ]

    # Revenue/margin decomposition only when EBITDA-type is primary and both Revenue + margin exist
    revenue_values = _get_metric_values(om, "Revenue") or _get_metric_values(om, "revenue")
    margin_key = None
    for candidate in ("EBITDA Margin", "ebitda_margin", "EBITDA_Margin", "Margin"):
        if candidate in metrics:
            margin_key = candidate
            break
    margin_values = _get_metric_values(om, margin_key) if margin_key else []

    if (primary.lower() in ("ebitda",) and len(revenue_values) >= 2
            and len(margin_values) >= 2 and revenue_values[0] > 0 and revenue_values[-1] > 0):
        entry_rev = revenue_values[0]
        exit_rev = revenue_values[-1]
        entry_margin = margin_values[0] / 100 if margin_values[0] > 1 else margin_values[0]
        exit_margin = margin_values[-1] / 100 if margin_values[-1] > 1 else margin_values[-1]

        rev_growth_contribution = (exit_rev - entry_rev) * entry_margin
        margin_expansion_contribution = exit_rev * (exit_margin - entry_margin)
        computed_exit = entry_val + rev_growth_contribution + margin_expansion_contribution
        residual = exit_val - computed_exit

        items.append({"name": "Revenue Growth", "value": rev_growth_contribution})
        items.append({"name": "Margin Expansion", "value": margin_expansion_contribution})
        if abs(residual) > abs(entry_val) * 0.01:
            items.append({"name": "Other / Rounding", "value": residual})
    elif len(series) > 2:
        for i in range(1, len(series)):
            period_label = (om.get("periods") or [])[i] if i < len(om.get("periods", [])) else f"Year {i}"
            increment = series[i] - series[i - 1]
            items.append({"name": f"Δ {period_label}", "value": increment})
    else:
        items.append({"name": f"{primary} Growth", "value": exit_val - entry_val})

    items.append({"name": f"Exit {primary}", "value": exit_val, "isSubtotal": True})

    return format_waterfall_chart(items, title=f"{primary} Bridge: Entry → Exit")


def format_irr_moic_sensitivity(pe_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """IRR/MOIC sensitivity heatmap — exit multiple × growth → IRR.

    Uses format_heatmap_chart with the sensitivity_matrix from returns.
    Repurposes the heatmap chart type: dimensions = col values, companies = row values,
    scores = IRR grid.
    """
    sm = (pe_data.get("returns") or {}).get("sensitivity_matrix")
    if not sm or not isinstance(sm, dict):
        return None

    row_values = sm.get("row_values") or []
    col_values = sm.get("col_values") or []
    irr_grid = sm.get("irr_grid") or []

    if not row_values or not col_values or not irr_grid:
        return None

    row_label = sm.get("row_label", "Exit Multiple")
    col_label = sm.get("col_label", "EBITDA Growth")

    # format_heatmap_chart expects: dimensions (column headers), companies (row labels), scores (2D)
    dimensions = [f"{col_label}: {v}" for v in col_values]
    companies = [f"{row_label}: {v}" for v in row_values]

    # Convert IRR decimals to percentages for display
    scores = []
    for row in irr_grid:
        display_row = []
        for v in row:
            val = ensure_numeric(v, 0)
            # If values look like decimals (< 1), convert to pct
            if abs(val) < 1:
                display_row.append(round(val * 100, 1))
            else:
                display_row.append(round(val, 1))
        scores.append(display_row)

    return format_heatmap_chart(
        dimensions=dimensions,
        companies=companies,
        scores=scores,
        title="Returns Sensitivity — IRR % by Exit Multiple × Growth",
        data_suffix="%",
        data_value_type="irr",
    )


def format_debt_paydown(pe_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Debt paydown schedule — stacked bar by instrument over time.

    Uses actual per-instrument schedules when extracted from the model.
    Falls back to proportional estimate from total balance if per-instrument not available.
    """
    sched = pe_data.get("debt_schedule") or {}
    instruments = pe_data.get("instruments") or []

    periods = sched.get("periods") or []
    total_balance = sched.get("total_balance") or []

    if not periods or not total_balance:
        return None

    # Filter instruments to debt-type only for fallback proportional estimate
    debt_types = {"senior_debt", "second_lien", "mezzanine", "unitranche", "revolver",
                  "pik_note", "seller_note", "convertible_note"}
    debt_instruments = [i for i in instruments if i.get("type", "").lower() in debt_types]

    per_instrument = sched.get("per_instrument") or []
    colors = ["#4A90D9", "#D97B4A", "#7ED97B", "#D94A90", "#9B59B6"]

    # Prefer actual per-instrument schedules from the model
    if per_instrument and any(pi.get("ending_balance") for pi in per_instrument):
        datasets = []
        for i, pi in enumerate(per_instrument):
            pi_balances = pi.get("ending_balance") or []
            if pi_balances:
                datasets.append({
                    "label": pi.get("name", f"Instrument {i + 1}"),
                    "data": [ensure_numeric(v, 0) for v in pi_balances],
                    "backgroundColor": colors[i % len(colors)],
                })
        if datasets:
            return format_stacked_bar_chart(
                labels=[str(p) for p in periods],
                datasets=datasets,
                title="Debt Paydown Schedule",
            )

    # Fallback: estimate per-instrument proportionally from total
    if len(debt_instruments) > 1 and len(total_balance) == len(periods):
        total_debt = sum(inst.get("amount", 0) for inst in debt_instruments)
        if not total_debt:
            total_debt = total_balance[0] if total_balance else 1

        datasets = []
        for i, inst in enumerate(debt_instruments):
            inst_pct = (inst.get("amount", 0) / total_debt) if total_debt else 0
            inst_data = [round(bal * inst_pct) for bal in total_balance]
            datasets.append({
                "label": inst.get("name", f"Instrument {i + 1}"),
                "data": inst_data,
                "backgroundColor": colors[i % len(colors)],
            })

        chart = format_stacked_bar_chart(
            labels=[str(p) for p in periods],
            datasets=datasets,
            title="Debt Paydown Schedule (estimated per-instrument)",
        )
        if chart:
            chart["_estimated"] = True
        return chart

    # Single dataset — total debt
    datasets = [{
        "label": "Total Debt",
        "data": [ensure_numeric(v, 0) for v in total_balance],
        "backgroundColor": "#4A90D9",
    }]

    return format_stacked_bar_chart(
        labels=[str(p) for p in periods],
        datasets=datasets,
        title="Debt Paydown Schedule",
    )


def format_sources_uses(pe_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Sources & Uses — grouped bar chart.

    Uses format_bar_chart. Two groups: Sources and Uses, each with labeled items.
    """
    su = pe_data.get("sources_uses") or {}
    sources = su.get("sources") or []
    uses = su.get("uses") or []

    if not sources and not uses:
        return None

    # Build as grouped bar: labels are the item names, two datasets (Sources, Uses)
    # Pad shorter list to align
    max_items = max(len(sources), len(uses))
    if max_items == 0:
        return None

    labels = []
    source_values = []
    use_values = []

    # Sources
    for item in sources:
        labels.append(item.get("name", "Source"))
        source_values.append(ensure_numeric(item.get("amount"), 0))
        use_values.append(0)

    # Uses
    for item in uses:
        labels.append(item.get("name", "Use"))
        source_values.append(0)
        use_values.append(ensure_numeric(item.get("amount"), 0))

    datasets = [
        {"label": "Sources", "data": source_values, "backgroundColor": "#4A90D9"},
        {"label": "Uses", "data": use_values, "backgroundColor": "#D97B4A"},
    ]

    return format_bar_chart(
        labels=labels,
        datasets=datasets,
        title="Sources & Uses",
    )


# ---------------------------------------------------------------------------
# Deal-type-adaptive charts — fire when instruments/data support them
# ---------------------------------------------------------------------------

_EQUITY_TYPES = {"preferred_equity", "common_equity", "warrant", "convertible_note", "earnout"}
_DEBT_TYPES = {"senior_debt", "second_lien", "mezzanine", "unitranche", "revolver",
               "pik_note", "seller_note", "convertible_note"}


def format_capital_stack(pe_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Capital stack waterfall — visualizes the full capital structure as layers.

    Shows each instrument as a building block from equity (bottom) up through
    debt seniority. Works for ANY deal type — LBOs show debt-heavy stacks,
    structured equity shows preferred/common/warrant layers.
    Returns None if fewer than 2 instruments.
    """
    instruments = pe_data.get("instruments") or []
    if len(instruments) < 2:
        return None

    # Sort: equity at bottom (rendered first in waterfall), senior debt at top
    seniority_order = {
        "common_equity": 0, "warrant": 1, "earnout": 2, "convertible_note": 3,
        "preferred_equity": 4, "mezzanine": 5, "pik_note": 6, "second_lien": 7,
        "seller_note": 8, "unitranche": 9, "senior_debt": 10, "revolver": 11,
    }
    sorted_instruments = sorted(
        instruments,
        key=lambda i: seniority_order.get(i.get("type", "").lower(), 5),
    )

    items: List[Dict[str, Any]] = []
    for inst in sorted_instruments:
        amt = ensure_numeric(inst.get("amount"), 0)
        if not amt:
            continue
        inst_type = inst.get("type", "").lower()
        # Color code by category
        if inst_type in _EQUITY_TYPES:
            color = "#22C55E"  # green for equity
        elif inst_type in ("mezzanine", "pik_note", "second_lien"):
            color = "#F59E0B"  # amber for junior debt
        else:
            color = "#3B82F6"  # blue for senior debt
        items.append({
            "name": inst.get("name", inst.get("type", "?")),
            "value": amt,
            "color": color,
        })

    if len(items) < 2:
        return None

    # Add total as subtotal
    total = sum(i["value"] for i in items)
    items.append({"name": "Total Capital", "value": total, "isSubtotal": True})

    return format_waterfall_chart(items, title="Capital Stack")


# ---------------------------------------------------------------------------
# Dispatcher — called by _prebuild_charts in the memo service
# ---------------------------------------------------------------------------

PE_CHART_BUILDERS = {
    "ebitda_bridge": format_primary_metric_bridge,
    "sources_uses_chart": format_sources_uses,
    "debt_paydown": format_debt_paydown,
    "returns_sensitivity": format_irr_moic_sensitivity,
    "capital_stack": format_capital_stack,
}


def build_pe_chart(section_key: str, pe_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Dispatch chart building by section key. Returns chart config or None."""
    builder = PE_CHART_BUILDERS.get(section_key)
    if builder:
        try:
            return builder(pe_data)
        except Exception as e:
            logger.warning("[PE_CHARTS] Failed to build %s: %s", section_key, e)
    return None
