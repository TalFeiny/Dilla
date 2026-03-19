"""
Forecast Chart Transforms

Converts raw regression/forecast data into chart-ready shapes for
TableauLevelCharts on the frontend.

Pattern: same as dpi_sankey — backend returns the exact data shape
the renderer expects, frontend just passes through.

Each shape includes:
  - chart data in the format the renderer expects
  - citations: [{id, number, source, date, title, content}]
  - explanation: CFO-readable narrative of what the chart shows

Supported chart shapes:
  - branched_line: x_axis + series (actuals fork into forecast)
  - stacked_bar: [{period, cat1, cat2, ...}]
  - treemap: [{name, value, children?}]
  - line / regression_line: {labels, datasets}
  - monte_carlo_fan: {labels, datasets} with confidence bands
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from app.core.date_utils import parse_period_to_date

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Period intelligence
# ---------------------------------------------------------------------------

def detect_granularity(periods: List[str]) -> str:
    """Detect monthly / quarterly / annual from period strings."""
    if not periods or len(periods) < 2:
        return "monthly"
    if "Q" in periods[0]:
        return "quarterly"
    if len(periods[0]) == 4:
        return "annual"
    try:
        d0 = parse_period_to_date(periods[0])
        d1 = parse_period_to_date(periods[1])
        gap = (d1 - d0).days
        if gap > 300:
            return "annual"
        if gap > 60:
            return "quarterly"
    except (ValueError, IndexError):
        pass
    return "monthly"


def format_period(period: str, granularity: str) -> str:
    """Human-readable period label: Jan '25, Q1 '25, 2025."""
    if granularity == "annual":
        return period[:4]
    if granularity == "quarterly":
        if "Q" in period:
            return period
        try:
            parts = period.split("-")
            q = (int(parts[1]) - 1) // 3 + 1
            return f"Q{q} '{parts[0][2:]}"
        except (IndexError, ValueError):
            return period
    # Monthly
    try:
        d = parse_period_to_date(period)
        return d.strftime("%b") + f" '{d.strftime('%y')}"
    except ValueError:
        return period


# ---------------------------------------------------------------------------
# Citation + explanation builders
# ---------------------------------------------------------------------------

def _build_citation(
    model_meta: Optional[Dict[str, Any]],
    category: str,
    n_actuals: int,
    n_forecast: int,
) -> List[Dict[str, Any]]:
    """Build citation list from model metadata."""
    citations = []
    today = date.today().isoformat()

    citations.append({
        "id": 1, "number": 1,
        "source": "Company Actuals",
        "date": today,
        "title": f"{category.replace('_', ' ').title()} — {n_actuals} periods",
        "content": f"Based on {n_actuals} historical data points from fpa_actuals.",
    })

    if model_meta:
        model_name = model_meta.get("model_name", "Regression")
        equation = model_meta.get("equation", "")
        r2 = model_meta.get("r_squared")
        citations.append({
            "id": 2, "number": 2,
            "source": f"{model_name} Model",
            "date": today,
            "title": f"Model: {model_name}" + (f" (R² = {r2:.3f})" if r2 else ""),
            "content": f"Equation: {equation}" if equation else f"Fitted using {model_name}.",
        })

    if n_forecast > 0:
        risk = (model_meta or {}).get("extrapolation_risk", "unknown")
        citations.append({
            "id": 3, "number": 3,
            "source": "Forecast Projection",
            "date": today,
            "title": f"{n_forecast}-period forward projection",
            "content": f"Extrapolation risk: {risk}. Forecast extends model fit beyond observed data.",
        })

    return citations


def _build_explanation(
    chart_type: str,
    model_meta: Optional[Dict[str, Any]],
    category: str,
    n_actuals: int,
    n_forecast: int,
    granularity: str,
) -> str:
    """Business explanation — what the forecast means, not how it was computed."""
    meta = model_meta or {}
    biz_interp = meta.get("business_interpretation", "")
    qual = meta.get("qualitative_assessment", "")
    reasoning = meta.get("selection_reasoning", "")
    risk = meta.get("extrapolation_risk", "")
    cat_label = category.replace("_", " ")
    gran_label = {"monthly": "months", "quarterly": "quarters", "annual": "years"}.get(
        granularity, "periods"
    )

    # Business interpretation is the explanation. Everything else is secondary.
    if biz_interp:
        explanation = biz_interp
        if risk and risk not in ("low", "unknown"):
            explanation += f" Forward projection carries {risk} extrapolation risk."
        return explanation

    if qual:
        return qual + (f" Extrapolation risk: {risk}." if risk and risk not in ("low", "unknown") else "")

    if reasoning:
        return reasoning

    # Fallback — only if the regression service returned nothing useful
    return f"{cat_label.title()} forecast built from {n_actuals} {gran_label} of actuals, projecting {n_forecast} {gran_label} forward."


# ---------------------------------------------------------------------------
# Branched line (actuals → forecast fork with scenario branches)
# ---------------------------------------------------------------------------

def to_branched_line(
    periods: List[str],
    actuals: List[float],
    predictions: List[float],
    forecast_periods: List[str],
    forecast_vals: List[float],
    branches: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build branched_line chart data: x_axis + series."""
    all_periods = periods + forecast_periods
    gran = detect_granularity(all_periods)
    labels = [format_period(p, gran) for p in all_periods]

    n_actuals = len(actuals)

    # Actuals series (None for forecast periods)
    actual_vals = [round(v, 2) for v in actuals] + [None] * len(forecast_periods)

    # Fitted line over actuals (None for forecast periods)
    fitted_vals = [round(v, 2) for v in predictions[:n_actuals]] + [None] * len(forecast_periods)

    # Forecast series: bridge from last actual into forecast
    forecast_series = [None] * n_actuals + [round(v, 2) for v in forecast_vals]
    if n_actuals > 0 and forecast_vals:
        forecast_series[n_actuals - 1] = round(actuals[-1], 2)  # bridge point

    series = [
        {"name": "Actuals", "data": actual_vals, "style": "solid", "color": "#4e79a7"},
        {"name": "Fitted", "data": fitted_vals, "style": "dashed", "color": "#76b7b2"},
    ]
    if any(v is not None for v in forecast_series):
        series.append(
            {"name": "Forecast", "data": forecast_series, "style": "dashed", "color": "#f28e2c"}
        )

    # Scenario branches
    branch_colors = ["#e15759", "#59a14f", "#af7aa1", "#edc949"]
    if branches:
        for i, b in enumerate(branches):
            bvals = [None] * n_actuals + b.get("data", b.get("values", []))
            if n_actuals > 0 and bvals:
                bvals[n_actuals - 1] = round(actuals[-1], 2)
            series.append({
                "name": b.get("name", f"Branch {i+1}"),
                "data": bvals,
                "style": "dashed",
                "color": branch_colors[i % len(branch_colors)],
            })

    annotations = []
    if n_actuals > 0:
        annotations.append({
            "type": "fork_point",
            "x": n_actuals - 1,
            "label": {"content": "Today"},
        })

    return {"x_axis": labels, "series": series, "annotations": annotations}


# ---------------------------------------------------------------------------
# Stacked bar
# ---------------------------------------------------------------------------

def to_stacked_bar(
    periods: List[str],
    actuals: List[float],
    forecast_periods: List[str],
    forecast_vals: List[float],
    category: str = "revenue",
    subcategories: Optional[Dict[str, List[float]]] = None,
) -> List[Dict[str, Any]]:
    """Stacked bar: [{period, cat1, cat2, ...}]."""
    all_periods = periods + forecast_periods
    all_values = list(actuals) + list(forecast_vals)
    gran = detect_granularity(all_periods)

    if subcategories:
        return [
            {
                "period": format_period(p, gran),
                "_type": "actual" if i < len(periods) else "forecast",
                **{cat: round(vals[i], 2) if i < len(vals) else 0 for cat, vals in subcategories.items()},
            }
            for i, p in enumerate(all_periods)
        ]

    return [
        {
            "period": format_period(p, gran),
            category: round(all_values[i], 2) if i < len(all_values) else 0,
            "_type": "actual" if i < len(periods) else "forecast",
        }
        for i, p in enumerate(all_periods)
    ]


# ---------------------------------------------------------------------------
# Treemap
# ---------------------------------------------------------------------------

def to_treemap(
    actuals: List[float],
    forecast_vals: List[float],
    category: str = "revenue",
    subcategories: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """Treemap: [{name, value}]."""
    if subcategories:
        return [{"name": k, "value": abs(v)} for k, v in subcategories.items() if v]

    total_actual = sum(actuals) if actuals else 0
    total_forecast = sum(forecast_vals) if forecast_vals else 0
    return [
        {"name": "Actuals", "value": abs(total_actual)},
        {"name": "Forecast", "value": abs(total_forecast)},
    ]


# ---------------------------------------------------------------------------
# Line / regression_line (labels + datasets)
# ---------------------------------------------------------------------------

def to_line_chart(
    periods: List[str],
    actuals: List[float],
    predictions: List[float],
    forecast_periods: List[str],
    forecast_vals: List[float],
) -> Dict[str, Any]:
    """Line chart: {labels, datasets}."""
    all_periods = periods + forecast_periods
    gran = detect_granularity(all_periods)
    labels = [format_period(p, gran) for p in all_periods]

    n = len(periods)
    datasets = [
        {"label": "Actual", "data": [round(v, 2) for v in actuals] + [None] * len(forecast_periods)},
        {"label": "Fitted", "data": [round(v, 2) for v in predictions[:n]] + [None] * len(forecast_periods)},
    ]
    if forecast_vals:
        fc_data = [None] * n + [round(v, 2) for v in forecast_vals]
        # Bridge
        if n > 0:
            fc_data[n - 1] = round(actuals[-1], 2)
        datasets.append({"label": "Forecast", "data": fc_data})

    return {"labels": labels, "datasets": datasets}


# ---------------------------------------------------------------------------
# Monte Carlo fan
# ---------------------------------------------------------------------------

def to_monte_carlo_fan(
    periods: List[str],
    actuals: List[float],
    predictions: List[float],
    forecast_periods: List[str],
    forecast_vals: List[float],
    confidence_intervals: Optional[List[Dict[str, float]]] = None,
) -> Dict[str, Any]:
    """MC fan: line chart + upper/lower bounds."""
    result = to_line_chart(periods, actuals, predictions, forecast_periods, forecast_vals)
    if confidence_intervals:
        n = len(periods)
        result["datasets"].append({
            "label": "Upper Bound",
            "data": [None] * n + [round(ci.get("upper", 0), 2) for ci in confidence_intervals],
        })
        result["datasets"].append({
            "label": "Lower Bound",
            "data": [None] * n + [round(ci.get("lower", 0), 2) for ci in confidence_intervals],
        })
    return result


# ---------------------------------------------------------------------------
# Universal builder — returns all shapes so the frontend can switch freely
# ---------------------------------------------------------------------------

def build_all_chart_shapes(
    periods: List[str],
    actuals: List[float],
    predictions: List[float],
    forecast_periods: List[str],
    forecast_vals: List[float],
    category: str = "revenue",
    model_meta: Optional[Dict[str, Any]] = None,
    confidence_intervals: Optional[List[Dict[str, float]]] = None,
    branches: Optional[List[Dict[str, Any]]] = None,
    subcategories: Optional[Dict[str, List[float]]] = None,
) -> Dict[str, Any]:
    """Build all chart shapes at once so the frontend can toggle chart type
    without another API call. This is the main entry point.

    Each shape is wrapped with citations + explanation:
    {
      "branched_line": { "data": {...}, "citations": [...], "explanation": "..." },
      "stacked_bar":   { "data": [...], "citations": [...], "explanation": "..." },
      ...
    }
    """
    gran = detect_granularity(periods + forecast_periods)
    n_actuals = len(actuals)
    n_forecast = len(forecast_vals)

    # Shared citations across all shapes (same underlying data)
    citations = _build_citation(model_meta, category, n_actuals, n_forecast)

    chart_types = {
        "branched_line": to_branched_line(
            periods, actuals, predictions, forecast_periods, forecast_vals, branches,
        ),
        "stacked_bar": to_stacked_bar(
            periods, actuals, forecast_periods, forecast_vals, category, subcategories,
        ),
        "treemap": to_treemap(actuals, forecast_vals, category),
        "line": to_line_chart(periods, actuals, predictions, forecast_periods, forecast_vals),
        "regression_line": to_line_chart(periods, actuals, predictions, forecast_periods, forecast_vals),
        "bar_comparison": to_line_chart(periods, actuals, predictions, forecast_periods, forecast_vals),
        "monte_carlo_fan": to_monte_carlo_fan(
            periods, actuals, predictions, forecast_periods, forecast_vals, confidence_intervals,
        ),
    }

    return {
        chart_type: {
            "data": chart_data,
            "citations": citations,
            "explanation": _build_explanation(
                chart_type, model_meta, category, n_actuals, n_forecast, gran,
            ),
        }
        for chart_type, chart_data in chart_types.items()
    }
