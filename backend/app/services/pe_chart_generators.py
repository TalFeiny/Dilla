"""PE chart generators — 4 functions wrapping existing chart formatters for PE IC memos.

Each function takes pe_model_data (from PEModelIngestionService) and returns
a chart config dict ready for the frontend TableauLevelCharts renderer.
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


def format_ebitda_bridge(pe_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """EBITDA bridge waterfall: entry EBITDA → value creation drivers → exit EBITDA.

    Decomposes into revenue growth contribution vs margin expansion when data allows.
    Falls back to year-over-year deltas if revenue/margin data insufficient.
    """
    om = pe_data.get("operating_model") or {}
    txn = pe_data.get("transaction") or {}
    returns = pe_data.get("returns", {}).get("base") or {}

    ebitda_series = om.get("ebitda") or []
    if len(ebitda_series) < 2:
        return None

    entry_ebitda = ebitda_series[0] or ensure_numeric(txn.get("entry_ebitda"), 0)
    exit_ebitda = ebitda_series[-1] or ensure_numeric(returns.get("exit_ebitda"), 0)

    if not entry_ebitda:
        return None

    items: List[Dict[str, Any]] = [
        {"name": "Entry EBITDA", "value": entry_ebitda, "isSubtotal": True},
    ]

    # Try value creation driver decomposition: revenue growth vs margin expansion
    revenues = om.get("revenue") or []
    margins = om.get("ebitda_margin") or []
    if (len(revenues) >= 2 and len(margins) >= 2
            and revenues[0] > 0 and revenues[-1] > 0):
        entry_rev = revenues[0]
        exit_rev = revenues[-1]
        entry_margin = margins[0] / 100 if margins[0] > 1 else margins[0]
        exit_margin = margins[-1] / 100 if margins[-1] > 1 else margins[-1]

        # Revenue growth contribution = Δrevenue × entry margin
        rev_growth_contribution = (exit_rev - entry_rev) * entry_margin
        # Margin expansion contribution = exit revenue × Δmargin
        margin_expansion_contribution = exit_rev * (exit_margin - entry_margin)
        # Residual (cross-term)
        computed_exit = entry_ebitda + rev_growth_contribution + margin_expansion_contribution
        residual = exit_ebitda - computed_exit

        items.append({"name": "Revenue Growth", "value": rev_growth_contribution})
        items.append({"name": "Margin Expansion", "value": margin_expansion_contribution})
        if abs(residual) > abs(entry_ebitda) * 0.01:
            items.append({"name": "Other / Rounding", "value": residual})
    elif len(ebitda_series) > 2:
        # Fallback: year-over-year increments
        for i in range(1, len(ebitda_series)):
            period_label = (om.get("periods") or [])[i] if i < len(om.get("periods", [])) else f"Year {i}"
            increment = ebitda_series[i] - ebitda_series[i - 1]
            items.append({"name": f"Δ {period_label}", "value": increment})
    else:
        items.append({"name": "EBITDA Growth", "value": exit_ebitda - entry_ebitda})

    items.append({"name": "Exit EBITDA", "value": exit_ebitda, "isSubtotal": True})

    return format_waterfall_chart(items, title="EBITDA Bridge: Entry → Exit")


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
    """Debt paydown schedule — stacked bar by tranche over time.

    Uses actual per-tranche schedules when extracted from the model.
    Falls back to proportional estimate from total balance if per-tranche not available.
    """
    sched = pe_data.get("debt_schedule") or {}
    ds = pe_data.get("debt_structure") or {}

    periods = sched.get("periods") or []
    ending_balance = sched.get("ending_balance") or []

    if not periods or not ending_balance:
        return None

    tranches = ds.get("tranches") or []
    per_tranche = sched.get("per_tranche") or []
    colors = ["#4A90D9", "#D97B4A", "#7ED97B", "#D94A90", "#9B59B6"]

    # Prefer actual per-tranche schedules from the model
    if per_tranche and any(pt.get("ending_balance") for pt in per_tranche):
        datasets = []
        for i, pt in enumerate(per_tranche):
            pt_balances = pt.get("ending_balance") or []
            if pt_balances:
                datasets.append({
                    "label": pt.get("name", f"Tranche {i + 1}"),
                    "data": [ensure_numeric(v, 0) for v in pt_balances],
                    "backgroundColor": colors[i % len(colors)],
                })
        if datasets:
            chart = format_stacked_bar_chart(
                labels=[str(p) for p in periods],
                datasets=datasets,
                title="Debt Paydown Schedule",
            )
            return chart

    # Fallback: estimate per-tranche proportionally from total
    if len(tranches) > 1 and len(ending_balance) == len(periods):
        total_debt = ds.get("total_debt") or sum(t.get("amount", 0) for t in tranches)
        if not total_debt:
            total_debt = ending_balance[0] if ending_balance else 1

        datasets = []
        for i, tranche in enumerate(tranches):
            tranche_pct = (tranche.get("amount", 0) / total_debt) if total_debt else 0
            tranche_data = [round(bal * tranche_pct) for bal in ending_balance]
            datasets.append({
                "label": tranche.get("name", f"Tranche {i + 1}"),
                "data": tranche_data,
                "backgroundColor": colors[i % len(colors)],
            })

        chart = format_stacked_bar_chart(
            labels=[str(p) for p in periods],
            datasets=datasets,
            title="Debt Paydown Schedule (estimated per-tranche)",
        )
        if chart:
            chart["_estimated"] = True
        return chart

    # Single dataset — total debt
    datasets = [{
        "label": "Total Debt",
        "data": [ensure_numeric(v, 0) for v in ending_balance],
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
# Dispatcher — called by _prebuild_charts in the memo service
# ---------------------------------------------------------------------------

PE_CHART_BUILDERS = {
    "ebitda_bridge": format_ebitda_bridge,
    "sources_uses_chart": format_sources_uses,
    "debt_paydown": format_debt_paydown,
    "returns_sensitivity": format_irr_moic_sensitivity,
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
