"""Normalize extraction time_series → fpa_actuals rows."""

from datetime import date
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Metrics from extraction that map to fpa_actuals categories
METRIC_TO_CATEGORY = {
    # Universal
    "revenue": "revenue",
    "cogs": "cogs",
    "opex": "opex_total",
    "cash_balance": "cash_balance",
    "headcount": "headcount",
    # Venture / SaaS
    "arr": "arr",
    "mrr": "mrr",
    "burn_rate": "burn_rate",
    "customers": "customers",
    # PE / Operating / Traditional
    "ebitda": "ebitda",
    "operating_income": "operating_income",
    "net_income": "net_income",
    "capex": "capex",
    "fcf": "fcf",
    "interest_expense": "interest_expense",
    "tax_expense": "tax_expense",
    "total_debt": "total_debt",
    "working_capital": "working_capital",
    "debt_service": "debt_service",
    "depreciation": "depreciation",
    "amortization": "amortization",
    "gross_profit": "gross_profit",
    "dividends": "dividends",
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
# Subcomponent taxonomy — what goes BENEATH each subcategory
# ---------------------------------------------------------------------------
# Informed by real Workday comp reports (Base_Pay, Bonus_Target,
# Benefits_Cost) and Salesforce opportunity types.  Downstream services
# can forecast / budget at this depth when the data is available.

SUBCOMPONENT_TAXONOMY: Dict[str, List[str]] = {
    # -- Salary subcategories (from Workday comp breakdown) --
    "engineering_salaries":  ["base_pay", "bonus", "benefits", "equity_comp", "payroll_tax"],
    "ml_engineering":        ["base_pay", "bonus", "benefits", "equity_comp", "payroll_tax"],
    "data_engineering":      ["base_pay", "bonus", "benefits", "equity_comp", "payroll_tax"],
    "sales_salaries":        ["base_pay", "bonus", "commissions", "benefits", "equity_comp", "payroll_tax"],
    "admin_salaries":        ["base_pay", "bonus", "benefits", "payroll_tax"],
    "support_salaries":      ["base_pay", "bonus", "benefits", "payroll_tax"],
    "research":              ["base_pay", "bonus", "benefits", "equity_comp", "payroll_tax"],
    "delivery_salaries":     ["base_pay", "bonus", "benefits", "payroll_tax"],
    "direct_labor":          ["base_pay", "overtime", "benefits", "payroll_tax"],

    # -- Non-salary subcategories (from ERP chart of accounts) --
    "paid_acquisition":      ["sem_ppc", "social_ads", "display_programmatic", "retargeting", "affiliate"],
    "content_marketing":     ["seo", "blog_content", "social_media_organic", "design_creative", "video_production"],
    "events":                ["conferences", "trade_shows", "hosted_events", "sponsorships", "travel_events"],
    "partnerships":          ["partner_commissions", "co_marketing", "channel_incentives"],

    "infra_cloud":           ["compute", "storage", "bandwidth_cdn", "monitoring_observability", "ci_cd"],
    "tools_licenses":        ["ide_dev_tools", "project_management", "security_tools", "analytics_bi", "design_tools"],
    "hosting":               ["compute", "storage", "bandwidth_cdn", "database", "caching_queues"],

    "finance_legal":         ["accounting_fees", "legal_counsel", "audit_fees", "tax_advisory", "compliance_filings"],
    "office":                ["rent_lease", "utilities", "office_supplies", "maintenance", "coworking"],
    "insurance":             ["d_and_o", "e_and_o", "general_liability", "cyber", "workers_comp"],

    "payment_processing":    ["interchange_fees", "gateway_fees", "chargeback_costs", "fx_conversion"],
    "third_party_apis":      ["data_providers", "communication_apis", "identity_verification", "mapping_geo"],

    # -- Revenue subcategories (from Salesforce opp types) --
    "new_business_bookings": ["inbound", "outbound", "partner_sourced", "self_serve"],
    "renewal_bookings":      ["auto_renew", "negotiated_renew"],
    "expansion_bookings":    ["upsell", "cross_sell", "seat_expansion", "usage_upgrade"],

    # -- Manufacturing / hardware --
    "raw_materials":         ["metals", "plastics", "electronics", "chemicals", "packaging"],
    "manufacturing":         ["assembly", "machining", "testing", "quality_control", "tooling"],
    "logistics":             ["inbound_freight", "outbound_shipping", "warehousing", "customs_duties"],
    "inventory":             ["finished_goods", "wip", "raw_stock", "safety_stock"],
}

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
            parent_cat = entry.get("parent_category") or entry.get("category") or SUBCATEGORY_TO_PARENT.get(subcategory)
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

    # Derived categories (gross_profit, opex_total, ebitda, net_income) are
    # NOT stored in fpa_actuals. They are computed on the fly by pnl_builder
    # and company_data_pull._compute_derived(). Storing them caused duplicate
    # summary rows and stale data.

    # Single upsert — on_conflict must match the DB unique index exactly
    sb.table("fpa_actuals").upsert(
        rows,
        on_conflict="company_id,period,category,subcategory,hierarchy_path,source",
    ).execute()

    # Bayesian updating — adjust priors on any model specs stored in branches
    _update_model_spec_priors(sb, company_id, rows)

    return len(rows)


def _update_model_spec_priors(sb, company_id: str, rows: List[Dict]) -> None:
    """Find branches with model_specs for this company and update priors.

    Non-fatal — logs and moves on if anything fails.
    """
    try:
        branch_result = (
            sb.table("scenario_branches")
            .select("id, assumptions")
            .eq("company_id", company_id)
            .execute()
        )
        if not branch_result.data:
            return

        # Collect latest actuals by category from the ingested rows
        actuals_by_cat: Dict[str, float] = {}
        for row in rows:
            cat = row.get("category", "")
            if cat and not row.get("subcategory"):
                actuals_by_cat[cat] = row.get("amount", 0)

        if not actuals_by_cat:
            return

        from app.services.model_spec_schema import ModelSpec
        from app.services.model_spec_executor import update_model_with_actuals
        from app.core.date_utils import parse_period_to_date

        # Determine period index from the latest ingested period
        periods = [r.get("period", "") for r in rows if r.get("period")]
        if not periods:
            return
        latest_period = max(periods)

        for branch in branch_result.data:
            assumptions = branch.get("assumptions") or {}
            spec_data = assumptions.get("model_spec")
            if not spec_data:
                continue

            spec = ModelSpec(**spec_data)

            # Compute period index relative to spec metadata start_period
            start_period = spec.metadata.get("start_period")
            if not start_period:
                continue
            start_dt = parse_period_to_date(start_period)
            actual_dt = parse_period_to_date(latest_period[:10])
            period_idx = (actual_dt.year - start_dt.year) * 12 + (actual_dt.month - start_dt.month)
            if period_idx < 0:
                continue

            updated = update_model_with_actuals(spec, actuals_by_cat, period_idx)
            assumptions["model_spec"] = updated.model_dump()

            sb.table("scenario_branches").update(
                {"assumptions": assumptions}
            ).eq("id", branch["id"]).execute()

            logger.info(
                "Updated model spec priors on branch %s (period_idx=%d)",
                branch["id"], period_idx,
            )

    except Exception as e:
        logger.warning("Model spec prior update failed (non-fatal): %s", e)


def get_company_financials_snapshot(company_id: str) -> Dict[str, Any]:
    """DEPRECATED — use ``company_data_pull.pull_company_data()`` instead.

    Kept only as a thin wrapper so nothing breaks if called from an
    unexpected location.  Returns the same flat dict as before.
    """
    import warnings
    warnings.warn(
        "get_company_financials_snapshot is deprecated. "
        "Use company_data_pull.pull_company_data() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    from app.services.company_data_pull import pull_company_data
    return pull_company_data(company_id).as_flat_dict()


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
        prev_raw = actuals[i - 1]["period"]
        curr_raw = actuals[i]["period"]
        # Periods may be YYYY-MM — append -01 for date parsing
        prev = date.fromisoformat(prev_raw if len(prev_raw) > 7 else f"{prev_raw}-01")
        curr = date.fromisoformat(curr_raw if len(curr_raw) > 7 else f"{curr_raw}-01")
        gaps.append((curr - prev).days)
    median_gap = sorted(gaps)[len(gaps) // 2]
    if median_gap > 300:  # ~yearly
        return 1
    elif median_gap > 60:  # ~quarterly
        return 4
    return 12  # monthly


def seed_forecast_from_actuals(company_id: str) -> Dict[str, Any]:
    """Build company_data dict from actuals for downstream services.

    Delegates to pull_company_data() (single query, full time series) and
    returns the flat-dict shape that all 30+ callers expect.
    """
    from app.services.company_data_pull import pull_company_data
    return pull_company_data(company_id).to_forecast_seed()


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
    # Universal
    "revenue": "Revenue",
    "cogs": "COGS",
    "gross_profit": "Gross Profit",
    "opex_total": "Operating Expenses",
    "opex_rd": "R&D",
    "opex_sm": "Sales & Marketing",
    "opex_ga": "G&A",
    # Venture / SaaS
    "arr": "ARR",
    "mrr": "MRR",
    "burn_rate": "Burn Rate",
    "customers": "Customers",
    # PE / Operating / Traditional
    "ebitda": "EBITDA",
    "operating_income": "Operating Income",
    "net_income": "Net Income",
    "depreciation": "Depreciation",
    "amortization": "Amortization",
    "capex": "Capex",
    "fcf": "Free Cash Flow",
    "interest_expense": "Interest Expense",
    "tax_expense": "Tax Expense",
    "total_debt": "Total Debt",
    "working_capital": "Working Capital",
    "debt_service": "Debt Service",
    "dividends": "Dividends",
    # Shared
    "cash_balance": "Cash Balance",
    "headcount": "Headcount",
}

CATEGORY_TO_SECTION = {
    # Universal
    "revenue": "revenue",
    "cogs": "cogs",
    "gross_profit": "gross_profit",
    "opex_rd": "opex",
    "opex_sm": "opex",
    "opex_ga": "opex",
    "opex_total": "opex",
    # Venture / SaaS
    "arr": "revenue",
    "mrr": "revenue",
    "burn_rate": "bottom",
    "customers": "operational",
    # PE / Operating — income statement
    "ebitda": "ebitda",
    "operating_income": "ebitda",
    "depreciation": "below_ebitda",
    "amortization": "below_ebitda",
    "interest_expense": "below_ebitda",
    "tax_expense": "below_ebitda",
    "net_income": "net_income",
    # PE / Operating — cash flow & balance sheet
    "capex": "cash_flow",
    "fcf": "cash_flow",
    "working_capital": "cash_flow",
    "debt_service": "cash_flow",
    "dividends": "cash_flow",
    "total_debt": "balance_sheet",
    "cash_balance": "balance_sheet",
    # Operational
    "headcount": "operational",
}


    # Categories that are computed (not raw data) — never returned as actuals.
    # NOTE: For PE/operating companies, ebitda, net_income, interest_expense,
    # tax_expense, debt_service ARE real reported figures from management accounts,
    # not derived. Only exclude truly synthetic/noise categories.
_DERIVED_OR_NOISE_CATEGORIES = {
    "opex_total",       # always computed from opex_rd + opex_sm + opex_ga
    "below_the_line",   # noise category from bad extraction
    "below_line",       # noise category from bad extraction
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
        if cat in _DERIVED_OR_NOISE_CATEGORIES:
            continue
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
