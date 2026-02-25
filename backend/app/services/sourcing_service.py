"""
Sourcing Service — Fast local query + scoring engine for companies.

No LLM, no web calls. Pure SQL + math.
Works on the existing companies table (1k+ rows from CSV imports, enrichments).
Results are ephemeral — returned inline to the agent, not persisted.

The LLM populates filters directly as structured JSON — no NL regex parsing.
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
