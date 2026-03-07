"""
Centralized computed metrics.

Any service that needs LTV, LTV:CAC, magic number, payback period,
rule of 40, etc. calls this instead of computing inline.

Inputs come from seed_data (actuals-derived) + driver overrides.
"""

from typing import Any, Dict, Optional


# Display labels for computed metrics
COMPUTED_LABELS = {
    "ltv": "Customer LTV",
    "ltv_cac_ratio": "LTV:CAC Ratio",
    "magic_number": "Magic Number",
    "cac_payback_months": "CAC Payback (Months)",
    "rule_of_40": "Rule of 40",
    "net_burn_rate": "Net Burn Rate",
    "gross_burn_rate": "Gross Burn Rate",
    "runway_months": "Runway (Months)",
    "revenue_per_employee": "Revenue per Employee",
    "arr_per_customer": "ARR per Customer",
}


class ComputedMetrics:

    @staticmethod
    def compute_all(seed_data: Dict, driver_overrides: Dict = None) -> Dict:
        """Compute all computed metrics from seed data + overrides.

        Returns dict with metric values and _derivations for explainability.
        """
        overrides = driver_overrides or {}
        result: Dict[str, Any] = {}
        derivations: Dict[str, str] = {}

        # Resolve effective values
        revenue = seed_data.get("revenue", 0) or 0
        growth_rate = overrides.get("revenue_growth_override", seed_data.get("growth_rate", 0)) or 0
        gross_margin = overrides.get("gross_margin_override", seed_data.get("gross_margin", 0.65)) or 0.65
        monthly_churn = overrides.get("churn_rate", seed_data.get("_detected_churn_rate", 0)) or 0
        acv = overrides.get("acv_override", seed_data.get("_detected_acv", 0)) or 0
        cac = overrides.get("cac_override", 0) or 0
        customers = seed_data.get("_detected_customer_count", 0) or 0
        headcount = seed_data.get("headcount", 0) or 0
        burn_rate = seed_data.get("burn_rate", 0) or 0
        net_burn = seed_data.get("net_burn", 0) or 0
        cash_balance = seed_data.get("cash_balance", 0) or 0
        sm_spend = seed_data.get("_sm_spend", 0) or 0

        # LTV
        ltv = ComputedMetrics.compute_ltv(acv, gross_margin, monthly_churn)
        if ltv is not None:
            result["ltv"] = round(ltv, 2)
            annual_churn = 1 - (1 - monthly_churn) ** 12
            derivations["ltv"] = (
                f"ACV (${acv:,.0f}) × gross_margin ({gross_margin:.0%}) "
                f"/ annual_churn ({annual_churn:.0%}) = ${ltv:,.0f}"
            )

        # LTV:CAC
        if ltv and cac and cac > 0:
            ltv_cac = ltv / cac
            result["ltv_cac_ratio"] = round(ltv_cac, 2)
            derivations["ltv_cac_ratio"] = f"LTV (${ltv:,.0f}) / CAC (${cac:,.0f}) = {ltv_cac:.1f}x"

        # Magic Number
        if customers > 0 and sm_spend > 0:
            # Approximate: net new ARR / prior quarter S&M
            arr = acv * customers if acv else revenue * 12
            prior_arr = arr * (1 / (1 + growth_rate)) if growth_rate > -1 else arr
            quarterly_sm = sm_spend * 3
            magic = ComputedMetrics.compute_magic_number(arr, prior_arr, quarterly_sm)
            if magic is not None:
                result["magic_number"] = round(magic, 2)
                derivations["magic_number"] = (
                    f"Net new ARR (${arr - prior_arr:,.0f}) "
                    f"/ prior quarter S&M (${quarterly_sm:,.0f}) = {magic:.2f}"
                )

        # CAC Payback
        if cac > 0 and acv > 0:
            arpu_monthly = acv / 12
            payback = ComputedMetrics.compute_cac_payback(cac, arpu_monthly, gross_margin)
            if payback is not None:
                result["cac_payback_months"] = round(payback, 1)
                derivations["cac_payback_months"] = (
                    f"CAC (${cac:,.0f}) / monthly contribution "
                    f"(${arpu_monthly * gross_margin:,.0f}) = {payback:.1f} months"
                )

        # Rule of 40
        ebitda_margin = 0
        if revenue > 0:
            ebitda_margin = (revenue - burn_rate) / revenue if burn_rate else 0
        r40 = ComputedMetrics.compute_rule_of_40(growth_rate, ebitda_margin)
        result["rule_of_40"] = round(r40, 1)
        derivations["rule_of_40"] = (
            f"Growth ({growth_rate:.0%}) + EBITDA margin ({ebitda_margin:.0%}) "
            f"= {r40:.0f}%"
        )

        # Burns & Runway
        if burn_rate:
            result["gross_burn_rate"] = round(burn_rate, 2)
            derivations["gross_burn_rate"] = f"COGS + OpEx = ${burn_rate:,.0f}/mo"

        if net_burn:
            result["net_burn_rate"] = round(net_burn, 2)
            derivations["net_burn_rate"] = f"Gross burn - Revenue = ${net_burn:,.0f}/mo"

        if cash_balance and net_burn and net_burn > 0:
            runway = cash_balance / net_burn
            result["runway_months"] = round(runway, 1)
            derivations["runway_months"] = (
                f"Cash (${cash_balance:,.0f}) / net burn (${net_burn:,.0f}) "
                f"= {runway:.1f} months"
            )

        # Revenue per employee
        if revenue > 0 and headcount > 0:
            rev_per_emp = (revenue * 12) / headcount  # annualized
            result["revenue_per_employee"] = round(rev_per_emp, 2)
            derivations["revenue_per_employee"] = (
                f"Annual revenue (${revenue * 12:,.0f}) / headcount ({headcount:.0f}) "
                f"= ${rev_per_emp:,.0f}"
            )

        # ARR per customer
        if acv and customers > 0:
            result["arr_per_customer"] = round(acv, 2)
            derivations["arr_per_customer"] = f"ARR / customers = ${acv:,.0f}"

        result["_derivations"] = derivations
        return result

    @staticmethod
    def compute_ltv(
        acv: float, gross_margin: float, monthly_churn: float
    ) -> Optional[float]:
        if not acv or not monthly_churn or monthly_churn <= 0:
            return None
        annual_churn = 1 - (1 - monthly_churn) ** 12
        if annual_churn <= 0:
            return None
        return acv * gross_margin / annual_churn

    @staticmethod
    def compute_magic_number(
        current_arr: float, prior_arr: float, prior_sm_spend: float
    ) -> Optional[float]:
        if prior_sm_spend <= 0:
            return None
        return (current_arr - prior_arr) / prior_sm_spend

    @staticmethod
    def compute_cac_payback(
        cac: float, arpu_monthly: float, gross_margin: float
    ) -> Optional[float]:
        monthly_contribution = arpu_monthly * gross_margin
        if monthly_contribution <= 0:
            return None
        return cac / monthly_contribution

    @staticmethod
    def compute_rule_of_40(growth_rate: float, ebitda_margin: float) -> float:
        return (growth_rate + ebitda_margin) * 100
