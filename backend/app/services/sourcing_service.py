"""
Sourcing Service — Fast local query + scoring engine for companies.

No LLM, no web calls in the core path. Pure SQL + math.
Works on the existing companies table (1k+ rows from CSV imports, enrichments).
Results are ephemeral — returned inline to the agent, not persisted.

The LLM populates filters directly as structured JSON — no NL regex parsing.

When DB results are thin, generate_rubric() provides intent + search_context
that feeds into LLM-driven web discovery (handled by the orchestrator).
"""
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Columns we SELECT from companies for sourcing results
# ---------------------------------------------------------------------------
SOURCING_COLUMNS = (
    "id, name, sector, stage, description, current_arr_usd, "
    "current_valuation_usd, last_valuation_usd, total_raised, "
    "growth_rate, employee_count, headquarters, founded_year, "
    "burn_rate_monthly_usd, runway_months, revenue_model, "
    "funding_stage, last_funding_date, extra_data, "
    "fund_id, ai_category, tam"
)

# Mapping from sort key names to actual DB column names
SORT_COLUMN_MAP = {
    "name": "name",
    "arr": "current_arr_usd",
    "valuation": "current_valuation_usd",
    "total_funding": "total_raised",
    "growth_rate": "growth_rate",
    "employee_count": "employee_count",
    "founded_year": "founded_year",
    "created_at": "created_at",
    "burn_rate": "burn_rate_monthly_usd",
    "runway": "runway_months",
}

# ---------------------------------------------------------------------------
# Default scoring weights
# ---------------------------------------------------------------------------
DEFAULT_WEIGHTS = {
    "data_completeness": 0.15,
    "stage_fit": 0.15,
    "growth_signal": 0.20,
    "market_size": 0.10,
    "capital_efficiency": 0.20,
    "recency": 0.10,
    "scale": 0.10,
}


def _get_client():
    """Get Supabase client or None."""
    try:
        from app.core.database import get_supabase_service
        return get_supabase_service().get_client()
    except Exception:
        return None


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Extract numeric value, handling None and InferenceResult objects."""
    if val is None:
        return default
    if hasattr(val, "value"):
        val = val.value
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    """Extract integer value, handling strings like '50-100', '~200', None."""
    if val is None:
        return default
    if hasattr(val, "value"):
        val = val.value
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip().lstrip("~≈")
    # If range like "50-100", take the midpoint
    if "-" in s and not s.startswith("-"):
        parts = s.split("-")
        try:
            return int((int(parts[0].strip()) + int(parts[1].strip())) // 2)
        except (ValueError, IndexError):
            pass
    # Strip commas and try direct parse
    try:
        return int(float(s.replace(",", "")))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Core: query_companies — dynamic filter builder on companies table
# ---------------------------------------------------------------------------

async def query_companies(
    filters: Dict[str, Any],
    sort_by: str = "name",
    sort_desc: bool = True,
    limit: int = 50,
    fund_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Query the companies table with flexible filters. Pure DB, no LLM.

    Filters (all optional, AND-composed):
        sector, stage, geography, keyword,
        arr_min, arr_max, valuation_min, valuation_max,
        funding_min, funding_max, founded_after, founded_before,
        raised_within_months, latest_round_date_after, latest_round_date_before,
        business_model, has_arr, round_name,
        extra_data_filters (dict for JSONB queries)

    Returns: {"companies": [...], "count": N, "filters_applied": {...}}
    """
    client = _get_client()
    if not client:
        return {"companies": [], "count": 0, "error": "Supabase unavailable"}

    try:
        limit = min(limit, 200)
        q = client.table("companies").select(SOURCING_COLUMNS)

        # --- Scope to fund if provided ---
        if fund_id or filters.get("fund_id"):
            q = q.eq("fund_id", fund_id or filters["fund_id"])

        # --- Text filters (ilike) ---
        if filters.get("sector"):
            q = q.ilike("sector", f"%{filters['sector']}%")

        if filters.get("stage"):
            stage = filters["stage"]
            # Match both 'stage' and 'funding_stage' columns via OR
            q = q.or_(f"stage.ilike.%{stage}%,funding_stage.ilike.%{stage}%")

        if filters.get("geography"):
            q = q.ilike("headquarters", f"%{filters['geography']}%")

        if filters.get("business_model"):
            q = q.ilike("revenue_model", f"%{filters['business_model']}%")

        if filters.get("keyword"):
            kw = filters["keyword"]
            q = q.or_(
                f"name.ilike.%{kw}%,sector.ilike.%{kw}%,"
                f"description.ilike.%{kw}%,ai_category.ilike.%{kw}%"
            )

        if filters.get("round_name"):
            q = q.ilike("funding_stage", f"%{filters['round_name']}%")

        # --- Numeric range filters ---
        if filters.get("arr_min") is not None:
            q = q.gte("current_arr_usd", filters["arr_min"])
        if filters.get("arr_max") is not None:
            q = q.lte("current_arr_usd", filters["arr_max"])

        if filters.get("valuation_min") is not None:
            q = q.gte("current_valuation_usd", filters["valuation_min"])
        if filters.get("valuation_max") is not None:
            q = q.lte("current_valuation_usd", filters["valuation_max"])

        if filters.get("funding_min") is not None:
            q = q.gte("total_raised", filters["funding_min"])
        if filters.get("funding_max") is not None:
            q = q.lte("total_raised", filters["funding_max"])

        if filters.get("founded_after") is not None:
            q = q.gte("founded_year", filters["founded_after"])
        if filters.get("founded_before") is not None:
            q = q.lte("founded_year", filters["founded_before"])

        # --- Round date filters ---
        # raised_within_months: compute cutoff from last_funding_date
        if filters.get("raised_within_months") is not None:
            from dateutil.relativedelta import relativedelta
            cutoff = datetime.now() - relativedelta(months=int(filters["raised_within_months"]))
            q = q.gte("last_funding_date", cutoff.strftime("%Y-%m-%d"))
        if filters.get("latest_round_date_after") is not None:
            q = q.gte("last_funding_date", filters["latest_round_date_after"])
        if filters.get("latest_round_date_before") is not None:
            q = q.lte("last_funding_date", filters["latest_round_date_before"])

        # --- Boolean filters ---
        if filters.get("has_arr"):
            q = q.not_.is_("current_arr_usd", "null")

        # --- Sort ---
        sort_col = SORT_COLUMN_MAP.get(sort_by, "name")
        q = q.order(sort_col, desc=sort_desc)

        # --- Execute ---
        q = q.limit(limit)
        result = q.execute()
        rows = result.data or []

        # Format consistently with search_companies_db
        companies = []
        for c in rows:
            companies.append(_format_company(c))

        filters_applied = {k: v for k, v in filters.items() if v is not None}
        return {
            "companies": companies,
            "count": len(companies),
            "filters_applied": filters_applied,
        }

    except Exception as e:
        logger.error(f"sourcing_service.query_companies failed: {e}")
        return {"companies": [], "count": 0, "error": str(e)}


def _format_company(c: dict) -> dict:
    """Format a raw company row into a consistent dict."""
    return {
        "company_id": c.get("id"),
        "name": c.get("name", ""),
        "sector": c.get("sector", ""),
        "stage": c.get("stage") or c.get("funding_stage", ""),
        "description": c.get("description", ""),
        "arr": c.get("current_arr_usd"),
        "valuation": c.get("current_valuation_usd") or c.get("last_valuation_usd"),
        "total_funding": c.get("total_raised"),
        "growth_rate": c.get("growth_rate"),
        "employee_count": c.get("employee_count"),
        "hq": c.get("headquarters", ""),
        "founded": c.get("founded_year"),
        "burn_rate": c.get("burn_rate_monthly_usd"),
        "runway_months": c.get("runway_months"),
        "business_model": c.get("revenue_model", ""),
        "latest_round": c.get("funding_stage", ""),
        "latest_round_date": str(c.get("last_funding_date", "") or ""),
        "tam": c.get("tam"),
        "extra_data": c.get("extra_data") or {},
    }


# ---------------------------------------------------------------------------
# Core: score_companies — pure math scoring, no LLM
# ---------------------------------------------------------------------------

def score_companies(
    companies: List[Dict[str, Any]],
    weights: Optional[Dict[str, float]] = None,
    target_stage: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Score and rank a list of companies. Pure math, no LLM, no web.

    Each company gets a composite score 0–100 based on weighted dimensions.
    Missing data scores 0 — that IS the signal (sparse = low score).

    Returns the same dicts with score, rank, and score_breakdown added.
    """
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    # Normalize weights to sum to 1
    total_w = sum(w.values())
    if total_w > 0:
        w = {k: v / total_w for k, v in w.items()}

    scored = []
    for company in companies:
        breakdown = {}

        # 1. Data completeness (0-10): count non-null key fields
        check_fields = [
            "arr", "valuation", "total_funding", "stage", "sector",
            "description", "growth_rate", "employee_count", "business_model", "hq",
        ]
        non_null = sum(
            1 for f in check_fields
            if company.get(f) not in (None, "", 0, "0", {})
        )
        breakdown["data_completeness"] = non_null  # 0-10

        # 2. Stage fit (0-10)
        breakdown["stage_fit"] = _score_stage_fit(company.get("stage", ""), target_stage)

        # 3. Growth signal (0-10)
        gr = _safe_float(company.get("growth_rate"))
        if gr >= 3.0:
            breakdown["growth_signal"] = 10
        elif gr >= 2.0:
            breakdown["growth_signal"] = 8
        elif gr >= 1.0:
            breakdown["growth_signal"] = 6
        elif gr >= 0.5:
            breakdown["growth_signal"] = 4
        elif gr > 0:
            breakdown["growth_signal"] = 2
        else:
            breakdown["growth_signal"] = 0

        # 4. Market size (0-10) based on TAM
        tam = _safe_float(company.get("tam"))
        if tam >= 10_000_000_000:
            breakdown["market_size"] = 10
        elif tam >= 1_000_000_000:
            breakdown["market_size"] = 8
        elif tam >= 100_000_000:
            breakdown["market_size"] = 6
        elif tam > 0:
            breakdown["market_size"] = 3
        else:
            breakdown["market_size"] = 0

        # 5. Capital efficiency: ARR / total_funding
        arr = _safe_float(company.get("arr"))
        funding = _safe_float(company.get("total_funding"))
        if arr > 0 and funding > 0:
            ratio = arr / funding
            if ratio >= 1.0:
                breakdown["capital_efficiency"] = 10
            elif ratio >= 0.5:
                breakdown["capital_efficiency"] = 8
            elif ratio >= 0.3:
                breakdown["capital_efficiency"] = 6
            elif ratio >= 0.1:
                breakdown["capital_efficiency"] = 4
            else:
                breakdown["capital_efficiency"] = 2
        else:
            breakdown["capital_efficiency"] = 0

        # 6. Recency: how recently they raised
        breakdown["recency"] = _score_recency(company.get("latest_round_date"))

        # 7. Scale: absolute ARR
        if arr >= 50_000_000:
            breakdown["scale"] = 10
        elif arr >= 20_000_000:
            breakdown["scale"] = 8
        elif arr >= 10_000_000:
            breakdown["scale"] = 7
        elif arr >= 5_000_000:
            breakdown["scale"] = 6
        elif arr >= 1_000_000:
            breakdown["scale"] = 4
        elif arr > 0:
            breakdown["scale"] = 2
        else:
            breakdown["scale"] = 0

        # Composite: weighted sum normalized to 0–100
        composite = sum(breakdown.get(dim, 0) * w.get(dim, 0) for dim in w)
        composite = round(composite * 10, 1)  # scale 0-10 weighted → 0-100

        scored.append({
            **company,
            "score": composite,
            "score_breakdown": breakdown,
        })

    # Sort by score descending, assign ranks
    scored.sort(key=lambda x: x["score"], reverse=True)
    for i, item in enumerate(scored):
        item["rank"] = i + 1

    return scored


def _score_stage_fit(company_stage: str, target_stage: Optional[str]) -> int:
    """Score how well the company's stage matches the target."""
    if not target_stage:
        return 7  # neutral if no target

    stage_order = {
        "pre-seed": 0, "seed": 1, "series a": 2, "series b": 3,
        "series c": 4, "series d": 5, "series e": 6, "growth": 7,
        "pre-ipo": 8, "public": 9,
    }

    cs = (company_stage or "").lower().strip()
    ts = target_stage.lower().strip()

    ci = stage_order.get(cs)
    ti = stage_order.get(ts)

    if ci is None or ti is None:
        # Fuzzy: check if target appears in company stage string
        if ts in cs or cs in ts:
            return 10
        return 3

    diff = abs(ci - ti)
    if diff == 0:
        return 10
    elif diff == 1:
        return 7
    elif diff == 2:
        return 4
    else:
        return 2


def _parse_round_date(latest_round_date: Any) -> Optional[datetime]:
    """Parse a round date from various formats into a datetime.

    Handles: datetime objects, "Q2 2022", "2024-01-15", "2024-01",
    "2024", "2024-01-15 00:00:00".  Returns None on failure.
    """
    if not latest_round_date:
        return None

    # Already a datetime
    if isinstance(latest_round_date, datetime):
        return latest_round_date

    s = str(latest_round_date).strip()
    if not s:
        return None

    # Quarter format: "Q1 2022", "Q2 2023", etc.
    m = re.match(r"^Q([1-4])\s+(\d{4})$", s)
    if m:
        quarter = int(m.group(1))
        year = int(m.group(2))
        month = {1: 1, 2: 4, 3: 7, 4: 10}[quarter]
        return datetime(year, month, 1)

    # Standard formats (most specific first)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue

    return None


def _score_recency(latest_round_date: Any) -> int:
    """Score based on how recently the company raised."""
    dt = _parse_round_date(latest_round_date)
    if dt is None:
        return 0

    try:

        now = datetime.now()
        months_ago = (now.year - dt.year) * 12 + (now.month - dt.month)

        if months_ago <= 6:
            return 10
        elif months_ago <= 12:
            return 8
        elif months_ago <= 24:
            return 6
        elif months_ago <= 36:
            return 4
        else:
            return 2
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Display mode selection
# ---------------------------------------------------------------------------

def pick_display_mode(count: int, explicit: Optional[str] = None) -> str:
    """Pick the best display mode based on result count."""
    if explicit and explicit in ("card", "table", "ranked_list", "grid_rows"):
        return explicit

    if count == 0:
        return "table"
    elif count == 1:
        return "card"
    elif count <= 8:
        return "table"
    else:
        return "ranked_list"


def format_as_markdown_table(
    companies: List[Dict[str, Any]],
    include_score: bool = True,
) -> str:
    """Format a list of scored companies as a markdown table."""
    if not companies:
        return "*No companies found matching your criteria.*"

    headers = ["#", "Company", "Sector", "Stage", "ARR", "Valuation", "Funding"]
    if include_score:
        headers.append("Score")

    rows = []
    for c in companies:
        row = [
            str(c.get("rank", "")),
            c.get("name", ""),
            c.get("sector", "") or "",
            c.get("stage", "") or "",
            _fmt_money(c.get("arr")),
            _fmt_money(c.get("valuation")),
            _fmt_money(c.get("total_funding")),
        ]
        if include_score:
            row.append(str(c.get("score", "")))
        rows.append(row)

    # Build markdown
    sep = " | "
    header_line = sep.join(headers)
    divider = sep.join("---" for _ in headers)
    body = "\n".join(sep.join(r) for r in rows)
    return f"{header_line}\n{divider}\n{body}"


def _fmt_money(val: Any) -> str:
    """Format a dollar amount for display."""
    n = _safe_float(val)
    if n <= 0:
        return "—"
    if n >= 1_000_000_000:
        return f"${n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"${n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"${n / 1_000:.0f}K"
    return f"${n:.0f}"


# ---------------------------------------------------------------------------
# Persistence: upsert sourced companies back to the DB
# ---------------------------------------------------------------------------

async def upsert_sourced_companies(
    companies: List[Dict[str, Any]],
    fund_id: Optional[str] = None,
) -> int:
    """Upsert enriched sourcing results back into the companies table.

    Matches on company name (case-insensitive). Updates existing rows,
    inserts new ones. Returns number of rows upserted.

    Uses search-then-update/insert pattern since the companies table has
    no unique constraint on name.
    """
    client = _get_client()
    if not client:
        return 0

    upserted = 0
    for c in companies:
        name = c.get("name", "").strip()
        if not name:
            continue

        # Map score → thesis_match_score for DB persistence
        _score_val = _safe_float(c.get("score")) or _safe_float(c.get("composite_score"))

        row = {
            "name": name,
            "sector": c.get("sector") or None,
            "stage": c.get("stage") or None,
            "description": c.get("description") or None,
            "current_arr_usd": _safe_float(c.get("arr")) or None,
            "current_valuation_usd": _safe_float(c.get("valuation")) or None,
            "total_raised": _safe_float(c.get("total_funding")) or None,
            "growth_rate": _safe_float(c.get("growth_rate")) or None,
            "employee_count": _safe_int(c.get("employee_count")) or None,
            "headquarters": c.get("hq") or None,
            "revenue_model": c.get("business_model") or None,
            "funding_stage": c.get("latest_round") or None,
            "tam": _safe_float(c.get("tam")) or None,
            "thesis_match_score": _score_val if _score_val > 0 else None,
        }
        if fund_id:
            row["fund_id"] = fund_id

        # Remove None values — only update fields we have data for
        row = {k: v for k, v in row.items() if v is not None}

        try:
            # Search for existing company by name (case-insensitive)
            search = client.table("companies").select("id")
            if fund_id:
                search = search.eq("fund_id", fund_id)
            result = search.ilike("name", name).limit(1).execute()
            existing = result.data[0] if result.data else None

            if existing:
                update_row = {k: v for k, v in row.items() if k != "name"}
                if update_row:
                    client.table("companies").update(update_row).eq(
                        "id", existing["id"]
                    ).execute()
            else:
                client.table("companies").insert(row).execute()

            upserted += 1
        except Exception as e:
            logger.warning(f"upsert_sourced_companies failed for {name}: {e}")

    return upserted


# ---------------------------------------------------------------------------
# Rubric generation — turn a natural-language thesis into a complete
# sourcing instruction set: intent, weights, filters, scoring profile,
# entity type, and search context for LLM-driven web discovery.
# ---------------------------------------------------------------------------

# Predefined weight templates keyed by common thesis archetypes
_WEIGHT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "growth": {
        "weights": {
            "growth_signal": 0.35,
            "scale": 0.20,
            "capital_efficiency": 0.15,
            "stage_fit": 0.10,
            "market_size": 0.10,
            "recency": 0.05,
            "data_completeness": 0.05,
        },
        "description": "Growth-first: prioritises high growth rate and scale.",
    },
    "efficiency": {
        "weights": {
            "capital_efficiency": 0.35,
            "growth_signal": 0.20,
            "scale": 0.15,
            "stage_fit": 0.10,
            "market_size": 0.10,
            "recency": 0.05,
            "data_completeness": 0.05,
        },
        "description": "Efficiency-first: rewards high ARR/funding ratio.",
    },
    "market_size": {
        "weights": {
            "market_size": 0.30,
            "growth_signal": 0.20,
            "scale": 0.15,
            "capital_efficiency": 0.15,
            "stage_fit": 0.10,
            "recency": 0.05,
            "data_completeness": 0.05,
        },
        "description": "TAM-first: favours large addressable markets.",
    },
    "balanced": {
        "weights": dict(DEFAULT_WEIGHTS),
        "description": "Balanced: equal emphasis across all dimensions.",
    },
}


# ---------------------------------------------------------------------------
# Intent classification — determines how we search, extract, and score
# ---------------------------------------------------------------------------

# Each intent defines:
#   - patterns: keywords that trigger this intent
#   - entity_type: what shape of thing we're looking for
#   - search_context: instructions for the LLM query generator
#   - extraction_hint: what to tell the LLM to pull out of search results
#   - scoring_emphasis: which weight dimensions matter most
_INTENT_PROFILES: Dict[str, Dict[str, Any]] = {
    "dealflow": {
        "patterns": [
            "startup", "series", "funding", "raised", "pre-seed", "seed",
            "venture", "portfolio", "invest", "deal", "round", "valuation",
            "arr", "revenue", "growth", "b2b", "b2c", "saas",
        ],
        "entity_type": "startup",
        "search_context": (
            "Find startup companies that match this investment thesis. "
            "Look for companies that have raised venture funding, have traction "
            "(revenue, customers, growth), and fit the sector/stage/geography described. "
            "Prioritise sources where company names appear densely: funding announcements, "
            "Crunchbase profiles, TechCrunch articles, VC portfolio pages, startup lists."
        ),
        "extraction_hint": (
            "Extract company/startup names only. Not investors, not people, not products. "
            "Each name should be an actual company that could be in a VC pipeline."
        ),
        "scoring_emphasis": {
            "growth_signal": 1.2,
            "capital_efficiency": 1.2,
            "stage_fit": 1.1,
        },
    },
    "acquirer": {
        "patterns": [
            "acquirer", "acquire", "acquisition", "buy-side", "strategic",
            "mid-market", "mid market", "buyer", "m&a", "roll-up", "rollup",
            "consolidat", "bolt-on", "platform acquisition",
        ],
        "entity_type": "company",
        "search_context": (
            "Find companies that are active acquirers or likely acquisition candidates. "
            "Look for companies with acquisition track records, PE-backed platforms doing "
            "roll-ups, strategic buyers expanding via M&A. Search for M&A announcements, "
            "PE portfolio companies, corporate development activity, deal tombstones."
        ),
        "extraction_hint": (
            "Extract company names that are acquirers or buyers — not the targets being acquired. "
            "Include PE-backed platforms, strategics, and serial acquirers."
        ),
        "scoring_emphasis": {
            "scale": 1.5,
            "market_size": 1.2,
            "recency": 1.3,
        },
    },
    "gtm_leads": {
        "patterns": [
            "lead", "prospect", "customer", "gtm", "go-to-market", "go to market",
            "sell to", "icp", "ideal customer", "target account", "buyer",
            "pipeline", "sales", "outbound",
        ],
        "entity_type": "company",
        "search_context": (
            "Find companies that match this ideal customer profile or go-to-market target. "
            "Look for companies by size, industry, technology stack, pain points, or buying signals. "
            "Search for industry directories, G2/Capterra listings, conference attendee lists, "
            "job postings that signal need, case studies from competitors, industry reports."
        ),
        "extraction_hint": (
            "Extract company names that are potential customers or buyers of a product/service. "
            "Not the product companies themselves — the companies that would buy from them."
        ),
        "scoring_emphasis": {
            "scale": 1.3,
            "data_completeness": 1.3,
            "market_size": 1.0,
        },
    },
    "lp_investor": {
        "patterns": [
            "lp", "limited partner", "family office", "endowment", "allocator",
            "fund of funds", "institutional investor", "pension", "sovereign wealth",
            "anchor", "commitment", "allocation",
        ],
        "entity_type": "investor",
        "search_context": (
            "Find institutional investors, family offices, or LPs that allocate to this "
            "type of fund or asset class. Look for commitment announcements, LP directories, "
            "conference speaker lists, Preqin-style databases, annual reports mentioning "
            "alternative allocations."
        ),
        "extraction_hint": (
            "Extract names of institutional investors, family offices, endowments, pension funds, "
            "or fund-of-funds. Not the fund managers — the capital allocators."
        ),
        "scoring_emphasis": {
            "scale": 1.5,
            "recency": 1.3,
            "data_completeness": 1.2,
        },
    },
    "service_provider": {
        "patterns": [
            "law firm", "lawyer", "legal", "bank", "banker", "advisor",
            "consultant", "accounting", "auditor", "recruiter", "placement agent",
        ],
        "entity_type": "company",
        "search_context": (
            "Find professional service providers (law firms, banks, consultants, etc.) "
            "active in this sector or deal type. Search for deal tombstones, league tables, "
            "Chambers rankings, advisor credits on recent transactions."
        ),
        "extraction_hint": (
            "Extract names of firms (law firms, banks, advisory firms, consultancies). "
            "Not individual people — the firms/organisations."
        ),
        "scoring_emphasis": {
            "scale": 1.2,
            "recency": 1.4,
            "data_completeness": 1.0,
        },
    },
    "talent": {
        "patterns": [
            "hire", "recruit", "cto", "cfo", "vp ", "head of", "executive",
            "advisor", "board member", "founder", "operator", "talent",
        ],
        "entity_type": "person",
        "search_context": (
            "Find people who match this role/profile. Search LinkedIn-style results, "
            "press mentions, speaker lists, board announcements, team pages. "
            "Focus on professional background, current role, and relevant experience."
        ),
        "extraction_hint": (
            "Extract full names of people — not company names. "
            "Include their most recent title/company if mentioned."
        ),
        "scoring_emphasis": {
            "recency": 1.5,
            "data_completeness": 1.3,
        },
    },
}


def _classify_intent(thesis_lower: str) -> str:
    """Classify query intent by scoring pattern matches.

    Returns the intent with the most keyword hits, or 'dealflow' as default.
    Scores are weighted: more specific patterns (multi-word) count more.
    """
    scores: Dict[str, float] = {}
    for intent, profile in _INTENT_PROFILES.items():
        score = 0.0
        for pattern in profile["patterns"]:
            if pattern in thesis_lower:
                # Multi-word patterns are more specific, weight them higher
                score += len(pattern.split()) * 1.5
        scores[intent] = score

    best = max(scores, key=scores.get)  # type: ignore
    # Only return non-dealflow if we have a meaningful signal
    if best != "dealflow" and scores[best] < 1.5:
        return "dealflow"
    return best


def generate_rubric(
    thesis_description: str,
    weight_overrides: Optional[Dict[str, float]] = None,
    target_stage: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Turn a natural-language thesis into a complete sourcing rubric.

    Returns a dict with:
      - weights: Dict[str, float]       (scoring weights for score_companies)
      - filters: Dict[str, Any]         (suggested query_companies filters)
      - target_stage: Optional[str]
      - description: str                (human-readable summary)
      - intent: str                     (dealflow/acquirer/gtm_leads/lp_investor/service_provider/talent)
      - entity_type: str                (startup/company/investor/person)
      - search_context: str             (instructions for LLM query generation)
      - extraction_hint: str            (instructions for LLM name extraction)
      - thesis_input: str               (original query)

    The intent determines how the entire sourcing loop behaves:
      - What the LLM query generator optimises for
      - What entity shape the extractor looks for
      - Which scoring dimensions get emphasised
    """
    thesis_lower = thesis_description.lower()

    # ── 1. Classify intent ──
    intent = _classify_intent(thesis_lower)
    intent_profile = _INTENT_PROFILES[intent]

    # ── 2. Pick base weight template ──
    if any(kw in thesis_lower for kw in ("high growth", "hypergrowth", "fast growing", "100% nrr", ">100%", "triple")):
        base = dict(_WEIGHT_TEMPLATES["growth"]["weights"])
        desc = _WEIGHT_TEMPLATES["growth"]["description"]
    elif any(kw in thesis_lower for kw in ("efficient", "capital efficient", "lean", "profitable", "cash flow")):
        base = dict(_WEIGHT_TEMPLATES["efficiency"]["weights"])
        desc = _WEIGHT_TEMPLATES["efficiency"]["description"]
    elif any(kw in thesis_lower for kw in ("large market", "big tam", "massive market", "huge tam", "tam")):
        base = dict(_WEIGHT_TEMPLATES["market_size"]["weights"])
        desc = _WEIGHT_TEMPLATES["market_size"]["description"]
    else:
        base = dict(_WEIGHT_TEMPLATES["balanced"]["weights"])
        desc = _WEIGHT_TEMPLATES["balanced"]["description"]

    # ── 3. Apply intent scoring emphasis ──
    # The intent profile boosts/dampens certain dimensions
    for dim, multiplier in intent_profile.get("scoring_emphasis", {}).items():
        if dim in base:
            base[dim] = base[dim] * multiplier

    # ── 4. Apply explicit overrides ──
    if weight_overrides:
        for dim, val in weight_overrides.items():
            if dim in base:
                base[dim] = float(val)

    # Normalise weights to sum to 1.0
    total = sum(base.values())
    if total > 0:
        base = {k: round(v / total, 4) for k, v in base.items()}

    # ── 5. Extract implicit filters from thesis text ──
    extracted_filters: Dict[str, Any] = dict(filters or {})

    # Stage hints
    _stage_map = {
        "pre-seed": "Pre-Seed", "preseed": "Pre-Seed",
        "seed": "Seed",
        "series a": "Series A",
        "series b": "Series B",
        "series c": "Series C",
        "series d": "Series D",
    }
    detected_stage = target_stage
    for pattern, stage_val in _stage_map.items():
        if pattern in thesis_lower:
            detected_stage = stage_val
            extracted_filters.setdefault("stage", stage_val)
            break

    # Sector hints
    _sector_keywords = [
        "fintech", "healthtech", "health tech", "edtech", "saas", "b2b saas",
        "ai", "artificial intelligence", "ml", "machine learning",
        "cybersecurity", "security", "climate", "cleantech", "biotech",
        "e-commerce", "ecommerce", "marketplace", "infrastructure", "devtools",
        "developer tools", "data infrastructure", "proptech",
    ]
    for kw in _sector_keywords:
        if kw in thesis_lower:
            extracted_filters.setdefault("sector", kw)
            break

    # ARR hints — match patterns like "$3M ARR", "$3-10M ARR", ">$5M ARR"
    arr_match = re.search(r'[\$>]?\s*(\d+(?:\.\d+)?)\s*[–\-]?\s*(?:(\d+(?:\.\d+)?)\s*)?[mM]\s*(?:arr|ARR|revenue)', thesis_lower)
    if arr_match:
        arr_low = float(arr_match.group(1)) * 1_000_000
        extracted_filters.setdefault("arr_min", arr_low)
        if arr_match.group(2):
            arr_high = float(arr_match.group(2)) * 1_000_000
            extracted_filters.setdefault("arr_max", arr_high)

    # Geography hints
    _geo_keywords = ["us", "usa", "united states", "europe", "uk", "apac", "latam", "india", "emea"]
    for gk in _geo_keywords:
        if gk in thesis_lower.split():
            extracted_filters.setdefault("geography", gk.upper() if len(gk) <= 4 else gk.title())
            break

    # ── 6. Build search context for LLM query generation ──
    # This is the full instruction set that tells the LLM what kind of
    # searches to run when DB results are thin.
    search_context_parts = [intent_profile["search_context"]]
    if extracted_filters.get("sector"):
        search_context_parts.append(f"Sector focus: {extracted_filters['sector']}")
    if detected_stage:
        search_context_parts.append(f"Stage: {detected_stage}")
    if extracted_filters.get("geography"):
        search_context_parts.append(f"Geography: {extracted_filters['geography']}")
    if extracted_filters.get("arr_min"):
        search_context_parts.append(f"Minimum ARR: ${extracted_filters['arr_min']/1e6:.0f}M")

    entity_type = intent_profile["entity_type"]
    return {
        "weights": base,
        "filters": extracted_filters,
        "target_stage": detected_stage,
        "description": desc,
        "thesis_input": thesis_description,
        # New fields for the sourcing loop
        "intent": intent,
        "entity_type": entity_type,
        "search_context": " ".join(search_context_parts),
        "extraction_hint": intent_profile["extraction_hint"],
        "completeness_fields": _default_completeness_fields(entity_type),
    }


# ---------------------------------------------------------------------------
# LLM-based rubric generation — replaces brittle keyword pattern matching
# ---------------------------------------------------------------------------

# Default completeness fields per entity type.  Used when the LLM doesn't
# provide them or when falling back to the pattern-matched rubric.
_COMPLETENESS_FIELDS_BY_ENTITY: Dict[str, List[str]] = {
    "startup": ["name", "sector", "stage", "last_funding_amount", "description", "investors"],
    "company": ["name", "sector", "description", "employee_count", "hq", "website"],
    "investor": ["name", "description", "sector", "geography", "aum", "specialization"],
    "person": ["name", "title", "current_company", "description", "sector", "linkedin_url"],
}


def _default_completeness_fields(entity_type: str) -> List[str]:
    """Default completeness fields when LLM doesn't provide them."""
    return list(_COMPLETENESS_FIELDS_BY_ENTITY.get(
        entity_type, _COMPLETENESS_FIELDS_BY_ENTITY["startup"]
    ))


def build_rubric_classification_prompt(query: str) -> str:
    """Build prompt for LLM-based rubric generation.

    The LLM classifies the user's list-building query into intent, entity type,
    filters, and search strategy — replacing brittle keyword pattern matching.
    """
    return (
        "Analyze this list-building request and classify it for a search pipeline.\n\n"
        f"REQUEST: {query}\n\n"
        "Return JSON:\n"
        "{\n"
        '  "intent": one of "dealflow", "acquirer", "gtm_leads", "lp_investor", "service_provider", "talent",\n'
        '  "entity_type": one of "startup", "company", "investor", "person",\n'
        '  "weight_profile": one of "growth", "efficiency", "market_size", "balanced",\n'
        '  "sector": "detected sector/vertical or null",\n'
        '  "stage": "Pre-Seed|Seed|Series A|Series B|Series C|Series D or null",\n'
        '  "geography": "detected geography or null",\n'
        '  "arr_min": integer dollar amount or null,\n'
        '  "arr_max": integer dollar amount or null,\n'
        '  "search_context": "2-3 sentence instruction for a web search agent",\n'
        '  "extraction_hint": "1-2 sentence instruction for what entity names to extract",\n'
        '  "completeness_fields": ["name", "sector", ...4-6 fields]\n'
        "}\n\n"
        "INTENT DEFINITIONS:\n"
        "- dealflow: finding startups or companies for an investment pipeline\n"
        "- acquirer: finding companies that acquire others (PE platforms, strategic buyers, roll-ups)\n"
        "- gtm_leads: finding potential customers, sales prospects, ICP targets\n"
        "- lp_investor: finding institutional investors, family offices, LPs, allocators\n"
        "- service_provider: finding professional service firms (law, banking, consulting, recruiting)\n"
        "- talent: finding people (executives, advisors, board members, operators)\n\n"
        "WEIGHT PROFILE — pick the one that best matches the request's emphasis:\n"
        "- growth: growth signals, revenue trajectory, market expansion\n"
        "- efficiency: capital efficiency, profitability, unit economics\n"
        "- market_size: TAM, market position, scale\n"
        "- balanced: no strong emphasis (use when unclear)\n\n"
        "COMPLETENESS FIELDS — pick 4-6 that define a 'complete' record for this query:\n"
        "  Startup/company: name, sector, stage, last_funding_amount, description, investors, employee_count, hq, website\n"
        "  Person/talent: name, title, current_company, description, linkedin_url, sector, years_experience\n"
        "  Investor/LP: name, aum, fund_size, sector, geography, description, specialization\n\n"
        "SEARCH CONTEXT — describe what to search for and where:\n"
        "- What kind of entities to find and what makes them relevant\n"
        "- What web sources to prioritize (directories, funding pages, LinkedIn, portfolios, league tables, etc.)\n"
        "- Any specific criteria or constraints from the request\n\n"
        "EXTRACTION HINT — describe what to pull from search results:\n"
        "- What entity names to extract (company names, person names, firm names)\n"
        "- What NOT to extract (e.g., investors when looking for startups, firms when looking for people)\n"
    )


def parse_llm_rubric(
    llm_output: Dict[str, Any],
    query: str,
    weight_overrides: Optional[Dict[str, float]] = None,
    target_stage: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Parse LLM rubric classification into the standard rubric dict.

    Takes the raw LLM JSON output and produces the same shape as generate_rubric().
    """
    intent = llm_output.get("intent", "dealflow")
    if intent not in _INTENT_PROFILES:
        intent = "dealflow"

    entity_type = llm_output.get("entity_type")
    if entity_type not in ("startup", "company", "investor", "person"):
        entity_type = _INTENT_PROFILES[intent]["entity_type"]

    weight_profile = llm_output.get("weight_profile", "balanced")
    if weight_profile not in _WEIGHT_TEMPLATES:
        weight_profile = "balanced"

    # Build weights from profile
    base = dict(_WEIGHT_TEMPLATES[weight_profile]["weights"])
    desc = _WEIGHT_TEMPLATES[weight_profile]["description"]

    # Apply intent scoring emphasis from the profile
    intent_profile = _INTENT_PROFILES[intent]
    for dim, multiplier in intent_profile.get("scoring_emphasis", {}).items():
        if dim in base:
            base[dim] = base[dim] * multiplier

    # Apply explicit overrides
    if weight_overrides:
        for dim, val in weight_overrides.items():
            if dim in base:
                base[dim] = float(val)

    # Normalise weights to sum to 1.0
    total = sum(base.values())
    if total > 0:
        base = {k: round(v / total, 4) for k, v in base.items()}

    # Build filters from LLM output + explicit overrides
    extracted_filters: Dict[str, Any] = dict(filters or {})
    if llm_output.get("sector"):
        extracted_filters.setdefault("sector", llm_output["sector"])
    if llm_output.get("geography"):
        extracted_filters.setdefault("geography", llm_output["geography"])
    if llm_output.get("arr_min"):
        extracted_filters.setdefault("arr_min", llm_output["arr_min"])
    if llm_output.get("arr_max"):
        extracted_filters.setdefault("arr_max", llm_output["arr_max"])

    detected_stage = target_stage or llm_output.get("stage")
    if detected_stage:
        extracted_filters.setdefault("stage", detected_stage)

    # Search context — use LLM's version (tailored to this specific query)
    search_context = llm_output.get("search_context") or intent_profile["search_context"]
    # Append structured filter info for downstream query generation
    if extracted_filters.get("sector"):
        search_context += f" Sector focus: {extracted_filters['sector']}."
    if detected_stage:
        search_context += f" Stage: {detected_stage}."
    if extracted_filters.get("geography"):
        search_context += f" Geography: {extracted_filters['geography']}."

    extraction_hint = llm_output.get("extraction_hint") or intent_profile["extraction_hint"]

    # Completeness fields — LLM picks what matters for this query type
    completeness_fields = llm_output.get("completeness_fields")
    if not completeness_fields or not isinstance(completeness_fields, list) or len(completeness_fields) < 3:
        completeness_fields = _default_completeness_fields(entity_type)

    return {
        "weights": base,
        "filters": extracted_filters,
        "target_stage": detected_stage,
        "description": desc,
        "thesis_input": query,
        "intent": intent,
        "entity_type": entity_type,
        "search_context": search_context,
        "extraction_hint": extraction_hint,
        "completeness_fields": completeness_fields,
    }


# ---------------------------------------------------------------------------
# Search Strategy — intent-tagged query generation with template stamping
# ---------------------------------------------------------------------------

# Query intent types: determines how results get extracted downstream
QUERY_INTENTS = {
    "list_discovery": {
        "description": "Find aggregator list pages with many entity names",
        "expected_yield": "20-50+ names per page",
        "extraction_tier": "bulk",
    },
    "funding_signal": {
        "description": "Find funding announcements with rich metadata",
        "expected_yield": "1-3 names with stage, amount, investors",
        "extraction_tier": "rich",
    },
    "competitor_map": {
        "description": "Find competitor/alternative comparison pages",
        "expected_yield": "3-10 names with relational context",
        "extraction_tier": "rich",
    },
    "portfolio_mine": {
        "description": "Find VC portfolio pages for bulk name extraction",
        "expected_yield": "10-30 names with investor signal",
        "extraction_tier": "bulk",
    },
    "vertical_deep": {
        "description": "Find niche subcategory companies",
        "expected_yield": "5-15 names with sector classification",
        "extraction_tier": "bulk",
    },
}

# Query templates per intent, keyed by entity-level intent (dealflow, gtm_leads, etc.)
# {subcategory} and {year} are replaced at stamp time
_QUERY_TEMPLATES: Dict[str, Dict[str, List[str]]] = {
    "dealflow": {
        "list_discovery": [
            "top {subcategory} startups {year}",
            "best {subcategory} companies {year}",
            "fastest growing {subcategory} companies",
        ],
        "funding_signal": [
            "{subcategory} companies funding raised {year_prev} {year}",
            "{subcategory} {target_stage} funding {year}",
        ],
        "competitor_map": [
            "{known_company} competitors alternatives",
        ],
        "portfolio_mine": [
            "{investor} portfolio {sector}",
            "{investor} {sector} investments",
        ],
        "vertical_deep": [
            "{subcategory} software companies",
            "{subcategory} platform startups",
        ],
    },
    "acquirer": {
        "list_discovery": [
            "most active acquirers {subcategory} {year}",
            "top {subcategory} acquisition platforms {year}",
        ],
        "funding_signal": [
            "{subcategory} company acquired {year_prev} {year}",
            "PE backed {subcategory} platform acquisitions",
        ],
        "vertical_deep": [
            "{subcategory} roll-up platforms",
            "{subcategory} consolidation companies",
        ],
    },
    "gtm_leads": {
        "list_discovery": [
            "top {subcategory} companies {year}",
            "largest {subcategory} companies list",
            "fastest growing {subcategory} businesses {year}",
        ],
        "vertical_deep": [
            "{subcategory} companies hiring",
            "{subcategory} enterprise companies",
        ],
    },
    "lp_investor": {
        "list_discovery": [
            "top family offices investing in {subcategory} {year}",
            "institutional investors {subcategory} allocations",
        ],
        "funding_signal": [
            "endowment {subcategory} allocation {year}",
            "pension fund {subcategory} commitment {year}",
        ],
    },
    "service_provider": {
        "list_discovery": [
            "top {subcategory} advisory firms {year}",
            "best {subcategory} law firms league table",
        ],
        "vertical_deep": [
            "{subcategory} investment banks boutique",
            "{subcategory} consultants advisors",
        ],
    },
    "talent": {
        "list_discovery": [
            "top {subcategory} executives leaders {year}",
            "{subcategory} founders to watch {year}",
        ],
        "vertical_deep": [
            "{subcategory} CTO VP engineering leaders",
            "{subcategory} operator executives",
        ],
    },
}

# Fallback templates when entity intent has no specific templates for a query intent
_FALLBACK_TEMPLATES: Dict[str, List[str]] = {
    "list_discovery": [
        "top {subcategory} companies {year}",
        "best {subcategory} startups {year}",
    ],
    "funding_signal": [
        "{subcategory} funding raised {year_prev} {year}",
    ],
    "vertical_deep": [
        "{subcategory} companies",
    ],
}


def build_decomposition_prompt(rubric: Dict[str, Any]) -> str:
    """Build the prompt that decomposes a search request into subcategories.

    The LLM's job is ONLY to break down the request into 3-5 searchable
    subcategories. Query generation is then deterministic via templates.
    """
    thesis = rubric.get("thesis_input", "")
    intent = rubric.get("intent", "dealflow")
    entity_type = rubric.get("entity_type", "startup")
    filters = rubric.get("filters", {})

    sector = filters.get("sector", "")
    stage = rubric.get("target_stage", "")
    geography = filters.get("geography", "")

    # Only ask for investor data when portfolio mining is relevant
    if intent == "dealflow":
        extra_identify = (
            f"Also identify:\n"
            f"- 1-2 known companies in this space (for competitor mapping)\n"
            f"- 1-2 prominent investors in this space (for portfolio mining)\n\n"
        )
        json_schema = (
            f'{{\n'
            f'  "subcategories": ["subcategory1", "subcategory2", ...],\n'
            f'  "known_companies": ["Company1", "Company2"],\n'
            f'  "known_investors": ["Investor1", "Investor2"]\n'
            f'}}'
        )
    else:
        extra_identify = (
            f"Also identify:\n"
            f"- 1-2 known {entity_type}s or companies in this space (for finding similar ones)\n\n"
        )
        json_schema = (
            f'{{\n'
            f'  "subcategories": ["subcategory1", "subcategory2", ...],\n'
            f'  "known_companies": ["Company1", "Company2"]\n'
            f'}}'
        )

    return (
        f"Decompose this search request into 3-5 specific subcategories for web search.\n\n"
        f"REQUEST: {thesis}\n"
        f"ENTITY TYPE: {entity_type}\n"
        f"INTENT: {intent}\n"
        f"{f'SECTOR: {sector}' if sector else ''}\n"
        f"{f'STAGE: {stage}' if stage else ''}\n"
        f"{f'GEOGRAPHY: {geography}' if geography else ''}\n\n"
        f"Break this into 3-5 concrete subcategories that represent DIFFERENT segments "
        f"of what the user is looking for. Each subcategory should be a specific niche "
        f"that would appear on different web pages.\n\n"
        f"Example: 'healthcare SaaS' → ['EHR systems', 'telehealth platforms', "
        f"'revenue cycle management', 'clinical operations software', 'patient engagement']\n\n"
        f"{extra_identify}"
        f"Return JSON:\n"
        f"{json_schema}"
    )


def stamp_queries_from_decomposition(
    decomposition: Dict[str, Any],
    rubric: Dict[str, Any],
    max_queries: int = 10,
) -> List[Dict[str, str]]:
    """Stamp subcategories into proven query templates.

    Takes the LLM decomposition output and the rubric, returns a list of
    tagged queries: [{"query": "...", "intent": "list_discovery"}, ...]

    Each query carries its intent tag through the entire pipeline.
    """
    from datetime import datetime as _dt
    year = str(_dt.now().year)
    year_prev = str(_dt.now().year - 1)

    subcategories = decomposition.get("subcategories", [])
    known_companies = decomposition.get("known_companies", [])
    known_investors = decomposition.get("known_investors", [])

    entity_intent = rubric.get("intent", "dealflow")
    target_stage = rubric.get("target_stage", "")
    sector = rubric.get("filters", {}).get("sector", "")

    templates = _QUERY_TEMPLATES.get(entity_intent, {})
    tagged_queries: List[Dict[str, str]] = []

    # Phase 1: Stamp list_discovery + vertical_deep for each subcategory
    # These are the highest-yield query types
    for sub in subcategories[:5]:
        vars_ = {
            "subcategory": sub,
            "year": year,
            "year_prev": year_prev,
            "target_stage": target_stage or "Series A",
            "sector": sector or sub,
        }

        # List discovery — one per subcategory
        list_templates = templates.get("list_discovery", _FALLBACK_TEMPLATES["list_discovery"])
        if list_templates:
            t = list_templates[len(tagged_queries) % len(list_templates)]
            tagged_queries.append({
                "query": t.format(**vars_),
                "intent": "list_discovery",
                "subcategory": sub,
            })

        # Vertical deep — one per subcategory (alternating templates)
        deep_templates = templates.get("vertical_deep", _FALLBACK_TEMPLATES["vertical_deep"])
        if deep_templates and len(tagged_queries) < max_queries:
            t = deep_templates[len(tagged_queries) % len(deep_templates)]
            tagged_queries.append({
                "query": t.format(**vars_),
                "intent": "vertical_deep",
                "subcategory": sub,
            })

    # Phase 2: Funding signal queries (1-2, using first subcategories)
    funding_templates = templates.get("funding_signal", _FALLBACK_TEMPLATES.get("funding_signal", []))
    for i, sub in enumerate(subcategories[:2]):
        if len(tagged_queries) >= max_queries:
            break
        if funding_templates:
            vars_ = {
                "subcategory": sub,
                "year": year,
                "year_prev": year_prev,
                "target_stage": target_stage or "Series B",
                "sector": sector or sub,
            }
            t = funding_templates[i % len(funding_templates)]
            tagged_queries.append({
                "query": t.format(**vars_),
                "intent": "funding_signal",
                "subcategory": sub,
            })

    # Phase 3: Competitor map (if we have known companies)
    comp_templates = templates.get("competitor_map", [])
    for company in known_companies[:2]:
        if len(tagged_queries) >= max_queries:
            break
        if comp_templates:
            tagged_queries.append({
                "query": comp_templates[0].format(known_company=company),
                "intent": "competitor_map",
                "subcategory": company,
            })

    # Phase 4: Portfolio mine (if we have known investors)
    port_templates = templates.get("portfolio_mine", [])
    for investor in known_investors[:1]:
        if len(tagged_queries) >= max_queries:
            break
        if port_templates:
            tagged_queries.append({
                "query": port_templates[0].format(
                    investor=investor,
                    sector=sector or subcategories[0] if subcategories else "technology",
                ),
                "intent": "portfolio_mine",
                "subcategory": investor,
            })

    return tagged_queries[:max_queries]


def build_query_gen_prompt(
    rubric: Dict[str, Any],
    db_result_count: int = 0,
    db_top_names: Optional[List[str]] = None,
    round_num: int = 1,
) -> str:
    """Build the prompt that tells the LLM to generate web search queries.

    LEGACY INTERFACE — kept for backward compatibility.
    The new pipeline uses build_decomposition_prompt() + stamp_queries_from_decomposition()
    but this function is still called as a fallback if decomposition fails.
    """
    thesis = rubric.get("thesis_input", "")
    intent = rubric.get("intent", "dealflow")
    entity_type = rubric.get("entity_type", "startup")
    search_context = rubric.get("search_context", "")
    filters = rubric.get("filters", {})

    if round_num == 1:
        return (
            f"Generate 6 targeted web search queries to find {entity_type}s.\n\n"
            f"USER REQUEST: {thesis}\n"
            f"INTENT: {intent}\n"
            f"SEARCH STRATEGY: {search_context}\n"
            f"{'FILTERS: ' + str(filters) if filters else ''}\n"
            f"{'DB already returned ' + str(db_result_count) + ' results — find MORE, different ones.' if db_result_count > 0 else 'DB returned nothing — cast a wide net.'}\n"
            f"{'Avoid duplicating these (already found): ' + ', '.join(db_top_names[:5]) if db_top_names else ''}\n\n"
            f"QUERY GUIDELINES:\n"
            f"- Each query should find DIFFERENT {entity_type}s (don't overlap)\n"
            f"- Prefer queries that target LIST PAGES (aggregators, top-N lists, directories)\n"
            f"- Include at least one funding-focused query for recent raises\n"
            f"- Use year filters (2024, 2025, 2026) for recency\n"
            f"- AVOID landscape/market overview queries — they return analysis, not names\n\n"
            f"Return JSON: {{\"queries\": [\"query1\", \"query2\", ..., \"query6\"]}}"
        )

    return (
        f"Round 1 search found {db_result_count} {entity_type}s but we need more.\n\n"
        f"USER REQUEST: {thesis}\n"
        f"INTENT: {intent}\n"
        f"Already found: {', '.join(db_top_names[:10]) if db_top_names else 'very few'}\n\n"
        f"Generate 4 DIFFERENT search queries to find MORE {entity_type}s we missed.\n"
        f"Strategies for round 2:\n"
        f"- Search for competitors/alternatives to the best results from round 1\n"
        f"- Try adjacent sectors or subcategories the first round didn't cover\n"
        f"- Look at investor portfolios or VC portfolio pages\n"
        f"- Target list pages and directories we haven't hit yet\n\n"
        f"Return JSON: {{\"queries\": [\"query1\", \"query2\", \"query3\", \"query4\"]}}"
    )


# ---------------------------------------------------------------------------
# Two-tier extraction — bulk vs rich, routed by query intent
# ---------------------------------------------------------------------------

def build_bulk_extraction_prompt(
    rubric: Dict[str, Any],
    search_snippets: str,
    existing_names: Optional[List[str]] = None,
) -> str:
    """Tier A: Bulk extraction for list_discovery, portfolio_mine, vertical_deep.

    Optimized for maximum name yield. Extracts many names with light metadata.
    """
    entity_type = rubric.get("entity_type", "startup")
    extraction_hint = rubric.get("extraction_hint", "Extract company names.")
    thesis = rubric.get("thesis_input", "")

    return (
        f"Extract ALL {entity_type} names from these search results. Maximize name yield.\n\n"
        f"{extraction_hint}\n\n"
        f"CONTEXT: {thesis}\n"
        f"{'SKIP these (already known): ' + ', '.join(existing_names[:30]) if existing_names else ''}\n\n"
        f"SEARCH RESULTS:\n{search_snippets}\n\n"
        f"Return JSON: {{\"companies\": [\n"
        f"  {{\"name\": \"Company Name\", \"sector\": \"sector if mentioned\", \"source_url\": \"url if visible\"}},\n"
        f"  ...\n"
        f"]}}\n\n"
        f"RULES:\n"
        f"- Extract EVERY {entity_type} name mentioned, even if only listed once\n"
        f"- Only real {entity_type} names, not generic terms or product names\n"
        f"- Include sector/category if mentioned alongside the name\n"
        f"- No duplicates\n"
        f"- Aim for 10-50+ names from list pages"
    )


def build_rich_extraction_prompt(
    rubric: Dict[str, Any],
    search_snippets: str,
    existing_names: Optional[List[str]] = None,
) -> str:
    """Tier B: Rich extraction for funding_signal, competitor_map.

    Extracts fewer names but captures as much metadata as available.
    JSON schema adapts to entity_type so we don't ask for funding data
    on talent searches or investor fields on service provider searches.
    """
    entity_type = rubric.get("entity_type", "startup")
    extraction_hint = rubric.get("extraction_hint", "Extract entity names.")
    thesis = rubric.get("thesis_input", "")

    # Entity-type-aware JSON schemas
    if entity_type == "person":
        schema_body = (
            f"    \"name\": \"Full Name\",\n"
            f"    \"title\": \"current title/role\",\n"
            f"    \"current_company\": \"company name\",\n"
            f"    \"description\": \"background and experience\",\n"
            f"    \"sector\": \"sector/vertical\",\n"
            f"    \"hq\": \"location\",\n"
            f"    \"source_url\": \"url\""
        )
        extra_rules = "- Include title and current_company when mentioned\n"
    elif entity_type == "investor":
        schema_body = (
            f"    \"name\": \"Investor Name\",\n"
            f"    \"sector\": \"sector focus\",\n"
            f"    \"aum\": 1000000000,\n"
            f"    \"fund_size\": 500000000,\n"
            f"    \"description\": \"investment focus and strategy\",\n"
            f"    \"geography\": \"location/region\",\n"
            f"    \"source_url\": \"url\""
        )
        extra_rules = "- AUM and fund_size as integers in dollars\n"
    else:
        # startup or company
        schema_body = (
            f"    \"name\": \"Company Name\",\n"
            f"    \"sector\": \"sector/vertical\",\n"
            f"    \"stage\": \"funding stage (Seed, Series A, etc.)\",\n"
            f"    \"last_funding_amount\": 65000000,\n"
            f"    \"investors\": [\"Investor1\", \"Investor2\"],\n"
            f"    \"description\": \"what the company does\",\n"
            f"    \"employee_count\": 150,\n"
            f"    \"hq\": \"location\",\n"
            f"    \"source_url\": \"url\""
        )
        extra_rules = "- Funding amounts as integers (65000000, not \"$65M\")\n"

    return (
        f"Extract {entity_type} names AND all available metadata from these search results.\n\n"
        f"{extraction_hint}\n\n"
        f"CONTEXT: {thesis}\n"
        f"{'SKIP these (already known): ' + ', '.join(existing_names[:30]) if existing_names else ''}\n\n"
        f"SEARCH RESULTS:\n{search_snippets}\n\n"
        f"For each {entity_type}, capture as much data as the text provides:\n"
        f"Return JSON: {{\"companies\": [\n"
        f"  {{\n"
        f"{schema_body}\n"
        f"  }},\n"
        f"  ...\n"
        f"]}}\n\n"
        f"RULES:\n"
        f"- Only include fields that are ACTUALLY mentioned in the text\n"
        f"- Use null for fields not mentioned — do NOT guess\n"
        f"{extra_rules}"
        f"- This data will be used directly — accuracy matters more than quantity"
    )


def build_name_extraction_prompt(
    rubric: Dict[str, Any],
    search_snippets: str,
    existing_names: Optional[List[str]] = None,
) -> str:
    """LEGACY: Single-tier name extraction. Kept for backward compatibility.

    New pipeline uses build_bulk_extraction_prompt / build_rich_extraction_prompt
    routed by query intent.
    """
    entity_type = rubric.get("entity_type", "startup")
    extraction_hint = rubric.get("extraction_hint", "Extract company names.")
    thesis = rubric.get("thesis_input", "")

    return (
        f"From the search results below, extract all {entity_type} names mentioned.\n\n"
        f"{extraction_hint}\n\n"
        f"CONTEXT: {thesis}\n"
        f"{'SKIP these (already known): ' + ', '.join(existing_names[:20]) if existing_names else ''}\n\n"
        f"SEARCH RESULTS:\n{search_snippets}\n\n"
        f"Return JSON: {{\"names\": [\"Name1\", \"Name2\", ...]}}\n"
        f"RULES:\n"
        f"- Only real {entity_type} names, not generic terms\n"
        f"- No duplicates\n"
        f"- If uncertain whether something is a {entity_type} name, include it"
    )


# ---------------------------------------------------------------------------
# Completeness scoring — determines enrichment depth per company
# ---------------------------------------------------------------------------

# Legacy default — kept for backward compatibility with callers that
# don't pass rubric-driven fields.  New callers should use
# rubric["completeness_fields"] from generate_rubric / parse_llm_rubric.
_COMPLETENESS_FIELDS = [
    "name", "sector", "stage", "last_funding_amount",
    "description", "investors",
]


def completeness_score(
    company: Dict[str, Any],
    fields: Optional[List[str]] = None,
) -> float:
    """Score how complete a record is (0.0 - 1.0).

    Uses *fields* when provided (from rubric["completeness_fields"]),
    falling back to the legacy startup-centric defaults.
    """
    check_fields = fields or _COMPLETENESS_FIELDS
    if not check_fields:
        return 0.0
    filled = 0
    for field in check_fields:
        val = company.get(field)
        if val is not None and val != "" and val != [] and val != 0:
            filled += 1
    return filled / len(check_fields)


def classify_enrichment_tier(
    company: Dict[str, Any],
    fields: Optional[List[str]] = None,
) -> str:
    """Classify what enrichment a record needs based on data completeness.

    *fields* should come from rubric["completeness_fields"] so that
    talent searches don't penalise missing funding data, etc.

    Returns:
        'skip'        — completeness >= 0.6, score with what we have
        'lightweight'  — completeness 0.3-0.6, 1 Tavily + 1 LLM fill gaps
        'full'         — completeness < 0.3, run full _execute_company_fetch
    """
    score = completeness_score(company, fields=fields)
    company["_completeness"] = round(score, 2)
    if score >= 0.6:
        return "skip"
    elif score >= 0.3:
        return "lightweight"
    else:
        return "full"


# ---------------------------------------------------------------------------
# Dedupe & merge — combine companies found across multiple search results
# ---------------------------------------------------------------------------

def _normalize_name(name: str) -> str:
    """Normalize a company name for dedup matching."""
    n = name.lower().strip()
    # Strip common suffixes
    for suffix in (", inc.", ", inc", " inc.", " inc", ", ltd", " ltd",
                   ", llc", " llc", " corp", " corporation", " co."):
        if n.endswith(suffix):
            n = n[: -len(suffix)].strip()
    return n


def merge_discovered_companies(companies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate and merge company records from multiple search results.

    Same company from a Tracxn list (name only) and a TechCrunch article
    (name + funding + investors) get merged into the most-complete record.
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for c in companies:
        key = _normalize_name(c.get("name", ""))
        if not key:
            continue
        groups.setdefault(key, []).append(c)

    merged = []
    for key, records in groups.items():
        if len(records) == 1:
            merged.append(records[0])
            continue

        # Sort by completeness descending — richest record is base
        records.sort(key=lambda r: completeness_score(r), reverse=True)
        base = dict(records[0])

        # Merge non-null fields from other records
        for other in records[1:]:
            for field, val in other.items():
                if field.startswith("_"):
                    continue
                existing = base.get(field)
                if (existing is None or existing == "" or existing == [] or existing == 0) and \
                   val is not None and val != "" and val != [] and val != 0:
                    base[field] = val

            # Collect all source URLs
            if other.get("source_url"):
                existing_urls = base.get("source_urls", [])
                if base.get("source_url") and base["source_url"] not in existing_urls:
                    existing_urls.append(base["source_url"])
                if other["source_url"] not in existing_urls:
                    existing_urls.append(other["source_url"])
                base["source_urls"] = existing_urls

        base["_merge_count"] = len(records)
        merged.append(base)

    return merged


def build_round2_adaptive_queries(
    rubric: Dict[str, Any],
    round1_results: List[Dict[str, Any]],
    round1_subcategories: List[str],
    existing_names: List[str],
    max_queries: int = 4,
) -> List[Dict[str, str]]:
    """Generate Round 2 queries targeting underrepresented subcategories.

    Analyzes Round 1 results to find which subcategories got poor coverage,
    then generates targeted queries for those gaps.
    """
    from datetime import datetime as _dt
    year = str(_dt.now().year)
    year_prev = str(_dt.now().year - 1)

    # Count results per subcategory from Round 1
    sub_counts: Dict[str, int] = {s: 0 for s in round1_subcategories}
    for company in round1_results:
        sub = company.get("_subcategory", company.get("sector", ""))
        for s in round1_subcategories:
            if s.lower() in sub.lower() or sub.lower() in s.lower():
                sub_counts[s] = sub_counts.get(s, 0) + 1
                break

    # Sort by count ascending — least-covered first
    underserved = sorted(sub_counts.items(), key=lambda x: x[1])

    entity_intent = rubric.get("intent", "dealflow")
    templates = _QUERY_TEMPLATES.get(entity_intent, {})
    target_stage = rubric.get("target_stage", "")
    sector = rubric.get("filters", {}).get("sector", "")

    tagged_queries: List[Dict[str, str]] = []

    for sub_name, count in underserved:
        if len(tagged_queries) >= max_queries:
            break

        vars_ = {
            "subcategory": sub_name,
            "year": year,
            "year_prev": year_prev,
            "target_stage": target_stage or "Series A",
            "sector": sector or sub_name,
        }

        # Use list_discovery for underserved subcategories
        list_templates = templates.get("list_discovery", _FALLBACK_TEMPLATES["list_discovery"])
        if list_templates:
            # Pick a different template than Round 1 used
            t = list_templates[min(1, len(list_templates) - 1)]
            tagged_queries.append({
                "query": t.format(**vars_),
                "intent": "list_discovery",
                "subcategory": sub_name,
            })

    # If we have room, add competitor queries from top Round 1 results
    if len(tagged_queries) < max_queries and existing_names:
        comp_templates = templates.get("competitor_map", [])
        if comp_templates:
            for name in existing_names[:2]:
                if len(tagged_queries) >= max_queries:
                    break
                tagged_queries.append({
                    "query": comp_templates[0].format(known_company=name),
                    "intent": "competitor_map",
                    "subcategory": name,
                })

    return tagged_queries[:max_queries]
