"""
Canonical extraction schema shared by document extraction and valuation services.

All services (ValuationEngineService, IntelligentGapFiller, CellActions) consume
fields aligned with SERVICE_ALIGNED_FIELDS. Document extraction must produce these
when available; transforms map extraction output → canonical shape.
"""

from typing import Any, Dict, List, Optional

# Fields that valuation and analysis services expect on company_data
SERVICE_ALIGNED_FIELDS = [
    "business_model",  # CRITICAL for correct multiples (ai_first, saas, services, rollup)
    "sector",          # Industry/sector (synonym: industry)
    "category",       # For rollup, SaaS, AI detection
    "stage",          # Funding stage
    "target_market",  # Who they sell to
    "revenue",        # Or arr, current_arr_usd
    "arr",
    "growth_rate",
    "current_valuation_usd",
    "last_round_valuation",
    "total_raised",
    "total_invested_usd",
]

# Shape for market_insights (replaces flat industry_terms)
# signal: what the document mentions
# insight: why it matters
# category: model-extracted, free-form (e.g. regulatory, competitive, stage, market)
MARKET_INSIGHT_SHAPE = {"signal": str, "insight": Optional[str], "category": Optional[str]}


def canonicalize_company_data(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map extraction output to canonical shape for services.
    Handles: sector/industry synonym, arr/revenue, extracted_entities → flat.
    """
    out = {}
    # Revenue/ARR
    rev = raw.get("revenue") or raw.get("arr") or raw.get("current_arr_usd")
    if rev is not None:
        out["revenue"] = rev
        out["arr"] = rev
        out["current_arr_usd"] = rev
    # Sector/industry
    sector = raw.get("sector") or raw.get("industry") or raw.get("company_info", {}).get("sector")
    if sector is not None:
        out["sector"] = sector
        out["industry"] = sector
    # Business model, category, stage
    for k in ("business_model", "category", "stage", "target_market"):
        v = raw.get(k) or (raw.get("company_info") or {}).get(k)
        if v is not None:
            out[k] = v
    # Valuation/funding
    for k, aliases in [
        ("current_valuation_usd", ["valuation", "current_valuation_usd", "valuation_pre_money"]),
        ("last_round_valuation", ["last_round_valuation", "current_valuation_usd"]),
        ("total_raised", ["total_raised", "total_funding", "total_invested_usd", "funding_raised"]),
    ]:
        v = raw.get(k)
        for a in aliases:
            if v is None:
                v = raw.get(a) or (raw.get("company_info") or {}).get(a)
            else:
                break
        if v is not None:
            out[k] = v
    # Growth
    g = raw.get("growth_rate") or raw.get("revenue_growth_pct")
    if g is not None:
        if isinstance(g, (int, float)) and 0 < g < 10:
            out["growth_rate"] = float(g) / 100.0
        else:
            out["growth_rate"] = float(g) if g is not None else None
    return {**raw, **out}
