"""
Dynamic P&L waterfall builder.

Discovers line items from real fpa_actuals data, derives category ratios,
and projects forecast that preserves the actual structure.

Replaces the hardcoded PNL_ROW_DEFS / _map_forecast_to_pnl_values approach.
"""

import logging
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _normalize_period(raw: str) -> Optional[str]:
    """Parse a period string flexibly into 'YYYY-MM' format.

    Handles: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, YYYY/MM/DD, YYYY-MM,
    MM/YYYY, Month YYYY, YYYYMMDD, etc.
    Returns None (with a warning) if unparseable rather than silently corrupting.
    """
    if not raw or not isinstance(raw, str):
        logger.warning("Empty or non-string period value: %r", raw)
        return None

    s = raw.strip()

    # Already YYYY-MM
    if re.match(r"^\d{4}-\d{2}$", s):
        return s

    # YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS...
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s[:7]

    # YYYY/MM/DD
    if re.match(r"^\d{4}/\d{2}/\d{2}$", s):
        return f"{s[:4]}-{s[5:7]}"

    # YYYYMMDD
    if re.match(r"^\d{8}$", s):
        return f"{s[:4]}-{s[4:6]}"

    # MM/YYYY or M/YYYY
    m = re.match(r"^(\d{1,2})/(\d{4})$", s)
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}"

    # DD/MM/YYYY or DD-MM-YYYY (ambiguous, assume day-first since month is 2nd)
    m = re.match(r"^\d{1,2}[/-](\d{1,2})[/-](\d{4})$", s)
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}"

    # "January 2025", "Jan 2025", etc.
    for fmt in ("%B %Y", "%b %Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return f"{dt.year:04d}-{dt.month:02d}"
        except ValueError:
            continue

    # Q1 2025, Q2-2025, etc.
    m = re.match(r"^Q(\d)\s*[-/]?\s*(\d{4})$", s, re.IGNORECASE)
    if m:
        q = int(m.group(1))
        y = m.group(2)
        month = (q - 1) * 3 + 1
        return f"{y}-{month:02d}"

    logger.warning("Could not parse period %r — skipping row", raw)
    return None

# ---------------------------------------------------------------------------
# Waterfall section ordering — controls how rows are grouped and sorted
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Fixed P&L skeleton — these rows ALWAYS exist.
# Dynamic subcategories from actuals slot in under their correct parent.
# Parents sum their children. Computed rows derive from parent totals.
# ---------------------------------------------------------------------------

# The skeleton defines the fixed rows of the income statement.
# Each entry: (id, label, section, depth)
# All rows are "parent" rows.  Leaf parents sum their dynamic children.
# Formula parents (gross_profit, total_opex, ebitda) derive values from
# other parents — no separate "computed" type needed.
SKELETON = [
    ("revenue",       "Revenue",            "revenue",       0),
    ("cogs",          "COGS",               "cogs",          0),
    ("gross_profit",  "Gross Profit",       "gross_profit",  0),
    ("opex_rd",       "R&D",                "opex",          1),
    ("opex_sm",       "Sales & Marketing",  "opex",          1),
    ("opex_ga",       "G&A",                "opex",          1),
    ("total_opex",    "Total OpEx",         "opex",          0),
    ("ebitda",        "EBITDA",             "ebitda",        0),
]

# Parent rows whose values are derived from other parents via formula.
# These never get dynamic children — their value IS the formula result.
FORMULA_ROWS = {
    "gross_profit": ("revenue", "-", "cogs"),
    "total_opex":   ("opex_rd", "+", "opex_sm", "+", "opex_ga"),
    "ebitda":       ("gross_profit", "-", "total_opex"),
}

# Which fpa_actuals categories map to which skeleton parent
CATEGORY_TO_PARENT = {
    "revenue": "revenue",
    "arr": "revenue",
    "mrr": "revenue",
    "cogs": "cogs",
    "opex_rd": "opex_rd",
    "opex_sm": "opex_sm",
    "opex_ga": "opex_ga",
    "opex_total": None,      # derived — skip
    "gross_profit": None,    # derived — skip
    "ebitda": None,          # derived — skip
    "net_income": None,      # derived — skip
    "debt_service": None,    # not in skeleton
    "interest": None,
    "tax": None,
    "tax_expense": None,
    "headcount": None,
    "customers": None,
    "cash_balance": None,
    "burn_rate": None,
}

# Parent IDs that can have dynamic subcategory children
PARENT_IDS = {"revenue", "cogs", "opex_rd", "opex_sm", "opex_ga"}

# Sign convention for computed rows: negative categories subtract
COST_CATEGORIES = {"cogs", "opex_total", "opex_rd", "opex_sm", "opex_ga"}

# Categories that are computed — never discovered from actuals
DERIVED_CATEGORIES = {"gross_profit", "ebitda", "opex_total", "net_income"}

# Labels for parent categories
CATEGORY_LABELS = {
    "revenue": "Revenue",
    "cogs": "COGS",
    "opex_rd": "R&D",
    "opex_sm": "Sales & Marketing",
    "opex_ga": "G&A",
}


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------

class PnlBuilder:
    """Builds a dynamic P&L waterfall from fpa_actuals + forecast."""

    def __init__(self, company_id: Optional[str] = None, fund_id: Optional[str] = None, company_data=None):
        self.company_id = company_id
        self.fund_id = fund_id
        self._company_data = company_data  # Optional CompanyData — avoids re-pull

    def build(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        forecast_months: int = 12,
        view: str = "waterfall",
        budget_id: Optional[str] = None,
        forecast_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Full P&L build: actuals → derive ratios → forecast → assemble rows.

        Views:
            waterfall            — default: actuals + inline forecast
            actuals_vs_budget    — actuals alongside budget data
            actuals_vs_forecast  — actuals alongside a saved forecast

        Returns:
            {
                "periods": ["2025-01", "2025-02", ...],
                "forecastStartIndex": int,
                "rows": [{"id", "label", "depth", "section", "values", ...}, ...],
                "view": str,
            }
        """
        # 1. Pull actuals
        actuals, actual_periods = self._pull_actuals(start, end)
        if not actuals:
            logger.info("No actuals for %s — falling back to forecast-only", self.company_id)

        # 2. Derive ratios from last actual period
        ratios = self._derive_ratios(actuals, actual_periods)

        # 3. Build forecast — prefer saved forecast, then compute inline
        if forecast_id:
            forecast, forecast_periods = self._pull_saved_forecast(forecast_id, actual_periods)
        elif view == "actuals_vs_forecast":
            # Try active forecast first
            forecast, forecast_periods = self._pull_active_forecast(actual_periods)
            if not forecast:
                forecast, forecast_periods = self._build_forecast(
                    actuals, actual_periods, ratios, forecast_months
                )
        else:
            forecast, forecast_periods = self._build_forecast(
                actuals, actual_periods, ratios, forecast_months
            )

        # 4. Pull budget if requested
        budget_data = None
        if view == "actuals_vs_budget" or budget_id:
            budget_data = self._pull_budget(budget_id)

        # 5. Discover line items from actuals (dynamic waterfall)
        line_items = self._discover_line_items(actuals)

        # 6. Assemble rows
        all_periods = actual_periods + forecast_periods
        rows = self._assemble_rows(line_items, actuals, forecast, all_periods)

        # 7. Add budget comparison rows if available
        if budget_data:
            rows = self._add_budget_comparison(rows, budget_data, actual_periods)

        # 8. Attach computed metrics to memo (not as rows)
        computed_metrics = self._get_computed_metrics()

        result = {
            "periods": all_periods,
            "forecastStartIndex": len(actual_periods),
            "rows": rows,
            "view": view,
        }
        if computed_metrics:
            result["computed_metrics"] = computed_metrics
        if forecast_id:
            result["forecast_id"] = forecast_id

        return result

    # ------------------------------------------------------------------
    # Step 1: Pull actuals from fpa_actuals
    # ------------------------------------------------------------------

    def _pull_actuals(
        self,
        start: Optional[str],
        end: Optional[str],
        excluded_sources: Optional[List[str]] = None,
        source_multipliers: Optional[Dict[str, float]] = None,
        terminated_sources: Optional[Dict[str, str]] = None,
        entity_id: Optional[str] = None,
    ) -> Tuple[Dict[str, Dict[str, float]], List[str]]:
        """
        Returns:
            actuals_by_key_period: {"revenue": {"2025-01": 500000, ...}, ...}
                Keys are "category" or "category:subcategory"
            periods: sorted list of period strings

        Contract scenario params (used by scenario engine):
            excluded_sources: list of source strings to zero out (e.g. ["document:abc"])
            source_multipliers: {source: factor} to scale amounts (e.g. 0.8 = 20% reduction)
            terminated_sources: {source: "YYYY-MM"} to zero out after that period
        """
        from app.core.supabase_client import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            logger.warning("Supabase client unavailable — cannot fetch actuals")
            return {}, []

        # Always include hierarchy_path for correct key resolution.
        # Include source when contract filtering is active.
        has_contract_filters = excluded_sources or source_multipliers or terminated_sources
        select_cols = "period, category, subcategory, hierarchy_path, amount, source" if has_contract_filters else "period, category, subcategory, hierarchy_path, amount"

        query = sb.table("fpa_actuals").select(select_cols)
        if self.company_id:
            query = query.eq("company_id", self.company_id)
        elif self.fund_id:
            query = query.eq("fund_id", self.fund_id)
        else:
            return {}, []
        if entity_id:
            query = query.eq("entity_id", entity_id)
        if start:
            query = query.gte("period", f"{start}-01")
        if end:
            query = query.lte("period", f"{end}-01")

        result = query.order("period").execute()

        if not result.data:
            return {}, []

        actuals: Dict[str, Dict[str, float]] = {}
        periods_set: set = set()

        excluded = set(excluded_sources or [])
        multipliers = source_multipliers or {}
        terminated = terminated_sources or {}

        for row in result.data:
            period = _normalize_period(row.get("period", ""))
            if not period:
                logger.warning("Skipping actuals row with unparseable period: %r", row.get("period"))
                continue
            cat = row["category"]
            sub = row.get("subcategory")
            hp = row.get("hierarchy_path", "")
            amount = float(row["amount"])
            source = row.get("source", "")

            # Apply contract-level scenario modifications
            if has_contract_filters and source:
                if source in excluded:
                    continue
                if source in terminated and period > terminated[source]:
                    continue
                if source in multipliers:
                    amount = amount * multipliers[source]

            # Use hierarchy_path as key when it encodes >2 levels
            if hp and hp.count("/") > 1:
                key = hp
            elif sub:
                key = f"{cat}:{sub}"
            else:
                key = cat

            periods_set.add(period)
            actuals.setdefault(key, {})[period] = (
                actuals.get(key, {}).get(period, 0) + amount
            )

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
        from app.services.company_data_pull import pull_company_data

        cd = self._company_data
        try:
            cd = cd or pull_company_data(self.company_id)
            company_data = cd.to_forecast_seed()
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
            try:
                y, m = map(int, last.split("-"))
                m += 1
                if m > 12:
                    m, y = 1, y + 1
                forecast_start = f"{y:04d}-{m:02d}"
            except (ValueError, TypeError) as e:
                logger.error("Cannot parse last actual period %r for forecast start: %s", last, e)
                today = date.today()
                forecast_start = f"{today.year:04d}-{today.month:02d}"
        else:
            today = date.today()
            forecast_start = f"{today.year:04d}-{today.month:02d}"

        # Route through ForecastMethodRouter to auto-select the best of 7 methods
        # (driver_based, advanced_regression, seasonal, regression, budget_pct,
        #  growth_rate, manual) instead of always using raw growth_rate decay.
        from app.services.forecast_method_router import ForecastMethodRouter
        router = ForecastMethodRouter()
        method, reasoning = router.auto_select_method(self.company_id, company_data, company_data=cd)
        monthly, provenance = router.build_forecast(
            company_id=self.company_id,
            method=method,
            seed_data=company_data,
            months=months,
            start_period=forecast_start,
            company_data=cd,
        )
        # Store provenance so agent can explain methodology
        company_data["_forecast_method"] = method
        company_data["_forecast_reasoning"] = reasoning
        company_data["_forecast_provenance"] = provenance

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
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Discover dynamic subcategory rows from fpa_actuals keys.

        Whatever subcategories the CSV/ERP upserted — those are the children.
        Returns: {parent_id: [child_defs]}
        """
        children: Dict[str, List[Dict[str, Any]]] = {pid: [] for pid in PARENT_IDS}
        seen: set = set()

        for key in sorted(actuals.keys()):
            if ":" in key:
                cat, sub = key.split(":", 1)
            elif "/" in key and key.count("/") > 1:
                parts = key.split("/")
                cat = parts[0]
                sub = parts[-1]
            else:
                continue  # bare parent key — skeleton handles it

            if cat in DERIVED_CATEGORIES:
                continue

            parent_id = CATEGORY_TO_PARENT.get(cat, cat)
            if parent_id is None or parent_id not in PARENT_IDS:
                continue

            if key in seen:
                continue
            seen.add(key)

            depth = 2 if parent_id.startswith("opex_") else 1
            children[parent_id].append({
                "id": key,
                "label": sub.replace("_", " ").title(),
                "subcategory": sub,
                "parentId": parent_id,
                "depth": depth,
            })

        return children

    # ------------------------------------------------------------------
    # Step 5: Assemble final rows — fixed skeleton + dynamic subcategories
    # ------------------------------------------------------------------

    def _assemble_rows(
        self,
        line_items: Dict[str, List[Dict[str, Any]]],
        actuals: Dict[str, Dict[str, float]],
        forecast: Dict[str, Dict[str, float]],
        all_periods: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Fixed skeleton parents + dynamic subcategory children.

        Every skeleton row is a parent. Three kinds:
        1. Leaf parents (revenue, cogs, opex_rd/sm/ga) — sum their dynamic children,
           or use direct actuals/forecast if no children were discovered.
        2. Formula parents (gross_profit, total_opex, ebitda) — derive from other
           parents. No children. Values are pushed into the parent row itself.

        No separate "computed" rows. No duplicates.
        """
        rows: List[Dict[str, Any]] = []
        self._parent_totals: Dict[str, Dict[str, Optional[float]]] = {}

        for skel_id, label, section, depth in SKELETON:
            # --- Formula rows: derive from other parent totals ---
            if skel_id in FORMULA_ROWS:
                parent_values = self._eval_formula(skel_id, all_periods, actuals, forecast)
                self._parent_totals[skel_id] = parent_values
                rows.append({
                    "id": skel_id,
                    "label": label,
                    "depth": depth,
                    "section": section,
                    "isTotal": True,
                    "values": parent_values,
                })
                continue

            # --- Leaf parents: sum dynamic children ---
            children = line_items.get(skel_id, [])
            child_rows: List[Dict[str, Any]] = []

            for child in children:
                child_id = child["id"]
                values: Dict[str, Optional[float]] = {}
                for p in all_periods:
                    val = actuals.get(child_id, {}).get(p)
                    if val is None:
                        val = forecast.get(p, {}).get(child_id)
                    values[p] = val
                child_rows.append({
                    "id": child_id,
                    "label": child["label"],
                    "depth": child["depth"],
                    "section": section,
                    "parentId": skel_id,
                    "values": values,
                })

            # Parent value: sum of children, or direct actuals/forecast
            parent_values: Dict[str, Optional[float]] = {}
            for p in all_periods:
                if child_rows:
                    total = 0.0
                    found = False
                    for cr in child_rows:
                        v = cr["values"].get(p)
                        if v is not None:
                            total += v
                            found = True
                    if found:
                        parent_values[p] = total
                    else:
                        val = actuals.get(skel_id, {}).get(p)
                        if val is None:
                            val = forecast.get(p, {}).get(skel_id)
                        parent_values[p] = val
                else:
                    val = actuals.get(skel_id, {}).get(p)
                    if val is None:
                        val = forecast.get(p, {}).get(skel_id)
                    parent_values[p] = val

            self._parent_totals[skel_id] = parent_values

            rows.append({
                "id": skel_id,
                "label": label,
                "depth": depth,
                "section": section,
                "isTotal": bool(child_rows),
                "values": parent_values,
            })
            for cr in child_rows:
                rows.append(cr)

        return rows

    def _eval_formula(
        self,
        row_id: str,
        periods: List[str],
        actuals: Dict[str, Dict[str, float]],
        forecast: Dict[str, Dict[str, float]],
    ) -> Dict[str, Optional[float]]:
        """Evaluate a formula parent row from already-computed parent totals."""
        values: Dict[str, Optional[float]] = {}
        for p in periods:
            if row_id == "gross_profit":
                rev = self._parent_totals.get("revenue", {}).get(p)
                cogs = self._parent_totals.get("cogs", {}).get(p)
                if rev is not None and cogs is not None:
                    values[p] = rev - cogs
                elif rev is not None:
                    values[p] = rev
                else:
                    values[p] = actuals.get("gross_profit", {}).get(p) or forecast.get(p, {}).get("gross_profit")

            elif row_id == "total_opex":
                rd = self._parent_totals.get("opex_rd", {}).get(p) or 0
                sm = self._parent_totals.get("opex_sm", {}).get(p) or 0
                ga = self._parent_totals.get("opex_ga", {}).get(p) or 0
                total = rd + sm + ga
                values[p] = total if total else (
                    actuals.get("opex_total", {}).get(p) or forecast.get(p, {}).get("total_opex")
                )

            elif row_id == "ebitda":
                gp = self._parent_totals.get("gross_profit", {}).get(p)
                opex = self._parent_totals.get("total_opex", {}).get(p)
                if gp is not None and opex is not None:
                    values[p] = gp - opex
                elif gp is not None:
                    values[p] = gp
                else:
                    values[p] = actuals.get("ebitda", {}).get(p) or forecast.get(p, {}).get("ebitda")

        return values

    # ------------------------------------------------------------------
    # Saved forecast loading
    # ------------------------------------------------------------------

    def _pull_saved_forecast(
        self, forecast_id: str, actual_periods: List[str]
    ) -> Tuple[Dict[str, Dict[str, float]], List[str]]:
        """Load a persisted forecast and reshape to same format as _build_forecast."""
        try:
            from app.services.forecast_persistence_service import ForecastPersistenceService
            fps = ForecastPersistenceService()
            loaded = fps.load_forecast(forecast_id)
            if not loaded or not loaded.get("lines"):
                return {}, []
            return self._reshape_forecast_lines(loaded["lines"], actual_periods)
        except Exception as e:
            logger.warning(f"Failed to load saved forecast {forecast_id}: {e}")
            return {}, []

    def _pull_active_forecast(
        self, actual_periods: List[str]
    ) -> Tuple[Dict[str, Dict[str, float]], List[str]]:
        """Load the active forecast for this company."""
        try:
            from app.services.forecast_persistence_service import ForecastPersistenceService
            fps = ForecastPersistenceService()
            active = fps.get_active_forecast(self.company_id)
            if not active:
                return {}, []
            loaded = fps.load_forecast(active["id"])
            if not loaded or not loaded.get("lines"):
                return {}, []
            return self._reshape_forecast_lines(loaded["lines"], actual_periods)
        except Exception as e:
            logger.warning(f"Failed to load active forecast: {e}")
            return {}, []

    def _reshape_forecast_lines(
        self, lines: List[Dict], actual_periods: List[str]
    ) -> Tuple[Dict[str, Dict[str, float]], List[str]]:
        """Reshape fpa_forecast_lines into the format expected by _assemble_rows."""
        forecast: Dict[str, Dict[str, float]] = {}
        periods_set: set = set()
        actual_set = set(actual_periods)

        for line in lines:
            period = _normalize_period(line.get("period", ""))
            if not period:
                logger.warning("Skipping forecast line with unparseable period: %r", line.get("period"))
                continue
            if period in actual_set:
                continue  # Don't overlap with actuals
            category = line["category"]
            amount = float(line["amount"])
            periods_set.add(period)
            forecast.setdefault(period, {})[category] = amount

        forecast_periods = sorted(periods_set)
        return forecast, forecast_periods

    # ------------------------------------------------------------------
    # Budget loading
    # ------------------------------------------------------------------

    def _pull_budget(self, budget_id: Optional[str] = None) -> Optional[Dict[str, Dict[str, float]]]:
        """Pull budget lines and reshape to {category: {period: amount}}.

        If no budget_id, finds the latest approved budget for the company.
        """
        from app.core.supabase_client import get_supabase_client

        sb = get_supabase_client()
        if not sb:
            return None

        try:
            if not budget_id:
                budget_result = (
                    sb.table("budgets")
                    .select("id, fiscal_year")
                    .eq("company_id", self.company_id)
                    .eq("status", "approved")
                    .order("fiscal_year", desc=True)
                    .limit(1)
                    .execute()
                )
                if not budget_result.data:
                    return None
                budget_id = budget_result.data[0]["id"]

            lines = (
                sb.table("budget_lines")
                .select("*")
                .eq("budget_id", budget_id)
                .execute()
            )
            if not lines.data:
                return None

            # Get fiscal year for period generation
            budget_meta = (
                sb.table("budgets")
                .select("fiscal_year")
                .eq("id", budget_id)
                .limit(1)
                .execute()
            )
            fiscal_year = budget_meta.data[0]["fiscal_year"] if budget_meta.data else 2026

            # Reshape: budget_lines have m1-m12 columns
            budget_data: Dict[str, Dict[str, float]] = {}
            for line in lines.data:
                category = line.get("category", "")
                if not category:
                    continue
                for m in range(1, 13):
                    val = line.get(f"m{m}")
                    if val is not None:
                        period = f"{fiscal_year}-{m:02d}"
                        budget_data.setdefault(category, {})[period] = float(val)

            return budget_data
        except Exception as e:
            logger.warning(f"Failed to load budget: {e}")
            return None

    def _add_budget_comparison(
        self,
        rows: List[Dict[str, Any]],
        budget_data: Dict[str, Dict[str, float]],
        actual_periods: List[str],
    ) -> List[Dict[str, Any]]:
        """Add budget and variance rows alongside existing data rows."""
        new_rows = []
        for row in rows:
            new_rows.append(row)
            row_id = row.get("id", "")
            if row.get("isHeader") or row_id not in budget_data:
                continue

            # Budget row
            budget_values = {}
            for p in actual_periods:
                budget_values[p] = budget_data.get(row_id, {}).get(p)
            new_rows.append({
                "id": f"{row_id}_budget",
                "label": f"{row.get('label', '')} (Budget)",
                "depth": row.get("depth", 0) + 1,
                "section": row.get("section", ""),
                "isBudget": True,
                "values": budget_values,
            })

            # Variance row
            variance_values = {}
            for p in actual_periods:
                actual = row.get("values", {}).get(p)
                budget = budget_values.get(p)
                if actual is not None and budget is not None and budget != 0:
                    variance_values[p] = {
                        "delta": actual - budget,
                        "pct": (actual - budget) / abs(budget),
                    }
            if variance_values:
                new_rows.append({
                    "id": f"{row_id}_variance",
                    "label": f"{row.get('label', '')} (Variance)",
                    "depth": row.get("depth", 0) + 1,
                    "section": row.get("section", ""),
                    "isVariance": True,
                    "values": variance_values,
                })

        return new_rows

    # ------------------------------------------------------------------
    # Computed metrics rows
    # ------------------------------------------------------------------

    def _get_computed_metrics(self) -> Optional[Dict[str, Any]]:
        """Return unit economics as memo data (not rows)."""
        try:
            from app.services.computed_metrics import ComputedMetrics, COMPUTED_LABELS
            from app.services.company_data_pull import pull_company_data

            cd = self._company_data or pull_company_data(self.company_id)
            seed = cd.to_forecast_seed()
            if not seed.get("_detected_acv") and not seed.get("_detected_customer_count"):
                return None

            metrics = ComputedMetrics.compute_all(seed)
            if not metrics or all(k.startswith("_") for k in metrics):
                return None

            result = {}
            for metric_id, value in metrics.items():
                if metric_id.startswith("_"):
                    continue
                label = COMPUTED_LABELS.get(metric_id, metric_id.replace("_", " ").title())
                derivation = metrics.get("_derivations", {}).get(metric_id)
                result[metric_id] = {
                    "label": label,
                    "value": value,
                    "derivation": derivation,
                }
            return result if result else None
        except Exception as e:
            logger.debug(f"Computed metrics skipped: {e}")
            return None

    # ------------------------------------------------------------------
    # Group consolidation entry point
    # ------------------------------------------------------------------

    async def build_group_pnl(
        self,
        parent_entity_id: str,
        period_start: Optional[str] = None,
        period_end: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build consolidated group P&L with IC elimination.

        Delegates to ConsolidationEngine, returns result formatted for the matrix.
        """
        from app.services.consolidation_engine import ConsolidationEngine

        engine = ConsolidationEngine(self.company_id, self.fund_id)
        result = await engine.consolidate_pnl(
            parent_entity_id, period_start, period_end,
        )

        return {
            "consolidated": dict(result.consolidated),
            "eliminations": [
                {
                    "category": e.category,
                    "subcategory": e.subcategory,
                    "period": e.period,
                    "amount": e.amount,
                    "description": e.description,
                }
                for e in result.eliminations
            ],
            "entities_consolidated": result.entities_consolidated,
            "entities_equity_method": result.entities_equity_method,
            "minority_interest": result.minority_interest,
            "periods": result.periods,
            "audit": result.audit,
        }
