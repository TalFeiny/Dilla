"""
Dynamic P&L waterfall builder.

Discovers line items from real fpa_actuals data, derives category ratios,
and projects forecast that preserves the actual structure.

Replaces the hardcoded PNL_ROW_DEFS / _map_forecast_to_pnl_values approach.
"""

import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Waterfall section ordering — controls how rows are grouped and sorted
# ---------------------------------------------------------------------------

SECTION_ORDER = ["revenue", "cogs", "gross_profit", "opex", "ebitda", "bottom", "operational"]

SECTION_LABELS = {
    "revenue": "Revenue",
    "cogs": "Cost of Sales",
    "gross_profit": "Gross Profit",
    "opex": "Operating Expenses",
    "ebitda": "EBITDA",
    "bottom": "Cash & Runway",
    "operational": "Operational Metrics",
}

# Which fpa_actuals categories roll into which sections
CATEGORY_SECTION = {
    "revenue": "revenue",
    "arr": "revenue",
    "mrr": "revenue",
    "cogs": "cogs",
    "opex_total": "opex",
    "opex_rd": "opex",
    "opex_sm": "opex",
    "opex_ga": "opex",
    "ebitda": "ebitda",
    "cash_balance": "bottom",
    "burn_rate": "bottom",
    "headcount": "operational",
    "customers": "operational",
}

# Sign convention for computed rows: negative categories subtract
COST_CATEGORIES = {"cogs", "opex_total", "opex_rd", "opex_sm", "opex_ga"}

# Fallback labels when subcategory is null
CATEGORY_LABELS = {
    "revenue": "Revenue",
    "cogs": "COGS",
    "opex_total": "Total OpEx",
    "opex_rd": "R&D",
    "opex_sm": "Sales & Marketing",
    "opex_ga": "G&A",
    "ebitda": "EBITDA",
    "cash_balance": "Cash Balance",
    "burn_rate": "Burn Rate",
    "headcount": "Headcount",
    "customers": "Customers",
    "arr": "ARR",
    "mrr": "MRR",
}


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

class PnlBuilder:
    """Builds a dynamic P&L waterfall from fpa_actuals + forecast."""

    def __init__(self, company_id: str, fund_id: Optional[str] = None):
        self.company_id = company_id
        self.fund_id = fund_id

    def build(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        forecast_months: int = 12,
    ) -> Dict[str, Any]:
        """
        Full P&L build: actuals → derive ratios → forecast → assemble rows.

        Returns:
            {
                "periods": ["2025-01", "2025-02", ...],
                "forecastStartIndex": int,
                "rows": [{"id", "label", "depth", "section", "values", ...}, ...],
            }
        """
        # 1. Pull actuals
        actuals, actual_periods = self._pull_actuals(start, end)
        if not actuals:
            logger.info("No actuals for %s — falling back to forecast-only", self.company_id)

        # 2. Derive ratios from last actual period
        ratios = self._derive_ratios(actuals, actual_periods)

        # 3. Build forecast
        forecast, forecast_periods = self._build_forecast(
            actuals, actual_periods, ratios, forecast_months
        )

        # 4. Discover line items from actuals (dynamic waterfall)
        line_items = self._discover_line_items(actuals)

        # 5. Assemble rows
        all_periods = actual_periods + forecast_periods
        rows = self._assemble_rows(line_items, actuals, forecast, all_periods)

        return {
            "periods": all_periods,
            "forecastStartIndex": len(actual_periods),
            "rows": rows,
        }

    # ------------------------------------------------------------------
    # Step 1: Pull actuals from fpa_actuals
    # ------------------------------------------------------------------

    def _pull_actuals(
        self, start: Optional[str], end: Optional[str]
    ) -> Tuple[Dict[str, Dict[str, float]], List[str]]:
        """
        Returns:
            actuals_by_key_period: {"revenue": {"2025-01": 500000, ...}, ...}
                Keys are "category" or "category:subcategory"
            periods: sorted list of period strings
        """
        from app.core.supabase_client import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            logger.warning("Supabase client unavailable — cannot fetch actuals")
            return {}, []

        query = (
            sb.table("fpa_actuals")
            .select("period, category, subcategory, amount")
            .eq("company_id", self.company_id)
        )
        if start:
            query = query.gte("period", f"{start}-01")
        if end:
            query = query.lte("period", f"{end}-01")

        result = query.order("period").execute()

        if not result.data:
            return {}, []

        actuals: Dict[str, Dict[str, float]] = {}
        periods_set: set = set()

        for row in result.data:
            period = row["period"][:7]
            cat = row["category"]
            sub = row.get("subcategory")
            amount = float(row["amount"])
            key = f"{cat}:{sub}" if sub else cat

            periods_set.add(period)
            actuals.setdefault(key, {})[period] = amount

        periods = sorted(periods_set)
        return actuals, periods

    # ------------------------------------------------------------------
    # Step 2: Derive ratios from the latest actual period
    # ------------------------------------------------------------------

    def _derive_ratios(
        self,
        actuals: Dict[str, Dict[str, float]],
        periods: List[str],
    ) -> Dict[str, float]:
        """
        Look at the last actual period and compute:
        - Revenue subcategory splits (e.g. SaaS 85%, Services 15%)
        - OpEx subcategory splits (e.g. R&D salaries 75%, tooling 25%)
        - Gross margin
        - COGS as % of revenue
        - OpEx category splits as % of total opex

        Returns a flat dict of ratio keys → values.
        """
        if not periods:
            return {}

        last = periods[-1]
        ratios: Dict[str, float] = {}

        # Helper: get value for a key at the last period
        def val(key: str) -> float:
            return actuals.get(key, {}).get(last, 0.0)

        # Revenue subcategory splits — prefer subs; only use parent if no subs
        rev_sub_total = 0.0
        has_rev_subs = False
        rev_subs: Dict[str, float] = {}
        for key, vals in actuals.items():
            if key.startswith("revenue:") and last in vals:
                rev_subs[key] = vals[last]
                rev_sub_total += vals[last]
                has_rev_subs = True

        total_revenue = rev_sub_total if has_rev_subs else val("revenue")

        if total_revenue > 0:
            for key, amount in rev_subs.items():
                ratios[f"split:{key}"] = amount / total_revenue
            ratios["total_revenue"] = total_revenue

        # COGS ratio — prefer subcategories; only use parent "cogs" if no subs
        cogs_sub_total = 0.0
        has_cogs_subs = False
        for key, vals in actuals.items():
            if key.startswith("cogs:") and last in vals:
                cogs_sub_total += vals[last]
                has_cogs_subs = True
        total_cogs = cogs_sub_total if has_cogs_subs else val("cogs")
        if total_revenue > 0 and total_cogs > 0:
            ratios["cogs_pct"] = total_cogs / total_revenue
            ratios["gross_margin"] = 1 - (total_cogs / total_revenue)

        # OpEx splits
        total_opex = 0.0
        opex_subs: Dict[str, float] = {}
        for key, vals in actuals.items():
            cat = key.split(":")[0]
            if cat.startswith("opex") and cat != "opex_total" and last in vals:
                opex_subs[key] = vals[last]
                total_opex += vals[last]

        # If we only have opex_total, use that
        if total_opex == 0:
            total_opex = val("opex_total")

        if total_opex > 0:
            for key, amount in opex_subs.items():
                ratios[f"split:{key}"] = amount / total_opex
            ratios["total_opex"] = total_opex
            if total_revenue > 0:
                ratios["opex_pct"] = total_opex / total_revenue

        return ratios

    # ------------------------------------------------------------------
    # Step 3: Build forecast preserving actual structure
    # ------------------------------------------------------------------

    def _build_forecast(
        self,
        actuals: Dict[str, Dict[str, float]],
        actual_periods: List[str],
        ratios: Dict[str, float],
        months: int,
    ) -> Tuple[Dict[str, Dict[str, float]], List[str]]:
        """
        Build forecast months using CashFlowPlanningService, then redistribute
        its output back into the actual category structure using derived ratios.
        """
        from app.services.cash_flow_planning_service import CashFlowPlanningService
        from app.services.actuals_ingestion import seed_forecast_from_actuals

        try:
            company_data = seed_forecast_from_actuals(self.company_id)
        except Exception:
            company_data = {"revenue": 0, "growth_rate": 0.5}

        if company_data.get("revenue", 0) <= 0 and not actual_periods:
            return {}, []

        # Inject actual gross margin if we derived it
        if "gross_margin" in ratios and "gross_margin" not in company_data:
            company_data["gross_margin"] = ratios["gross_margin"]

        # Determine forecast start
        if actual_periods:
            last = actual_periods[-1]
            y, m = map(int, last.split("-"))
            m += 1
            if m > 12:
                m, y = 1, y + 1
            forecast_start = f"{y:04d}-{m:02d}"
        else:
            today = date.today()
            forecast_start = f"{today.year:04d}-{today.month:02d}"

        svc = CashFlowPlanningService()
        monthly = svc.build_monthly_cash_flow_model(
            company_data, months=months, start_period=forecast_start
        )

        forecast: Dict[str, Dict[str, float]] = {}
        forecast_periods: List[str] = []

        for entry in monthly:
            period = entry.get("period", "")
            if not period:
                continue
            forecast_periods.append(period)

            # Redistribute forecast output using actual ratios
            forecast[period] = self._redistribute_forecast(entry, ratios, actuals)

        return forecast, forecast_periods

    def _redistribute_forecast(
        self,
        month: Dict[str, Any],
        ratios: Dict[str, float],
        actuals: Dict[str, Dict[str, float]],
    ) -> Dict[str, float]:
        """
        Take a single month from CashFlowPlanningService and split it
        into the same category keys that exist in actuals.

        If actuals had "revenue:saas" and "revenue:services" at 80/20,
        forecast revenue gets split 80/20 into those same keys.
        """
        result: Dict[str, float] = {}
        revenue = month.get("revenue", 0)
        cogs = month.get("cogs", 0)
        gross_profit = month.get("gross_profit", 0)
        rd = month.get("rd_spend", 0)
        sm = month.get("sm_spend", 0)
        ga = month.get("ga_spend", 0)
        total_opex = month.get("total_opex", 0)

        # --- Revenue subcategories ---
        rev_splits = {k: v for k, v in ratios.items() if k.startswith("split:revenue")}
        if rev_splits:
            for split_key, pct in rev_splits.items():
                key = split_key.replace("split:", "")  # "revenue:saas"
                result[key] = revenue * pct
        else:
            result["revenue"] = revenue

        # Always include total_revenue as a computed key
        result["total_revenue"] = revenue

        # --- COGS subcategories ---
        cogs_splits = {k: v for k, v in ratios.items() if k.startswith("split:cogs")}
        if cogs_splits:
            for split_key, pct in cogs_splits.items():
                key = split_key.replace("split:", "")
                result[key] = cogs * pct
        else:
            result["cogs"] = cogs
        result["total_cogs"] = cogs

        # --- Gross profit (always computed) ---
        result["gross_profit"] = gross_profit

        # --- OpEx subcategories ---
        # First, check if actuals had detailed opex categories (opex_rd, opex_sm, etc.)
        opex_splits = {k: v for k, v in ratios.items() if k.startswith("split:opex")}
        if opex_splits:
            # Actuals had opex subcategories — distribute total_opex by those ratios
            for split_key, pct in opex_splits.items():
                key = split_key.replace("split:", "")
                result[key] = total_opex * pct
        else:
            # No detailed opex in actuals — use the forecast engine's R&D/S&M/G&A breakdown
            result["opex_rd"] = rd
            result["opex_sm"] = sm
            result["opex_ga"] = ga

        # Check for opex sub-subcategories (e.g. opex_rd:salaries, opex_rd:tooling)
        for cat_key in ["opex_rd", "opex_sm", "opex_ga"]:
            cat_subs = {k: v for k, v in ratios.items() if k.startswith(f"split:{cat_key}:")}
            if cat_subs and cat_key in result:
                parent_val = result[cat_key]
                for split_key, pct in cat_subs.items():
                    key = split_key.replace("split:", "")
                    result[key] = parent_val * pct

        result["total_opex"] = total_opex

        # --- Bottom line ---
        result["ebitda"] = month.get("ebitda", 0)
        result["cash_balance"] = month.get("cash_balance", 0)
        result["runway"] = month.get("runway_months", 0)

        return result

    # ------------------------------------------------------------------
    # Step 4: Discover line items from actual data
    # ------------------------------------------------------------------

    def _discover_line_items(
        self, actuals: Dict[str, Dict[str, float]]
    ) -> List[Dict[str, Any]]:
        """
        Build the waterfall row definitions dynamically from what's in actuals.
        Returns a list of row defs with id, label, depth, section, parentId, etc.
        """
        items: List[Dict[str, Any]] = []
        seen_sections: set = set()
        seen_categories: set = set()

        # First pass: find which categories have subcategories
        cats_with_subs: set = set()
        for key in actuals.keys():
            if ":" in key:
                cats_with_subs.add(key.split(":", 1)[0])

        # Collect all keys from actuals
        for key in sorted(actuals.keys()):
            cat, sub = (key.split(":", 1) + [None])[:2]
            section = CATEGORY_SECTION.get(cat, "other")
            seen_sections.add(section)
            seen_categories.add(cat)

            if sub:
                items.append({
                    "id": key,
                    "label": sub.replace("_", " ").title(),
                    "category": cat,
                    "subcategory": sub,
                    "section": section,
                    "depth": 2 if cat.startswith("opex_") else 1,
                    "parentId": cat,
                })
            else:
                # Skip parent row when subcategories exist (avoids double-counting)
                if cat in cats_with_subs:
                    continue
                items.append({
                    "id": key,
                    "label": CATEGORY_LABELS.get(cat, cat.replace("_", " ").title()),
                    "category": cat,
                    "subcategory": None,
                    "section": section,
                    "depth": 1 if section in ("revenue", "cogs", "opex") else 0,
                    "parentId": None,
                })

        # If no actuals at all, return a minimal skeleton
        if not items:
            return self._fallback_skeleton()

        return items

    def _fallback_skeleton(self) -> List[Dict[str, Any]]:
        """Minimal row defs when there are no actuals — just forecast categories."""
        return [
            {"id": "revenue", "label": "Revenue", "section": "revenue", "depth": 0},
            {"id": "cogs", "label": "COGS", "section": "cogs", "depth": 0},
            {"id": "gross_profit", "label": "Gross Profit", "section": "gross_profit", "depth": 0, "isComputed": True},
            {"id": "opex_rd", "label": "R&D", "section": "opex", "depth": 1},
            {"id": "opex_sm", "label": "Sales & Marketing", "section": "opex", "depth": 1},
            {"id": "opex_ga", "label": "G&A", "section": "opex", "depth": 1},
            {"id": "total_opex", "label": "Total OpEx", "section": "opex", "depth": 0, "isTotal": True},
            {"id": "ebitda", "label": "EBITDA", "section": "ebitda", "depth": 0, "isComputed": True},
            {"id": "cash_balance", "label": "Cash Balance", "section": "bottom", "depth": 0},
            {"id": "runway", "label": "Runway (months)", "section": "bottom", "depth": 0},
        ]

    # ------------------------------------------------------------------
    # Step 5: Assemble final rows
    # ------------------------------------------------------------------

    def _assemble_rows(
        self,
        line_items: List[Dict[str, Any]],
        actuals: Dict[str, Dict[str, float]],
        forecast: Dict[str, Dict[str, float]],
        all_periods: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Build the final row list with section headers, data rows,
        and computed subtotals inserted at the right points.
        """
        rows: List[Dict[str, Any]] = []

        # Group items by section
        by_section: Dict[str, List[Dict[str, Any]]] = {}
        for item in line_items:
            sec = item.get("section", "other")
            by_section.setdefault(sec, []).append(item)

        for section in SECTION_ORDER:
            items = by_section.get(section, [])
            if not items and section not in ("gross_profit", "ebitda"):
                continue

            # Section header
            rows.append({
                "id": f"{section}_header",
                "label": SECTION_LABELS.get(section, section.title()),
                "depth": 0,
                "isHeader": True,
                "section": section,
                "values": {},
            })

            # Data rows for this section
            for item in items:
                row_id = item["id"]
                values: Dict[str, Optional[float]] = {}
                for p in all_periods:
                    # Check actuals first, then forecast
                    val = actuals.get(row_id, {}).get(p)
                    if val is None:
                        val = forecast.get(p, {}).get(row_id)
                    values[p] = val

                row = {
                    "id": row_id,
                    "label": item["label"],
                    "depth": item.get("depth", 1),
                    "section": section,
                    "values": values,
                }
                if item.get("parentId"):
                    row["parentId"] = item["parentId"]
                if item.get("isComputed"):
                    row["isComputed"] = True
                if item.get("isTotal"):
                    row["isTotal"] = True
                rows.append(row)

            # Section subtotals
            if section == "revenue":
                rows.append(self._computed_row(
                    "total_revenue", "Total Revenue", section, all_periods,
                    actuals, forecast
                ))
            elif section == "cogs":
                rows.append(self._computed_row(
                    "total_cogs", "Total COGS", section, all_periods,
                    actuals, forecast
                ))
                # Insert Gross Profit after COGS
                rows.append(self._inline_computed_row(
                    "gross_profit", "Gross Profit", "gross_profit", all_periods,
                    actuals, forecast, compute_fn=self._compute_gross_profit
                ))
            elif section == "opex":
                rows.append(self._computed_row(
                    "total_opex", "Total OpEx", section, all_periods,
                    actuals, forecast
                ))
            elif section == "ebitda":
                # EBITDA is computed: gross_profit - total_opex
                rows.append(self._inline_computed_row(
                    "ebitda", "EBITDA", "ebitda", all_periods,
                    actuals, forecast, compute_fn=self._compute_ebitda
                ))

        return rows

    def _computed_row(
        self,
        row_id: str,
        label: str,
        section: str,
        periods: List[str],
        actuals: Dict[str, Dict[str, float]],
        forecast: Dict[str, Dict[str, float]],
    ) -> Dict[str, Any]:
        """Build a total/subtotal row from actuals or forecast."""
        values: Dict[str, Optional[float]] = {}
        for p in periods:
            val = actuals.get(row_id, {}).get(p)
            if val is None:
                val = forecast.get(p, {}).get(row_id)
            values[p] = val
        return {
            "id": row_id,
            "label": label,
            "depth": 0,
            "section": section,
            "isTotal": True,
            "values": values,
        }

    def _inline_computed_row(
        self,
        row_id: str,
        label: str,
        section: str,
        periods: List[str],
        actuals: Dict[str, Dict[str, float]],
        forecast: Dict[str, Dict[str, float]],
        compute_fn=None,
    ) -> Dict[str, Any]:
        """Build a computed row — uses stored value if available, else computes."""
        values: Dict[str, Optional[float]] = {}
        for p in periods:
            # Prefer stored value
            val = actuals.get(row_id, {}).get(p)
            if val is None:
                val = forecast.get(p, {}).get(row_id)
            if val is None and compute_fn:
                val = compute_fn(p, actuals, forecast)
            values[p] = val
        return {
            "id": row_id,
            "label": label,
            "depth": 0,
            "section": section,
            "isComputed": True,
            "values": values,
        }

    @staticmethod
    def _compute_gross_profit(
        period: str,
        actuals: Dict[str, Dict[str, float]],
        forecast: Dict[str, Dict[str, float]],
    ) -> Optional[float]:
        rev = actuals.get("total_revenue", {}).get(period)
        if rev is None:
            rev = forecast.get(period, {}).get("total_revenue")
        cogs = actuals.get("total_cogs", {}).get(period)
        if cogs is None:
            cogs = forecast.get(period, {}).get("total_cogs")
        if rev is not None and cogs is not None:
            return rev - cogs
        return None

    @staticmethod
    def _compute_ebitda(
        period: str,
        actuals: Dict[str, Dict[str, float]],
        forecast: Dict[str, Dict[str, float]],
    ) -> Optional[float]:
        gp = PnlBuilder._compute_gross_profit(period, actuals, forecast)
        opex = actuals.get("total_opex", {}).get(period)
        if opex is None:
            opex = forecast.get(period, {}).get("total_opex")
        if gp is not None and opex is not None:
            return gp - opex
        return None
