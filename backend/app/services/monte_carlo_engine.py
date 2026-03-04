"""
Monte Carlo Engine
Wraps build_monthly_cash_flow_model() in a sampling loop.

Each driver gets a probability distribution derived from actual data
(actuals variance, not hardcoded sigmas). When actuals aren't available,
uses conservative distribution defaults.

Usage:
    engine = MonteCarloEngine()
    result = engine.simulate(company_id, iterations=1000)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class DistSpec:
    """Distribution specification for a driver."""
    dist_type: str  # "normal" | "lognormal" | "beta" | "uniform"
    mu: float = 0.0
    sigma: float = 0.1
    clip_low: Optional[float] = None
    clip_high: Optional[float] = None
    # For beta distribution
    alpha: float = 2.0
    beta_param: float = 30.0


@dataclass
class MonteCarloResult:
    """Results of Monte Carlo simulation."""
    iterations: int
    months: int
    # Percentile trajectories: {metric: {p5: [...], p25: [...], p50: [...], p75: [...], p95: [...]}}
    trajectory_percentiles: Dict[str, Dict[str, List[float]]] = field(default_factory=dict)
    # Final month distribution stats
    final_distribution: Dict[str, Dict[str, float]] = field(default_factory=dict)
    # Value at Risk: cash position at p5 at 12 months
    var_cash_12m: Optional[float] = None
    # Runway distribution
    runway_distribution: Dict[str, float] = field(default_factory=dict)
    # Break-even probability
    break_even_probability: Optional[float] = None
    # Driver sensitivity: ranked by correlation to cash variance
    driver_sensitivity: List[Dict[str, Any]] = field(default_factory=list)
    # Periods metadata
    periods: List[str] = field(default_factory=list)


# Default distribution specs — only used when we can't derive from actuals
_DEFAULT_DISTRIBUTIONS: Dict[str, DistSpec] = {
    "revenue_growth": DistSpec(
        dist_type="normal", sigma=0.15,
        clip_low=-0.5, clip_high=3.0,
    ),
    "churn_rate": DistSpec(
        dist_type="beta", alpha=2, beta_param=30,
    ),
    "nrr": DistSpec(
        dist_type="normal", sigma=0.10,
        clip_low=0.8, clip_high=1.5,
    ),
    "gross_margin": DistSpec(
        dist_type="normal", sigma=0.08,
        clip_low=0.2, clip_high=0.95,
    ),
    "cac": DistSpec(
        dist_type="lognormal", sigma=0.3,
    ),
    "payroll_cost_per_head": DistSpec(
        dist_type="lognormal", sigma=0.15,
    ),
    "sales_cycle": DistSpec(
        dist_type="normal", sigma=1.5,
        clip_low=0, clip_high=24,
    ),
}

# Drivers to perturb in Monte Carlo
_MC_DRIVERS = [
    "revenue_growth", "gross_margin", "churn_rate", "nrr",
    "burn_rate", "headcount_change", "cac",
]


class MonteCarloEngine:

    def simulate(
        self,
        company_id: str,
        iterations: int = 1000,
        months: int = 24,
        driver_overrides: Optional[Dict[str, DistSpec]] = None,
        branch_id: Optional[str] = None,
    ) -> MonteCarloResult:
        """Run Monte Carlo simulation over the cash flow model.

        For each iteration:
        1. Sample driver values from distributions (derived from actuals)
        2. Apply to company_data
        3. Run build_monthly_cash_flow_model()
        4. Extract metrics per month

        Returns percentile bands, VaR, runway distribution, driver sensitivity.
        """
        from app.services.actuals_ingestion import seed_forecast_from_actuals
        from app.services.cash_flow_planning_service import CashFlowPlanningService
        from app.services.scenario_branch_service import ScenarioBranchService

        cfp = CashFlowPlanningService()

        # Get base company data from actuals
        base_data = seed_forecast_from_actuals(company_id)
        if not base_data.get("revenue") and not base_data.get("burn_rate"):
            logger.warning("MC: no actuals for %s", company_id)
            return MonteCarloResult(iterations=0, months=months)

        # If branch specified, merge branch assumptions
        if branch_id:
            sbs = ScenarioBranchService()
            chain = sbs.get_ancestor_chain(branch_id)
            if chain:
                merged = sbs.merge_assumptions(chain)
                base_data = sbs._apply_overrides({**base_data}, merged)

        # Build distribution specs from actual data where possible
        dist_specs = _build_distributions(company_id, base_data, driver_overrides)

        # Storage for all iterations
        metrics_to_track = [
            "revenue", "ebitda", "cash_balance", "runway_months",
            "free_cash_flow", "total_opex",
        ]
        all_trajectories: Dict[str, List[List[float]]] = {
            m: [] for m in metrics_to_track
        }
        driver_samples: Dict[str, List[float]] = {d: [] for d in _MC_DRIVERS}
        final_cash_values: List[float] = []

        rng = np.random.default_rng(seed=None)

        for _ in range(iterations):
            # Sample driver values
            sampled_data = {**base_data}
            for driver_id in _MC_DRIVERS:
                spec = dist_specs.get(driver_id)
                if not spec:
                    continue

                base_val = base_data.get(driver_id) or base_data.get(
                    _DRIVER_TO_DATA_KEY.get(driver_id, driver_id)
                )
                if base_val is None:
                    continue

                sampled_val = _sample_from_dist(rng, spec, float(base_val))
                data_key = _DRIVER_TO_DATA_KEY.get(driver_id, driver_id)
                sampled_data[data_key] = sampled_val
                driver_samples[driver_id].append(sampled_val)

            # Disable seasonality for MC (already captured in base)
            sampled_data["seasonality_factors"] = "none"

            # Run forecast
            try:
                forecast = cfp.build_monthly_cash_flow_model(
                    sampled_data, months=months,
                )
            except Exception:
                continue

            if not forecast:
                continue

            # Extract metric trajectories
            for metric in metrics_to_track:
                trajectory = [m.get(metric, 0) or 0 for m in forecast]
                all_trajectories[metric].append(trajectory)

            final_cash = forecast[-1].get("cash_balance", 0) or 0
            final_cash_values.append(final_cash)

        actual_iterations = len(all_trajectories["revenue"])
        if actual_iterations == 0:
            return MonteCarloResult(iterations=0, months=months)

        # Compute percentiles
        percentile_levels = [5, 25, 50, 75, 95]
        trajectory_percentiles: Dict[str, Dict[str, List[float]]] = {}

        for metric in metrics_to_track:
            arr = np.array(all_trajectories[metric])
            pcts: Dict[str, List[float]] = {}
            for p in percentile_levels:
                pcts[f"p{p}"] = np.percentile(arr, p, axis=0).tolist()
            trajectory_percentiles[metric] = pcts

        # Final distribution stats
        final_distribution: Dict[str, Dict[str, float]] = {}
        for metric in metrics_to_track:
            arr = np.array(all_trajectories[metric])
            finals = arr[:, -1]
            final_distribution[metric] = {
                "mean": float(np.mean(finals)),
                "median": float(np.median(finals)),
                "std": float(np.std(finals)),
                "p5": float(np.percentile(finals, 5)),
                "p25": float(np.percentile(finals, 25)),
                "p75": float(np.percentile(finals, 75)),
                "p95": float(np.percentile(finals, 95)),
            }

        # VaR: cash at p5 at 12 months (or final if < 12)
        cash_arr = np.array(all_trajectories["cash_balance"])
        var_month = min(11, months - 1)
        var_cash_12m = float(np.percentile(cash_arr[:, var_month], 5))

        # Runway distribution
        runway_arr = np.array(all_trajectories["runway_months"])
        runway_finals = runway_arr[:, -1]
        runway_distribution = {
            "median": float(np.median(runway_finals)),
            "p5": float(np.percentile(runway_finals, 5)),
            "p25": float(np.percentile(runway_finals, 25)),
            "p75": float(np.percentile(runway_finals, 75)),
            "p95": float(np.percentile(runway_finals, 95)),
        }

        # Break-even probability: % of iterations where final EBITDA > 0
        ebitda_arr = np.array(all_trajectories["ebitda"])
        ebitda_finals = ebitda_arr[:, -1]
        break_even_probability = float(np.mean(ebitda_finals > 0))

        # Driver sensitivity: correlation of each driver to final cash
        driver_sensitivity = _compute_driver_sensitivity(
            driver_samples, final_cash_values,
        )

        # Extract period labels from a sample forecast
        periods = []
        try:
            sample = cfp.build_monthly_cash_flow_model(base_data, months=months)
            periods = [m.get("period", "") for m in sample]
        except Exception:
            pass

        return MonteCarloResult(
            iterations=actual_iterations,
            months=months,
            trajectory_percentiles=trajectory_percentiles,
            final_distribution=final_distribution,
            var_cash_12m=var_cash_12m,
            runway_distribution=runway_distribution,
            break_even_probability=break_even_probability,
            driver_sensitivity=driver_sensitivity,
            periods=periods,
        )


# ---------------------------------------------------------------------------
# Distribution building — from actuals, not hardcoded
# ---------------------------------------------------------------------------

# Map driver_id to company_data key
_DRIVER_TO_DATA_KEY = {
    "revenue_growth": "growth_rate",
    "gross_margin": "gross_margin",
    "churn_rate": "churn_rate",
    "nrr": "nrr",
    "burn_rate": "burn_rate",
    "headcount_change": "headcount_change",
    "cac": "cac",
    "payroll_cost_per_head": "cost_per_head",
}


def _build_distributions(
    company_id: str,
    base_data: Dict[str, Any],
    overrides: Optional[Dict[str, DistSpec]],
) -> Dict[str, DistSpec]:
    """Build distribution specs from actual data variance where possible.

    For each driver:
    1. If user provided an override, use it
    2. If we have actuals history, compute sigma from actual variance
    3. Fall back to default distribution
    """
    from app.services.actuals_ingestion import get_actuals_for_forecast

    specs: Dict[str, DistSpec] = {}

    for driver_id in _MC_DRIVERS:
        # User override takes priority
        if overrides and driver_id in overrides:
            specs[driver_id] = overrides[driver_id]
            continue

        # Try to derive from actuals
        actuals_category = _DRIVER_TO_ACTUALS_CATEGORY.get(driver_id)
        if actuals_category:
            try:
                series = get_actuals_for_forecast(company_id, actuals_category, months=24)
                if len(series) >= 6:
                    values = [e["amount"] for e in series if e.get("amount")]
                    if len(values) >= 6:
                        mean_val = sum(values) / len(values)
                        if mean_val != 0:
                            # Coefficient of variation → sigma
                            variance = sum((v - mean_val) ** 2 for v in values) / len(values)
                            cv = (variance ** 0.5) / abs(mean_val)
                            specs[driver_id] = DistSpec(
                                dist_type="normal",
                                sigma=min(cv, 0.5),  # cap at 50%
                                clip_low=_DEFAULT_DISTRIBUTIONS.get(
                                    driver_id, DistSpec()
                                ).clip_low,
                                clip_high=_DEFAULT_DISTRIBUTIONS.get(
                                    driver_id, DistSpec()
                                ).clip_high,
                            )
                            continue
            except Exception:
                pass

        # Fall back to default
        if driver_id in _DEFAULT_DISTRIBUTIONS:
            specs[driver_id] = _DEFAULT_DISTRIBUTIONS[driver_id]

    return specs


_DRIVER_TO_ACTUALS_CATEGORY = {
    "revenue_growth": "revenue",  # will compute growth rate from series
    "gross_margin": None,  # derived, not direct actuals
    "burn_rate": "burn_rate",
    "headcount_change": "headcount",
}


def _sample_from_dist(rng: np.random.Generator, spec: DistSpec, base: float) -> float:
    """Sample a value from the specified distribution around the base value."""
    if spec.dist_type == "normal":
        val = rng.normal(base, abs(base * spec.sigma) if base != 0 else spec.sigma)
    elif spec.dist_type == "lognormal":
        if base <= 0:
            base = 1.0
        log_mu = math.log(base)
        val = rng.lognormal(log_mu, spec.sigma)
    elif spec.dist_type == "beta":
        # Beta distribution: good for rates bounded [0, 1]
        val = rng.beta(spec.alpha, spec.beta_param)
    elif spec.dist_type == "uniform":
        low = spec.clip_low if spec.clip_low is not None else base * 0.5
        high = spec.clip_high if spec.clip_high is not None else base * 1.5
        val = rng.uniform(low, high)
    else:
        val = base

    # Apply clips
    if spec.clip_low is not None:
        val = max(val, spec.clip_low)
    if spec.clip_high is not None:
        val = min(val, spec.clip_high)

    return float(val)


def _compute_driver_sensitivity(
    driver_samples: Dict[str, List[float]],
    final_cash: List[float],
) -> List[Dict[str, Any]]:
    """Rank drivers by their correlation to final cash balance."""
    if len(final_cash) < 10:
        return []

    cash_arr = np.array(final_cash)
    results = []

    for driver_id, samples in driver_samples.items():
        if len(samples) != len(final_cash) or len(samples) < 10:
            continue

        driver_arr = np.array(samples)
        # Skip if no variance
        if np.std(driver_arr) < 1e-10:
            continue

        try:
            corr = np.corrcoef(driver_arr, cash_arr)[0, 1]
            if np.isnan(corr):
                continue
            results.append({
                "driver_id": driver_id,
                "correlation": round(float(corr), 4),
                "abs_correlation": round(abs(float(corr)), 4),
                "direction": "positive" if corr > 0 else "negative",
            })
        except Exception:
            continue

    results.sort(key=lambda x: x["abs_correlation"], reverse=True)
    return results


def result_to_dict(result: MonteCarloResult) -> Dict[str, Any]:
    """Convert MC result to JSON-serializable dict for API response."""
    return {
        "iterations": result.iterations,
        "months": result.months,
        "periods": result.periods,
        "trajectory_percentiles": result.trajectory_percentiles,
        "final_distribution": result.final_distribution,
        "var_cash_12m": result.var_cash_12m,
        "runway_distribution": result.runway_distribution,
        "break_even_probability": result.break_even_probability,
        "driver_sensitivity": result.driver_sensitivity,
    }
