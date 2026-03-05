"""
FPA Query API Endpoints
Natural Language FP&A query processing
"""

from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, Form
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import logging
import time
import io
import csv
import re
from datetime import date, timedelta

from app.services.nl_fpa_parser import NLFPAParser
from app.services.fpa_query_classifier import FPAQueryClassifier
from app.services.fpa_workflow_builder import FPAWorkflowBuilder
from app.services.fpa_executor import FPAExecutor, ExecutorContext
from app.services.fpa_model_editor import FPAModelEditor
from app.services.fpa_regression_service import FPARegressionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fpa", tags=["fpa"])


# Request/Response models
class FPAQueryRequest(BaseModel):
    """Request for FPA query"""
    query: str = Field(..., description="Natural language query")
    fund_id: Optional[str] = None
    company_ids: Optional[list[str]] = None
    save_model: bool = False
    model_name: Optional[str] = None


class FPAModelRequest(BaseModel):
    """Request to create/update FPA model"""
    name: str
    model_type: str
    model_definition: Dict[str, Any]
    formulas: Dict[str, str]
    assumptions: Dict[str, Any]
    fund_id: Optional[str] = None


class FPARegressionRequest(BaseModel):
    """Request for regression analysis"""
    regression_type: str  # "linear" | "exponential" | "time_series" | "monte_carlo" | "sensitivity"
    data: Dict[str, Any]
    options: Optional[Dict[str, Any]] = None


class FPAForecastRequest(BaseModel):
    """Request for forecast generation"""
    company_id: Optional[str] = None
    base_data: Optional[Dict[str, Any]] = None
    forecast_periods: int = 24
    granularity: str = "monthly"  # "monthly" | "quarterly" | "annual"
    growth_rate: Optional[float] = None
    assumptions: Optional[Dict[str, Any]] = None


# Initialize services
nl_parser = NLFPAParser()
classifier = FPAQueryClassifier()
workflow_builder = FPAWorkflowBuilder()
executor = FPAExecutor()
model_editor = FPAModelEditor()
regression_service = FPARegressionService()


# ---------------------------------------------------------------------------
# P&L waterfall endpoint — assembles actuals + forecast into hierarchical rows
# ---------------------------------------------------------------------------


@router.get("/pnl")
async def get_pnl(
    company_id: Optional[str] = Query(None),
    fund_id: Optional[str] = Query(None),
    start: Optional[str] = Query(None, description="Start period YYYY-MM"),
    end: Optional[str] = Query(None, description="End period YYYY-MM"),
    months: int = Query(24, description="Forecast months"),
):
    """
    Fetch P&L data: actuals + forecast via PnlBuilder (single source of truth).
    Returns hierarchical rows for the matrix grid.
    """
    from app.services.pnl_builder import PnlBuilder

    try:
        if not company_id:
            return {"periods": [], "forecastStartIndex": 0, "rows": []}

        builder = PnlBuilder(company_id, fund_id=fund_id)
        return builder.build(start=start, end=end, forecast_months=months)

    except Exception as e:
        logger.error("Error fetching P&L: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class PnlCellEditRequest(BaseModel):
    """Manual cell edit → upsert into fpa_actuals."""
    company_id: str
    fund_id: Optional[str] = None
    category: str          # row id, e.g. "revenue", "cogs", "opex_rd"
    period: str            # column id, e.g. "2025-09"
    amount: float
    source: str = "manual_cell_edit"


@router.post("/pnl")
async def upsert_pnl_cell(req: PnlCellEditRequest):
    """Upsert a single P&L cell value into fpa_actuals (manual override)."""
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Normalize period to first-of-month date
    period_str = req.period.strip()
    if len(period_str) == 7:  # "2025-09"
        period_str = f"{period_str}-01"

    try:
        sb.table("fpa_actuals").upsert(
            {
                "company_id": req.company_id,
                "fund_id": req.fund_id,
                "period": period_str,
                "category": req.category,
                "amount": req.amount,
                "source": req.source,
            },
            on_conflict="company_id,period,category,source",
        ).execute()
    except Exception as e:
        logger.error("P&L cell upsert failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    return {"success": True, "category": req.category, "period": req.period, "amount": req.amount}


# ---------------------------------------------------------------------------
# Variance endpoint — compare actuals vs budget
# ---------------------------------------------------------------------------

@router.get("/variance")
async def get_variance(
    company_id: str = Query(..., description="Company ID"),
    budget_id: str = Query(..., description="Budget ID to compare against"),
    start: str = Query(..., description="Start period YYYY-MM"),
    end: str = Query(..., description="End period YYYY-MM"),
):
    """Compare actuals to budget. Returns per-category variance with status badges."""
    from app.services.budget_variance_service import get_variance_report
    from datetime import date as date_type

    try:
        period_start = date_type.fromisoformat(f"{start}-01")
        period_end = date_type.fromisoformat(f"{end}-01")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM.")

    try:
        results = get_variance_report(company_id, budget_id, period_start, period_end)
        return {"company_id": company_id, "budget_id": budget_id, "period": {"start": start, "end": end}, "variances": results}
    except Exception as e:
        logger.error("Variance report error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Budget creation endpoints
# ---------------------------------------------------------------------------

class BudgetCreateRequest(BaseModel):
    company_id: str
    fund_id: Optional[str] = None
    name: str
    fiscal_year: int
    status: str = "draft"


class BudgetLineItem(BaseModel):
    category: str
    subcategory: Optional[str] = None
    m1: float = 0
    m2: float = 0
    m3: float = 0
    m4: float = 0
    m5: float = 0
    m6: float = 0
    m7: float = 0
    m8: float = 0
    m9: float = 0
    m10: float = 0
    m11: float = 0
    m12: float = 0
    notes: Optional[str] = None


class BudgetLinesRequest(BaseModel):
    lines: List[BudgetLineItem]


@router.post("/budgets")
async def create_budget(req: BudgetCreateRequest):
    """Create a new budget. Returns the budget_id."""
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")

    result = sb.table("budgets").insert({
        "company_id": req.company_id,
        "fund_id": req.fund_id,
        "name": req.name,
        "fiscal_year": req.fiscal_year,
        "status": req.status,
    }).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create budget")

    return result.data[0]


@router.post("/budgets/{budget_id}/lines")
async def upsert_budget_lines(budget_id: str, req: BudgetLinesRequest):
    """Bulk create/update budget lines for a budget."""
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Verify budget exists
    budget = sb.table("budgets").select("id").eq("id", budget_id).execute()
    if not budget.data:
        raise HTTPException(status_code=404, detail="Budget not found")

    rows = [{"budget_id": budget_id, **line.model_dump()} for line in req.lines]
    result = sb.table("budget_lines").upsert(
        rows,
        on_conflict="budget_id,category",
    ).execute()

    return {"budget_id": budget_id, "lines_upserted": len(result.data or [])}


@router.get("/budgets")
async def list_budgets(
    company_id: str = Query(...),
    fiscal_year: Optional[int] = Query(None),
):
    """List budgets for a company, optionally filtered by fiscal year."""
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")

    query = sb.table("budgets").select("*").eq("company_id", company_id)
    if fiscal_year:
        query = query.eq("fiscal_year", fiscal_year)
    result = query.order("fiscal_year", desc=True).execute()

    return result.data or []


@router.get("/budgets/{budget_id}/lines")
async def get_budget_lines(budget_id: str):
    """Get all budget lines for a budget."""
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")

    result = sb.table("budget_lines").select("*").eq("budget_id", budget_id).execute()
    return result.data or []


# ---------------------------------------------------------------------------
# FPA CSV upload — P&L-style CSV with monthly columns → fpa_actuals
# ---------------------------------------------------------------------------

# Month header patterns: "Jan", "January", "2025-01", "Jan-25", "Jan 2025", "1/2025"
_MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4,
    "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}

# Category header patterns for row labels
_CATEGORY_PATTERNS: List[tuple] = [
    (re.compile(r"(?:total\s+)?revenue|sales|top\s*line", re.I), "revenue"),
    (re.compile(r"arr|annual\s*recurring", re.I), "arr"),
    (re.compile(r"mrr|monthly\s*recurring", re.I), "mrr"),
    (re.compile(r"co[gs]s|cost\s*of\s*(goods|sales|revenue)|direct\s*cost", re.I), "cogs"),
    (re.compile(r"r\s*&?\s*d|research|engineering", re.I), "opex_rd"),
    (re.compile(r"s\s*&?\s*m|sales\s*&?\s*market|marketing", re.I), "opex_sm"),
    (re.compile(r"g\s*&?\s*a|general\s*&?\s*admin|admin", re.I), "opex_ga"),
    (re.compile(r"(?:total\s+)?op(?:erating\s+)?ex|opex", re.I), "opex_total"),
    (re.compile(r"ebitda", re.I), "ebitda"),
    (re.compile(r"cash\s*(?:balance|in\s*bank)?|bank\s*balance", re.I), "cash_balance"),
    (re.compile(r"burn\s*rate|monthly\s*burn|net\s*burn", re.I), "burn_rate"),
    (re.compile(r"headcount|employees|fte|hc", re.I), "headcount"),
    (re.compile(r"customers?|clients?", re.I), "customers"),
    (re.compile(r"gross\s*profit|gp", re.I), "gross_profit"),
    (re.compile(r"net\s*(?:income|profit|loss)", re.I), "net_income"),
]


def _parse_month_header(header: str) -> Optional[str]:
    """Try to parse a column header as a month. Returns 'YYYY-MM' or None."""
    h = header.strip().lower()

    # "2025-01" or "2025-01-01"
    m = re.match(r"^(\d{4})-(\d{2})(?:-\d{2})?$", h)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # "Jan-25", "Jan 25", "Jan-2025", "Jan 2025"
    m = re.match(r"^([a-z]+)[\s\-](\d{2,4})$", h)
    if m:
        month_num = _MONTH_NAMES.get(m.group(1))
        if month_num:
            year = m.group(2)
            if len(year) == 2:
                year = f"20{year}"
            return f"{year}-{month_num:02d}"

    # "1/2025", "01/2025"
    m = re.match(r"^(\d{1,2})/(\d{4})$", h)
    if m:
        month_num = int(m.group(1))
        if 1 <= month_num <= 12:
            return f"{m.group(2)}-{month_num:02d}"

    # Bare month name with no year — skip (ambiguous)
    return None


def _match_category(label: str) -> Optional[str]:
    """Match a row label to an fpa_actuals category."""
    for pattern, category in _CATEGORY_PATTERNS:
        if pattern.search(label):
            return category
    return None


def _parse_amount(raw: str) -> Optional[float]:
    """Parse a cell value as a number, handling currency symbols, commas, parens, K/M/B."""
    if not raw:
        return None
    s = raw.strip()
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    s = re.sub(r"[$€£¥₹\s]", "", s)
    s = s.replace(",", "")
    m = re.match(r"^(-?[\d.]+)\s*([BMKbmk])?$", s)
    if not m:
        return None
    val = float(m.group(1))
    suffix = (m.group(2) or "").upper()
    if suffix == "B":
        val *= 1_000_000_000
    elif suffix == "M":
        val *= 1_000_000
    elif suffix == "K":
        val *= 1_000
    return -val if neg else val


@router.post("/upload-actuals")
async def upload_actuals_csv(
    company_id: str = Form(...),
    fund_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
):
    """
    Upload a P&L-style CSV and ingest into fpa_actuals.

    Accepts CSVs where:
    - Rows = categories (Revenue, COGS, OpEx, etc.)
    - Columns = months (Jan-25, 2025-01, Feb 2025, etc.)
    OR transposed (months as rows, categories as columns).

    Auto-detects orientation and maps headers to fpa_actuals categories.
    """
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")

    content = await file.read()
    text = content.decode("utf-8-sig")  # handle BOM
    reader = csv.reader(io.StringIO(text))
    all_rows = [row for row in reader if any(cell.strip() for cell in row)]

    if len(all_rows) < 2:
        raise HTTPException(status_code=400, detail="CSV needs at least a header row and one data row")

    headers = [h.strip() for h in all_rows[0]]
    data_rows = all_rows[1:]

    # Detect orientation: are column headers months or category labels?
    month_cols: Dict[int, str] = {}  # col_index → "YYYY-MM"
    for i, h in enumerate(headers):
        if i == 0:
            continue  # first column is typically the row label
        period = _parse_month_header(h)
        if period:
            month_cols[i] = period

    # Standard orientation: first col = category, other cols = months
    if len(month_cols) >= 2:
        actuals_rows = []
        mapped_categories = []
        unmapped_labels = []

        for row in data_rows:
            if not row or not row[0].strip():
                continue
            label = row[0].strip()
            category = _match_category(label)
            if not category:
                unmapped_labels.append(label)
                continue
            mapped_categories.append({"label": label, "category": category})

            for col_idx, period in month_cols.items():
                if col_idx >= len(row):
                    continue
                amount = _parse_amount(row[col_idx])
                if amount is None:
                    continue
                actuals_rows.append({
                    "company_id": company_id,
                    "fund_id": fund_id,
                    "period": f"{period}-01",
                    "category": category,
                    "amount": amount,
                    "source": "csv_upload",
                })
    else:
        # Try transposed: first col = month, other cols = categories
        cat_cols: Dict[int, str] = {}
        for i, h in enumerate(headers):
            if i == 0:
                continue
            cat = _match_category(h)
            if cat:
                cat_cols[i] = cat

        if len(cat_cols) < 2:
            raise HTTPException(
                status_code=400,
                detail="Could not detect month columns or category columns. "
                       "Expected either months as columns (Jan-25, 2025-01...) or categories as columns (Revenue, COGS...)."
            )

        actuals_rows = []
        mapped_categories = [{"label": headers[i], "category": c} for i, c in cat_cols.items()]
        unmapped_labels = []

        for row in data_rows:
            if not row or not row[0].strip():
                continue
            period = _parse_month_header(row[0].strip())
            if not period:
                unmapped_labels.append(row[0].strip())
                continue

            for col_idx, category in cat_cols.items():
                if col_idx >= len(row):
                    continue
                amount = _parse_amount(row[col_idx])
                if amount is None:
                    continue
                actuals_rows.append({
                    "company_id": company_id,
                    "fund_id": fund_id,
                    "period": f"{period}-01",
                    "category": category,
                    "amount": amount,
                    "source": "csv_upload",
                })

    if not actuals_rows:
        raise HTTPException(status_code=400, detail="No valid data rows found after parsing")

    # Upsert into fpa_actuals
    sb.table("fpa_actuals").upsert(
        actuals_rows,
        on_conflict="company_id,period,category,source",
    ).execute()

    periods = sorted(set(r["period"][:7] for r in actuals_rows))
    categories = sorted(set(r["category"] for r in actuals_rows))

    return {
        "ingested": len(actuals_rows),
        "periods": periods,
        "categories": categories,
        "mapped_categories": mapped_categories,
        "unmapped_labels": unmapped_labels,
    }


@router.post("/upload-budget")
async def upload_budget_csv(
    company_id: str = Form(...),
    fund_id: Optional[str] = Form(None),
    name: str = Form(...),
    fiscal_year: int = Form(...),
    file: UploadFile = File(...),
):
    """
    Upload a budget CSV and create budget + budget_lines.
    Same format as actuals CSV — months as columns, categories as rows.
    """
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Create budget first
    budget_result = sb.table("budgets").insert({
        "company_id": company_id,
        "fund_id": fund_id,
        "name": name,
        "fiscal_year": fiscal_year,
        "status": "draft",
    }).execute()

    if not budget_result.data:
        raise HTTPException(status_code=500, detail="Failed to create budget")

    budget_id = budget_result.data[0]["id"]

    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    all_rows = [row for row in reader if any(cell.strip() for cell in row)]

    if len(all_rows) < 2:
        raise HTTPException(status_code=400, detail="CSV needs at least a header row and one data row")

    headers = [h.strip() for h in all_rows[0]]
    data_rows = all_rows[1:]

    # Detect month columns
    month_cols: Dict[int, int] = {}  # col_index → month_number (1-12)
    for i, h in enumerate(headers):
        if i == 0:
            continue
        period = _parse_month_header(h)
        if period:
            month_num = int(period.split("-")[1])
            month_cols[i] = month_num

    if len(month_cols) < 2:
        raise HTTPException(status_code=400, detail="Could not detect month columns in headers")

    budget_lines = []
    unmapped = []
    for row in data_rows:
        if not row or not row[0].strip():
            continue
        label = row[0].strip()
        category = _match_category(label)
        if not category:
            unmapped.append(label)
            continue

        line: Dict[str, Any] = {"budget_id": budget_id, "category": category}
        for col_idx, month_num in month_cols.items():
            if col_idx >= len(row):
                continue
            amount = _parse_amount(row[col_idx])
            if amount is not None:
                line[f"m{month_num}"] = amount

        budget_lines.append(line)

    if budget_lines:
        sb.table("budget_lines").insert(budget_lines).execute()

    return {
        "budget_id": budget_id,
        "lines_created": len(budget_lines),
        "unmapped_labels": unmapped,
    }


# ---------------------------------------------------------------------------
# Rolling forecast endpoint
# ---------------------------------------------------------------------------

@router.get("/rolling-forecast")
async def get_rolling_forecast(
    company_id: str = Query(..., description="Company ID"),
    window: int = Query(24, description="Total window in months"),
    granularity: str = Query("monthly", description="monthly | quarterly | annual"),
):
    """
    Rolling actuals+forecast view. Actuals on the left, forecast on the right,
    clear boundary where forecast begins. Moves forward as new actuals arrive.
    """
    from app.services.rolling_forecast_service import RollingForecastService

    if granularity not in ("monthly", "quarterly", "annual"):
        raise HTTPException(status_code=400, detail="granularity must be monthly, quarterly, or annual")

    try:
        svc = RollingForecastService()
        result = svc.build_rolling_view(
            company_id=company_id,
            window_months=window,
            granularity=granularity,
        )
        if not result.get("rows"):
            raise HTTPException(
                status_code=400,
                detail="No actuals or forecast data available. Upload financials first.",
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Rolling forecast error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Scenario tree endpoints
# ---------------------------------------------------------------------------

class ScenarioBranchCreateRequest(BaseModel):
    company_id: str
    fund_id: Optional[str] = None
    parent_branch_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    fork_period: Optional[str] = None  # "YYYY-MM"
    assumptions: Dict[str, Any] = {}
    probability: Optional[float] = None


class ScenarioBranchPatchRequest(BaseModel):
    drivers: Optional[Dict[str, Any]] = None
    name: Optional[str] = None
    description: Optional[str] = None
    probability: Optional[float] = None
    forecast_months: int = 24


class ScenarioCompareRequest(BaseModel):
    company_id: str
    branch_ids: List[str]
    forecast_months: int = 24
    start_period: Optional[str] = None  # "YYYY-MM", defaults to current month


@router.post("/scenarios/branch")
async def create_scenario_branch(req: ScenarioBranchCreateRequest):
    """Create a scenario branch with assumption overrides."""
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")

    row: Dict[str, Any] = {
        "company_id": req.company_id,
        "fund_id": req.fund_id,
        "parent_branch_id": req.parent_branch_id,
        "name": req.name,
        "description": req.description,
        "assumptions": req.assumptions,
        "probability": req.probability,
    }
    if req.fork_period:
        try:
            row["fork_period"] = date.fromisoformat(f"{req.fork_period}-01").isoformat()
        except ValueError:
            raise HTTPException(status_code=400, detail="fork_period must be YYYY-MM")

    result = sb.table("scenario_branches").insert(row).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create scenario branch")

    return result.data[0]


@router.get("/scenarios/tree")
async def get_scenario_tree(
    company_id: str = Query(...),
    enrich: bool = Query(False),
    forecast_months: int = Query(12),
):
    """
    Get the scenario branch tree for a company.
    With enrich=true, includes computed metrics (revenue, EBITDA, cash, runway) per branch.
    """
    if enrich:
        from app.services.scenario_branch_service import ScenarioBranchService
        svc = ScenarioBranchService()
        return svc.get_enriched_tree(company_id, forecast_months)

    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")

    result = sb.table("scenario_branches").select("*").eq("company_id", company_id).order("created_at").execute()
    branches = result.data or []

    by_id = {b["id"]: {**b, "children": []} for b in branches}
    roots = []
    for b in branches:
        node = by_id[b["id"]]
        parent_id = b.get("parent_branch_id")
        if parent_id and parent_id in by_id:
            by_id[parent_id]["children"].append(node)
        else:
            roots.append(node)

    return {"company_id": company_id, "branches": roots}


@router.post("/scenarios/compare")
async def compare_scenarios(req: ScenarioCompareRequest):
    """
    Run fork-aware forecast for each branch with parent chain inheritance
    and return side-by-side comparison with deltas, expected-value forecast,
    and multi-branch charts.
    """
    from app.services.scenario_branch_service import ScenarioBranchService

    svc = ScenarioBranchService()
    result = svc.execute_comparison(
        company_id=req.company_id,
        branch_ids=req.branch_ids,
        forecast_months=req.forecast_months,
        start_period=req.start_period,
    )

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.delete("/scenarios/branch/{branch_id}")
async def delete_scenario_branch(branch_id: str):
    """Delete a scenario branch and ALL descendants recursively."""
    from app.services.scenario_branch_service import ScenarioBranchService

    svc = ScenarioBranchService()
    deleted = svc.delete_branch_recursive(branch_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Branch not found")

    return {"deleted": deleted}


# ---------------------------------------------------------------------------
# Driver Engine endpoints
# ---------------------------------------------------------------------------


@router.get("/drivers/registry")
async def get_driver_registry():
    """
    Full driver schema — the agent reads this to know what levers exist,
    their ranges, units, and ripple effects before constructing a scenario.
    """
    from app.services.driver_registry import get_registry_schema
    return {"drivers": get_registry_schema()}


@router.get("/scenarios/branch/{branch_id}/drivers")
async def get_branch_drivers(
    branch_id: str,
    company_id: str = Query(...),
):
    """
    Resolved driver state for a branch: base / override / effective for every driver.
    Includes computed unit-economics drivers (LTV, LTV:CAC).
    """
    from app.services.scenario_branch_service import ScenarioBranchService

    svc = ScenarioBranchService()
    result = svc.resolve_drivers(branch_id, company_id)

    if isinstance(result, dict) and "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return {"branch_id": branch_id, "drivers": result}


@router.patch("/scenarios/branch/{branch_id}")
async def patch_scenario_branch(branch_id: str, req: ScenarioBranchPatchRequest):
    """
    Update a branch via driver-format payload. Converts drivers → assumption keys,
    merges into existing assumptions, re-executes, and returns updated forecast
    plus resolved driver state.
    """
    from app.core.supabase_client import get_supabase_client
    from app.services.scenario_branch_service import ScenarioBranchService
    from app.services.driver_registry import drivers_to_assumptions
    import json as _json

    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Fetch existing branch
    row = sb.table("scenario_branches").select("*").eq("id", branch_id).execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="Branch not found")

    branch = row.data[0]
    company_id = branch["company_id"]

    # Merge driver values into existing assumptions
    existing = branch.get("assumptions") or {}
    if isinstance(existing, str):
        try:
            existing = _json.loads(existing)
        except (ValueError, TypeError):
            existing = {}

    if req.drivers:
        new_assumptions = drivers_to_assumptions(req.drivers)
        # Deep-merge opex_adjustments
        for k, v in new_assumptions.items():
            if isinstance(v, dict) and isinstance(existing.get(k), dict):
                existing[k].update(v)
            else:
                existing[k] = v

    # Update metadata fields
    updates: Dict[str, Any] = {"assumptions": _json.dumps(existing)}
    if req.name is not None:
        updates["name"] = req.name
    if req.description is not None:
        updates["description"] = req.description
    if req.probability is not None:
        updates["probability"] = req.probability

    sb.table("scenario_branches").update(updates).eq("id", branch_id).execute()

    # Re-execute
    svc = ScenarioBranchService()
    exec_result = svc.execute_branch(branch_id, company_id, req.forecast_months)
    if "error" in exec_result:
        raise HTTPException(status_code=400, detail=exec_result["error"])

    resolved = svc.resolve_drivers(branch_id, company_id)

    return {
        "branch_id": branch_id,
        "name": req.name or branch.get("name"),
        "assumptions": existing,
        "forecast": exec_result.get("forecast"),
        "base_forecast": exec_result.get("base_forecast"),
        "drivers": resolved,
    }


@router.post("/query")
async def process_fpa_query(request: FPAQueryRequest):
    """
    Process a natural language FP&A query

    Returns parsed query, workflow, results, and model structure
    """
    start_time = time.time()
    
    try:
        # Parse query
        parsed_query = nl_parser.parse(request.query)
        
        # Classify query
        handler = await classifier.route(parsed_query)
        
        # Build workflow
        workflow = workflow_builder.build(parsed_query, handler)
        
        # Execute workflow
        ctx = ExecutorContext(
            fund_id=request.fund_id,
            company_ids=request.company_ids,
            user_id=None  # TODO: Get from auth
        )
        
        execution_result = await executor.execute(workflow, ctx)
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        # Optionally save model
        model_id = None
        if request.save_model and request.model_name:
            model = await model_editor.create_model(
                name=request.model_name,
                model_type=handler,
                model_definition=parsed_query.dict(),
                formulas=execution_result["model_structure"]["formulas"],
                assumptions=execution_result["model_structure"]["assumptions"],
                created_by="user",  # TODO: Get from auth
                fund_id=request.fund_id
            )
            model_id = model.get("id")
        
        return {
            "parsed_query": parsed_query.dict(),
            "handler": handler,
            "workflow": [step.dict() for step in workflow],
            "results": execution_result["results"],
            "step_results": execution_result["step_results"],
            "model_structure": execution_result["model_structure"],
            "execution_time_ms": execution_time_ms,
            "model_id": model_id
        }
        
    except Exception as e:
        logger.error(f"Error processing FPA query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models")
async def create_fpa_model(request: FPAModelRequest):
    """Create a new FPA model"""
    try:
        model = await model_editor.create_model(
            name=request.name,
            model_type=request.model_type,
            model_definition=request.model_definition,
            formulas=request.formulas,
            assumptions=request.assumptions,
            created_by="user",  # TODO: Get from auth
            fund_id=request.fund_id
        )
        return model
    except Exception as e:
        logger.error(f"Error creating model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/{model_id}")
async def get_fpa_model(model_id: str):
    """Get an FPA model by ID"""
    try:
        model = await model_editor.get_model(model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        return model
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/models/{model_id}/formula")
async def update_model_formula(
    model_id: str,
    step_id: str,
    formula: str
):
    """Update a formula for a specific step"""
    try:
        result = await model_editor.update_formula(model_id, step_id, formula)
        return result
    except Exception as e:
        logger.error(f"Error updating formula: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/models/{model_id}/assumptions")
async def update_model_assumptions(
    model_id: str,
    assumptions: Dict[str, Any]
):
    """Update assumptions for a model"""
    try:
        result = await model_editor.update_assumptions(model_id, assumptions)
        return result
    except Exception as e:
        logger.error(f"Error updating assumptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/{model_id}/execute")
async def execute_model(model_id: str):
    """Re-run a model with current formulas/assumptions"""
    try:
        model = await model_editor.get_model(model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        # Rebuild workflow from model definition
        # TODO: Implement model re-execution
        return {"status": "executed", "model_id": model_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/regression")
async def run_regression(request: FPARegressionRequest):
    """Run regression analysis"""
    try:
        if request.regression_type == "linear":
            x = request.data.get("x", [])
            y = request.data.get("y", [])
            result = await regression_service.linear_regression(x, y)
        elif request.regression_type == "exponential":
            data = request.data.get("data", [])
            time_periods = request.data.get("time_periods", [])
            result = await regression_service.exponential_decay(data, time_periods)
        elif request.regression_type == "time_series":
            historical_data = request.data.get("historical_data", [])
            periods = request.options.get("periods", 12) if request.options else 12
            result = await regression_service.time_series_forecast(historical_data, periods)
        elif request.regression_type == "monte_carlo":
            base_scenario = request.data.get("base_scenario", {})
            distributions = request.data.get("distributions", {})
            iterations = request.options.get("iterations", 1000) if request.options else 1000
            result = await regression_service.monte_carlo_simulation(base_scenario, distributions, iterations)
        elif request.regression_type == "sensitivity":
            base_inputs = request.data.get("base_inputs", {})
            variable_ranges = request.data.get("variable_ranges", {})
            # TODO: Pass model function
            result = await regression_service.sensitivity_analysis(base_inputs, variable_ranges, None)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown regression type: {request.regression_type}")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running regression: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Forecast → budget_lines helper ────────────────────────────────────────

# Maps build_projection() output keys to budget_lines categories
_FORECAST_TO_BUDGET_CATEGORY = {
    "revenue": "revenue",
    "cogs": "cogs",
    "total_opex": "opex",
    "rd_spend": "opex_rd",
    "sm_spend": "opex_sm",
    "ga_spend": "opex_ga",
    "ebitda": "ebitda",
    "net_income": "net_income",
    "free_cash_flow": "free_cash_flow",
    "capex": "capex",
}


def _write_forecast_to_budget_lines(
    forecast: list[dict],
    granularity: str,
    company_id: str,
    fund_id: Optional[str] = None,
) -> list[str]:
    """
    Transpose monthly forecast rows into budget_lines format and upsert.
    One budget per company per fiscal year, auto-created if missing.
    Returns list of budget IDs written.
    """
    from app.core.supabase_client import get_supabase_client
    from collections import defaultdict

    sb = get_supabase_client()
    if not sb:
        return []

    # Only monthly granularity maps cleanly to m1..m12.
    # For quarterly/annual, we'd need to expand — skip for now.
    if granularity != "monthly":
        return []

    # Group forecast periods by fiscal year (calendar year from period string)
    by_year: dict[int, list[tuple[int, dict]]] = defaultdict(list)
    for row in forecast:
        period_str = row.get("period", "")
        # period is "YYYY-MM" or "YYYY-MM-DD"
        parts = period_str.split("-")
        if len(parts) < 2:
            continue
        year = int(parts[0])
        month = int(parts[1])
        by_year[year].append((month, row))

    budget_ids = []
    for fiscal_year, month_rows in by_year.items():
        # Find or create budget for this company + fiscal year
        existing = (
            sb.table("budgets")
            .select("id")
            .eq("company_id", company_id)
            .eq("fiscal_year", fiscal_year)
            .limit(1)
            .execute()
        )
        if existing.data:
            budget_id = existing.data[0]["id"]
        else:
            insert_row: dict = {
                "company_id": company_id,
                "name": f"Forecast {fiscal_year}",
                "fiscal_year": fiscal_year,
                "status": "forecast",
            }
            if fund_id:
                insert_row["fund_id"] = fund_id
            result = sb.table("budgets").insert(insert_row).execute()
            if not result.data:
                continue
            budget_id = result.data[0]["id"]

        # Transpose: for each P&L category, build {m1..m12} from monthly rows
        lines: list[dict] = []
        for forecast_key, budget_category in _FORECAST_TO_BUDGET_CATEGORY.items():
            line: dict = {"budget_id": budget_id, "category": budget_category}
            for month_num, row in month_rows:
                if 1 <= month_num <= 12:
                    line[f"m{month_num}"] = round(row.get(forecast_key, 0), 2)
            # Fill missing months with 0
            for m in range(1, 13):
                line.setdefault(f"m{m}", 0)
            lines.append(line)

        if lines:
            sb.table("budget_lines").upsert(
                lines, on_conflict="budget_id,category"
            ).execute()
            budget_ids.append(budget_id)

    return budget_ids


@router.post("/forecast")
async def generate_forecast(request: FPAForecastRequest):
    """
    Generate a forecast seeded from actuals (if company_id provided) or from
    explicit base_data. Returns a full P&L projection at the requested granularity.
    """
    from app.services.cash_flow_planning_service import CashFlowPlanningService
    from app.services.actuals_ingestion import seed_forecast_from_actuals

    try:
        # Seed company_data from actuals or use provided base_data
        if request.company_id:
            company_data = seed_forecast_from_actuals(request.company_id)
            if not company_data.get("revenue") and not (request.base_data or {}).get("revenue"):
                raise HTTPException(
                    status_code=400,
                    detail="No actuals found for this company. Upload financials first or provide base_data.",
                )
            # Merge explicit base_data on top (caller overrides)
            if request.base_data:
                company_data.update(request.base_data)
        elif request.base_data:
            company_data = request.base_data
        else:
            raise HTTPException(
                status_code=400,
                detail="Provide either company_id or base_data.",
            )

        # Apply explicit growth rate override
        if request.growth_rate is not None:
            company_data["growth_rate"] = request.growth_rate

        # Apply any assumption overrides (stage, gross_margin, burn_rate, etc.)
        if request.assumptions:
            company_data.update(request.assumptions)

        # Validate granularity
        if request.granularity not in ("monthly", "quarterly", "annual"):
            raise HTTPException(status_code=400, detail="granularity must be monthly, quarterly, or annual")

        svc = CashFlowPlanningService()
        forecast = svc.build_projection(
            company_data=company_data,
            granularity=request.granularity,
            horizon=request.forecast_periods,
            start_period=None,
        )

        # ── Write forecast into budget_lines ──────────────────────────
        # Transpose monthly P&L rows into budget_lines (one row per category
        # with m1..m12), grouped by fiscal year. Auto-creates the budget.
        budget_ids_written: list[str] = []
        if request.company_id and forecast:
            try:
                budget_ids_written = _write_forecast_to_budget_lines(
                    forecast=forecast,
                    granularity=request.granularity,
                    company_id=request.company_id,
                    fund_id=company_data.get("fund_id"),
                )
            except Exception as bl_err:
                logger.warning("budget_lines write-through failed: %s", bl_err)

        return {
            "forecast": forecast,
            "granularity": request.granularity,
            "periods": len(forecast),
            "budget_ids": budget_ids_written,
            "assumptions": {
                "revenue": company_data.get("revenue"),
                "growth_rate": company_data.get("growth_rate"),
                "burn_rate": company_data.get("burn_rate"),
                "cash_balance": company_data.get("cash_balance"),
                "stage": company_data.get("stage"),
                "gross_margin": company_data.get("gross_margin"),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating forecast: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
