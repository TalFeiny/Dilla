"""
Transfer Pricing Engine — method selection, PLI computation, IQR analysis.

Orchestration flow:
  1. Load transaction + tested party + comparable set
  2. Select TP method (rule-based + LLM confirmation)
  3. Compute PLI for tested party and each accepted comparable
  4. Build IQR from comparable PLIs (proper interpolation)
  5. Determine arm's-length range and any adjustment needed
  6. Normalize currencies via FXIntelligenceService + fx_rates table
  7. Persist results to tp_analyses table
"""

import json
import logging
import math
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from app.core.database import supabase_service
from app.services.far_analysis_service import (
    FARAnalysisService,
    _parse_json_response,
    _ensure_list,
)
from app.services.fx_intelligence_service import fx_intelligence_service

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# PLI Calculator
# ═══════════════════════════════════════════════════════════════════════

# Definitions match OECD Transfer Pricing Guidelines Ch. II terminology.
# Each PLI has:
#   - name: OECD label
#   - numerator / denominator: field names from entity_financials aggregation
#   - methods: which TP methods use this PLI
#   - direction: "higher_is_better" or "neutral" — for adjustment narrative

PLI_DEFINITIONS = {
    "operating_margin": {
        "name": "Operating Margin (OP/Revenue)",
        "numerator": "operating_profit",
        "denominator": "revenue",
        "methods": ["tnmm", "resale_price"],
        "direction": "neutral",
    },
    "gross_margin": {
        "name": "Gross Margin (GP/Revenue)",
        "numerator": "gross_profit",
        "denominator": "revenue",
        "methods": ["resale_price"],
        "direction": "neutral",
    },
    "berry_ratio": {
        "name": "Berry Ratio (GP/OpEx)",
        "numerator": "gross_profit",
        "denominator": "opex",
        "methods": ["tnmm"],
        "direction": "neutral",
    },
    "markup_on_total_costs": {
        "name": "Markup on Total Costs (OP/(COGS+OpEx))",
        "numerator": "operating_profit",
        "denominator": "total_costs",
        "methods": ["cost_plus", "tnmm"],
        "direction": "neutral",
    },
    "net_cost_plus": {
        "name": "Net Cost Plus (OP/Total Costs)",
        "numerator": "operating_profit",
        "denominator": "total_costs",
        "methods": ["cost_plus"],
        "direction": "neutral",
    },
    "return_on_assets": {
        "name": "Return on Assets (OP/Total Assets)",
        "numerator": "operating_profit",
        "denominator": "total_assets",
        "methods": ["tnmm"],
        "direction": "neutral",
    },
}

# Method → preferred PLIs (first is default)
METHOD_DEFAULT_PLI = {
    "tnmm": ["operating_margin", "berry_ratio", "markup_on_total_costs", "return_on_assets"],
    "cost_plus": ["markup_on_total_costs", "net_cost_plus"],
    "resale_price": ["gross_margin", "operating_margin"],
    "cup": ["operating_margin"],  # CUP uses price comparison, PLI is secondary
    "profit_split": ["operating_margin"],  # contribution analysis, PLI secondary
}


def compute_pli(financials: Dict, pli_code: str) -> Optional[float]:
    """Compute a single PLI from a financials dict. Returns None on zero-division."""
    defn = PLI_DEFINITIONS.get(pli_code)
    if not defn:
        return None

    revenue = float(financials.get("revenue", 0) or 0)
    cogs = abs(float(financials.get("cogs", 0) or 0))
    opex = abs(float(financials.get("opex", 0) or 0))
    gp = float(financials.get("gross_profit", revenue - cogs))
    op = float(financials.get("operating_profit", gp - opex))
    total_assets = float(financials.get("total_assets", 0) or 0)
    total_costs = cogs + opex

    # Resolve numerator
    num_map = {
        "operating_profit": op,
        "gross_profit": gp,
    }
    # Resolve denominator
    den_map = {
        "revenue": revenue,
        "opex": opex,
        "total_costs": total_costs,
        "total_assets": total_assets,
    }

    num = num_map.get(defn["numerator"])
    den = den_map.get(defn["denominator"])

    if num is None or den is None or den == 0:
        return None

    return round(num / den, 4)


def compute_all_plis(financials: Dict) -> Dict[str, Optional[float]]:
    """Compute all 6 PLIs from a financials dict."""
    return {code: compute_pli(financials, code) for code in PLI_DEFINITIONS}


# ═══════════════════════════════════════════════════════════════════════
# IQR Computation (numpy-style linear interpolation)
# ═══════════════════════════════════════════════════════════════════════

def compute_iqr(values: List[float]) -> Optional[Dict[str, float]]:
    """Compute IQR statistics from a list of PLI values.

    Uses linear interpolation for percentiles (numpy default method).
    Returns None if fewer than 3 values (OECD recommends minimum comparable set).
    """
    clean = sorted([v for v in values if v is not None and not math.isnan(v)])
    if len(clean) < 3:
        return None

    def _percentile(data: List[float], pct: float) -> float:
        """Linear interpolation percentile (numpy 'linear' method)."""
        n = len(data)
        idx = (pct / 100) * (n - 1)
        lo = int(math.floor(idx))
        hi = int(math.ceil(idx))
        if lo == hi:
            return data[lo]
        frac = idx - lo
        return data[lo] * (1 - frac) + data[hi] * frac

    q1 = round(_percentile(clean, 25), 4)
    median = round(_percentile(clean, 50), 4)
    q3 = round(_percentile(clean, 75), 4)

    return {
        "q1": q1,
        "median": median,
        "q3": q3,
        "full_range_low": clean[0],
        "full_range_high": clean[-1],
        "count": len(clean),
    }


def assess_arm_length(
    tested_pli: float, iqr: Dict[str, float]
) -> Dict[str, Any]:
    """Determine if tested party PLI is within the arm's-length range.

    Returns in_range status, adjustment direction and amount.
    Adjustment target = median (OECD standard when out of range).
    """
    q1 = iqr["q1"]
    q3 = iqr["q3"]
    median = iqr["median"]

    in_range = q1 <= tested_pli <= q3

    result = {
        "tested_pli": tested_pli,
        "in_range": in_range,
        "iqr_low": q1,
        "iqr_high": q3,
        "median": median,
    }

    if in_range:
        result["adjustment_needed"] = None
        result["adjustment_direction"] = None
        result["narrative"] = (
            f"Tested party PLI of {tested_pli:.4f} falls within the interquartile range "
            f"[{q1:.4f} – {q3:.4f}] (median {median:.4f}). No adjustment required."
        )
    else:
        adjustment = median - tested_pli
        if tested_pli < q1:
            direction = "increase_price"
            narrative = (
                f"Tested party PLI of {tested_pli:.4f} is below the interquartile range "
                f"[{q1:.4f} – {q3:.4f}]. An upward adjustment of {abs(adjustment):.4f} "
                f"to the median ({median:.4f}) is recommended."
            )
        else:
            direction = "decrease_price"
            narrative = (
                f"Tested party PLI of {tested_pli:.4f} is above the interquartile range "
                f"[{q1:.4f} – {q3:.4f}]. A downward adjustment of {abs(adjustment):.4f} "
                f"to the median ({median:.4f}) is recommended."
            )

        result["adjustment_needed"] = round(adjustment, 4)
        result["adjustment_direction"] = direction
        result["narrative"] = narrative

    return result


# ═══════════════════════════════════════════════════════════════════════
# Method Selection
# ═══════════════════════════════════════════════════════════════════════

# Rule-based method selection matrix per OECD Guidelines Ch. II.
# Characterization → primary method, secondary options.
_METHOD_RULES = {
    # Entity characterizations
    "services": {"primary": "tnmm", "pli": "operating_margin", "alternatives": ["cost_plus"]},
    "shared_services": {"primary": "tnmm", "pli": "markup_on_total_costs", "alternatives": ["cost_plus"]},
    "management_services": {"primary": "tnmm", "pli": "operating_margin", "alternatives": ["cost_plus"]},
    "contract_manufacturing": {"primary": "cost_plus", "pli": "markup_on_total_costs", "alternatives": ["tnmm"]},
    "manufacturing": {"primary": "cost_plus", "pli": "markup_on_total_costs", "alternatives": ["tnmm", "profit_split"]},
    "distribution": {"primary": "tnmm", "pli": "operating_margin", "alternatives": ["resale_price"]},
    "limited_risk_distribution": {"primary": "resale_price", "pli": "gross_margin", "alternatives": ["tnmm"]},
    "ip_licensing": {"primary": "cup", "pli": "operating_margin", "alternatives": ["tnmm", "profit_split"]},
    "ip_development": {"primary": "profit_split", "pli": "operating_margin", "alternatives": ["tnmm"]},
    "ip_holding": {"primary": "tnmm", "pli": "return_on_assets", "alternatives": ["cup", "profit_split"]},
    "financing": {"primary": "cup", "pli": "operating_margin", "alternatives": ["tnmm"]},
    "commissionaire": {"primary": "tnmm", "pli": "berry_ratio", "alternatives": ["resale_price"]},
    "cost_sharing": {"primary": "profit_split", "pli": "operating_margin", "alternatives": ["tnmm"]},
    # Transaction types
    "goods": {"primary": "cup", "pli": "operating_margin", "alternatives": ["resale_price", "cost_plus"]},
}


def select_method_rule_based(
    transaction: Dict,
    tested_entity: Dict,
    far_profile: Optional[Dict] = None,
) -> Dict[str, Any]:
    """Rule-based TP method selection.

    Checks transaction_type, entity_type, and FAR characterization to pick method.
    """
    txn_type = transaction.get("transaction_type", "").lower()
    entity_type = tested_entity.get("entity_type", "").lower()
    functional_role = (tested_entity.get("functional_role") or "").lower()

    # FAR-derived characterization takes priority
    characterization = ""
    if far_profile:
        char_data = far_profile.get("characterization") or far_profile.get("_full_profile", {}).get("characterization", {})
        if isinstance(char_data, dict):
            characterization = char_data.get("entity_characterization", "").lower()
            # Also check FAR-suggested methods
            suggested = char_data.get("suggested_tp_methods", [])

    # Priority chain: characterization keywords → transaction type → entity type
    rule = None
    match_source = "default"

    # 1. Check characterization string for keywords
    for key, r in _METHOD_RULES.items():
        if key in characterization:
            rule = r
            match_source = f"characterization: {key}"
            break

    # 2. Check transaction type
    if not rule and txn_type in _METHOD_RULES:
        rule = _METHOD_RULES[txn_type]
        match_source = f"transaction_type: {txn_type}"

    # 3. Check entity type
    if not rule and entity_type in _METHOD_RULES:
        rule = _METHOD_RULES[entity_type]
        match_source = f"entity_type: {entity_type}"

    # 4. Check functional role keywords
    if not rule:
        for key, r in _METHOD_RULES.items():
            if key in functional_role:
                rule = r
                match_source = f"functional_role: {key}"
                break

    # Default: TNMM with operating margin (most broadly applicable)
    if not rule:
        rule = {"primary": "tnmm", "pli": "operating_margin", "alternatives": ["cost_plus", "resale_price"]}
        match_source = "default (TNMM is most broadly applicable per OECD)"

    alternatives = [
        {
            "method": alt,
            "applicable": True,
            "reasoning": f"Alternative per OECD guidelines for {match_source}",
        }
        for alt in rule.get("alternatives", [])
    ]

    return {
        "method": rule["primary"],
        "pli": rule["pli"],
        "match_source": match_source,
        "alternatives": alternatives,
    }


async def select_method_with_llm(
    transaction: Dict,
    tested_entity: Dict,
    far_profile: Optional[Dict],
    rule_result: Dict,
    llm_fn: Callable,
) -> Dict[str, Any]:
    """LLM confirms or overrides the rule-based method selection."""

    far_summary = ""
    if far_profile:
        full = far_profile.get("_full_profile", far_profile)
        far_summary = full.get("narrative", "")
        char = (full.get("characterization") or {})
        if isinstance(char, dict):
            far_summary += f"\nCharacterization: {char.get('entity_characterization', '')}"
            far_summary += f"\nSubstance: {char.get('economic_substance_level', '')}"
            far_summary += f"\nSuggested methods: {char.get('suggested_tp_methods', [])}"

    prompt = f"""Review this transfer pricing method selection and confirm or override.

TRANSACTION:
  Type: {transaction.get('transaction_type', '')}
  Description: {transaction.get('description', '')}
  Value: {transaction.get('currency', 'USD')} {transaction.get('annual_value', 'N/A')}
  Pricing basis: {transaction.get('pricing_basis', 'unknown')}

TESTED PARTY:
  Name: {tested_entity.get('name', '')}
  Type: {tested_entity.get('entity_type', '')}
  Jurisdiction: {tested_entity.get('jurisdiction', '')}
  Role: {tested_entity.get('functional_role', '')}

FAR ANALYSIS:
{far_summary}

RULE-BASED SELECTION:
  Method: {rule_result['method']}
  PLI: {rule_result['pli']}
  Basis: {rule_result['match_source']}

OECD METHODS:
- CUP (Comparable Uncontrolled Price): Best when identical/very similar uncontrolled transactions exist
- TNMM (Transactional Net Margin Method): Most flexible, compares net profit margin relative to an appropriate base
- Cost Plus: Appropriate for manufacturing, services — markup on costs
- Resale Price: Distribution activities — margin on resale
- Profit Split: Unique intangibles, highly integrated operations

Do you agree with the rule-based selection? If not, what method and PLI should be used?

Return JSON:
{{
  "confirmed": bool,
  "method": "<method code>",
  "pli": "<pli code>",
  "reasoning": "<2-3 sentences justifying the method choice>",
  "alternatives": [
    {{"method": "<code>", "applicable": bool, "reasoning": "<why applicable or not>"}}
  ]
}}
JUST JSON."""

    raw = await llm_fn(
        prompt,
        "You are an OECD-trained transfer pricing economist. Select the most appropriate method per Chapter II guidelines. Return ONLY valid JSON.",
    )
    parsed = _parse_json_response(raw)
    if not parsed:
        return rule_result

    method = parsed.get("method", rule_result["method"])
    pli = parsed.get("pli", rule_result["pli"])

    # Validate method code
    valid_methods = {"cup", "tnmm", "cost_plus", "resale_price", "profit_split"}
    if method not in valid_methods:
        method = rule_result["method"]

    # Validate PLI code
    if pli not in PLI_DEFINITIONS:
        pli = rule_result["pli"]

    return {
        "method": method,
        "pli": pli,
        "match_source": rule_result["match_source"],
        "llm_confirmed": parsed.get("confirmed", True),
        "reasoning": parsed.get("reasoning", ""),
        "alternatives": parsed.get("alternatives", rule_result.get("alternatives", [])),
    }


# ═══════════════════════════════════════════════════════════════════════
# Currency Normalization
# ═══════════════════════════════════════════════════════════════════════

async def get_period_average_rate(
    from_ccy: str,
    to_ccy: str,
    period_start: date,
    period_end: date,
) -> Optional[float]:
    """Get period-average FX rate, checking fx_rates table first, then computing from daily rates.

    For TP, period-average rates are required (not spot rates) per OECD guidelines.
    Stores computed averages in fx_rates for future use.
    """
    from_ccy = from_ccy.upper()
    to_ccy = to_ccy.upper()
    if from_ccy == to_ccy:
        return 1.0

    client = supabase_service.get_client()

    # Check for existing period average
    existing = client.from_("fx_rates") \
        .select("rate") \
        .eq("base_currency", from_ccy) \
        .eq("target_currency", to_ccy) \
        .eq("rate_type", "annual_avg") \
        .gte("rate_date", period_start.isoformat()) \
        .lte("rate_date", period_end.isoformat()) \
        .execute().data

    if existing:
        rates = [float(r["rate"]) for r in existing]
        return round(sum(rates) / len(rates), 6)

    # Check for monthly averages in the period
    monthly = client.from_("fx_rates") \
        .select("rate") \
        .eq("base_currency", from_ccy) \
        .eq("target_currency", to_ccy) \
        .eq("rate_type", "monthly_avg") \
        .gte("rate_date", period_start.isoformat()) \
        .lte("rate_date", period_end.isoformat()) \
        .execute().data

    if monthly and len(monthly) >= 3:
        rates = [float(r["rate"]) for r in monthly]
        avg = round(sum(rates) / len(rates), 6)
        # Store as annual average for future lookups
        _store_fx_rate(client, from_ccy, to_ccy, avg, period_end, "annual_avg", "computed")
        return avg

    # Check for daily rates
    daily = client.from_("fx_rates") \
        .select("rate") \
        .eq("base_currency", from_ccy) \
        .eq("target_currency", to_ccy) \
        .eq("rate_type", "daily") \
        .gte("rate_date", period_start.isoformat()) \
        .lte("rate_date", period_end.isoformat()) \
        .execute().data

    if daily and len(daily) >= 10:
        rates = [float(r["rate"]) for r in daily]
        avg = round(sum(rates) / len(rates), 6)
        _store_fx_rate(client, from_ccy, to_ccy, avg, period_end, "annual_avg", "computed")
        return avg

    # Fall back to live spot rate from FXIntelligenceService
    live_rate = await fx_intelligence_service.get_rate(from_ccy, to_ccy)
    if live_rate:
        logger.info(f"[TP_FX] Using spot rate for {from_ccy}/{to_ccy} = {live_rate} (no historical data)")
        return live_rate

    return None


def _store_fx_rate(
    client: Any,
    base_ccy: str,
    target_ccy: str,
    rate: float,
    rate_date: date,
    rate_type: str,
    source: str,
) -> None:
    """Store an FX rate, ignoring conflicts on the dedup index."""
    try:
        client.from_("fx_rates").upsert({
            "base_currency": base_ccy,
            "target_currency": target_ccy,
            "rate": rate,
            "rate_date": rate_date.isoformat(),
            "rate_type": rate_type,
            "source": source,
        }, on_conflict="base_currency,target_currency,rate_date,rate_type").execute()
    except Exception as e:
        logger.debug(f"[TP_FX] Failed to store rate {base_ccy}/{target_ccy}: {e}")


async def store_daily_rates(
    target_currencies: List[str],
    rate_date: Optional[date] = None,
) -> int:
    """Fetch current rates from FXIntelligenceService and store as daily snapshots.

    Call this periodically (e.g., daily cron) to build up historical rate data
    for period-average computation.
    """
    rate_date = rate_date or date.today()
    client = supabase_service.get_client()
    stored = 0

    for ccy in target_currencies:
        ccy = ccy.upper()
        if ccy == "USD":
            continue
        rate = await fx_intelligence_service.get_rate("USD", ccy)
        if rate:
            _store_fx_rate(client, "USD", ccy, rate, rate_date, "daily", "exchangerate_host")
            stored += 1

    logger.info(f"[TP_FX] Stored {stored} daily rates for {rate_date}")
    return stored


async def normalize_financials_to_currency(
    financials: Dict,
    from_ccy: str,
    to_ccy: str,
    period_start: Optional[date] = None,
    period_end: Optional[date] = None,
) -> Dict:
    """Convert financial figures from one currency to another using period-average rate."""
    if from_ccy.upper() == to_ccy.upper():
        return financials

    if period_start and period_end:
        rate = await get_period_average_rate(from_ccy, to_ccy, period_start, period_end)
    else:
        rate = await fx_intelligence_service.get_rate(from_ccy, to_ccy)

    if not rate:
        logger.warning(f"[TP_FX] No rate for {from_ccy}/{to_ccy}, returning unconverted")
        return financials

    converted = dict(financials)
    monetary_fields = {
        "revenue", "cogs", "opex", "gross_profit", "operating_profit",
        "total_assets", "total_costs", "ic_revenue", "third_party_revenue",
        "rd_cost", "annual_value",
    }
    for field in monetary_fields:
        if field in converted and converted[field] is not None:
            converted[field] = round(float(converted[field]) * rate, 2)

    converted["_fx_rate_applied"] = rate
    converted["_original_currency"] = from_ccy
    converted["_converted_to"] = to_ccy
    return converted


# ═══════════════════════════════════════════════════════════════════════
# Main Engine
# ═══════════════════════════════════════════════════════════════════════

class TransferPricingEngine:
    """Orchestrates TP analysis: method selection → PLI computation → IQR → adjustment."""

    def __init__(self, llm_fn: Optional[Callable] = None):
        self.llm_fn = llm_fn
        self.far_service = FARAnalysisService(llm_fn=llm_fn)

    async def _llm_call(self, prompt: str, system: str) -> str:
        """Route LLM calls through injected fn or model_router."""
        if self.llm_fn:
            return await self.llm_fn(prompt, system)
        try:
            from app.services.model_router import get_model_router, ModelCapability
            router = get_model_router()
            result = await router.get_completion(
                prompt=prompt,
                system_prompt=system,
                capability=ModelCapability.ANALYSIS,
                max_tokens=4096,
                temperature=0.3,
                json_mode=True,
                caller_context="tp_engine",
            )
            return result.get("response", "")
        except Exception as e:
            logger.warning(f"[TP_ENGINE] LLM call failed: {e}")
            return ""

    # ── Load tested party financials ──────────────────────────────────

    def _load_tested_party_financials(
        self, entity_id: str, group_currency: str = "USD"
    ) -> Tuple[Dict, Dict[str, Dict]]:
        """Load entity financials aggregated by period.

        Returns:
            (aggregate_financials, by_year: {"2024": {...}, "2025": {...}})
        """
        client = supabase_service.get_client()
        fin_resp = client.from_("entity_financials") \
            .select("period, category, subcategory, amount, currency, amount_group_currency") \
            .eq("entity_id", entity_id) \
            .order("period", desc=True) \
            .limit(500) \
            .execute()

        rows = fin_resp.data or []
        if not rows:
            return {}, {}

        # Group by year
        by_year: Dict[str, Dict[str, float]] = {}
        aggregate: Dict[str, float] = {}

        for r in rows:
            period = r.get("period", "")
            year = period[:4] if period else "unknown"
            # Use group_currency amount if available, else raw amount
            amt = float(r.get("amount_group_currency") or r.get("amount", 0) or 0)
            cat = r.get("category", "")

            if year not in by_year:
                by_year[year] = {}
            by_year[year][cat] = by_year[year].get(cat, 0) + amt
            aggregate[cat] = aggregate.get(cat, 0) + amt

        # Normalize: compute derived fields for each year
        year_count = len(by_year) or 1
        averaged = {k: v / year_count for k, v in aggregate.items()}

        # Compute GP/OP for each year
        for year, data in by_year.items():
            rev = data.get("revenue", 0)
            cogs = abs(data.get("cogs", 0))
            opex_val = abs(data.get("opex", 0))
            data.setdefault("gross_profit", rev - cogs)
            data.setdefault("operating_profit", data["gross_profit"] - opex_val)
            data["total_costs"] = cogs + opex_val

        rev = averaged.get("revenue", 0)
        cogs_avg = abs(averaged.get("cogs", 0))
        opex_avg = abs(averaged.get("opex", 0))
        averaged.setdefault("gross_profit", rev - cogs_avg)
        averaged.setdefault("operating_profit", averaged["gross_profit"] - opex_avg)
        averaged["total_costs"] = cogs_avg + opex_avg

        return averaged, by_year

    # ── Extract comparable PLIs ───────────────────────────────────────

    def _extract_comparable_plis(
        self, comparables: List[Dict], pli_code: str
    ) -> Tuple[List[float], List[Dict]]:
        """Extract the specified PLI from each accepted comparable.

        Returns (pli_values, per_comparable_detail).
        """
        values = []
        details = []
        for c in comparables:
            if not c.get("accepted", True):
                continue

            fin = c.get("financials", {})
            if isinstance(fin, str):
                try:
                    fin = json.loads(fin)
                except (json.JSONDecodeError, TypeError):
                    fin = {}

            # Try direct PLI field first (yfinance/web already computed)
            pli_val = fin.get(pli_code)
            if pli_val is None:
                # Try computing from raw financials
                pli_val = compute_pli(fin, pli_code)

            detail = {
                "name": c.get("candidate_name", ""),
                "source": c.get("candidate_source", ""),
                "pli_code": pli_code,
                "pli_value": pli_val,
                "composite_score": c.get("composite_score"),
                "data_quality": c.get("data_quality", "estimated"),
            }

            if pli_val is not None:
                values.append(pli_val)
            else:
                detail["excluded_reason"] = f"No {pli_code} data available"

            details.append(detail)

        return values, details

    # ── Multi-year PLI analysis ───────────────────────────────────────

    def _multi_year_tested_pli(
        self, by_year: Dict[str, Dict], pli_code: str
    ) -> Dict[str, Optional[float]]:
        """Compute tested party PLI for each year."""
        result = {}
        for year, data in sorted(by_year.items()):
            result[year] = compute_pli(data, pli_code)
        return result

    # ── Choose best PLI given available data ──────────────────────────

    def _choose_best_pli(
        self, method: str, comparables: List[Dict], tested_financials: Dict
    ) -> str:
        """If the default PLI has insufficient data, try alternatives."""
        preferred = METHOD_DEFAULT_PLI.get(method, ["operating_margin"])

        for pli_code in preferred:
            values, _ = self._extract_comparable_plis(comparables, pli_code)
            tested_val = compute_pli(tested_financials, pli_code)
            if len(values) >= 3 and tested_val is not None:
                return pli_code

        # Fallback: return default even if data is thin
        return preferred[0] if preferred else "operating_margin"

    # ── Main analyze method ───────────────────────────────────────────

    async def analyze(
        self,
        transaction_id: str,
        search_id: Optional[str] = None,
        force_method: Optional[str] = None,
        force_pli: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run full TP analysis for an intercompany transaction.

        Steps:
          1. Load transaction, tested party, FAR profile
          2. Load comparable set (from search_id or latest search)
          3. Select TP method
          4. Compute PLIs
          5. Build IQR and assess arm's-length range
          6. Persist to tp_analyses
        """
        client = supabase_service.get_client()

        # ── 1. Load transaction and tested party ──────────────────────
        txn = client.from_("intercompany_transactions") \
            .select("*") \
            .eq("id", transaction_id) \
            .single().execute().data
        if not txn:
            raise ValueError(f"Transaction {transaction_id} not found")

        # Determine tested party (same logic as comparable service)
        tested_entity_id = txn.get("from_entity_id")
        tested_entity = client.from_("company_entities") \
            .select("*") \
            .eq("id", tested_entity_id) \
            .single().execute().data

        other_id = txn.get("to_entity_id")
        other = client.from_("company_entities") \
            .select("*") \
            .eq("id", other_id) \
            .single().execute().data
        if other and other.get("is_tested_party"):
            tested_entity_id = other_id
            tested_entity = other

        # Load FAR profile
        far_profile = await self.far_service.get_profile(tested_entity_id)

        # ── 2. Load comparable set ────────────────────────────────────
        if not search_id:
            # Find latest completed search for this transaction
            searches = client.from_("tp_comparable_searches") \
                .select("id") \
                .eq("transaction_id", transaction_id) \
                .eq("status", "completed") \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute().data
            if searches:
                search_id = searches[0]["id"]

        if not search_id:
            raise ValueError(
                f"No comparable search found for transaction {transaction_id}. "
                "Run TPComparableService.search_comparables() first."
            )

        comps_resp = client.from_("tp_comparables") \
            .select("*") \
            .eq("search_id", search_id) \
            .order("composite_score", desc=True) \
            .execute()
        comparables = comps_resp.data or []

        # Parse JSONB fields
        for c in comparables:
            for key in ("financials", "financial_years"):
                if isinstance(c.get(key), str):
                    try:
                        c[key] = json.loads(c[key])
                    except (json.JSONDecodeError, TypeError):
                        pass

        accepted = [c for c in comparables if c.get("accepted")]
        if not accepted:
            raise ValueError(
                f"No accepted comparables in search {search_id}. "
                "Review rejection log and adjust thresholds."
            )

        # ── 3. Method selection ───────────────────────────────────────
        rule_result = select_method_rule_based(txn, tested_entity, far_profile)

        if force_method:
            method_result = {
                "method": force_method,
                "pli": force_pli or rule_result["pli"],
                "match_source": "user_override",
                "alternatives": rule_result.get("alternatives", []),
            }
        elif self.llm_fn:
            method_result = await select_method_with_llm(
                txn, tested_entity, far_profile, rule_result, self._llm_call,
            )
        else:
            method_result = rule_result

        method = method_result["method"]
        pli_code = method_result.get("pli", "operating_margin")

        # ── 4. Load tested party financials ───────────────────────────
        tested_fin, tested_by_year = self._load_tested_party_financials(
            tested_entity_id, txn.get("currency", "USD")
        )

        # Choose best PLI given available data
        if not force_pli:
            pli_code = self._choose_best_pli(method, accepted, tested_fin)
            method_result["pli"] = pli_code

        # Compute tested party PLI
        tested_pli = compute_pli(tested_fin, pli_code)
        tested_pli_by_year = self._multi_year_tested_pli(tested_by_year, pli_code)

        # ── 5. Extract comparable PLIs and compute IQR ────────────────
        comp_pli_values, comp_details = self._extract_comparable_plis(accepted, pli_code)

        iqr = compute_iqr(comp_pli_values)

        arm_length_result = None
        if iqr and tested_pli is not None:
            arm_length_result = assess_arm_length(tested_pli, iqr)

        # ── 6. Persist to tp_analyses ─────────────────────────────────
        analysis_row = {
            "transaction_id": transaction_id,
            "search_id": search_id,
            "method": method,
            "method_reasoning": method_result.get("reasoning") or method_result.get("match_source", ""),
            "profit_level_indicator": pli_code,
            "tested_party_pli": tested_pli,
            "tested_party_pli_by_year": json.dumps(tested_pli_by_year),
            "comparable_results": json.dumps(comp_details, default=str),
            "iqr_low": iqr["q1"] if iqr else None,
            "iqr_high": iqr["q3"] if iqr else None,
            "median": iqr["median"] if iqr else None,
            "full_range_low": iqr["full_range_low"] if iqr else None,
            "full_range_high": iqr["full_range_high"] if iqr else None,
            "in_range": arm_length_result["in_range"] if arm_length_result else None,
            "adjustment_needed": arm_length_result["adjustment_needed"] if arm_length_result else None,
            "adjustment_direction": arm_length_result["adjustment_direction"] if arm_length_result else None,
            "alternative_methods": json.dumps(method_result.get("alternatives", []), default=str),
        }

        saved = client.from_("tp_analyses").insert(analysis_row).execute()
        analysis_id = saved.data[0]["id"] if saved.data else None

        # Update transaction benchmark_status
        if arm_length_result:
            status = "in_range" if arm_length_result["in_range"] else "out_of_range"
        else:
            status = "needs_review"

        client.from_("intercompany_transactions") \
            .update({"benchmark_status": status, "last_benchmarked_at": "now()"}) \
            .eq("id", transaction_id).execute()

        # ── 7. Build response ─────────────────────────────────────────
        return {
            "analysis_id": analysis_id,
            "transaction_id": transaction_id,
            "search_id": search_id,
            "tested_party": {
                "entity_id": tested_entity_id,
                "name": tested_entity.get("name"),
                "entity_type": tested_entity.get("entity_type"),
                "jurisdiction": tested_entity.get("jurisdiction"),
            },
            "method_selection": {
                "method": method,
                "method_name": {
                    "cup": "Comparable Uncontrolled Price",
                    "tnmm": "Transactional Net Margin Method",
                    "cost_plus": "Cost Plus Method",
                    "resale_price": "Resale Price Method",
                    "profit_split": "Transactional Profit Split Method",
                }.get(method, method),
                "pli": pli_code,
                "pli_name": PLI_DEFINITIONS.get(pli_code, {}).get("name", pli_code),
                "reasoning": method_result.get("reasoning") or method_result.get("match_source", ""),
                "alternatives": method_result.get("alternatives", []),
            },
            "tested_party_results": {
                "pli_code": pli_code,
                "pli_value": tested_pli,
                "pli_by_year": tested_pli_by_year,
                "financials_available": bool(tested_fin),
            },
            "comparable_set": {
                "total_accepted": len(accepted),
                "pli_values_used": len(comp_pli_values),
                "details": comp_details,
            },
            "iqr_analysis": {
                "computed": iqr is not None,
                "q1": iqr["q1"] if iqr else None,
                "median": iqr["median"] if iqr else None,
                "q3": iqr["q3"] if iqr else None,
                "full_range_low": iqr["full_range_low"] if iqr else None,
                "full_range_high": iqr["full_range_high"] if iqr else None,
                "count": iqr["count"] if iqr else 0,
            },
            "arm_length_assessment": arm_length_result,
            "benchmark_status": status,
        }

    # ── Retrieve existing analysis ────────────────────────────────────

    async def get_analysis(self, analysis_id: str) -> Dict[str, Any]:
        """Load a saved TP analysis by ID."""
        client = supabase_service.get_client()
        row = client.from_("tp_analyses") \
            .select("*") \
            .eq("id", analysis_id) \
            .single().execute().data
        if not row:
            raise ValueError(f"Analysis {analysis_id} not found")

        for key in ("tested_party_pli_by_year", "comparable_results", "alternative_methods"):
            if isinstance(row.get(key), str):
                try:
                    row[key] = json.loads(row[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        return row

    async def get_analyses_for_transaction(self, transaction_id: str) -> List[Dict]:
        """Get all analyses for a transaction, newest first."""
        client = supabase_service.get_client()
        rows = client.from_("tp_analyses") \
            .select("*") \
            .eq("transaction_id", transaction_id) \
            .order("created_at", desc=True) \
            .execute().data or []

        for row in rows:
            for key in ("tested_party_pli_by_year", "comparable_results", "alternative_methods"):
                if isinstance(row.get(key), str):
                    try:
                        row[key] = json.loads(row[key])
                    except (json.JSONDecodeError, TypeError):
                        pass
        return rows

    # ── Batch analysis for all IC transactions in a group ─────────────

    async def analyze_group(
        self,
        company_id: str,
        force_method: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Run TP analysis on every IC transaction under a portfolio company.

        Skips transactions without a completed comparable search.
        """
        client = supabase_service.get_client()
        txns = client.from_("intercompany_transactions") \
            .select("id, transaction_type, description") \
            .eq("company_id", company_id) \
            .execute().data or []

        results = []
        for txn in txns:
            try:
                result = await self.analyze(txn["id"], force_method=force_method)
                results.append({
                    "transaction_id": txn["id"],
                    "status": "ok",
                    "result": result,
                })
            except ValueError as e:
                results.append({
                    "transaction_id": txn["id"],
                    "status": "skipped",
                    "reason": str(e),
                })
            except Exception as e:
                logger.error(f"[TP_ENGINE] Failed for txn {txn['id']}: {e}")
                results.append({
                    "transaction_id": txn["id"],
                    "status": "error",
                    "error": str(e),
                })
        return results
