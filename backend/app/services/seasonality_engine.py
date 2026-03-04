"""
Seasonality Engine
Detects seasonal patterns from actuals and applies them to forecasts.

All detection runs on actual company data — no hardcoded patterns used
unless the user explicitly requests industry defaults.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SeasonalPattern:
    """Detected or user-specified seasonal factors."""
    monthly_factors: Dict[int, float]  # {1: 0.85, 2: 0.90, ..., 12: 1.15} — sum to 12.0
    strength: float  # 0-1, how pronounced the seasonality is
    pattern_type: str  # "detected" | "industry_default" | "user_override"
    confidence: float  # 0-1, statistical confidence
    metric: str = "revenue"  # which metric this pattern applies to
    source_periods: int = 0  # how many periods were used for detection


class SeasonalityEngine:

    def detect_pattern(
        self,
        company_id: str,
        metric: str = "revenue",
        min_periods: int = 12,
    ) -> Optional[SeasonalPattern]:
        """Detect seasonal pattern from actual actuals data.

        Method:
        1. Pull 12-24 months of actuals
        2. Detrend using moving average
        3. Compute month-of-year seasonal factors (multiplicative)
        4. Test significance: max/min ratio < 1.1 = not seasonal
        5. Return 12 monthly factors (sum to 12.0)
        """
        from app.services.actuals_ingestion import get_actuals_for_forecast

        series = get_actuals_for_forecast(company_id, metric, months=36)
        if len(series) < min_periods:
            logger.debug(
                "Seasonality: need %d periods, have %d for %s/%s",
                min_periods, len(series), company_id, metric,
            )
            return None

        # Extract (month, amount) pairs
        data_points: List[tuple] = []
        for entry in series:
            period = entry["period"][:7]  # "2025-01"
            amount = entry["amount"]
            if amount is None or amount == 0:
                continue
            try:
                month = int(period.split("-")[1])
                data_points.append((month, amount))
            except (ValueError, IndexError):
                continue

        if len(data_points) < min_periods:
            return None

        # Detrend: compute ratio of each point to its local trend
        # Use centered moving average when we have enough data
        amounts = [dp[1] for dp in data_points]
        trend = _moving_average(amounts, window=min(6, len(amounts) // 2))

        if not trend:
            return None

        # Compute seasonal ratios
        ratios_by_month: Dict[int, List[float]] = {m: [] for m in range(1, 13)}
        for i, (month, amount) in enumerate(data_points):
            if i < len(trend) and trend[i] and trend[i] > 0:
                ratio = amount / trend[i]
                ratios_by_month[month].append(ratio)

        # Average ratios per month
        monthly_factors: Dict[int, float] = {}
        for month in range(1, 13):
            ratios = ratios_by_month[month]
            if ratios:
                monthly_factors[month] = sum(ratios) / len(ratios)
            else:
                monthly_factors[month] = 1.0

        # Normalize so factors sum to 12.0
        factor_sum = sum(monthly_factors.values())
        if factor_sum > 0:
            for month in monthly_factors:
                monthly_factors[month] = monthly_factors[month] * 12.0 / factor_sum

        # Test significance: max/min ratio
        factor_values = [f for f in monthly_factors.values() if f > 0]
        if not factor_values:
            return None

        max_factor = max(factor_values)
        min_factor = min(factor_values)
        ratio = max_factor / min_factor if min_factor > 0 else 1.0

        if ratio < 1.1:
            # Not meaningfully seasonal
            return None

        # Strength: how far the most extreme month deviates from 1.0
        strength = min(1.0, (ratio - 1.0) / 0.5)  # cap at 1.0

        # Confidence: based on number of data points per month
        avg_points_per_month = sum(len(v) for v in ratios_by_month.values()) / 12
        confidence = min(1.0, avg_points_per_month / 2)  # 2+ observations = high

        return SeasonalPattern(
            monthly_factors=monthly_factors,
            strength=round(strength, 3),
            pattern_type="detected",
            confidence=round(confidence, 3),
            metric=metric,
            source_periods=len(data_points),
        )

    def apply_seasonal_factors(
        self,
        monthly_forecast: List[Dict[str, Any]],
        pattern: SeasonalPattern,
        metric_key: str = "revenue",
    ) -> List[Dict[str, Any]]:
        """Apply seasonal factors to a monthly forecast.

        revenue_adjusted = revenue_base * seasonal_factor[month]

        Modifies the forecast in-place and returns it.
        Cascades to downstream P&L metrics (gross_profit, ebitda, etc).
        """
        for month_data in monthly_forecast:
            period = month_data.get("period", "")
            try:
                month_num = int(period.split("-")[1])
            except (ValueError, IndexError):
                continue

            factor = pattern.monthly_factors.get(month_num, 1.0)
            base_value = month_data.get(metric_key, 0) or 0
            adjusted_value = base_value * factor
            month_data[metric_key] = adjusted_value

            # Cascade if applying to revenue
            if metric_key == "revenue":
                delta = adjusted_value - base_value
                cogs_pct = 0
                if base_value and base_value > 0:
                    cogs_pct = (month_data.get("cogs", 0) or 0) / base_value

                month_data["cogs"] = adjusted_value * cogs_pct
                month_data["gross_profit"] = adjusted_value - month_data["cogs"]

                # EBITDA = gross_profit - total_opex (opex stays fixed)
                total_opex = month_data.get("total_opex", 0) or 0
                month_data["ebitda"] = month_data["gross_profit"] - total_opex

                # FCF = EBITDA - capex
                capex = month_data.get("capex", 0) or 0
                month_data["free_cash_flow"] = month_data["ebitda"] - capex

        # Recalculate cumulative cash balance
        _recalc_cash_balance(monthly_forecast)

        return monthly_forecast

    def get_industry_default(self, industry: str) -> Optional[SeasonalPattern]:
        """Get industry default seasonal pattern.

        Only used when explicitly requested — not injected automatically.
        These are reference patterns, not hardcoded assumptions.
        """
        defaults = _INDUSTRY_SEASONAL_DEFAULTS.get(industry.lower())
        if not defaults:
            return None

        return SeasonalPattern(
            monthly_factors=defaults,
            strength=0.5,
            pattern_type="industry_default",
            confidence=0.3,  # low confidence — it's a generic default
            metric="revenue",
        )


def _moving_average(values: List[float], window: int = 3) -> List[float]:
    """Simple centered moving average for detrending."""
    if window < 1 or len(values) < window:
        return values[:]

    result = []
    half = window // 2
    for i in range(len(values)):
        start = max(0, i - half)
        end = min(len(values), i + half + 1)
        segment = values[start:end]
        result.append(sum(segment) / len(segment))
    return result


def _recalc_cash_balance(forecast: List[Dict[str, Any]]) -> None:
    """Recalculate cash_balance from FCF after seasonal adjustment."""
    for i, month in enumerate(forecast):
        if i == 0:
            # First month: keep existing cash or use FCF
            continue
        prev_cash = forecast[i - 1].get("cash_balance", 0) or 0
        fcf = month.get("free_cash_flow", 0) or 0
        month["cash_balance"] = prev_cash + fcf
        # Recalc runway
        net_burn = -(month.get("ebitda", 0) or 0)
        if net_burn > 0:
            month["runway_months"] = month["cash_balance"] / net_burn
        elif month.get("cash_balance", 0) > 0:
            month["runway_months"] = 999  # not burning


# Industry seasonal defaults — reference only, used when explicitly requested
_INDUSTRY_SEASONAL_DEFAULTS = {
    "b2b_saas": {
        1: 0.85, 2: 0.90, 3: 1.05, 4: 0.95, 5: 0.95, 6: 1.05,
        7: 0.85, 8: 0.85, 9: 1.05, 10: 1.05, 11: 1.10, 12: 1.35,
    },
    "ecommerce": {
        1: 0.70, 2: 0.65, 3: 0.75, 4: 0.80, 5: 0.85, 6: 0.90,
        7: 0.85, 8: 0.90, 9: 0.95, 10: 1.05, 11: 1.40, 12: 1.50,
    },
    "enterprise": {
        1: 0.85, 2: 0.85, 3: 1.10, 4: 0.90, 5: 0.90, 6: 1.10,
        7: 0.80, 8: 0.80, 9: 1.10, 10: 0.95, 11: 1.00, 12: 1.15,
    },
    "services": {
        1: 0.80, 2: 0.85, 3: 1.00, 4: 1.05, 5: 1.05, 6: 1.00,
        7: 0.85, 8: 0.80, 9: 1.05, 10: 1.10, 11: 1.10, 12: 1.05,
    },
}
