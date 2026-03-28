"""
Model Spec Executor
Turns a ModelSpec into monthly arrays, feeds into LiquidityManagementService.

Bridge between:
  LLM-constructed ModelSpec → LiquidityManagementService (via revenue_trajectory)

Reuses:
  - LiquidityManagementService.build_liquidity_model() for P&L cascade
  - MonteCarloEngine patterns for confidence bands
  - DriverRegistry keys for driver_overrides passthrough
  - date_utils for period arithmetic
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
    """Execute a ModelSpec → full P&L forecast via LiquidityManagementService."""

    # Metrics that LMS produces and we can modify
    _KNOWN_METRICS = {
        "revenue", "cogs", "gross_profit", "rd_spend", "sm_spend", "ga_spend",
        "total_opex", "ebitda", "capex", "free_cash_flow", "cash_balance",
        "debt_service", "tax_expense", "headcount",
    }

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

    def execute(
        self,
        spec: ModelSpec,
        company_data: Dict[str, Any],
        months: int = 24,
        start_period: Optional[str] = None,
        parent_result: Optional[ExecutionResult] = None,
        company_id: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute a ModelSpec and return full forecast with confidence bands.

        Uses event-chain-driven execution when the spec has an event chain
        with causal links. Falls back to curve evaluation for legacy specs.
        """
        if not start_period:
            today = date.today()
            start_period = f"{today.year}-{today.month:02d}"

        if not company_id:
            logger.warning("ModelSpecExecutor: no company_id — cannot build forecast")
            return ExecutionResult(model_id=spec.model_id, forecast=[], curves={})

        # Choose execution path: event chain (preferred) vs curves (legacy)
        has_event_chain = (
            spec.event_chain
            and spec.event_chain.links
        )

        if has_event_chain:
            forecast, applied_impacts = self._execute_from_event_chain(
                spec, company_data, months, start_period, company_id,
            )
        else:
            forecast, applied_impacts = self._execute_from_curves(
                spec, company_data, months, start_period, company_id,
                parent_result,
            )

        # Apply funding events (shared by both paths)
        self._apply_funding_events(spec, forecast, start_period)

        # Re-propagate cash_balance cumulatively after ALL modifications
        _propagate_cash_balance(forecast)

        # Confidence bands from priors (Monte Carlo)
        bands = self._generate_confidence_bands(spec, company_data, months, start_period)

        # Check milestones
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

        # Compute cascade ripple
        cascade_ripple = self._compute_cascade_ripple(
            spec, {}, forecast, start_period
        )

        # Extract per-month metric values for charting (works for both paths)
        curves_out: Dict[str, List[float]] = {}
        if isinstance(applied_impacts, dict):
            # Event chain path: extract modified metric values from forecast
            impacted_metrics = set()
            for k, v in applied_impacts.items():
                if isinstance(v, list) and v and isinstance(v[0], dict):
                    impacted_metrics.add(k)
                else:
                    curves_out[k] = v  # Already float lists (curve path)
            for metric in impacted_metrics:
                curves_out[metric] = [
                    m.get(metric, 0) for m in forecast
                ]

        return ExecutionResult(
            model_id=spec.model_id,
            narrative=spec.narrative,
            event_chain=spec.event_chain,
            forecast=forecast,
            confidence_bands=bands,
            cascade_ripple=cascade_ripple,
            milestones=milestone_results,
            curves=curves_out,
            spec=spec,
        )

    # ------------------------------------------------------------------
    # Event-chain-driven execution (primary path)
    # ------------------------------------------------------------------

    def _execute_from_event_chain(
        self,
        spec: ModelSpec,
        company_data: Dict[str, Any],
        months: int,
        start_period: str,
        company_id: str,
    ) -> tuple:
        """Execute using event chain: base LMS forecast + event-driven modifications.

        Flow:
        1. Resolve event chain → which events fire and when
        2. Run LMS for base forecast (realistic shape from actual drivers)
        3. Walk resolved events chronologically
        4. Each causal link targeting a metric modifies the forecast
        5. Recompute derived fields after each metric modification
        6. Cash balance re-propagated separately after all modifications

        Returns (forecast, applied_impacts_dict).
        """
        chain = spec.event_chain

        # 1. Resolve event timing — account for triggers, blocks, shifts
        resolved_events = self._resolve_event_chain(chain, start_period)

        # 2. Build base forecast from LMS using actual company drivers
        seed = dict(company_data)
        seed.update(spec.driver_overrides)

        from app.services.liquidity_management_service import LiquidityManagementService
        lms = LiquidityManagementService()
        lms_result = lms.build_liquidity_model(
            company_id=company_id,
            months=months,
            start_period=start_period,
            scenario_overrides=seed,
        )
        forecast = lms_result.get("monthly", [])

        if not forecast:
            return forecast, {}

        # 3. Collect metric-targeting links with resolved timing
        metric_impacts = self._collect_metric_impacts(
            chain, resolved_events, start_period, months,
        )

        # 4. Apply impacts chronologically, recompute cascade after each
        applied = {}  # metric → list of monthly values (for charting)
        for impact in metric_impacts:
            metric = impact["metric"]
            month_idx = impact["month_idx"]
            effect = impact["effect"]
            magnitude = impact["magnitude"]
            probability = impact["probability"]
            duration = impact["duration"]

            # Weight by event probability
            effective_mag = magnitude * probability

            if effect in ("amplifies", "dampens"):
                # Percentage modification from month_idx onward (or for duration)
                end_idx = min(month_idx + duration, len(forecast)) if duration else len(forecast)
                for i in range(month_idx, end_idx):
                    old_val = forecast[i].get(metric, 0)
                    forecast[i][metric] = old_val * (1 + effective_mag)
                    if metric == "cogs":
                        forecast[i]["_cogs_override"] = True

            elif effect == "scales":
                # Direct multiplier from month_idx onward
                end_idx = min(month_idx + duration, len(forecast)) if duration else len(forecast)
                for i in range(month_idx, end_idx):
                    old_val = forecast[i].get(metric, 0)
                    forecast[i][metric] = old_val * effective_mag
                    if metric == "cogs":
                        forecast[i]["_cogs_override"] = True

            elif effect == "sets_ceiling":
                for i in range(month_idx, len(forecast)):
                    old_val = forecast[i].get(metric, 0)
                    forecast[i][metric] = min(old_val, magnitude)

            elif effect == "sets_floor":
                for i in range(month_idx, len(forecast)):
                    old_val = forecast[i].get(metric, 0)
                    forecast[i][metric] = max(old_val, magnitude)

            # Recompute the full cascade for affected months
            end = min(month_idx + (duration or months), len(forecast))
            for i in range(month_idx, end):
                _recompute_derived(forecast[i])

            # Track what we applied for charting
            applied.setdefault(metric, []).append({
                "event_id": impact["event_id"],
                "effect": effect,
                "magnitude": effective_mag,
                "month_idx": month_idx,
                "reasoning": impact["reasoning"],
            })

        # Also apply macro shocks directly as event impacts
        for shock in spec.macro_shocks:
            for metric, imp in shock.impacts.items():
                resolved_metric = self._METRIC_ALIASES.get(metric, metric)
                start_month = imp.get("start_month", 0)
                mag = imp.get("magnitude", 0) * shock.probability
                dur = imp.get("duration_months", 6)
                recovery = imp.get("recovery", "gradual")

                for i in range(start_month, min(start_month + dur, len(forecast))):
                    progress = (i - start_month) / max(dur, 1)
                    if recovery == "gradual":
                        factor = 1 + mag * (1 - progress)
                    else:
                        factor = 1 + mag

                    old_val = forecast[i].get(resolved_metric, 0)
                    forecast[i][resolved_metric] = old_val * factor
                    _recompute_derived(forecast[i])

        return forecast, applied

    def _resolve_event_chain(
        self,
        chain,
        start_period: str,
    ) -> Dict[str, Dict[str, Any]]:
        """Resolve which events fire and their final timing.

        Handles triggers (event A causes event B), blocks (A prevents B),
        and shifts_timing (A delays B).

        Returns: {event_id: {fired: bool, month_idx: int, probability: float}}
        """
        resolved = {}

        # Initialize all events with base timing
        for ev in chain.events:
            month_idx = 0
            if ev.timing:
                try:
                    month_idx = _period_diff(start_period, ev.timing)
                except Exception:
                    month_idx = 0
            month_idx = max(0, month_idx)

            resolved[ev.id] = {
                "fired": True,  # assume fires unless blocked
                "month_idx": month_idx,
                "probability": ev.probability,
                "duration_months": ev.duration_months,
            }

        # Walk event-to-event links to resolve triggers/blocks/shifts
        for link in chain.links:
            src = link.source
            tgt = link.target

            # Only process event→event links here
            if src not in resolved or tgt not in resolved:
                continue

            src_info = resolved[src]
            if not src_info["fired"]:
                continue

            if link.effect == "triggers":
                # Source triggers target — target fires after delay
                resolved[tgt]["fired"] = True
                resolved[tgt]["month_idx"] = max(
                    resolved[tgt]["month_idx"],
                    src_info["month_idx"] + link.delay_months,
                )

            elif link.effect == "blocks":
                # Source blocks target — target doesn't fire
                resolved[tgt]["fired"] = False

            elif link.effect == "shifts_timing":
                # Source delays target by delay_months
                resolved[tgt]["month_idx"] += link.delay_months

        return resolved

    def _collect_metric_impacts(
        self,
        chain,
        resolved_events: Dict[str, Dict[str, Any]],
        start_period: str,
        months: int,
    ) -> List[Dict[str, Any]]:
        """Convert causal links into chronological metric modifications.

        Filters to links where target is a known metric and source event fired.
        Returns sorted list of impacts.
        """
        impacts = []

        for link in chain.links:
            # Resolve target metric
            target_metric = self._METRIC_ALIASES.get(link.target, link.target)
            if target_metric not in self._KNOWN_METRICS:
                continue  # event→event link, handled in resolution

            # Find source event
            src_info = resolved_events.get(link.source)
            if not src_info or not src_info["fired"]:
                continue

            impact_month = src_info["month_idx"] + link.delay_months
            if impact_month < 0 or impact_month >= months:
                continue

            impacts.append({
                "event_id": link.source,
                "metric": target_metric,
                "effect": link.effect,
                "magnitude": link.magnitude or 0,
                "probability": src_info["probability"],
                "month_idx": impact_month,
                "duration": src_info.get("duration_months") or 0,
                "reasoning": link.reasoning,
            })

        # Sort chronologically so earlier impacts compound into later ones
        impacts.sort(key=lambda x: x["month_idx"])
        return impacts

    # ------------------------------------------------------------------
    # Legacy curve-based execution (fallback for specs without event chain)
    # ------------------------------------------------------------------

    def _execute_from_curves(
        self,
        spec: ModelSpec,
        company_data: Dict[str, Any],
        months: int,
        start_period: str,
        company_id: str,
        parent_result: Optional[ExecutionResult] = None,
    ) -> tuple:
        """Legacy path: evaluate curves → override LMS forecast.

        Kept for backward compatibility with existing ModelSpecs that
        use curve definitions instead of event chain links.
        """
        x = np.arange(months, dtype=float)
        context: Dict[str, np.ndarray] = {}

        if parent_result and parent_result.curves:
            context["_parent_curves"] = parent_result.curves

        # Evaluate each metric's curve in dependency order
        eval_order = _topo_sort(spec.curves)
        for metric in eval_order:
            curve = spec.curves[metric]
            try:
                values = evaluate_curve(curve, x, context)
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(
                    "Curve evaluation failed for '%s' (type=%s): %s — using zeros",
                    metric, curve.type, e,
                )
                values = np.zeros_like(x, dtype=float)

            # Apply macro shocks (probability-weighted)
            for shock in spec.macro_shocks:
                if metric in shock.impacts:
                    imp = shock.impacts[metric]
                    from app.services.model_spec_schema import ModifierSpec
                    shock_mod = ModifierSpec(type="shock", params={
                        "start_month": imp.get("start_month", 0),
                        "magnitude": imp.get("magnitude", 0) * shock.probability,
                        "duration_months": imp.get("duration_months", 6),
                        "recovery": imp.get("recovery", "gradual"),
                    })
                    values = _apply_modifiers(values, x, [shock_mod])

            context[metric] = values

        # Build revenue trajectory
        revenue = context.get("revenue")
        trajectory = None
        if revenue is not None:
            trajectory = [
                {"period": _period_add(start_period, i), "revenue": float(revenue[i])}
                for i in range(months)
            ]

        # Run LMS
        seed = dict(company_data)
        seed.update(spec.driver_overrides)

        from app.services.liquidity_management_service import LiquidityManagementService
        lms = LiquidityManagementService()
        if trajectory:
            seed["_revenue_trajectory"] = trajectory
        lms_result = lms.build_liquidity_model(
            company_id=company_id,
            months=months,
            start_period=start_period,
            scenario_overrides=seed,
        )
        forecast = lms_result.get("monthly", [])

        # Override non-revenue metrics from curves
        for i, month in enumerate(forecast):
            for metric, values_arr in context.items():
                if metric == "revenue" or metric.startswith("_"):
                    continue
                cascade_key = self._METRIC_ALIASES.get(metric, metric)
                if i < len(values_arr) and cascade_key in month:
                    month[cascade_key] = float(values_arr[i])
            _recompute_derived(month)

        curves_out = {
            k: v.tolist() for k, v in context.items() if not k.startswith("_")
        }
        return forecast, curves_out

    # ------------------------------------------------------------------
    # Funding events (shared by both paths)
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_funding_events(
        spec: ModelSpec,
        forecast: List[Dict[str, Any]],
        start_period: str,
    ):
        """Apply discrete funding events (equity/debt injections)."""
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
                        _recompute_derived(forecast[j])

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
    """Recompute the full P&L cascade after metric overrides.

    Chain: revenue → COGS (via gross_margin) → gross_profit → EBITDA → FCF.
    Does NOT touch cash_balance — that requires cumulative propagation
    across months (see _propagate_cash_balance).
    """
    rev = month.get("revenue", 0)
    cogs = month.get("cogs", 0)

    # Re-derive COGS from gross_margin to maintain ratio consistency,
    # but only if gross_margin looks like a stored ratio (not yet recomputed).
    # Skip if _cogs_override flag is set (event directly targeted COGS).
    gm = month.get("gross_margin")
    if gm and isinstance(gm, (int, float)) and 0 < gm < 1 and not month.get("_cogs_override"):
        cogs = rev * (1 - gm)
        month["cogs"] = cogs

    month["gross_profit"] = rev - cogs
    month["gross_margin"] = (rev - cogs) / rev if rev else 0

    opex = month.get("total_opex", 0)
    month["ebitda"] = month["gross_profit"] - opex
    month["ebitda_margin"] = month["ebitda"] / rev if rev else 0

    capex = month.get("capex", 0)
    debt_svc = month.get("debt_service", 0)
    tax = month.get("tax_expense", 0)
    month["free_cash_flow"] = month["ebitda"] - capex - debt_svc - tax


def _propagate_cash_balance(forecast: List[Dict[str, Any]]):
    """Re-propagate cash_balance cumulatively across all months.

    cash_balance[0] stays as-is (initial cash from LMS).
    Each subsequent month: cash_balance[i] = cash_balance[i-1] + free_cash_flow[i].
    Also recomputes runway_months.
    """
    if not forecast:
        return

    for i in range(1, len(forecast)):
        prev_cash = forecast[i - 1].get("cash_balance", 0)
        fcf = forecast[i].get("free_cash_flow", 0)
        forecast[i]["cash_balance"] = prev_cash + fcf

    # Recompute runway for each month
    for month in forecast:
        cash = month.get("cash_balance", 0)
        fcf = month.get("free_cash_flow", 0)
        if fcf < 0:
            month["runway_months"] = round(cash / (-fcf), 1)
        else:
            month["runway_months"] = 999


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
