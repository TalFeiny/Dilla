"""Normalize extraction time_series → fpa_actuals rows."""

from datetime import date
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Metrics from extraction that map to fpa_actuals categories
METRIC_TO_CATEGORY = {
    "revenue": "revenue",
    "cogs": "cogs",
    "opex": "opex_total",
    "ebitda": "ebitda",
    "cash_balance": "cash_balance",
    "headcount": "headcount",
    "arr": "arr",
    "mrr": "mrr",
    "burn_rate": "burn_rate",
    "customers": "customers",
}

# Standard subcategory taxonomy for cost center granularity
SUBCATEGORY_TAXONOMY = {
    "opex_rd": [
        "engineering_salaries", "infra_cloud", "tools_licenses",
        "contractor", "research",
    ],
    "opex_sm": [
        "paid_acquisition", "content_marketing", "sales_salaries",
        "events", "partnerships",
    ],
    "opex_ga": [
        "finance_legal", "office", "admin_salaries",
        "insurance", "other_ga",
    ],
    "cogs": [
        "hosting", "support_salaries", "payment_processing",
        "third_party_apis", "data_costs",
    ],
}

# Subcategory → parent category mapping (auto-generated from taxonomy)
SUBCATEGORY_TO_PARENT = {}
for parent_cat, subcats in SUBCATEGORY_TAXONOMY.items():
    for sub in subcats:
        SUBCATEGORY_TO_PARENT[sub] = parent_cat

# ---------------------------------------------------------------------------
# Business-model-aware taxonomy overrides
# Extends the base SaaS taxonomy with model-specific subcategories.
# Uses the same 14 categories already in intelligent_gap_filler.py.
# ---------------------------------------------------------------------------

BUSINESS_MODEL_TAXONOMY: Dict[str, Dict[str, list]] = {
    "saas": {},  # base taxonomy IS saas — no overrides needed
    "ai_saas": {
        "cogs": ["hosting", "api_inference_costs", "data_costs", "support_salaries", "payment_processing"],
    },
    "ai_first": {
        "cogs": ["api_inference_costs", "data_costs", "hosting", "model_training", "support_salaries"],
        "opex_rd": ["ml_engineering", "data_engineering", "infra_cloud", "tools_licenses", "research"],
    },
    "marketplace": {
        "cogs": ["payment_processing", "trust_safety", "support_salaries", "hosting"],
        "opex_sm": ["supply_acquisition", "demand_acquisition", "content_marketing", "sales_salaries", "partnerships"],
    },
    "ecommerce": {
        "cogs": ["inventory", "fulfillment", "shipping_costs", "returns", "payment_processing"],
        "opex_sm": ["paid_acquisition", "email_marketing", "affiliate", "content_marketing", "retail_ops"],
    },
    "services": {
        "cogs": ["delivery_salaries", "subcontractors", "travel", "tools"],
        "opex_sm": ["business_development", "proposals", "events", "partnerships"],
    },
    "tech_enabled_services": {
        "cogs": ["delivery_salaries", "subcontractors", "hosting", "tools"],
        "opex_sm": ["business_development", "content_marketing", "sales_salaries", "partnerships"],
    },
    "hardware": {
        "cogs": ["materials", "manufacturing", "assembly", "quality_control", "logistics"],
        "opex_rd": ["hardware_engineering", "firmware", "industrial_design", "prototyping", "certifications"],
    },
    "deeptech_hardware": {
        "cogs": ["materials", "manufacturing", "quality_control", "logistics", "calibration"],
        "opex_rd": ["research", "hardware_engineering", "firmware", "prototyping", "certifications"],
    },
    "industrial": {
        "cogs": ["raw_materials", "manufacturing", "labor", "maintenance", "logistics"],
        "opex_ga": ["facility_lease", "utilities", "insurance", "admin_salaries", "compliance"],
        "opex_sm": ["sales_salaries", "distributor_commissions", "trade_shows", "partnerships"],
    },
    "manufacturing": {
        "cogs": ["raw_materials", "direct_labor", "manufacturing_overhead", "quality_control", "logistics"],
        "opex_ga": ["facility_lease", "utilities", "insurance", "admin_salaries", "finance_legal"],
    },
    "materials": {
        "cogs": ["raw_materials", "processing", "labor", "logistics", "waste_disposal"],
        "opex_ga": ["facility_lease", "utilities", "compliance", "insurance", "admin_salaries"],
    },
    "fintech": {
        "cogs": ["payment_processing", "compliance_ops", "fraud_prevention", "support_salaries", "banking_partner_fees"],
        "opex_ga": ["compliance", "finance_legal", "audit", "admin_salaries", "insurance"],
    },
    "rollup": {
        "cogs": ["acquired_entity_cogs", "integration_costs", "support_salaries", "hosting"],
        "opex_ga": ["integration_ops", "finance_legal", "admin_salaries", "insurance", "office"],
    },
    "gtm_software": {
        "opex_sm": ["paid_acquisition", "sales_salaries", "content_marketing", "events", "channel_partners"],
    },
    "full_stack_ai": {
        "cogs": ["api_inference_costs", "data_costs", "hosting", "model_training", "support_salaries"],
        "opex_rd": ["ml_engineering", "data_engineering", "infra_cloud", "research", "tools_licenses"],
    },
}

# Register all business-model subcategories in SUBCATEGORY_TO_PARENT
for _model_overrides in BUSINESS_MODEL_TAXONOMY.values():
    for _cat, _subs in _model_overrides.items():
        for _sub in _subs:
            if _sub not in SUBCATEGORY_TO_PARENT:
                SUBCATEGORY_TO_PARENT[_sub] = _cat


def get_taxonomy_for_model(business_model: str = "saas") -> Dict[str, list]:
    """Merge base SUBCATEGORY_TAXONOMY with business-model-specific overrides."""
    merged = {k: list(v) for k, v in SUBCATEGORY_TAXONOMY.items()}
    model_overrides = BUSINESS_MODEL_TAXONOMY.get(business_model.lower(), {})
    for cat, subs in model_overrides.items():
        merged[cat] = subs  # model-specific replaces generic
    return merged


def classify_label_to_subcategory(
    label: str, business_model: str = "saas"
) -> tuple:
    """Map a P&L line-item label to (category, subcategory).

    Uses keyword matching against the active taxonomy for the business model.
    Returns ("", "") if no match found.
    """
    normalized = label.lower().strip().replace("-", "_").replace(" ", "_")
    taxonomy = get_taxonomy_for_model(business_model)

    # Direct subcategory match
    for cat, subs in taxonomy.items():
        for sub in subs:
            if sub in normalized or normalized in sub:
                return (cat, sub)

    # Keyword-based fallback patterns (business-model-agnostic)
    _KEYWORD_MAP = {
        ("revenue", "subscription"): ["subscription", "recurring", "mrr", "arr", "saas"],
        ("revenue", "professional_services"): ["professional", "consulting", "advisory", "implementation"],
        ("revenue", "usage_based"): ["usage", "consumption", "metered", "api_calls"],
        ("revenue", "take_rate"): ["take_rate", "commission", "marketplace_fee", "gmv"],
        ("revenue", "product_sales"): ["product_sales", "device_sales", "unit_sales"],
        ("cogs", "hosting"): ["hosting", "aws", "gcp", "azure", "cloud", "servers"],
        ("cogs", "support_salaries"): ["support", "customer_success", "cs_team"],
        ("cogs", "payment_processing"): ["stripe", "payment", "processing_fee", "interchange"],
        ("cogs", "inventory"): ["inventory", "raw_material", "goods", "stock"],
        ("cogs", "fulfillment"): ["fulfillment", "warehouse", "picking", "packing", "3pl"],
        ("cogs", "raw_materials"): ["raw_materials", "feedstock", "components", "supplies"],
        ("cogs", "manufacturing"): ["manufacturing", "production", "assembly_line", "factory"],
        ("cogs", "labor"): ["direct_labor", "shop_floor", "production_staff", "hourly_labor"],
        ("cogs", "logistics"): ["logistics", "freight", "shipping", "distribution", "trucking"],
        ("opex_rd", "engineering_salaries"): ["engineering", "developer", "software_eng", "tech_team"],
        ("opex_rd", "infra_cloud"): ["infra", "devops", "platform"],
        ("opex_rd", "tools_licenses"): ["tools", "license", "software_sub", "jira", "github"],
        ("opex_rd", "hardware_engineering"): ["hardware_eng", "electrical_eng", "mechanical_eng"],
        ("opex_sm", "paid_acquisition"): ["paid", "ads", "advertising", "google_ads", "meta_ads", "sem", "ppc"],
        ("opex_sm", "content_marketing"): ["content", "seo", "blog", "social_media"],
        ("opex_sm", "sales_salaries"): ["sales_team", "sales_salary", "ae_", "sdr_", "bdr_"],
        ("opex_ga", "finance_legal"): ["legal", "accounting", "audit", "finance_team", "cfo"],
        ("opex_ga", "office"): ["office", "rent", "utilities", "coworking"],
        ("opex_ga", "facility_lease"): ["facility", "warehouse_lease", "factory_rent", "plant_lease"],
        ("opex_ga", "admin_salaries"): ["admin", "hr", "people_ops", "office_manager"],
        ("opex_ga", "insurance"): ["insurance", "d&o", "e&o", "liability"],
        ("opex_ga", "compliance"): ["compliance", "regulatory", "licensing"],
    }

    for (cat, sub), keywords in _KEYWORD_MAP.items():
        if any(kw in normalized for kw in keywords):
            return (cat, sub)

    return ("", "")


def _resolve_account_code(
    company_id: str, account_code: str, erp_source: str = "unknown"
) -> Optional[Dict]:
    """Resolve ERP account code to category via erp_account_mappings or patterns."""
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        return None
    try:
        result = sb.rpc("resolve_category_by_code", {
            "p_account_code": account_code,
            "p_erp_source": erp_source,
        }).execute()
        if result.data:
            return {"category": result.data, "subcategory": ""}
    except Exception as e:
        logger.debug(f"Account code resolution failed for {account_code}: {e}")
    return None


def ingest_time_series(
    time_series: List[Dict[str, Any]],
    company_id: str,
    fund_id: Optional[str],
    document_id: int,
    source: str = "csv_upload",
) -> int:
    """Transform extracted time_series into fpa_actuals rows and upsert.

    Enhanced: rows can include a `subcategory` field. If present, stores at
    that granularity AND aggregates up to the parent category for backward
    compatibility with services that read by category.
    """
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        return 0

    rows = []
    # Track subcategory amounts per (period, parent_category) for aggregation
    aggregation: Dict[str, Dict[str, float]] = {}  # "period|parent_cat" → {sub: amount}

    for entry in time_series:
        period_str = entry.get("period")
        if not period_str:
            continue
        # Normalize to first-of-month date
        try:
            if len(period_str) == 7:  # "2025-01"
                period = date.fromisoformat(f"{period_str}-01")
            else:
                period = date.fromisoformat(period_str)
                period = period.replace(day=1)
        except ValueError:
            logger.warning("Skipping unparseable period: %s", period_str)
            continue

        # Standard category metrics
        for metric_key, category in METRIC_TO_CATEGORY.items():
            value = entry.get(metric_key)
            if value is None:
                continue
            try:
                amount = float(value)
            except (ValueError, TypeError):
                continue

            rows.append({
                "company_id": company_id,
                "fund_id": fund_id,
                "document_id": document_id,
                "period": period.isoformat(),
                "category": category,
                "subcategory": "",
                "hierarchy_path": category,
                "amount": amount,
                "source": source,
            })

        # Account code resolution: if entry has erp_account_code but no category, resolve it
        if not entry.get("category") and entry.get("erp_account_code"):
            resolved = _resolve_account_code(
                company_id, entry["erp_account_code"],
                erp_source=entry.get("erp_source", "unknown"),
            )
            if resolved:
                cat = resolved["category"]
                amt = entry.get("amount")
                if cat and amt is not None:
                    try:
                        amount = float(amt)
                    except (ValueError, TypeError):
                        pass
                    else:
                        rows.append({
                            "company_id": company_id,
                            "fund_id": fund_id,
                            "document_id": document_id,
                            "period": period.isoformat(),
                            "category": cat,
                            "subcategory": resolved.get("subcategory", ""),
                            "hierarchy_path": cat,
                            "amount": amount,
                            "source": source,
                        })

        # Subcategory metrics: e.g. entry has "subcategory": "engineering_salaries", "amount": 50000
        # Known taxonomy takes priority; unknown subcategories accepted when caller provides parent_category
        subcategory = entry.get("subcategory")
        if subcategory:
            parent_cat = SUBCATEGORY_TO_PARENT.get(subcategory) or entry.get("parent_category") or entry.get("category")
            if not parent_cat:
                continue  # no parent resolvable — skip
            amount_val = entry.get("amount")
            if amount_val is not None:
                try:
                    amount = float(amount_val)
                except (ValueError, TypeError):
                    continue

                # Build hierarchy_path
                hierarchy_path = entry.get("hierarchy_path") or f"{parent_cat}/{subcategory}"

                # Store subcategory row
                rows.append({
                    "company_id": company_id,
                    "fund_id": fund_id,
                    "document_id": document_id,
                    "period": period.isoformat(),
                    "category": parent_cat,
                    "subcategory": subcategory,
                    "hierarchy_path": hierarchy_path,
                    "amount": amount,
                    "source": source,
                })

                # Track for parent aggregation
                agg_key = f"{period.isoformat()}|{parent_cat}"
                aggregation.setdefault(agg_key, {})[subcategory] = amount

    # Auto-aggregate subcategories to parent category totals
    for agg_key, subs in aggregation.items():
        period_str, parent_cat = agg_key.split("|")
        total = sum(subs.values())
        rows.append({
            "company_id": company_id,
            "fund_id": fund_id,
            "document_id": document_id,
            "period": period_str,
            "category": parent_cat,
            "subcategory": "",
            "hierarchy_path": parent_cat,
            "amount": total,
            "source": source,
        })

    if not rows:
        return 0

    # Upsert: unique index is (company_id, period, category, subcategory, hierarchy_path, source)
    sb.table("fpa_actuals").upsert(
        rows,
        on_conflict="company_id,period,category,subcategory,hierarchy_path,source",
    ).execute()

    return len(rows)


def get_actuals_for_forecast(
    company_id: str, category: str = "revenue", months: int = 12
) -> List[Dict[str, Any]]:
    """Pull recent actuals to seed forecast engines."""
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        return []

    rows = (
        sb.table("fpa_actuals")
        .select("period, amount")
        .eq("company_id", company_id)
        .eq("category", category)
        .order("period", desc=True)
        .limit(months)
        .execute()
        .data
    )
    return sorted(rows, key=lambda r: r["period"])  # chronological


def _detect_frequency(actuals: List[Dict[str, Any]]) -> int:
    """Detect data frequency from period gaps. Returns annualization multiplier."""
    if len(actuals) < 2:
        return 12  # default to monthly assumption
    gaps = []
    for i in range(1, len(actuals)):
        prev = date.fromisoformat(actuals[i - 1]["period"])
        curr = date.fromisoformat(actuals[i]["period"])
        gaps.append((curr - prev).days)
    median_gap = sorted(gaps)[len(gaps) // 2]
    if median_gap > 300:  # ~yearly
        return 1
    elif median_gap > 60:  # ~quarterly
        return 4
    return 12  # monthly


def seed_forecast_from_actuals(company_id: str) -> Dict[str, Any]:
    """Build company_data dict from actuals for cash_flow_planning_service.

    All analytical metrics are computed here from ledger actuals — they are
    derived fields, not stored values. The downstream service is a consumer
    and should never re-derive these.

    Computed metrics (when underlying actuals exist):
      burn_rate    = COGS + OpEx  (gross burn — for consumer opex estimation)
      net_burn     = (COGS + OpEx) - revenue  (positive = burning cash)
      gross_margin = (revenue - COGS) / revenue
      growth_rate  = trailing MoM annualized
      runway       = cash_balance / abs(net_burn)  (only when burning)

    NOT computed here (require cohort-level data we don't have):
      churn_rate   — needs churned customer count, not just totals
      nrr          — needs same-cohort ARR, not total ARR
      cac          — needs S&M spend + new customer count
    These should be computed by the agent when cohort data is available.
    """
    revenue_actuals = get_actuals_for_forecast(company_id, "revenue")
    cogs_actuals = get_actuals_for_forecast(company_id, "cogs")
    opex_actuals = get_actuals_for_forecast(company_id, "opex_total")
    cash_actuals = get_actuals_for_forecast(company_id, "cash_balance")
    headcount_actuals = get_actuals_for_forecast(company_id, "headcount")

    base_revenue = revenue_actuals[-1]["amount"] if revenue_actuals else 0
    growth_rate = _trailing_growth(revenue_actuals) if len(revenue_actuals) >= 2 else 0.5

    last_rev = revenue_actuals[-1]["amount"] if revenue_actuals else 0
    last_cogs = cogs_actuals[-1]["amount"] if cogs_actuals else 0
    last_opex = opex_actuals[-1]["amount"] if opex_actuals else 0

    # --- Gross burn = COGS + OpEx (total monthly expenses) ---
    # Consumer uses this for opex split estimation when no revenue exists
    burn_rate = (last_cogs + last_opex) if (cogs_actuals or opex_actuals) else None

    # --- Net burn = expenses - revenue (positive = burning cash) ---
    net_burn = None
    if burn_rate is not None:
        net_burn = burn_rate - last_rev

    # --- Gross margin = (revenue - COGS) / revenue ---
    gross_margin = None
    if last_rev > 0 and cogs_actuals:
        gross_margin = (last_rev - last_cogs) / last_rev

    # --- Runway = cash / net_burn, only meaningful when burning ---
    cash_balance = cash_actuals[-1]["amount"] if cash_actuals else None
    runway = None
    if cash_balance is not None and net_burn is not None and net_burn > 0:
        runway = cash_balance / net_burn  # months

    # --- Cost per head = (COGS + OpEx) / headcount ---
    # Derived when both expense and headcount actuals exist
    cost_per_head = None
    last_headcount = headcount_actuals[-1]["amount"] if headcount_actuals else None
    if burn_rate is not None and last_headcount and last_headcount > 0:
        cost_per_head = burn_rate / last_headcount

    result: Dict[str, Any] = {
        "revenue": base_revenue,
        "growth_rate": growth_rate,
        "burn_rate": burn_rate,        # gross burn — for consumer opex estimation
        "net_burn": net_burn,          # net burn (positive = burning) — for runway
        "cash_balance": cash_balance,
        "company_id": company_id,
    }
    if gross_margin is not None:
        result["gross_margin"] = gross_margin
    if runway is not None:
        result["runway_months"] = runway
    if cost_per_head is not None:
        result["cost_per_head"] = cost_per_head
    if last_headcount is not None:
        result["headcount"] = last_headcount

    # --- Enhanced: trailing growth analysis ---
    if len(revenue_actuals) >= 4:
        trailing_growth_3m = _trailing_growth_window(revenue_actuals, window=3)
        trailing_growth_6m = _trailing_growth_window(revenue_actuals, window=6) if len(revenue_actuals) >= 7 else growth_rate
        result["_trailing_growth_3m"] = trailing_growth_3m
        result["_trailing_growth_6m"] = trailing_growth_6m
        result["_growth_trend"] = "accelerating" if trailing_growth_3m > trailing_growth_6m else "decelerating"

    # --- Enhanced: OpEx breakdown from subcategories ---
    rd_actuals = get_actuals_for_forecast(company_id, "opex_rd")
    sm_actuals = get_actuals_for_forecast(company_id, "opex_sm")
    ga_actuals = get_actuals_for_forecast(company_id, "opex_ga")
    if rd_actuals:
        result["_rd_spend"] = rd_actuals[-1]["amount"]
    if sm_actuals:
        result["_sm_spend"] = sm_actuals[-1]["amount"]
    if ga_actuals:
        result["_ga_spend"] = ga_actuals[-1]["amount"]

    # --- Enhanced: detect driver data from actuals ---
    customer_actuals = get_actuals_for_forecast(company_id, "customers")
    arr_actuals = get_actuals_for_forecast(company_id, "arr")

    if customer_actuals and len(customer_actuals) >= 2:
        last_customers = customer_actuals[-1]["amount"]
        prev_customers = customer_actuals[-2]["amount"]
        result["_detected_customer_count"] = last_customers
        if prev_customers and prev_customers > 0 and last_customers < prev_customers:
            # Monthly churn approximation from customer decline
            monthly_churn = (prev_customers - last_customers) / prev_customers
            result["_detected_churn_rate"] = monthly_churn

    if arr_actuals and customer_actuals:
        last_arr = arr_actuals[-1]["amount"]
        last_customers_val = customer_actuals[-1]["amount"] if customer_actuals else 0
        if last_customers_val and last_customers_val > 0:
            result["_detected_acv"] = last_arr / last_customers_val

    # --- Data quality score ---
    result["_data_quality"] = {
        "revenue_months": len(revenue_actuals),
        "has_opex_breakdown": bool(rd_actuals or sm_actuals or ga_actuals),
        "has_customer_data": bool(customer_actuals),
        "has_arr_data": bool(arr_actuals),
        "has_cash_data": bool(cash_actuals),
        "has_headcount": bool(headcount_actuals),
        "growth_trend": result.get("_growth_trend", "unknown"),
        "recommended_method": _recommend_method(result),
    }

    return result


def _trailing_growth(actuals: List[Dict[str, Any]]) -> float:
    """Compute trailing MoM growth rate from the last two actuals, annualized.

    CashFlowPlanningService expects an annual growth rate, so we convert
    the MoM rate: annual = (1 + mom) ** 12 - 1.
    """
    if len(actuals) < 2:
        return 0.0
    prev = actuals[-2]["amount"]
    curr = actuals[-1]["amount"]
    if prev and prev != 0:
        mom = (curr - prev) / abs(prev)
        # Cap MoM at ±50% to prevent annualized explosion
        mom = max(-0.5, min(0.5, mom))
        return (1 + mom) ** 12 - 1
    return 0.0


def _trailing_growth_window(actuals: List[Dict[str, Any]], window: int = 3) -> float:
    """Compute trailing growth rate over a window of months, annualized.

    Uses CAGR over the window instead of just last 2 points.
    """
    if len(actuals) < window + 1:
        return 0.0
    start_val = actuals[-(window + 1)]["amount"]
    end_val = actuals[-1]["amount"]
    if start_val and start_val > 0 and end_val and end_val > 0:
        monthly_growth = (end_val / start_val) ** (1 / window) - 1
        monthly_growth = max(-0.5, min(0.5, monthly_growth))
        return (1 + monthly_growth) ** 12 - 1
    return 0.0


def _recommend_method(seed_data: Dict[str, Any]) -> str:
    """Recommend forecast method based on data availability."""
    if seed_data.get("_detected_acv") and seed_data.get("_detected_customer_count"):
        return "driver_based"
    quality = seed_data.get("_data_quality", {})
    rev_months = quality.get("revenue_months", 0)
    if rev_months >= 12:
        return "seasonal"  # enough data for seasonal detection
    if rev_months >= 6:
        return "regression"
    return "growth_rate"


def get_subcategory_breakdown(
    company_id: str,
    parent_category: str,
    months: int = 12,
) -> Dict[str, List[Dict[str, Any]]]:
    """Get subcategory breakdown for a parent category.

    Returns: {subcategory_name: [{period, amount}, ...]}
    If no subcategory data exists, returns empty dict.
    """
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        return {}

    rows = (
        sb.table("fpa_actuals")
        .select("period, subcategory, amount")
        .eq("company_id", company_id)
        .eq("category", parent_category)
        .neq("subcategory", "")
        .order("period", desc=True)
        .limit(months * 10)  # generous limit for multiple subcategories
        .execute()
        .data
    )

    result: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows or []:
        sub = row.get("subcategory")
        if not sub:
            continue
        result.setdefault(sub, []).append({
            "period": row["period"][:7],
            "amount": float(row["amount"]),
        })

    # Sort each series chronologically
    for sub in result:
        result[sub].sort(key=lambda r: r["period"])

    return result


def get_subcategory_proportions(
    company_id: str,
    parent_category: str,
) -> Dict[str, float]:
    """Get latest subcategory proportions for a parent category.

    Returns: {subcategory: proportion} where proportions sum to ~1.0.
    Used by cash_flow_planning_service to decompose forecasts.
    """
    breakdown = get_subcategory_breakdown(company_id, parent_category, months=3)
    if not breakdown:
        return {}

    # Use latest period's values
    latest_values: Dict[str, float] = {}
    for sub, series in breakdown.items():
        if series:
            latest_values[sub] = series[-1]["amount"]

    total = sum(latest_values.values())
    if total <= 0:
        return {}

    return {sub: amount / total for sub, amount in latest_values.items()}


# ---------------------------------------------------------------------------
# Category metadata for P&L waterfall
# ---------------------------------------------------------------------------

CATEGORY_LABELS = {
    "revenue": "Revenue",
    "cogs": "COGS",
    "opex_total": "Operating Expenses",
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

CATEGORY_TO_SECTION = {
    "revenue": "revenue",
    "arr": "revenue",
    "mrr": "revenue",
    "cogs": "cogs",
    "opex_rd": "opex",
    "opex_sm": "opex",
    "opex_ga": "opex",
    "opex_total": "opex",
    "ebitda": "ebitda",
    "cash_balance": "bottom",
    "burn_rate": "bottom",
    "headcount": "operational",
    "customers": "operational",
}


def get_company_actuals(
    company_id: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Pull all actuals for a company, structured for P&L grid consumption.

    Returns:
        {
            "periods": ["2025-01", ...],
            "line_items": [{"key", "category", "subcategory", "label", "section"}, ...],
            "values": {"revenue": {"2025-01": 500000, ...}, ...}
        }
    """
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        return {"periods": [], "line_items": [], "values": {}}

    query = (
        sb.table("fpa_actuals")
        .select("period, category, subcategory, amount")
        .eq("company_id", company_id)
    )
    if start:
        query = query.gte("period", f"{start}-01")
    if end:
        query = query.lte("period", f"{end}-01")
    result = query.order("period").execute()

    periods_set: set = set()
    items_seen: Dict[str, Dict] = {}
    values: Dict[str, Dict[str, float]] = {}

    for row in result.data or []:
        period = row["period"][:7]  # "2025-01-01" -> "2025-01"
        cat = row["category"]
        sub = row.get("subcategory")
        amount = float(row["amount"])

        periods_set.add(period)
        key = f"{cat}:{sub}" if sub else cat
        if key not in items_seen:
            items_seen[key] = {
                "key": key,
                "category": cat,
                "subcategory": sub,
                "label": sub or CATEGORY_LABELS.get(cat, cat.replace("_", " ").title()),
                "section": CATEGORY_TO_SECTION.get(cat, "other"),
            }
        values.setdefault(key, {})[period] = amount

    return {
        "periods": sorted(periods_set),
        "line_items": list(items_seen.values()),
        "values": values,
    }
