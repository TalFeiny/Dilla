"""Forecast Explainer — human-readable explanations for forecast methodology and cells."""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ForecastExplainer:
    """Generates human-readable explanations for forecast methodology and individual cells."""

    # ------------------------------------------------------------------
    # Top-level forecast explanation
    # ------------------------------------------------------------------

    def explain_forecast(
        self, method: str, seed_data: Dict, forecast: List[Dict]
    ) -> str:
        """Generate a methodology explanation for an entire forecast.

        Returns a natural-language paragraph describing how the forecast
        was generated, what inputs were used, and key assumptions.
        """
        parts = []
        months = len(forecast)
        revenue = seed_data.get("revenue", 0)
        growth = seed_data.get("growth_rate", 0)
        gm = seed_data.get("gross_margin")
        cash = seed_data.get("cash_balance")
        runway = seed_data.get("runway_months")
        data_quality = seed_data.get("_data_quality", {})
        rev_months = data_quality.get("revenue_months", 0)

        # Method description
        method_desc = {
            "growth_rate": "growth-rate extrapolation with monthly decay",
            "regression": "linear regression on historical actuals",
            "driver_based": "driver-based customer model (ACV x customers x NRR)",
            "seasonal": "growth-rate model with seasonal overlay",
            "budget_pct": "budget achievement-rate projection",
            "manual": "manually specified values",
            "scenario_promoted": "promoted scenario branch",
        }
        parts.append(f"{months}-month forecast using {method_desc.get(method, method)}.")

        # Data source
        if rev_months:
            parts.append(f"Seeded from {rev_months} months of actuals.")
        elif revenue:
            parts.append(f"Seeded from actuals.")

        # Revenue
        if revenue:
            parts.append(f"Base revenue ${revenue:,.0f}/mo growing at {growth:.0%} annual.")

        # Gross margin
        if gm is not None:
            parts.append(f"Gross margin {gm:.0%} from actuals.")

        # Method-specific details
        if method == "regression":
            reg = seed_data.get("_regression_params", {})
            r2 = reg.get("r_squared")
            if r2 is not None:
                parts.append(f"Regression R² = {r2:.2f}.")

        if method == "seasonal":
            seasonal = seed_data.get("_seasonal_factors", {})
            if seasonal:
                parts.append(f"Seasonal factors applied across {len(seasonal)} periods.")

        if method == "driver_based":
            drivers = seed_data.get("_drivers_used", {})
            if drivers:
                driver_list = ", ".join(f"{k}={v}" for k, v in list(drivers.items())[:5])
                parts.append(f"Drivers: {driver_list}.")

        if method == "budget_pct":
            achievement = seed_data.get("_budget_achievement_rate")
            if achievement:
                parts.append(f"Trailing budget achievement rate: {achievement:.0%}.")

        # Cash / Runway
        if cash is not None:
            parts.append(f"Starting cash ${cash:,.0f}.")
        if runway is not None:
            parts.append(f"Runway: {runway:.1f} months at current trajectory.")

        # End-of-forecast snapshot
        if forecast:
            last = forecast[-1]
            end_rev = last.get("revenue", 0)
            end_ebitda = last.get("ebitda", 0)
            end_cash = last.get("cash_balance", 0)
            parts.append(
                f"End of forecast: revenue ${end_rev:,.0f}, "
                f"EBITDA ${end_ebitda:,.0f}, cash ${end_cash:,.0f}."
            )

        return " ".join(parts)

    # ------------------------------------------------------------------
    # Per-cell derivation
    # ------------------------------------------------------------------

    def explain_cell(
        self,
        category: str,
        period: str,
        amount: float,
        method: str,
        seed_data: Dict,
        month_index: int = 0,
    ) -> str:
        """Generate a per-cell derivation string.

        Example: "Revenue 2026-09: $683K = $500K × (1.042)^7 × 1.15 (Q4 seasonal)"
        """
        revenue = seed_data.get("revenue", 0)
        growth = seed_data.get("growth_rate", 0)
        gm = seed_data.get("gross_margin")

        if category == "revenue":
            return self._explain_revenue_cell(
                period, amount, revenue, growth, method, seed_data, month_index
            )
        elif category == "cogs":
            return self._explain_cogs_cell(period, amount, gm)
        elif category in ("opex_rd", "opex_sm", "opex_ga"):
            return self._explain_opex_cell(category, period, amount)
        elif category == "gross_profit":
            return f"Gross Profit {period}: ${amount:,.0f} = Revenue - COGS"
        elif category == "ebitda":
            return f"EBITDA {period}: ${amount:,.0f} = Gross Profit - Total OpEx"
        elif category == "cash_balance":
            return f"Cash {period}: ${amount:,.0f} = Prior cash + Free Cash Flow"
        elif category == "opex_total":
            return f"Total OpEx {period}: ${amount:,.0f} = R&D + S&M + G&A"
        else:
            return f"{category} {period}: ${amount:,.0f}"

    def _explain_revenue_cell(
        self, period, amount, base_revenue, growth, method, seed_data, month_index
    ):
        if method == "growth_rate" and base_revenue > 0:
            monthly_growth = (1 + growth) ** (1 / 12) - 1
            return (
                f"Revenue {period}: ${amount:,.0f} = "
                f"${base_revenue:,.0f} × (1 + {monthly_growth:.3f})^{month_index + 1} "
                f"({growth:.0%} annual growth with decay)"
            )
        elif method == "regression":
            reg = seed_data.get("_regression_params", {})
            eq = reg.get("equation", "")
            return f"Revenue {period}: ${amount:,.0f} from regression ({eq})"
        elif method == "driver_based":
            return f"Revenue {period}: ${amount:,.0f} from customer model"
        else:
            return f"Revenue {period}: ${amount:,.0f}"

    def _explain_cogs_cell(self, period, amount, gm):
        if gm is not None:
            cogs_pct = 1 - gm
            return f"COGS {period}: ${amount:,.0f} = Revenue × {cogs_pct:.0%} (inverse of {gm:.0%} gross margin)"
        return f"COGS {period}: ${amount:,.0f}"

    def _explain_opex_cell(self, category, period, amount):
        label = {"opex_rd": "R&D", "opex_sm": "S&M", "opex_ga": "G&A"}.get(category, category)
        return f"{label} {period}: ${amount:,.0f} from stage-based OpEx benchmark with efficiency decay"

    # ------------------------------------------------------------------
    # Driver explanation
    # ------------------------------------------------------------------

    def explain_drivers(
        self, seed_data: Dict, assumptions: Dict = None
    ) -> List[Dict]:
        """List drivers with base/override/effective values and impact descriptions.

        Returns list of dicts with: driver, label, base, override, effective, source, impact.
        """
        assumptions = assumptions or {}
        results = []

        # Revenue growth
        base_growth = seed_data.get("growth_rate", 0)
        override_growth = assumptions.get("revenue_growth_override")
        effective_growth = override_growth if override_growth is not None else base_growth
        base_rev = seed_data.get("revenue", 0)
        impact_per_10pp = base_rev * 0.1 * 12  # rough annual impact of 10pp change
        results.append({
            "driver": "revenue_growth",
            "label": "Revenue Growth Rate",
            "base": base_growth,
            "override": override_growth,
            "effective": effective_growth,
            "source": "trailing actuals" if override_growth is None else "user override",
            "impact": f"Primary revenue driver. Each 10pp change ≈ ${impact_per_10pp:,.0f}/yr by M12.",
        })

        # Gross margin
        base_gm = seed_data.get("gross_margin", 0.65)
        override_gm = assumptions.get("gross_margin_override")
        effective_gm = override_gm if override_gm is not None else base_gm
        results.append({
            "driver": "gross_margin",
            "label": "Gross Margin",
            "base": base_gm,
            "override": override_gm,
            "effective": effective_gm,
            "source": "actuals-derived" if override_gm is None else "user override",
            "impact": f"Each 5pp change shifts gross profit by ~${base_rev * 0.05:,.0f}/mo.",
        })

        # Churn rate (if available)
        base_churn = seed_data.get("_detected_churn_rate")
        override_churn = assumptions.get("churn_rate")
        if base_churn is not None or override_churn is not None:
            effective_churn = override_churn if override_churn is not None else base_churn
            results.append({
                "driver": "churn_rate",
                "label": "Monthly Churn Rate",
                "base": base_churn,
                "override": override_churn,
                "effective": effective_churn,
                "source": "detected from actuals" if override_churn is None else "user override",
                "impact": "Compounds monthly — 1pp change shifts annual retention by ~12pp.",
            })

        # ACV (if available)
        base_acv = seed_data.get("_detected_acv")
        override_acv = assumptions.get("acv_override")
        if base_acv is not None or override_acv is not None:
            effective_acv = override_acv if override_acv is not None else base_acv
            results.append({
                "driver": "avg_contract_value",
                "label": "Average Contract Value",
                "base": base_acv,
                "override": override_acv,
                "effective": effective_acv,
                "source": "ARR/customers" if override_acv is None else "user override",
                "impact": "Drives per-customer revenue and LTV calculations.",
            })

        # Burn rate
        base_burn = seed_data.get("burn_rate")
        if base_burn is not None:
            results.append({
                "driver": "burn_rate",
                "label": "Gross Burn Rate",
                "base": base_burn,
                "override": None,
                "effective": base_burn,
                "source": "COGS + OpEx from actuals",
                "impact": f"${base_burn:,.0f}/mo. Directly affects runway.",
            })

        # Cash balance
        base_cash = seed_data.get("cash_balance")
        if base_cash is not None:
            results.append({
                "driver": "cash_balance",
                "label": "Starting Cash",
                "base": base_cash,
                "override": None,
                "effective": base_cash,
                "source": "latest actuals",
                "impact": f"${base_cash:,.0f}. Determines runway.",
            })

        return results

    # ------------------------------------------------------------------
    # Batch derivation for all lines in a forecast
    # ------------------------------------------------------------------

    def generate_line_derivations(
        self, method: str, seed_data: Dict, forecast: List[Dict]
    ) -> Dict[str, str]:
        """Generate derivation strings for every (period, category) in a forecast.

        Returns: {"period|category": "derivation string"}
        """
        derivations = {}
        for i, month in enumerate(forecast):
            period = month.get("period", "")
            for key in month:
                if key == "period":
                    continue
                amount = month[key]
                if not isinstance(amount, (int, float)):
                    continue
                from app.services.forecast_persistence_service import FORECAST_KEY_TO_CATEGORY
                category = FORECAST_KEY_TO_CATEGORY.get(key, key)
                derivation = self.explain_cell(
                    category, period, amount, method, seed_data, month_index=i
                )
                derivations[f"{period}|{category}"] = derivation
        return derivations
