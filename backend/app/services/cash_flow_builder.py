"""
Dynamic Cash Flow builder.

Discovers cash-flow line items from fpa_actuals, computes derived rows
(FCF, runway, net burn), and returns hierarchical rows matching the
PnlBuilder / BalanceSheetBuilder pattern.

Categories used:
  - operating_cash_flow, capex, free_cash_flow,
    cash_balance, net_burn_rate, runway_months,
    working_capital_delta, debt_service, financing_cash_flow
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Section ordering
# ---------------------------------------------------------------------------

CF_SECTION_ORDER = [
    "operating",
    "investing",
    "financing",
    "net_cash",
    "position",
]

CF_SECTION_LABELS = {
    "operating": "Operating Activities",
    "investing": "Investing Activities",
    "financing": "Financing Activities",
    "net_cash": "Net Cash Flow",
    "position": "Cash Position",
}

# Which fpa_actuals categories roll into which sections
CF_CATEGORY_SECTION = {
    "operating_cash_flow": "operating",
    "working_capital_delta": "operating",
    "capex": "investing",
    "free_cash_flow": "investing",
    "debt_service": "financing",
    "financing_cash_flow": "financing",
    "cash_balance": "position",
    "net_burn_rate": "position",
    "runway_months": "position",
}

CF_CATEGORY_LABELS = {
    "operating_cash_flow": "Operating Cash Flow",
    "working_capital_delta": "Working Capital Change",
    "capex": "Capital Expenditure",
    "free_cash_flow": "Free Cash Flow",
    "debt_service": "Debt Service",
    "financing_cash_flow": "Financing Cash Flow",
    "cash_balance": "Cash Balance",
    "net_burn_rate": "Net Burn Rate",
    "runway_months": "Runway (Months)",
}


class CashFlowBuilder:
    """Builds a dynamic Cash Flow statement from fpa_actuals."""

    def __init__(self, company_id: Optional[str] = None):
        self.company_id = company_id

    def build(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Full cash flow build: pull actuals → derive missing rows → assemble.

        Returns:
            {
                "periods": ["2025-01", "2025-02", ...],
                "rows": [{"id", "label", "depth", "section", "values", ...}, ...],
            }
        """
        actuals, periods = self._pull_cf_actuals(start, end)

        # Derive FCF if missing: FCF = Operating CF - CapEx
        if "free_cash_flow" not in actuals and "operating_cash_flow" in actuals:
            fcf = {}
            for p in periods:
                ocf = actuals.get("operating_cash_flow", {}).get(p, 0)
                capex = actuals.get("capex", {}).get(p, 0)
                fcf[p] = round(ocf - abs(capex), 2)
            actuals["free_cash_flow"] = fcf

        # Derive net burn if missing: burn = negative of operating CF
        if "net_burn_rate" not in actuals and "operating_cash_flow" in actuals:
            burn = {}
            for p in periods:
                ocf = actuals.get("operating_cash_flow", {}).get(p, 0)
                burn[p] = round(-ocf, 2) if ocf < 0 else 0
            actuals["net_burn_rate"] = burn

        # Derive runway if missing: runway = cash / burn
        if "runway_months" not in actuals and "cash_balance" in actuals and "net_burn_rate" in actuals:
            runway = {}
            for p in periods:
                cash = actuals.get("cash_balance", {}).get(p, 0)
                burn = actuals.get("net_burn_rate", {}).get(p, 0)
                runway[p] = round(cash / burn, 1) if burn > 0 else 999
            actuals["runway_months"] = runway

        rows = self._assemble_rows(actuals, periods)

        return {
            "periods": periods,
            "rows": rows,
        }

    def _pull_cf_actuals(
        self,
        start: Optional[str],
        end: Optional[str],
    ) -> Tuple[Dict[str, Dict[str, float]], List[str]]:
        """Pull cash-flow categories from fpa_actuals."""
        from app.core.supabase_client import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            logger.warning("Supabase unavailable — cannot fetch CF actuals")
            return {}, []

        # CF categories we care about
        cf_cats = list(CF_CATEGORY_SECTION.keys())

        query = (
            sb.table("fpa_actuals")
            .select("period, category, subcategory, amount")
        )
        if self.company_id:
            query = query.eq("company_id", self.company_id)
        query = query.in_("category", cf_cats)
        if start:
            query = query.gte("period", f"{start}-01")
        if end:
            query = query.lte("period", f"{end}-01")

        result = query.order("period").execute()

        if not result.data:
            # Fallback: try to derive from P&L categories
            return self._derive_from_pnl(start, end)

        actuals: Dict[str, Dict[str, float]] = {}
        periods_set: set = set()

        for row in result.data:
            period = row["period"][:7]
            cat = row["category"]
            amount = float(row["amount"])
            periods_set.add(period)
            actuals.setdefault(cat, {})[period] = (
                actuals.get(cat, {}).get(period, 0) + amount
            )

        periods = sorted(periods_set)
        return actuals, periods

    def _derive_from_pnl(
        self,
        start: Optional[str],
        end: Optional[str],
    ) -> Tuple[Dict[str, Dict[str, float]], List[str]]:
        """
        If no explicit CF rows exist, derive cash flow from P&L data:
        Operating CF ≈ EBITDA (or Revenue - COGS - OpEx)
        """
        from app.core.supabase_client import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return {}, []

        pnl_cats = ["revenue", "cogs", "opex_rd", "opex_sm", "opex_ga",
                     "ebitda", "net_income", "cash_balance", "capex",
                     "debt_service", "tax_expense"]

        query = (
            sb.table("fpa_actuals")
            .select("period, category, amount")
        )
        if self.company_id:
            query = query.eq("company_id", self.company_id)
        query = query.in_("category", pnl_cats)
        if start:
            query = query.gte("period", f"{start}-01")
        if end:
            query = query.lte("period", f"{end}-01")

        result = query.order("period").execute()
        if not result.data:
            return {}, []

        # Group by period
        by_period: Dict[str, Dict[str, float]] = {}
        for row in result.data:
            p = row["period"][:7]
            cat = row["category"]
            by_period.setdefault(p, {})[cat] = (
                by_period.get(p, {}).get(cat, 0) + float(row["amount"])
            )

        periods = sorted(by_period.keys())
        actuals: Dict[str, Dict[str, float]] = {}

        for p, cats in by_period.items():
            # Operating CF ≈ EBITDA if available, else revenue - costs
            ebitda = cats.get("ebitda")
            if ebitda is not None:
                ocf = ebitda
            else:
                rev = cats.get("revenue", 0)
                cogs = abs(cats.get("cogs", 0))
                opex = abs(cats.get("opex_rd", 0)) + abs(cats.get("opex_sm", 0)) + abs(cats.get("opex_ga", 0))
                ocf = rev - cogs - opex

            actuals.setdefault("operating_cash_flow", {})[p] = round(ocf, 2)

            capex = abs(cats.get("capex", 0))
            actuals.setdefault("capex", {})[p] = round(capex, 2)

            if "cash_balance" in cats:
                actuals.setdefault("cash_balance", {})[p] = round(cats["cash_balance"], 2)

            if "debt_service" in cats:
                actuals.setdefault("debt_service", {})[p] = round(cats["debt_service"], 2)

        return actuals, periods

    def _assemble_rows(
        self,
        actuals: Dict[str, Dict[str, float]],
        periods: List[str],
    ) -> List[Dict[str, Any]]:
        """Build row list with section headers and data rows."""
        rows: List[Dict[str, Any]] = []

        by_section: Dict[str, List[str]] = {}
        for cat, section in CF_CATEGORY_SECTION.items():
            if cat in actuals:
                by_section.setdefault(section, []).append(cat)

        for section in CF_SECTION_ORDER:
            cats = by_section.get(section, [])
            if not cats:
                continue

            # Section header
            rows.append({
                "id": f"{section}_header",
                "label": CF_SECTION_LABELS.get(section, section.replace("_", " ").title()),
                "depth": 0,
                "isHeader": True,
                "section": section,
                "values": {},
            })

            for cat in cats:
                values: Dict[str, Optional[float]] = {}
                for p in periods:
                    values[p] = actuals.get(cat, {}).get(p)
                rows.append({
                    "id": cat,
                    "label": CF_CATEGORY_LABELS.get(cat, cat.replace("_", " ").title()),
                    "depth": 1,
                    "section": section,
                    "values": values,
                })

        return rows
