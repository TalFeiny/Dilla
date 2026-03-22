"""
Model Spec Executor
Turns a ModelSpec into monthly arrays, feeds into existing cascade.

Not a replacement for anything — it's the bridge between:
  LLM-constructed ModelSpec → CashFlowPlanningService (via revenue_trajectory)

Reuses:
  - CashFlowPlanningService.build_monthly_cash_flow_model() for P&L cascade
  - MonteCarloEngine patterns for confidence bands
  - DriverRegistry keys for driver_overrides passthrough
  - date_utils for period arithmetic

The curve evaluation IS new (logistic/gompertz/etc with known params is different
from AdvancedRegressionService's curve_fit which FINDS params from data).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np
from dateutil.relativedelta import relativedelta

from app.core.date_utils import parse_period_to_date
from app.services.model_spec_schema import (
    ComponentSpec,
    CurveSpec,
    ExecutionResult,
    ModelSpec,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Curve evaluation — the actual math
# ---------------------------------------------------------------------------

def evaluate_curve(
    spec: CurveSpec,
    x: np.ndarray,
    context: Dict[str, np.ndarray],
) -> np.ndarray:
    """Evaluate a single curve over x (month indices 0..N-1).

    Args:
        spec: Curve definition with type, params, modifiers.
        x: Month indices as float array.
        context: Already-evaluated metrics (for ratio/inherit types).

    Returns:
        Monthly values as numpy array.
    """
    p = spec.params

    if spec.type == "logistic":
        L, k, x0 = p["L"], p["k"], p["x0"]
        y = L / (1 + np.exp(-k * (x - x0)))

    elif spec.type == "linear":
        y = p["slope"] * x + p["intercept"]

    elif spec.type == "exponential":
        y = p["a"] * np.exp(p["b"] * x)

    elif spec.type == "gompertz":
        a, b, c = p["a"], p["b"], p["c"]
        y = a * np.exp(-b * np.exp(-c * x))

    elif spec.type == "constant":
        y = np.full_like(x, p["value"], dtype=float)

    elif spec.type == "ratio":
        source = p.get("of", "revenue")
        if source not in context:
            logger.warning("ratio curve references '%s' but not yet evaluated", source)
            y = np.zeros_like(x, dtype=float)
        else:
            y = context[source] * p.get("ratio", 1.0)

    elif spec.type == "step_function":
        y = np.zeros_like(x, dtype=float)
        for step in p.get("steps", []):
            mask = x >= step["from_period"]
            y[mask] = step["value"]

    elif spec.type == "composite":
        y = np.zeros_like(x, dtype=float)
        for comp in spec.components:
            comp_spec = CurveSpec(
                type=comp.base,
                params=comp.params,
                prior=comp.prior,
                modifiers=comp.modifiers,
            )
            comp_y = evaluate_curve(comp_spec, x, context)
            y += comp.weight * comp_y

    elif spec.type == "inherit":
        parent_metric = p.get("metric", "revenue")
        parent_curves = context.get("_parent_curves", {})
        if parent_metric in parent_curves:
            y = np.array(parent_curves[parent_metric], dtype=float)
            # Pad or trim to match x length
            if len(y) < len(x):
                y = np.pad(y, (0, len(x) - len(y)), constant_values=y[-1])
            else:
                y = y[:len(x)]
        else:
            logger.warning("inherit curve: parent metric '%s' not found", parent_metric)
            y = np.zeros_like(x, dtype=float)

    elif spec.type == "custom_expr":
        # Not implementing eval — the LLM should use composite instead
        logger.warning("custom_expr not supported, falling back to zero")
        y = np.zeros_like(x, dtype=float)

    else:
        logger.warning("Unknown curve type '%s', returning zeros", spec.type)
        y = np.zeros_like(x, dtype=float)

    # Apply modifiers
    y = _apply_modifiers(y, x, spec.modifiers)

    return y


def _apply_modifiers(
    y: np.ndarray,
    x: np.ndarray,
    modifiers: list,
) -> np.ndarray:
    """Layer modifiers onto base curve values."""
    for mod in modifiers:
        mp = mod.params
        if mod.type == "seasonal":
            amp = mp.get("amplitude", 0.1)
            phase = mp.get("phase", 0)
            period = mp.get("period", 12)
            y = y * (1 + amp * np.sin(2 * np.pi * (x - phase) / period))

        elif mod.type == "shock":
            start = mp.get("start_month", 0)
            mag = mp.get("magnitude", -0.1)
            dur = mp.get("duration_months", 6)
            rec = mp.get("recovery", "gradual")
            for i in range(len(x)):
                if start <= x[i] < start + dur:
                    progress = (x[i] - start) / max(dur, 1)
                    if rec == "gradual":
                        y[i] *= (1 + mag * (1 - progress))
                    elif rec == "immediate":
                        y[i] *= (1 + mag)
                    elif rec == "step":
                        y[i] *= (1 + mag)

        elif mod.type == "trend_break":
            month = mp.get("month", 0)
            new_slope = mp.get("new_slope", 0)
            mask = x >= month
            y[mask] += new_slope * (x[mask] - month)

        elif mod.type == "step":
            month = mp.get("month", 0)
            delta = mp.get("delta", 0)
            y[x >= month] += delta

    return y


# ---------------------------------------------------------------------------
# Topological sort for metric evaluation order
# ---------------------------------------------------------------------------

def _topo_sort(curves: Dict[str, CurveSpec]) -> List[str]:
    """Sort metrics so ratio/inherit curves evaluate after their source."""
    deps: Dict[str, set] = {}
    for metric, curve in curves.items():
        d = set()
        if curve.type == "ratio":
            source = curve.params.get("of", "revenue")
            if source in curves:
                d.add(source)
        if curve.type == "inherit":
            pass  # parent curves come from context, not current spec
        deps[metric] = d

    ordered = []
    visited: set = set()

    def visit(m: str):
        if m in visited:
            return
        visited.add(m)
        for dep in deps.get(m, set()):
            visit(dep)
        ordered.append(m)

    for m in curves:
        visit(m)
    return ordered


# ---------------------------------------------------------------------------
# Period helpers
# ---------------------------------------------------------------------------

def _period_add(base: str, months_offset: int) -> str:
    """Add months to a YYYY-MM period string."""
    dt = parse_period_to_date(base)
    new_dt = dt + relativedelta(months=months_offset)
    return new_dt.strftime("%Y-%m")


def _period_diff(a: str, b: str) -> int:
    """Number of months from period a to period b (b - a)."""
    da = parse_period_to_date(a)
    db = parse_period_to_date(b)
    return (db.year - da.year) * 12 + (db.month - da.month)


# ---------------------------------------------------------------------------
# Main executor
# ---------------------------------------------------------------------------

class ModelSpecExecutor:
    """Execute a ModelSpec → full P&L forecast via existing cascade."""

    def __init__(self):
        from app.services.cash_flow_planning_service import CashFlowPlanningService
        self._cfp = CashFlowPlanningService()

    def execute(
        self,
        spec: ModelSpec,
        company_data: Dict[str, Any],
        months: int = 24,
        start_period: Optional[str] = None,
        parent_result: Optional[ExecutionResult] = None,
    ) -> ExecutionResult:
        """Execute a ModelSpec and return full forecast with confidence bands.

        Args:
            spec: The model specification to execute.
            company_data: Forecast seed dict (from CompanyData.to_forecast_seed()).
            months: Projection horizon.
            start_period: YYYY-MM start (defaults to next month).
            parent_result: If spec.parent_model, pass the parent's result for inheritance.

        Returns:
            ExecutionResult with forecast, confidence_bands, milestones, raw curves.
        """
        if not start_period:
            today = date.today()
            start_period = f"{today.year}-{today.month:02d}"

        x = np.arange(months, dtype=float)
        context: Dict[str, np.ndarray] = {}

        # Resolve parent curves for inheritance
        if parent_result and parent_result.curves:
            context["_parent_curves"] = parent_result.curves

        # 1. Evaluate each metric's curve in dependency order
        eval_order = _topo_sort(spec.curves)
        for metric in eval_order:
            curve = spec.curves[metric]
            values = evaluate_curve(curve, x, context)

            # Apply macro shocks (probability-weighted)
            for shock in spec.macro_shocks:
                if metric in shock.impacts:
                    imp = shock.impacts[metric]
                    shock_mod_params = {
                        "start_month": imp.get("start_month", 0),
                        "magnitude": imp.get("magnitude", 0) * shock.probability,
                        "duration_months": imp.get("duration_months", 6),
                        "recovery": imp.get("recovery", "gradual"),
                    }
                    from app.services.model_spec_schema import ModifierSpec
                    shock_mod = ModifierSpec(type="shock", params=shock_mod_params)
                    values = _apply_modifiers(values, x, [shock_mod])

            context[metric] = values

        # 2. Build revenue_trajectory for cascade
        revenue = context.get("revenue")
        trajectory = None
        if revenue is not None:
            trajectory = [
                {"period": _period_add(start_period, i), "revenue": float(revenue[i])}
                for i in range(months)
            ]

        # 3. Merge driver_overrides into company_data
        seed = dict(company_data)
        seed.update(spec.driver_overrides)

        # 4. Feed into existing P&L cascade
        forecast = self._cfp.build_monthly_cash_flow_model(
            company_data=seed,
            months=months,
            start_period=start_period,
            revenue_trajectory=trajectory,
        )

        # 5. Override non-revenue metrics if spec defines them.
        # Map common LLM metric names to cascade keys.
        _METRIC_ALIASES = {
            "opex": "total_opex",
            "operating_expenses": "total_opex",
            "rd": "rd_spend",
            "r_and_d": "rd_spend",
            "sales_marketing": "sm_spend",
            "s_and_m": "sm_spend",
            "general_admin": "ga_spend",
            "g_and_a": "ga_spend",
            "fcf": "free_cash_flow",
            "cash": "cash_balance",
            "gp": "gross_profit",
        }
        for i, month in enumerate(forecast):
            for metric, values_arr in context.items():
                if metric == "revenue" or metric.startswith("_"):
                    continue
                # Resolve alias to cascade key
                cascade_key = _METRIC_ALIASES.get(metric, metric)
                if i < len(values_arr) and cascade_key in month:
                    month[cascade_key] = float(values_arr[i])
            # Recompute derived fields
            _recompute_derived(month)

        # 6. Apply funding events
        for event in spec.funding_events:
            month_idx = _period_diff(start_period, event.period)
            if 0 <= month_idx < len(forecast):
                forecast[month_idx]["cash_balance"] = (
                    forecast[month_idx].get("cash_balance", 0) + event.amount
                )
                if event.type == "debt":
                    rate = event.terms.get("interest_rate", 0.10)
                    monthly_payment = event.amount * rate / 12
                    for j in range(month_idx, len(forecast)):
                        forecast[j]["debt_service"] = (
                            forecast[j].get("debt_service", 0) + monthly_payment
                        )
                # Propagate cash_balance forward after injection
                for j in range(month_idx + 1, len(forecast)):
                    fcf = forecast[j].get("free_cash_flow", 0)
                    prev_cash = forecast[j - 1].get("cash_balance", 0)
                    forecast[j]["cash_balance"] = prev_cash + fcf

        # 7. Confidence bands from priors (Monte Carlo)
        bands = self._generate_confidence_bands(spec, company_data, months, start_period)

        # 8. Check milestones
        milestone_results = []
        for ms in spec.milestones:
            idx = _period_diff(start_period, ms.period)
            if 0 <= idx < len(forecast):
                actual_val = forecast[idx].get(ms.metric, 0)
                milestone_results.append({
                    "period": ms.period,
                    "metric": ms.metric,
                    "target": ms.target,
                    "label": ms.label,
                    "actual": actual_val,
                    "hit": actual_val >= ms.target,
                    "gap": ms.target - actual_val,
                })

        # 9. Compute cascade ripple — how each curve propagates through P&L
        cascade_ripple = self._compute_cascade_ripple(
            spec, context, forecast, start_period
        )

        # Convert context arrays to lists for serialization
        curves_out = {
            k: v.tolist() for k, v in context.items() if not k.startswith("_")
        }

        return ExecutionResult(
            model_id=spec.model_id,
            narrative=spec.narrative,
            event_chain=spec.event_chain,          # pass through for frontend
            forecast=forecast,
            confidence_bands=bands,
            cascade_ripple=cascade_ripple,          # new: how changes ripple
            milestones=milestone_results,
            curves=curves_out,
            spec=spec,
        )

    # ------------------------------------------------------------------
    # Cascade ripple — how each metric change propagates through P&L
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_cascade_ripple(
        spec: ModelSpec,
        context: Dict[str, np.ndarray],
        forecast: List[Dict[str, Any]],
        start_period: str,
    ) -> Dict[str, List[Dict[str, float]]]:
        """Compare each metric's curve vs a flat baseline to show deltas.

        Returns metric → [{period, delta, source}] for the stacked bar chart.
        The 'source' traces back to the event chain or curve type.
        """
        cascade_metrics = [
            "revenue", "cogs", "gross_profit", "total_opex",
            "ebitda", "free_cash_flow", "cash_balance",
        ]
        ripple: Dict[str, List[Dict[str, float]]] = {}

        for metric in cascade_metrics:
            if metric not in context and not forecast:
                continue

            entries = []
            for i, month in enumerate(forecast):
                period = month.get("period", _period_add(start_period, i))
                current = month.get(metric, 0)

                # Baseline: first period's value held flat
                baseline = forecast[0].get(metric, 0) if forecast else 0
                delta = current - baseline

                if abs(delta) > 0.01:
                    entries.append({
                        "period": period,
                        "delta": round(delta, 2),
                        "value": round(current, 2),
                    })

            if entries:
                ripple[metric] = entries

        return ripple

    # ------------------------------------------------------------------
    # Confidence bands via prior perturbation
    # ------------------------------------------------------------------

    def _generate_confidence_bands(
        self,
        spec: ModelSpec,
        company_data: Dict[str, Any],
        months: int,
        start_period: str,
        n_samples: int = 200,
    ) -> Dict[str, List[float]]:
        """Monte Carlo over prior distributions for belief-weighted bands.

        Uses the same MonteCarloEngine pattern: perturb → execute → percentiles.
        But perturbs curve PARAMETERS (not drivers) based on PriorSpec confidence.
        """
        x = np.arange(months, dtype=float)
        # Track samples for all metrics the spec defines
        metric_samples: Dict[str, list] = {}

        for _ in range(n_samples):
            perturbed = self._perturb_spec(spec)
            # Quick execute: just curve evaluation, no full cascade
            context: Dict[str, np.ndarray] = {}
            for metric in _topo_sort(perturbed.curves):
                context[metric] = evaluate_curve(perturbed.curves[metric], x, context)
            for metric, vals in context.items():
                if metric.startswith("_"):
                    continue
                metric_samples.setdefault(metric, []).append(vals.tolist())

        if not metric_samples:
            return {}

        bands: Dict[str, List[float]] = {}
        for metric, samples_list in metric_samples.items():
            arr = np.array(samples_list)
            bands[f"{metric}_p10"] = np.percentile(arr, 10, axis=0).tolist()
            bands[f"{metric}_p25"] = np.percentile(arr, 25, axis=0).tolist()
            bands[f"{metric}_p50"] = np.percentile(arr, 50, axis=0).tolist()
            bands[f"{metric}_p75"] = np.percentile(arr, 75, axis=0).tolist()
            bands[f"{metric}_p90"] = np.percentile(arr, 90, axis=0).tolist()

        # Backward compat: keep top-level p10-p90 as revenue bands
        if "revenue" in metric_samples:
            arr = np.array(metric_samples["revenue"])
            bands["p10"] = np.percentile(arr, 10, axis=0).tolist()
            bands["p25"] = np.percentile(arr, 25, axis=0).tolist()
            bands["p50"] = np.percentile(arr, 50, axis=0).tolist()
            bands["p75"] = np.percentile(arr, 75, axis=0).tolist()
            bands["p90"] = np.percentile(arr, 90, axis=0).tolist()

        return bands

    def _perturb_spec(self, spec: ModelSpec) -> ModelSpec:
        """Sample from prior distributions to create a perturbed spec."""
        perturbed = spec.model_copy(deep=True)
        for metric, curve in perturbed.curves.items():
            self._perturb_curve(curve)
            for comp in curve.components:
                self._perturb_component(comp)
        return perturbed

    @staticmethod
    def _perturb_curve(curve: CurveSpec):
        """Perturb a curve's params based on its prior confidence."""
        if not curve.prior:
            return
        conf = curve.prior.confidence
        noise_scale = (1 - conf) * 0.5  # confidence 0.5 → ±25% noise
        for key, val in curve.params.items():
            if isinstance(val, (int, float)):
                noise = np.random.normal(0, noise_scale * max(abs(val), 1e-6))
                new_val = val + noise
                if curve.prior.floor is not None:
                    new_val = max(curve.prior.floor, new_val)
                if curve.prior.ceiling is not None:
                    new_val = min(curve.prior.ceiling, new_val)
                curve.params[key] = new_val

    @staticmethod
    def _perturb_component(comp: ComponentSpec):
        """Perturb a component's params based on its prior confidence."""
        if not comp.prior:
            return
        conf = comp.prior.confidence
        noise_scale = (1 - conf) * 0.5
        for key, val in comp.params.items():
            if isinstance(val, (int, float)):
                noise = np.random.normal(0, noise_scale * max(abs(val), 1e-6))
                new_val = val + noise
                if comp.prior.floor is not None:
                    new_val = max(comp.prior.floor, new_val)
                if comp.prior.ceiling is not None:
                    new_val = min(comp.prior.ceiling, new_val)
                comp.params[key] = new_val


# ---------------------------------------------------------------------------
# Derived field recomputation
# ---------------------------------------------------------------------------

def _recompute_derived(month: Dict[str, Any]):
    """Recompute gross_profit, ebitda, fcf after metric overrides."""
    rev = month.get("revenue", 0)
    cogs = month.get("cogs", 0)
    month["gross_profit"] = rev - cogs
    month["gross_margin"] = (rev - cogs) / rev if rev else 0

    opex = month.get("total_opex", 0)
    month["ebitda"] = month["gross_profit"] - opex
    month["ebitda_margin"] = month["ebitda"] / rev if rev else 0

    capex = month.get("capex", 0)
    debt_svc = month.get("debt_service", 0)
    tax = month.get("tax_expense", 0)
    month["free_cash_flow"] = month["ebitda"] - capex - debt_svc - tax


# ---------------------------------------------------------------------------
# Bayesian updating when new actuals arrive
# ---------------------------------------------------------------------------

def update_model_with_actuals(
    spec: ModelSpec,
    new_actuals: Dict[str, float],
    current_period_idx: int,
) -> ModelSpec:
    """Bayesian-style update: compare prediction to reality, adjust confidence.

    Call this when a new month of actuals lands.
    Returns updated spec (mutated in place for efficiency).
    """
    x_point = np.array([float(current_period_idx)])
    context: Dict[str, np.ndarray] = {}

    for metric, curve in spec.curves.items():
        predicted_arr = evaluate_curve(curve, x_point, context)
        context[metric] = predicted_arr

        if curve.prior and metric in new_actuals:
            predicted = float(predicted_arr[0])
            actual = new_actuals[metric]
            error_pct = abs(actual - predicted) / max(abs(predicted), 1)

            if error_pct < 0.05:
                curve.prior.confidence = min(0.95, curve.prior.confidence + 0.05)
            elif error_pct < 0.15:
                pass
            else:
                curve.prior.confidence = max(0.3, curve.prior.confidence - 0.10)
                spec.metadata.setdefault("needs_refit", []).append(metric)

    return spec
