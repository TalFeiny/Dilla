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

# Heavy NL/FPA services — lazy-loaded so the module always imports
# even if these optional dependencies are missing. The core PnL/upload
# endpoints don't need them.
_nl_parser = None
_classifier = None
_workflow_builder = None
_executor = None
_model_editor = None
_regression_service = None


def _get_nl_services():
    """Lazy-init NL FPA services on first use."""
    global _nl_parser, _classifier, _workflow_builder, _executor, _model_editor, _regression_service
    if _nl_parser is None:
        from app.services.nl_fpa_parser import NLFPAParser
        from app.services.fpa_query_classifier import FPAQueryClassifier
        from app.services.fpa_workflow_builder import FPAWorkflowBuilder
        from app.services.fpa_executor import FPAExecutor
        from app.services.fpa_model_editor import FPAModelEditor
        from app.services.fpa_regression_service import FPARegressionService
        _nl_parser = NLFPAParser()
        _classifier = FPAQueryClassifier()
        _workflow_builder = FPAWorkflowBuilder()
        _executor = FPAExecutor()
        _model_editor = FPAModelEditor()
        _regression_service = FPARegressionService()
    return _nl_parser, _classifier, _workflow_builder, _executor, _model_editor, _regression_service


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
    branch_name: Optional[str] = None        # custom branch name (auto-generated if None)
    parent_branch_id: Optional[str] = None   # fork from existing branch


class FPAForecastRequest(BaseModel):
    """Request for forecast generation"""
    company_id: Optional[str] = None
    base_data: Optional[Dict[str, Any]] = None
    forecast_periods: int = 24
    granularity: str = "monthly"  # "monthly" | "quarterly" | "annual"
    growth_rate: Optional[float] = None
    assumptions: Optional[Dict[str, Any]] = None


# Services are lazy-loaded via _get_nl_services() — see top of file


# ---------------------------------------------------------------------------
# Persistence helper — every FPA compute endpoint calls this so results
# land on a scenario branch (and optionally the grid when it's empty).
# Errors are swallowed so persistence never breaks the endpoint.
# ---------------------------------------------------------------------------

def _persist_fpa_output(
    company_id: str,
    analysis_type: str,
    assumptions: Dict[str, Any],
    *,
    branch_name: Optional[str] = None,
    parent_branch_id: Optional[str] = None,
    trajectory: Optional[List[Dict[str, Any]]] = None,
    periods: Optional[List[str]] = None,
    summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Persist FPA output to branch + grid (if empty). Never raises."""
    try:
        from app.services.analysis_persistence_service import AnalysisPersistenceService
        aps = AnalysisPersistenceService()
        return aps.persist_analysis_result(
            company_id=company_id,
            analysis_type=analysis_type,
            assumptions=assumptions,
            branch_name=branch_name,
            parent_branch_id=parent_branch_id,
            trajectory=trajectory,
            periods=periods,
            summary=summary,
        )
    except Exception as e:
        logger.warning("FPA persistence failed (%s): %s", analysis_type, e)
        return {}


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
        builder = PnlBuilder(company_id=company_id, fund_id=fund_id)
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
    subcategory: str = ""
    hierarchy_path: str = ""
    source: str = "manual_cell_edit"


class BulkPnlWriteRequest(BaseModel):
    """Batch cell writes — used by agents, CSV ingest, forecast apply."""
    cells: List[PnlCellEditRequest] = Field(..., min_length=1, max_length=5000)


def _normalize_cell_row(cell: PnlCellEditRequest) -> dict:
    """Normalize a single cell edit into an fpa_actuals row."""
    period_str = cell.period.strip()
    if len(period_str) == 7:
        period_str = f"{period_str}-01"
    hierarchy_path = cell.hierarchy_path or (
        f"{cell.category}/{cell.subcategory}" if cell.subcategory else cell.category
    )
    return {
        "company_id": cell.company_id,
        "fund_id": cell.fund_id,
        "period": period_str,
        "category": cell.category,
        "subcategory": cell.subcategory,
        "hierarchy_path": hierarchy_path,
        "amount": cell.amount,
        "source": cell.source,
    }


@router.post("/pnl")
async def upsert_pnl_cell(req: PnlCellEditRequest):
    """Upsert a single P&L cell value into fpa_actuals (manual override)."""
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")

    row = _normalize_cell_row(req)

    try:
        sb.table("fpa_actuals").upsert(
            row,
            on_conflict="company_id,period,category,subcategory,hierarchy_path,source",
        ).execute()
    except Exception as e:
        logger.error("P&L cell upsert failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    return {"success": True, "category": req.category, "period": req.period, "amount": req.amount}


@router.post("/pnl/bulk")
async def bulk_upsert_pnl_cells(req: BulkPnlWriteRequest):
    """Batch upsert up to 5000 cells into fpa_actuals in one call.

    Used by: agents (CFO, portfolio, sourcing), CSV ingest, forecast apply.
    Chunks into 500-row batches for Supabase.
    Returns grid_commands so the frontend can update the grid in one pass.
    """
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")

    rows = [_normalize_cell_row(c) for c in req.cells]

    try:
        # Batch upsert in 500-row chunks
        for i in range(0, len(rows), 500):
            chunk = rows[i:i + 500]
            sb.table("fpa_actuals").upsert(
                chunk,
                on_conflict="company_id,period,category,subcategory,hierarchy_path,source",
            ).execute()
    except Exception as e:
        logger.error("Bulk P&L upsert failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    # Build grid_commands so frontend can update without re-fetching
    grid_commands = []
    for row in rows:
        grid_commands.append({
            "action": "edit",
            "company_id": row["company_id"],
            "field": row["category"],
            "period": row["period"][:7],
            "value": row["amount"],
            "source": row["source"],
        })

    periods = sorted(set(r["period"][:7] for r in rows))
    categories = sorted(set(r["category"] for r in rows))
    companies = sorted(set(r["company_id"] for r in rows))

    return {
        "success": True,
        "rows_written": len(rows),
        "companies": companies,
        "periods": periods,
        "categories": categories,
        "grid_commands": grid_commands,
    }


# ---------------------------------------------------------------------------
# Balance Sheet endpoint — assembles bs_* actuals into hierarchical rows
# ---------------------------------------------------------------------------


@router.get("/balance-sheet")
async def get_balance_sheet(
    company_id: Optional[str] = Query(None),
    start: Optional[str] = Query(None, description="Start period YYYY-MM"),
    end: Optional[str] = Query(None, description="End period YYYY-MM"),
):
    """
    Fetch Balance Sheet data via BalanceSheetBuilder.
    Returns hierarchical rows (assets / liabilities / equity) with computed totals
    and balance check.
    """
    from app.services.balance_sheet_builder import BalanceSheetBuilder

    try:
        builder = BalanceSheetBuilder(company_id=company_id)
        return builder.build(start=start, end=end)

    except Exception as e:
        logger.error("Error fetching Balance Sheet: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/balance-sheet")
async def upsert_bs_cell(req: PnlCellEditRequest):
    """Upsert a single Balance Sheet cell value into fpa_actuals."""
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")

    if not req.category.startswith("bs_"):
        raise HTTPException(status_code=400, detail="Balance sheet categories must start with 'bs_'")

    row = _normalize_cell_row(req)

    try:
        sb.table("fpa_actuals").upsert(
            row,
            on_conflict="company_id,period,category,subcategory,hierarchy_path,source",
        ).execute()
    except Exception as e:
        logger.error("BS cell upsert failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    return {"success": True, "category": req.category, "period": req.period, "amount": req.amount}


# ---------------------------------------------------------------------------
# Cash Flow endpoint — assembles CF actuals + derived rows
# ---------------------------------------------------------------------------


@router.get("/cash-flow")
async def get_cash_flow(
    company_id: Optional[str] = Query(None),
    start: Optional[str] = Query(None, description="Start period YYYY-MM"),
    end: Optional[str] = Query(None, description="End period YYYY-MM"),
):
    """
    Fetch Cash Flow data via CashFlowBuilder.
    Returns hierarchical rows (operating / investing / financing / position)
    with derived FCF, burn rate, and runway.
    """
    from app.services.cash_flow_builder import CashFlowBuilder

    try:
        builder = CashFlowBuilder(company_id=company_id)
        return builder.build(start=start, end=end)

    except Exception as e:
        logger.error("Error fetching Cash Flow: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Metrics endpoint — computes KPIs from latest actuals
# ---------------------------------------------------------------------------


@router.get("/metrics")
async def get_metrics(
    company_id: str = Query(..., description="Company ID"),
):
    """
    Compute key metrics from fpa_actuals for a company.
    Returns latest-period KPIs with trends and severity indicators.
    """
    from app.services.company_data_pull import pull_company_data

    try:
        data = pull_company_data(company_id)
        if not data.time_series:
            return {"metrics": []}

        def lp(cat: str) -> tuple:
            return data.category_latest_and_prev(cat)

        def trend(curr: float, previous: float) -> str:
            if curr > previous:
                return "up"
            if curr < previous:
                return "down"
            return "flat"

        def trend_pct(curr: float, previous: float) -> float:
            if previous == 0:
                return 0
            return (curr - previous) / abs(previous)

        metrics = []

        # Revenue
        rev, rev_prev = lp("revenue")
        if rev != 0:
            metrics.append({
                "id": "revenue",
                "label": "Revenue",
                "value": rev,
                "unit": "currency",
                "trend": trend(rev, rev_prev),
                "trendValue": round(trend_pct(rev, rev_prev), 4),
                "severity": "green" if rev > rev_prev else "amber",
            })

        # EBITDA
        ebitda_val, ebitda_prev = lp("ebitda")
        if ebitda_val != 0 or "ebitda" in data.time_series:
            metrics.append({
                "id": "ebitda",
                "label": "EBITDA",
                "value": ebitda_val,
                "unit": "currency",
                "trend": trend(ebitda_val, ebitda_prev),
                "trendValue": round(trend_pct(ebitda_val, ebitda_prev), 4),
                "severity": "green" if ebitda_val >= 0 else "red",
            })

        # EBITDA Margin
        if rev != 0:
            margin = ebitda_val / rev
            metrics.append({
                "id": "ebitda_margin",
                "label": "EBITDA Margin",
                "value": round(margin, 4),
                "unit": "percentage",
                "severity": "green" if margin > 0.2 else "amber" if margin > 0 else "red",
            })

        # Gross Margin
        cogs_val, _ = lp("cogs")
        if rev != 0 and (cogs_val != 0 or "cogs" in data.time_series):
            gm = (rev - abs(cogs_val)) / rev
            metrics.append({
                "id": "gross_margin",
                "label": "Gross Margin",
                "value": round(gm, 4),
                "unit": "percentage",
                "severity": "green" if gm > 0.5 else "amber" if gm > 0.3 else "red",
            })

        # Cash Balance
        cash_val, _ = lp("cash_balance")
        if not cash_val:
            cash_val, _ = lp("bs_cash")
        cash = cash_val
        if cash != 0:
            metrics.append({
                "id": "cash",
                "label": "Cash Balance",
                "value": cash,
                "unit": "currency",
                "severity": "green" if cash > 0 else "red",
            })

        # Net Burn
        burn, _ = lp("net_burn_rate")
        if burn == 0 and ebitda_val < 0:
            burn = abs(ebitda_val)
        if burn != 0:
            metrics.append({
                "id": "net_burn",
                "label": "Net Burn",
                "value": burn,
                "unit": "currency",
                "severity": "amber" if burn > 0 else "green",
            })

        # Runway
        if cash > 0 and burn > 0:
            runway = cash / burn
            metrics.append({
                "id": "runway",
                "label": "Runway",
                "value": round(runway, 1),
                "unit": "months",
                "severity": "green" if runway > 12 else "amber" if runway > 6 else "red",
            })

        # OpEx breakdown
        opex_rd, _ = lp("opex_rd")
        opex_sm, _ = lp("opex_sm")
        opex_ga, _ = lp("opex_ga")
        total_opex = abs(opex_rd) + abs(opex_sm) + abs(opex_ga)
        if total_opex > 0 and rev != 0:
            metrics.append({
                "id": "opex_ratio",
                "label": "OpEx / Revenue",
                "value": round(total_opex / rev, 4),
                "unit": "percentage",
                "severity": "green" if total_opex / rev < 0.8 else "amber" if total_opex / rev < 1.0 else "red",
            })

        # Persist metrics snapshot to branch
        persist = _persist_fpa_output(
            company_id=company_id,
            analysis_type="metrics_snapshot",
            assumptions={"source": "fpa_actuals"},
            summary={"metrics": metrics},
            branch_name="Metrics Snapshot",
        )

        return {"metrics": metrics, "_persistence": persist}

    except Exception as e:
        logger.error("Error computing metrics: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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

        # Persist variance report to branch
        persist = _persist_fpa_output(
            company_id=company_id,
            analysis_type="budget_variance",
            assumptions={
                "budget_id": budget_id,
                "period_start": start,
                "period_end": end,
            },
            summary=results,
            branch_name=f"Variance {start} – {end}",
        )

        return {
            "company_id": company_id,
            "budget_id": budget_id,
            "period": {"start": start, "end": end},
            "variances": results,
            "_persistence": persist,
        }
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
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4,
    "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}

# Category header patterns for row labels
# Order matters: more specific patterns first to avoid false matches
_CATEGORY_PATTERNS: List[tuple] = [
    # Recurring revenue (before general revenue)
    (re.compile(r"arr|annual\s*recurring", re.I), "arr"),
    (re.compile(r"mrr|monthly\s*recurring", re.I), "mrr"),
    # COGS (before revenue — "Cost of Sales" must not match "sales" → revenue)
    (re.compile(r"co[gs]s|cost\s*of\s*(?:goods|sales|revenue)|direct\s*cost", re.I), "cogs"),
    # Revenue
    (re.compile(r"(?:total\s+)?revenue|(?:total\s+)?sales(?!\s*&?\s*m)|top\s*line|turnover|gross\s*revenue", re.I), "revenue"),
    (re.compile(r"other\s*income|non.?operating\s*income|interest\s*income|sundry\s*income", re.I), "other_income"),
    # OpEx subcategories (before opex_total to avoid swallowing them)
    (re.compile(r"r\s*&?\s*d|research|engineering|product\s*development|technology", re.I), "opex_rd"),
    (re.compile(r"s\s*&?\s*m|sales\s*(?:&|and)\s*market|marketing|advertising|commercial", re.I), "opex_sm"),
    (re.compile(r"g\s*&?\s*a|general\s*(?:&|and)\s*admin|admin(?:istrative)?", re.I), "opex_ga"),
    (re.compile(r"payroll|salaries|wages|compensation|personnel|staff\s*costs?|people\s*costs?", re.I), "opex_ga"),
    (re.compile(r"establishment\s*costs?|premises|rent|occupancy", re.I), "opex_ga"),
    # OpEx total
    (re.compile(r"(?:total\s+)?op(?:erating\s+)?ex|opex|overheads?|indirect\s*costs?", re.I), "opex_total"),
    # Computed / P&L waterfall
    (re.compile(r"gross\s*profit|gp", re.I), "gross_profit"),
    (re.compile(r"ebitda", re.I), "ebitda"),
    (re.compile(r"operating\s*(?:income|profit|loss)", re.I), "operating_income"),
    (re.compile(r"depreciation|amortization|d\s*&?\s*a", re.I), "depreciation"),
    (re.compile(r"interest\s*expense|finance\s*costs?|debt\s*service", re.I), "interest_expense"),
    (re.compile(r"profit\s*before\s*tax|pbt|earnings\s*before\s*tax|ebt", re.I), "ebt"),
    (re.compile(r"(?:income\s*)?tax(?:es)?|corporation\s*tax|provision\s*for\s*tax", re.I), "tax"),
    (re.compile(r"net\s*(?:income|profit|loss)|profit\s*after\s*tax|pat|earnings\s*after\s*tax", re.I), "net_income"),
    # Operational
    (re.compile(r"cash\s*(?:balance|in\s*bank)?|bank\s*balance", re.I), "cash_balance"),
    (re.compile(r"burn\s*rate|monthly\s*burn|net\s*burn", re.I), "burn_rate"),
    (re.compile(r"headcount|employees|fte|hc", re.I), "headcount"),
    (re.compile(r"customers?|clients?", re.I), "customers"),
    # ---- Balance Sheet categories ----
    # Current Assets
    (re.compile(r"cash\s*(?:&|and)\s*cash\s*equiv|cash\s*at\s*bank|petty\s*cash|checking|savings", re.I), "bs_cash"),
    (re.compile(r"(?:accounts?\s*)?receiv|trade\s*debtors?|debtors?|sundry\s*debtors?", re.I), "bs_receivables"),
    (re.compile(r"other\s*receiv|other\s*debtors?|employee\s*advances?|intercompany\s*receiv", re.I), "bs_other_receivables"),
    (re.compile(r"prepay|prepaid\s*exp|accrued\s*(?:income|revenue)", re.I), "bs_prepayments"),
    (re.compile(r"inventor|stock(?:\s*on\s*hand)?|raw\s*materials?|work\s*in\s*progress|finished\s*goods|merchandise", re.I), "bs_inventory"),
    (re.compile(r"short[\s-]*term\s*invest|marketable\s*securities|current\s*investments?", re.I), "bs_st_investments"),
    (re.compile(r"(?:tax|vat|gst|income\s*tax|corporation\s*tax)\s*receiv|input\s*tax", re.I), "bs_tax_receivable"),
    # Non-Current Assets
    (re.compile(r"property[\s,]*plant|pp\s*&?\s*e|fixed\s*assets?|land\s*(?:&|and)\s*build|plant\s*(?:&|and)\s*machin|furniture|motor\s*vehic|computer\s*equip|office\s*equip|leasehold\s*improv|accumulated\s*deprec", re.I), "bs_ppe"),
    (re.compile(r"intangible|goodwill|patent|trademark|capitalised?\s*(?:dev|software)|intellectual\s*prop|accumulated\s*amortiz", re.I), "bs_intangibles"),
    (re.compile(r"right[\s-]*of[\s-]*use|rou\s*assets?|operating\s*lease\s*assets?", re.I), "bs_rou_assets"),
    (re.compile(r"long[\s-]*term\s*invest|invest(?:ments?)?\s*in\s*(?:subsidiar|associat)|equity\s*method", re.I), "bs_lt_investments"),
    (re.compile(r"deferred\s*tax\s*asset", re.I), "bs_deferred_tax_asset"),
    # Current Liabilities
    (re.compile(r"(?:accounts?\s*)?payab|trade\s*creditors?|creditors?|sundry\s*creditors?", re.I), "bs_payables"),
    (re.compile(r"accrued\s*(?:exp|liabilit)|accruals?|wages?\s*payab|salaries?\s*payab", re.I), "bs_accrued_expenses"),
    (re.compile(r"short[\s-]*term\s*(?:debt|borrow)|bank\s*overdraft|revolving\s*credit|line\s*of\s*credit|credit\s*line", re.I), "bs_st_debt"),
    (re.compile(r"current\s*(?:portion|maturit)", re.I), "bs_current_ltd"),
    (re.compile(r"deferred\s*revenue|unearned\s*(?:revenue|income)|contract\s*liabilit|customer\s*deposits?|prepaid\s*revenue", re.I), "bs_deferred_revenue"),
    (re.compile(r"(?:tax|vat|gst|income\s*tax|corporation\s*tax|payroll\s*tax|sales\s*tax)\s*payab|output\s*tax", re.I), "bs_tax_payable"),
    (re.compile(r"interest\s*payab|accrued\s*interest", re.I), "bs_interest_payable"),
    (re.compile(r"dividends?\s*payab", re.I), "bs_dividends_payable"),
    # Non-Current Liabilities
    (re.compile(r"long[\s-]*term\s*(?:debt|borrow)|term\s*loans?|bonds?\s*payab|notes?\s*payab|mortgage", re.I), "bs_lt_debt"),
    (re.compile(r"convertible\s*(?:note|debt|loan)|safe(?:\s*notes?)?", re.I), "bs_convertible_notes"),
    (re.compile(r"lease\s*liabilit|finance\s*lease|operating\s*lease\s*liabilit", re.I), "bs_lease_liabilities"),
    (re.compile(r"deferred\s*tax\s*liabilit", re.I), "bs_deferred_tax_liability"),
    (re.compile(r"provisions?|warranty\s*provision|legal\s*provision|restructuring\s*provision|contingent\s*liabilit", re.I), "bs_provisions"),
    (re.compile(r"pension|retirement\s*benefit|post[\s-]*employment|defined\s*benefit\s*obligation", re.I), "bs_pension"),
    # Equity
    (re.compile(r"share\s*capital|common\s*stock|ordinary\s*shares?|issued\s*capital|paid[\s-]*up\s*capital", re.I), "bs_share_capital"),
    (re.compile(r"additional\s*paid[\s-]*in|share\s*premium|capital\s*surplus|paid[\s-]*in\s*capital\s*in\s*excess", re.I), "bs_apic"),
    (re.compile(r"retained\s*earnings?|accumulated\s*profits?|retained\s*profits?|profit\s*(?:&|and)\s*loss\s*reserve", re.I), "bs_retained_earnings"),
    (re.compile(r"current\s*(?:year|period)\s*earnings?|profit\s*for\s*the\s*period", re.I), "bs_current_pnl"),
    (re.compile(r"other\s*comprehensive|revaluation\s*reserve|foreign\s*currency\s*translat|hedging\s*reserve", re.I), "bs_oci"),
    (re.compile(r"treasury\s*(?:stock|shares?)|own\s*shares?", re.I), "bs_treasury_stock"),
    (re.compile(r"(?:non[\s-]*)?controlling\s*interest|minority\s*interest", re.I), "bs_minority_interest"),
]


def _clean_header(raw: str) -> str:
    """Strip parenthetical suffixes and noise from a column header."""
    h = raw.strip()
    # Remove trailing parenthetical: (Est.), (Actual), (Budget), (Forecast)
    h = re.sub(r"\s*\((?:Est\.?|Actual|Budget|Forecast|Projected|Plan)\)\s*$", "", h, flags=re.I)
    # Remove period after abbreviated month names: "Jan." → "Jan", "Sept." → "Sept"
    h = re.sub(r"^([A-Za-z]{3,5})\.\s*", r"\1 ", h)
    return h.strip()


def _parse_period_header(header: str) -> Optional[List[tuple]]:
    """Parse a column header as period(s). Returns list of (period, divisor) or None.

    Monthly:   [("2025-01", 1)]
    Quarterly: [("2026-01", 3), ("2026-02", 3), ("2026-03", 3)]
    Annual:    [("2025-01", 12), ..., ("2025-12", 12)]
    """
    h = _clean_header(header).lower()

    # "2025-01" or "2025-01-01"
    m = re.match(r"^(\d{4})-(\d{2})(?:-\d{2})?$", h)
    if m:
        return [(f"{m.group(1)}-{m.group(2)}", 1)]

    # "Jan-25", "Jan 25", "Jan-2025", "Jan 2025"
    m = re.match(r"^([a-z]+)[\s\-](\d{2,4})$", h)
    if m:
        month_num = _MONTH_NAMES.get(m.group(1))
        if month_num:
            year = m.group(2)
            if len(year) == 2:
                year = f"20{year}"
            return [(f"{year}-{month_num:02d}", 1)]

    # "1/2025", "01/2025"
    m = re.match(r"^(\d{1,2})/(\d{4})$", h)
    if m:
        month_num = int(m.group(1))
        if 1 <= month_num <= 12:
            return [(f"{m.group(2)}-{month_num:02d}", 1)]

    # "01-2025", "1-2025" (digit-month with dash)
    m = re.match(r"^(\d{1,2})-(\d{4})$", h)
    if m:
        month_num = int(m.group(1))
        if 1 <= month_num <= 12:
            return [(f"{m.group(2)}-{month_num:02d}", 1)]

    # "01/01/2025", "1/1/2025" (MM/DD/YYYY — use month only)
    m = re.match(r"^(\d{1,2})/\d{1,2}/(\d{4})$", h)
    if m:
        month_num = int(m.group(1))
        if 1 <= month_num <= 12:
            return [(f"{m.group(2)}-{month_num:02d}", 1)]

    # Quarterly: "Q1 2026", "Q4-2025", "q2 26"
    m = re.match(r"^q([1-4])[\s\-](\d{2,4})$", h)
    if m:
        q = int(m.group(1))
        year = m.group(2)
        if len(year) == 2:
            year = f"20{year}"
        start_month = (q - 1) * 3 + 1
        return [(f"{year}-{start_month + i:02d}", 3) for i in range(3)]

    # Half-year: "H1 2026", "H2-2025"
    m = re.match(r"^h([12])[\s\-](\d{2,4})$", h)
    if m:
        half = int(m.group(1))
        year = m.group(2)
        if len(year) == 2:
            year = f"20{year}"
        start_month = 1 if half == 1 else 7
        return [(f"{year}-{start_month + i:02d}", 6) for i in range(6)]

    # Annual: "FY2025", "FY 2025", "FY25"
    m = re.match(r"^fy\s?(\d{2,4})$", h)
    if m:
        year = m.group(1)
        if len(year) == 2:
            year = f"20{year}"
        return [(f"{year}-{i:02d}", 12) for i in range(1, 13)]

    # Bare year: "2025"
    m = re.match(r"^(\d{4})$", h)
    if m:
        year = m.group(1)
        yr = int(year)
        if 2000 <= yr <= 2099:
            return [(f"{year}-{i:02d}", 12) for i in range(1, 13)]

    # Month range: "January - March 2025", "Jan-Mar 2025"
    m = re.match(r"^([a-z]+)\s*[\-–]\s*([a-z]+)\s+(\d{4})$", h)
    if m:
        start = _MONTH_NAMES.get(m.group(1))
        end = _MONTH_NAMES.get(m.group(2))
        year = m.group(3)
        if start and end and end >= start:
            count = end - start + 1
            return [(f"{year}-{start + i:02d}", count) for i in range(count)]

    return None


def _parse_month_only(header: str) -> Optional[int]:
    """Parse a bare month name with no year (e.g. 'January', 'Feb', 'Sept').
    Returns month number (1-12) or None."""
    h = _clean_header(header).lower().strip()
    return _MONTH_NAMES.get(h)


def _infer_year_for_month_headers(headers: List[str], period_cols: Dict[int, List[tuple]]) -> Dict[int, List[tuple]]:
    """Fallback: if regular _parse_period_header found very few columns but many
    headers are bare month names, infer the year from any successfully parsed column
    or default to the current year.

    This handles CSVs like: Category | January | February | March | ...
    """
    from datetime import date

    # Count how many non-first headers are bare month names
    month_only_cols: Dict[int, int] = {}  # col_index → month_num
    for i, h in enumerate(headers):
        if i == 0:
            continue
        if i in period_cols:
            continue  # already detected
        mn = _parse_month_only(h)
        if mn:
            month_only_cols[i] = mn

    # Only apply if month-only columns outnumber already-detected period columns
    if not month_only_cols or len(month_only_cols) <= len(period_cols):
        return period_cols

    # Infer year: from an already-detected period column, or current year
    inferred_year = str(date.today().year)
    for tuples in period_cols.values():
        if tuples:
            inferred_year = tuples[0][0][:4]
            break

    logger.info(
        "[upload-actuals] Inferred year %s for %d bare month-name headers: %s",
        inferred_year, len(month_only_cols),
        {i: headers[i] for i in month_only_cols},
    )

    # Merge month-only columns into period_cols
    merged = dict(period_cols)
    for col_idx, mn in month_only_cols.items():
        merged[col_idx] = [(f"{inferred_year}-{mn:02d}", 1)]
    return merged


def _parse_month_header(header: str) -> Optional[str]:
    """Backward-compatible wrapper: returns single 'YYYY-MM' or None."""
    result = _parse_period_header(header)
    if result and len(result) == 1 and result[0][1] == 1:
        return result[0][0]
    return None


def _match_category(label: str) -> Optional[str]:
    """Match a row label to an fpa_actuals category."""
    for pattern, category in _CATEGORY_PATTERNS:
        if pattern.search(label):
            return category
    return None


# --- Label cleaning & hierarchy detection ---

_NOISE_PREFIXES = re.compile(
    r"^(?:total|less|plus|sub[\-\s]?total|subtotal)\s+", re.I
)
# Noise words that are safe to strip (not "net" — needed for "Net Income")
_NOISE_SUFFIXES = re.compile(
    r"\s+(?:total|amount|balance)$", re.I
)


def _clean_label(raw: str) -> tuple:
    """Clean a row label for matching. Returns (cleaned_label, indent_depth, original_stripped)."""
    stripped = raw.rstrip()
    leading = len(stripped) - len(stripped.lstrip())
    stripped = stripped.strip()
    # Normalize indent: 2-4 spaces or 1 tab = depth 1
    depth = 0
    if leading > 0:
        raw_prefix = raw[:leading]
        if "\t" in raw_prefix:
            depth = raw_prefix.count("\t")
        else:
            depth = max(1, leading // 2)

    original = stripped

    # Strip parenthetical suffixes for matching, but keep for subcategory naming
    # "Cost of Goods Sold (COGS)" → "Cost of Goods Sold"
    cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", stripped)

    # Strip noise prefixes: "Total Revenue" → "Revenue", "Less Cost of Sales" → "Cost of Sales"
    cleaned = _NOISE_PREFIXES.sub("", cleaned)
    cleaned = _NOISE_SUFFIXES.sub("", cleaned)

    # Normalize slashes and extra whitespace
    cleaned = re.sub(r"\s*/\s*", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned, depth, original


# ---------------------------------------------------------------------------
# ERP hierarchy detection helpers
# ---------------------------------------------------------------------------

_ACCOUNT_COL_NAMES = {"account", "account_number", "account_no", "acct", "acct_no", "account_id"}
_PARENT_COL_NAMES = {"parent_account", "parent_id", "parent_account_id", "parent_acct"}
_LEVEL_COL_NAMES = {"level", "depth", "indent_level", "hierarchy_level"}
_LABEL_COL_NAMES = {"name", "label", "description", "account_name", "line_item"}
_SUBCATEGORY_COL_NAMES = {"subcategory", "sub_category", "sub-category", "line_item", "detail",
                           "sub", "item", "description", "memo"}
_CATEGORY_COL_NAMES = {"category", "type", "account_type", "group", "section"}


def _detect_hierarchy_columns(headers: List[str]) -> Dict[str, Any]:
    """Scan CSV headers to detect ERP hierarchy strategy.

    Precedence: explicit_subcategory > parent_id > level_column > account_number > indent (default).
    """
    lower_headers = [h.lower().strip() for h in headers]
    result: Dict[str, Any] = {"strategy": "indent"}

    account_col = None
    parent_col = None
    level_col = None
    label_col = 0  # default to first column
    subcategory_col = None
    category_col = None

    for i, h in enumerate(lower_headers):
        if h in _ACCOUNT_COL_NAMES:
            account_col = i
        elif h in _PARENT_COL_NAMES:
            parent_col = i
        elif h in _LEVEL_COL_NAMES:
            level_col = i
        elif h in _CATEGORY_COL_NAMES:
            category_col = i
        elif h in _SUBCATEGORY_COL_NAMES and subcategory_col is None:
            subcategory_col = i
        elif h in _LABEL_COL_NAMES:
            label_col = i

    # Explicit Category + Subcategory columns (e.g. "Category, Subcategory, Jan-25, ...")
    # This is highest priority — the CSV explicitly names the relationship.
    if category_col is not None and subcategory_col is not None:
        result = {"strategy": "explicit_subcategory", "category_col": category_col,
                  "subcategory_col": subcategory_col, "label_col": category_col}
        logger.info("[upload-actuals] Detected explicit Category/Subcategory columns: cat=%d, sub=%d", category_col, subcategory_col)
    elif parent_col is not None and account_col is not None:
        result = {"strategy": "parent_id", "account_col": account_col,
                  "parent_col": parent_col, "label_col": label_col}
    elif level_col is not None:
        result = {"strategy": "level_column", "level_col": level_col,
                  "label_col": label_col}
    elif account_col is not None:
        result = {"strategy": "account_number", "account_col": account_col,
                  "label_col": label_col}

    return result


def _build_account_number_tree(
    data_rows: List[List[str]], account_col: int, label_col: int
) -> Dict[int, int]:
    """Derive depth per row from account number hierarchy (e.g. 4000→4100→4110).

    Returns {row_index: depth}.
    """
    account_numbers: List[Optional[str]] = []
    for row in data_rows:
        val = row[account_col].strip() if account_col < len(row) else ""
        account_numbers.append(val if val else None)

    # Build set of known account numbers
    known = {a for a in account_numbers if a}

    row_depth: Dict[int, int] = {}
    for idx, acct in enumerate(account_numbers):
        if not acct:
            row_depth[idx] = 0
            continue
        # Walk up by trimming trailing characters until we find a parent
        depth = 0
        candidate = acct
        while len(candidate) > 1:
            candidate = candidate[:-1]
            # Trim trailing zeros for cleaner matching (4100 → 41 → 4)
            trimmed = candidate.rstrip("0") or candidate
            if trimmed in known or candidate in known:
                depth += 1
                # Keep walking up from trimmed
                candidate = trimmed if trimmed in known else candidate
            # Also check padded variants
        row_depth[idx] = depth

    return row_depth


def _build_parent_id_tree(
    data_rows: List[List[str]], account_col: int, parent_col: int
) -> Dict[int, int]:
    """Derive depth per row from explicit parent-ID column.

    Returns {row_index: depth}.
    """
    # Map account_id → row_index
    id_to_idx: Dict[str, int] = {}
    parent_map: Dict[str, str] = {}  # account_id → parent_id

    for idx, row in enumerate(data_rows):
        acct = row[account_col].strip() if account_col < len(row) else ""
        par = row[parent_col].strip() if parent_col < len(row) else ""
        if acct:
            id_to_idx[acct] = idx
            if par:
                parent_map[acct] = par

    row_depth: Dict[int, int] = {}
    for idx, row in enumerate(data_rows):
        acct = row[account_col].strip() if account_col < len(row) else ""
        if not acct:
            row_depth[idx] = 0
            continue
        # Walk parent chain to compute depth (max 10, cycle-safe)
        depth = 0
        current = acct
        visited: set = set()
        while current in parent_map and depth < 10:
            if current in visited:
                break  # cycle
            visited.add(current)
            current = parent_map[current]
            depth += 1
        row_depth[idx] = depth

    return row_depth


def _build_level_column_map(
    data_rows: List[List[str]], level_col: int
) -> Dict[int, int]:
    """Read depth directly from a level/depth column.

    Returns {row_index: depth}.
    """
    row_depth: Dict[int, int] = {}
    for idx, row in enumerate(data_rows):
        val = row[level_col].strip() if level_col < len(row) else "0"
        try:
            row_depth[idx] = int(val)
        except ValueError:
            row_depth[idx] = 0
    return row_depth


def _is_separator_row(row: list) -> bool:
    """Skip rows that are formatting separators (---, ===, blank)."""
    return all(re.match(r"^[\s\-=_]*$", cell) for cell in row)


# Computed rows that should be skipped when their component rows are present
_COMPUTED_DEPENDENCIES = {
    "gross_profit": [{"revenue", "cogs"}],
    "ebitda": [
        {"revenue", "cogs", "opex_total"},
        {"revenue", "cogs", "opex_rd", "opex_sm", "opex_ga"},
    ],
    "operating_income": [
        {"revenue", "cogs", "opex_total"},
        {"revenue", "cogs", "opex_rd", "opex_sm", "opex_ga"},
    ],
    "net_income": [{"revenue", "cogs"}],  # skip if any expense categories present
}


def _should_skip_computed(category: str, present_categories: set) -> bool:
    """Check if a computed row should be skipped because its components are present."""
    dep_sets = _COMPUTED_DEPENDENCIES.get(category)
    if not dep_sets:
        return False
    return any(deps.issubset(present_categories) for deps in dep_sets)


# --- Fuzzy category fallback ---

from difflib import SequenceMatcher

_CATEGORY_SYNONYMS = {
    "revenue": ["revenue", "sales", "income", "turnover", "top line", "gross revenue"],
    "cogs": ["cost of goods sold", "cost of sales", "direct costs", "cogs", "cost of revenue"],
    "opex_rd": ["research and development", "r&d", "engineering", "product development", "technology"],
    "opex_sm": ["sales and marketing", "s&m", "marketing", "commercial", "advertising"],
    "opex_ga": ["general and administrative", "g&a", "admin", "overhead", "payroll",
                "salaries", "wages", "compensation", "personnel", "staff costs",
                "finance legal", "office", "rent", "occupancy", "establishment costs",
                "premises", "insurance"],
    "opex_total": ["operating expenses", "opex", "total expenses", "overheads", "indirect costs"],
    "ebitda": ["ebitda", "operating income", "operating profit"],
    "gross_profit": ["gross profit", "gross margin"],
    "net_income": ["net income", "net profit", "net loss", "profit after tax", "pat",
                   "earnings after tax", "bottom line"],
    "depreciation": ["depreciation", "amortization", "d&a", "deprec"],
    "interest_expense": ["interest expense", "finance costs", "debt service"],
    "tax": ["tax", "income tax", "corporation tax", "provision for tax"],
    "other_income": ["other income", "non operating income", "interest income", "sundry income"],
    "ebt": ["profit before tax", "pbt", "earnings before tax", "ebt"],
    "cash_balance": ["cash balance", "cash in bank", "bank balance", "cash"],
    "burn_rate": ["burn rate", "monthly burn", "net burn"],
    "headcount": ["headcount", "employees", "fte", "head count"],
    "customers": ["customers", "clients"],
    "arr": ["arr", "annual recurring revenue"],
    "mrr": ["mrr", "monthly recurring revenue"],
    # Balance Sheet fuzzy synonyms
    "bs_cash": ["cash", "cash and cash equivalents", "bank", "bank accounts", "petty cash"],
    "bs_receivables": ["accounts receivable", "trade debtors", "debtors", "trade receivables"],
    "bs_inventory": ["inventory", "stock", "stock on hand", "raw materials", "finished goods"],
    "bs_ppe": ["property plant and equipment", "fixed assets", "pp&e"],
    "bs_intangibles": ["intangible assets", "goodwill", "patents", "software"],
    "bs_payables": ["accounts payable", "trade creditors", "creditors", "trade payables"],
    "bs_accrued_expenses": ["accrued expenses", "accrued liabilities", "accruals"],
    "bs_deferred_revenue": ["deferred revenue", "unearned revenue", "contract liabilities"],
    "bs_lt_debt": ["long term debt", "term loans", "bonds payable", "notes payable"],
    "bs_convertible_notes": ["convertible notes", "convertible debt", "safe", "safe notes"],
    "bs_lease_liabilities": ["lease liabilities", "finance lease", "operating lease liability"],
    "bs_share_capital": ["share capital", "common stock", "ordinary shares", "issued capital"],
    "bs_apic": ["additional paid in capital", "share premium", "capital surplus"],
    "bs_retained_earnings": ["retained earnings", "accumulated profits", "retained profits"],
    "bs_treasury_stock": ["treasury stock", "treasury shares", "own shares"],
    "bs_minority_interest": ["minority interest", "non controlling interest"],
}


def _fuzzy_match_category(label: str, threshold: float = 0.65) -> Optional[tuple]:
    """Fuzzy match a row label to a category. Returns (category, score) or None."""
    label_lower = label.lower().strip()
    best_score = 0.0
    best_category = None

    for category, synonyms in _CATEGORY_SYNONYMS.items():
        for synonym in synonyms:
            score = SequenceMatcher(None, label_lower, synonym).ratio()
            # Boost if one contains the other
            if label_lower in synonym or synonym in label_lower:
                score = max(score, 0.85)
            if score > best_score:
                best_score = score
                best_category = category

    if best_score >= threshold and best_category:
        return (best_category, round(best_score, 2))
    return None


def _label_to_subcategory(label: str, business_model: str = "saas") -> str:
    """Map a label to a subcategory using business-model-aware taxonomy.

    Tries the classifier first; falls back to snake_case normalization.
    """
    try:
        from app.services.actuals_ingestion import classify_label_to_subcategory
        _cat, sub = classify_label_to_subcategory(label, business_model)
        if sub:
            return sub
    except Exception:
        pass
    # Fallback: normalize to snake_case
    s = label.lower().strip()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", "_", s).strip("_")
    return s


# --- Section header detection for hierarchy ---

_SECTION_HEADER_PATTERNS = [
    (re.compile(r"^(?:total\s+)?(?:revenue|income|sales)$", re.I), "revenue"),
    (re.compile(r"^(?:cost\s+of\s+(?:goods\s+)?(?:sold|sales)|cogs|direct\s+costs?)$", re.I), "cogs"),
    (re.compile(r"^(?:(?:less\s+)?operating\s+expenses?|opex|overheads?)$", re.I), "opex_total"),
    (re.compile(r"^(?:r\s*&?\s*d|research\s*(?:&|and)\s*development)$", re.I), "opex_rd"),
    (re.compile(r"^(?:s\s*&?\s*m|sales\s*(?:&|and)\s*marketing)$", re.I), "opex_sm"),
    (re.compile(r"^(?:g\s*&?\s*a|general\s*(?:&|and)\s*admin(?:istrative)?)$", re.I), "opex_ga"),
    # Operational metrics section
    (re.compile(r"^key\s*metrics?|^operational\s*metrics?|^kpis?$", re.I), "headcount"),
    # Balance Sheet section headers
    (re.compile(r"^(?:current\s+)?assets$", re.I), "bs_cash"),
    (re.compile(r"^non[\s-]*current\s+assets?$", re.I), "bs_ppe"),
    (re.compile(r"^(?:current\s+)?liabilities$", re.I), "bs_payables"),
    (re.compile(r"^non[\s-]*current\s+liabilities$", re.I), "bs_lt_debt"),
    (re.compile(r"^equity|^shareholders?\s*equity|^stockholders?\s*equity|^owners?\s*equity$", re.I), "bs_share_capital"),
]

# Map section header categories to the parent category for child rows
_SECTION_TO_PARENT = {
    "revenue": "revenue",
    "cogs": "cogs",
    "opex_total": "opex_total",
    "opex_rd": "opex_rd",
    "opex_sm": "opex_sm",
    "opex_ga": "opex_ga",
    # Operational metrics
    "headcount": "headcount",
    # BS sections — child rows under these headers inherit the parent
    "bs_cash": "bs_cash",
    "bs_ppe": "bs_ppe",
    "bs_payables": "bs_payables",
    "bs_lt_debt": "bs_lt_debt",
    "bs_share_capital": "bs_share_capital",
}


def _parse_amount(raw: str) -> Optional[float]:
    """Parse a cell value as a number, handling currency, commas, parens, K/M/B/bn/mm, European notation."""
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None

    # Skip percentage values in P&L context
    if s.endswith("%"):
        return None

    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]

    # Strip currency symbols and whitespace
    s = re.sub(r"[$€£¥₹\s]", "", s)

    # Detect European notation: "1.234.567,89" or "1.234,56"
    # Pattern: dots as thousand separators + comma as decimal
    if re.match(r"^-?[\d.]+,\d{1,2}$", s):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")

    # Match number with optional suffix
    m = re.match(r"^(-?[\d.]+)\s*(bn|mm|[BMKbmk])?$", s, re.I)
    if not m:
        return None
    val = float(m.group(1))
    suffix = (m.group(2) or "").lower()
    if suffix in ("b", "bn"):
        val *= 1_000_000_000
    elif suffix in ("m", "mm"):
        val *= 1_000_000
    elif suffix == "k":
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

    ERP-agnostic 3-pass pipeline:
      Pass 1: Scan all rows — detect hierarchy, match categories, identify skippable rows
      Pass 2: Determine which computed rows to skip (only if dependencies present)
      Pass 3: Extract amounts, build actuals_rows with subcategory support

    Supports: monthly/quarterly/annual/half-year periods, indented subcategories,
    separator row exclusion, computed row dedup, fuzzy category matching.

    State-tracked: creates an fpa_upload_jobs record that transitions through
    pending → processing → completed/failed so failures are never a black box.
    """
    from app.core.supabase_client import get_supabase_client
    from datetime import datetime

    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # --- Create upload job record (pending) ---
    job_payload = {
        "company_id": company_id,
        "fund_id": fund_id,
        "source": "csv_upload",
        "file_name": file.filename,
        "file_size": file.size,
        "status": "pending",
        "step": "validating",
        "message": "Upload received, validating file",
    }
    job_row = sb.table("fpa_upload_jobs").insert(job_payload).execute()
    job_id = job_row.data[0]["id"] if job_row.data else None

    def _update_job(updates: dict):
        """Update the job record with current step/status."""
        if not job_id:
            return
        try:
            sb.table("fpa_upload_jobs").update(updates).eq("id", job_id).execute()
        except Exception as ue:
            logger.warning(f"[upload-actuals] Failed to update job {job_id}: {ue}")

    try:
        # Transition: pending → processing
        _update_job({
            "status": "processing",
            "started_at": datetime.utcnow().isoformat(),
            "step": "validating",
            "message": "Reading and validating CSV",
        })

        content = await file.read()
        text = content.decode("utf-8-sig")  # handle BOM
        reader = csv.reader(io.StringIO(text))
        all_rows = [row for row in reader if any(cell.strip() for cell in row)]

        if len(all_rows) < 2:
            _update_job({
                "status": "failed",
                "step": "validating",
                "error": "CSV needs at least a header row and one data row",
                "completed_at": datetime.utcnow().isoformat(),
            })
            raise HTTPException(status_code=400, detail="CSV needs at least a header row and one data row")

        headers = [h.strip() for h in all_rows[0]]
        data_rows = all_rows[1:]

        _update_job({"step": "parsing_headers", "message": f"Parsing {len(headers)} columns, {len(data_rows)} rows"})

        # --- Detect orientation & parse period columns ---
        # Try standard: col headers are periods
        period_cols: Dict[int, List[tuple]] = {}  # col_index → [(period, divisor), ...]
        for i, h in enumerate(headers):
            if i == 0:
                continue
            periods = _parse_period_header(h)
            if periods:
                period_cols[i] = periods

        # Fallback: if only 0-1 period columns detected, check for bare month names
        # (e.g. "January", "Feb") and infer year from context
        period_cols = _infer_year_for_month_headers(headers, period_cols)

        # --- Remove redundant aggregate columns (FY/quarterly) when monthly data exists ---
        # If we have monthly columns (divisor=1) for specific periods, drop any
        # annual/quarterly columns (divisor>1) whose periods overlap — they would
        # overwrite the precise monthly values with averaged totals in dedup.
        monthly_periods = set()
        for tuples in period_cols.values():
            for period, divisor in tuples:
                if divisor == 1:
                    monthly_periods.add(period)

        if monthly_periods:
            cols_to_remove = []
            for col_idx, tuples in period_cols.items():
                if any(d > 1 for _, d in tuples):
                    # This is an aggregate column — check if its periods overlap with monthly
                    expanded = {p for p, _ in tuples}
                    if expanded & monthly_periods:
                        cols_to_remove.append(col_idx)
                        logger.info(
                            "[upload-actuals] Dropping aggregate column %d (%s) — "
                            "monthly columns already cover %d of its %d periods",
                            col_idx, headers[col_idx] if col_idx < len(headers) else f"col{col_idx}",
                            len(expanded & monthly_periods), len(expanded),
                        )
            for col_idx in cols_to_remove:
                del period_cols[col_idx]
                warnings.append(f"Skipped aggregate column '{headers[col_idx]}' — monthly data takes priority")

        is_transposed = False
        cat_cols: Dict[int, str] = {}

        if not period_cols:
            # Try transposed: col headers are categories, row[0] is the period
            for i, h in enumerate(headers):
                if i == 0:
                    continue
                cat = _match_category(h)
                if cat:
                    cat_cols[i] = cat
            if not cat_cols:
                err = ("Could not detect period columns or category columns. "
                       "Expected either periods as columns (Jan-25, Q1 2026, FY2025...) "
                       "or categories as columns (Revenue, COGS...).")
                _update_job({
                    "status": "failed",
                    "step": "parsing_headers",
                    "error": err,
                    "completed_at": datetime.utcnow().isoformat(),
                })
                raise HTTPException(status_code=400, detail=err)
            is_transposed = True

        # Log period detection for debugging
        if not is_transposed:
            undetected = [
                (i, headers[i]) for i in range(1, len(headers))
                if i not in period_cols
            ]
            logger.info(
                "[upload-actuals] Period columns detected (%d/%d): %s",
                len(period_cols), len(headers) - 1,
                {col_idx: [(p, d) for p, d in tuples] for col_idx, tuples in period_cols.items()},
            )
            if undetected:
                logger.warning(
                    "[upload-actuals] Undetected headers (not parsed as periods): %s",
                    undetected,
                )
        else:
            logger.info("[upload-actuals] Orientation: transposed")
        logger.info("[upload-actuals] Headers: %s", headers)

        _update_job({"step": "detecting_categories", "message": f"Detected {'transposed' if is_transposed else 'standard'} orientation"})

        # --- Tracking for detailed response ---
        mapped_categories = []
        unmapped_labels = []
        warnings = []
        skipped_separators = 0
        skipped_computed = []
        skipped_empty = 0
        subcategories_created = []

        if is_transposed:
            # Transposed: simple path — no hierarchy detection needed
            mapped_categories = [{"label": headers[i], "category": c, "match": "regex"} for i, c in cat_cols.items()]
            actuals_rows = []

            for row in data_rows:
                if not row or not row[0].strip():
                    skipped_empty += 1
                    continue
                if _is_separator_row(row):
                    skipped_separators += 1
                    continue
                periods = _parse_period_header(row[0].strip())
                if not periods:
                    unmapped_labels.append(row[0].strip())
                    continue

                for col_idx, category in cat_cols.items():
                    if col_idx >= len(row):
                        continue
                    amount = _parse_amount(row[col_idx])
                    if amount is None:
                        continue
                    for period, divisor in periods:
                        actuals_rows.append({
                            "company_id": company_id,
                            "fund_id": fund_id,
                            "period": f"{period}-01",
                            "category": category,
                            "subcategory": "",
                            "hierarchy_path": category,
                            "amount": amount / divisor,
                            "source": "csv_upload",
                        })

            if divisor_used := any(d > 1 for ps in [_parse_period_header(row[0].strip()) or [] for row in data_rows] for _, d in ps):
                warnings.append("Quarterly/annual amounts divided evenly across constituent months")

        else:
            # Standard orientation: 3-pass pipeline

            # --- Detect ERP hierarchy strategy ---
            hierarchy_info = _detect_hierarchy_columns(headers)
            row_depth_map: Dict[int, int] = {}

            if hierarchy_info["strategy"] == "account_number":
                row_depth_map = _build_account_number_tree(
                    data_rows, hierarchy_info["account_col"], hierarchy_info.get("label_col", 0)
                )
            elif hierarchy_info["strategy"] == "parent_id":
                row_depth_map = _build_parent_id_tree(
                    data_rows, hierarchy_info["account_col"], hierarchy_info["parent_col"]
                )
            elif hierarchy_info["strategy"] == "level_column":
                row_depth_map = _build_level_column_map(
                    data_rows, hierarchy_info["level_col"]
                )

            if hierarchy_info["strategy"] != "indent":
                warnings.append(f"Detected ERP hierarchy format: {hierarchy_info['strategy']}")

            # Look up company's business model for taxonomy-aware classification
            _biz_model = "saas"
            try:
                _co = sb.table("companies").select("category").eq("id", company_id).limit(1).execute()
                if _co.data and _co.data[0].get("category"):
                    _biz_model = _co.data[0]["category"]
            except Exception:
                pass

            # =============================================
            # PASS 1: Scan all rows — build category + hierarchy map
            # =============================================
            row_info = []
            current_section_parent = None
            is_explicit_subcategory = hierarchy_info["strategy"] == "explicit_subcategory"

            for idx_row, row in enumerate(data_rows):
                if not row:
                    row_info.append({"skip": "empty"})
                    skipped_empty += 1
                    continue

                if _is_separator_row(row):
                    row_info.append({"skip": "separator"})
                    skipped_separators += 1
                    continue

                # --- Explicit Subcategory strategy ---
                # CSV has named Category + Subcategory columns (e.g. "Revenue", "DOE Grants")
                if is_explicit_subcategory:
                    cat_col_idx = hierarchy_info["category_col"]
                    sub_col_idx = hierarchy_info["subcategory_col"]
                    raw_cat = row[cat_col_idx].strip() if cat_col_idx < len(row) else ""
                    raw_sub = row[sub_col_idx].strip() if sub_col_idx < len(row) else ""

                    if not raw_cat:
                        row_info.append({"skip": "empty"})
                        skipped_empty += 1
                        continue

                    has_amounts = any(
                        _parse_amount(row[ci]) is not None
                        for ci in period_cols
                        if ci < len(row)
                    )

                    cleaned_cat, _, original_cat = _clean_label(raw_cat)

                    # Match the category column against known P&L categories
                    # (No unconditional skip — Pass 2 handles computed row dedup
                    # conditionally. Rows like Gross Profit, Net Loss are real metrics.)
                    cat = _match_category(cleaned_cat) or _match_category(original_cat)
                    if not cat:
                        fuzzy = _fuzzy_match_category(cleaned_cat)
                        if fuzzy:
                            cat = fuzzy[0]
                            warnings.append(f"Fuzzy-matched '{original_cat}' → {cat} (score: {fuzzy[1]})")
                        elif current_section_parent:
                            # Category like "Other" doesn't match directly but section
                            # header "Other Income / (Expense)" set current_section_parent
                            cat = current_section_parent
                        else:
                            row_info.append({"skip": "unmapped", "raw_label": raw_cat})
                            unmapped_labels.append(f"{raw_cat}: {raw_sub}" if raw_sub else raw_cat)
                            continue

                    # Determine subcategory — use the explicit column value
                    sub_name = raw_sub if raw_sub else None
                    depth = 1 if sub_name else 0

                    # Section header: category with no subcategory and no amounts
                    is_section_hdr = (not sub_name and not has_amounts)

                    # Track section context for child rows
                    if is_section_hdr:
                        current_section_parent = cat
                    elif not sub_name:
                        # Standalone metric row (Gross Profit, Net Loss, etc.) — reset section
                        if cat in _SECTION_TO_PARENT:
                            current_section_parent = _SECTION_TO_PARENT[cat]
                        else:
                            current_section_parent = None

                    # Build hierarchy_path directly for explicit subcategory rows
                    if sub_name:
                        h_path = f"{cat}/{sub_name}"
                    else:
                        h_path = cat

                    info = {
                        "skip": None,
                        "raw_label": raw_cat,
                        "cleaned": cleaned_cat,
                        "depth": depth,
                        "original": f"{original_cat}: {raw_sub}" if raw_sub else original_cat,
                        "category": cat if not is_section_hdr else None,
                        "subcategory": sub_name,
                        "match_type": "explicit_subcategory" if sub_name else "regex",
                        "is_section_header": is_section_hdr,
                        "has_amounts": has_amounts,
                        "hierarchy_path": h_path if not is_section_hdr else "",
                    }

                    if sub_name and sub_name not in subcategories_created:
                        subcategories_created.append(sub_name)
                    if not is_section_hdr:
                        mapped_categories.append({
                            "label": f"{raw_cat} / {raw_sub}" if raw_sub else raw_cat,
                            "category": cat,
                            "match": "explicit_subcategory",
                            **({"subcategory": sub_name} if sub_name else {}),
                        })

                    row_info.append(info)
                    continue

                # --- Non-explicit strategies (indent, account_number, etc.) ---
                label_col_idx = hierarchy_info.get("label_col", 0) if hierarchy_info["strategy"] != "indent" else 0
                raw_label = row[label_col_idx] if label_col_idx < len(row) else (row[0] if row else "")
                if not raw_label.strip():
                    row_info.append({"skip": "empty"})
                    skipped_empty += 1
                    continue

                if hierarchy_info["strategy"] != "indent":
                    depth = row_depth_map.get(idx_row, 0)
                    cleaned, _, original = _clean_label(raw_label)
                else:
                    cleaned, depth, original = _clean_label(raw_label)

                has_amounts = any(
                    _parse_amount(row[ci]) is not None
                    for ci in period_cols
                    if ci < len(row)
                )

                info = {
                    "skip": None,
                    "raw_label": raw_label,
                    "cleaned": cleaned,
                    "depth": depth,
                    "original": original,
                    "category": None,
                    "subcategory": None,
                    "match_type": None,
                    "is_section_header": False,
                    "has_amounts": has_amounts,
                }

                if depth == 0:
                    cat = _match_category(cleaned)
                    if cat:
                        info["category"] = cat
                        info["match_type"] = "regex"
                        current_section_parent = _SECTION_TO_PARENT.get(cat)
                        if not has_amounts and cat in _SECTION_TO_PARENT:
                            info["is_section_header"] = True
                    else:
                        cat = _match_category(original)
                        if cat:
                            info["category"] = cat
                            info["match_type"] = "regex"
                            current_section_parent = _SECTION_TO_PARENT.get(cat)
                            if not has_amounts and cat in _SECTION_TO_PARENT:
                                info["is_section_header"] = True
                        else:
                            for pat, sec_cat in _SECTION_HEADER_PATTERNS:
                                if pat.search(cleaned):
                                    info["is_section_header"] = True
                                    current_section_parent = _SECTION_TO_PARENT.get(sec_cat, sec_cat)
                                    break

                            if not info["is_section_header"]:
                                fuzzy = _fuzzy_match_category(cleaned)
                                if fuzzy:
                                    info["category"] = fuzzy[0]
                                    info["match_type"] = f"fuzzy ({fuzzy[1]})"
                                    warnings.append(f"Fuzzy-matched '{original}' → {fuzzy[0]} (score: {fuzzy[1]})")
                                    current_section_parent = _SECTION_TO_PARENT.get(fuzzy[0])
                                else:
                                    info["skip"] = "unmapped"
                                    unmapped_labels.append(original)

                else:
                    cat = _match_category(cleaned)
                    if cat and cat != current_section_parent:
                        info["category"] = cat
                        info["match_type"] = "regex"
                    elif cat and cat == current_section_parent:
                        sub_name = _label_to_subcategory(original, _biz_model)
                        if sub_name:
                            info["category"] = cat
                            info["subcategory"] = sub_name
                            info["match_type"] = "hierarchy"
                            if sub_name not in subcategories_created:
                                subcategories_created.append(sub_name)
                        else:
                            info["category"] = cat
                            info["match_type"] = "regex"
                    else:
                        fuzzy = _fuzzy_match_category(cleaned)
                        if fuzzy and fuzzy[0] != current_section_parent:
                            info["category"] = fuzzy[0]
                            info["match_type"] = f"fuzzy ({fuzzy[1]})"
                            warnings.append(f"Fuzzy-matched '{original}' → {fuzzy[0]} (score: {fuzzy[1]})")
                        elif current_section_parent:
                            sub_name = _label_to_subcategory(original, _biz_model)
                            if sub_name:
                                info["category"] = current_section_parent
                                info["subcategory"] = sub_name
                                info["match_type"] = "hierarchy"
                                if sub_name not in subcategories_created:
                                    subcategories_created.append(sub_name)
                        else:
                            info["skip"] = "unmapped"
                            unmapped_labels.append(original)

                row_info.append(info)

            # =============================================
            # PASS 1.5: Build hierarchy_path for each row using path stack
            # (Skipped for rows that already have hierarchy_path set, e.g. explicit_subcategory)
            # =============================================
            path_stack: List[tuple] = []
            for ri in row_info:
                if ri.get("hierarchy_path"):
                    continue  # already set (e.g. explicit_subcategory strategy)
                if ri.get("skip"):
                    ri["hierarchy_path"] = ""
                    continue
                if ri.get("is_section_header"):
                    path_stack = []
                    ri["hierarchy_path"] = ""
                    continue

                depth = ri.get("depth", 0)
                segment = ri.get("subcategory") or ri.get("category") or ""

                while path_stack and path_stack[-1][0] >= depth:
                    path_stack.pop()

                path_stack.append((depth, segment))
                ri["hierarchy_path"] = "/".join(p[1] for p in path_stack if p[1])

            # =============================================
            # PASS 2: Determine which computed rows to skip
            # =============================================
            present_categories = {
                ri["category"] for ri in row_info
                if ri.get("category") and not ri.get("skip")
            }

            for ri in row_info:
                if ri.get("skip") or ri.get("is_section_header"):
                    continue
                cat = ri.get("category")
                if cat and _should_skip_computed(cat, present_categories):
                    ri["skip"] = "computed"
                    skipped_computed.append(ri.get("original", cat))

            # Build mapped_categories from pass 1
            for ri in row_info:
                if ri.get("skip") or ri.get("is_section_header"):
                    continue
                if ri.get("category"):
                    entry = {
                        "label": ri.get("original", ""),
                        "category": ri["category"],
                        "match": ri.get("match_type", "regex"),
                    }
                    if ri.get("subcategory"):
                        entry["subcategory"] = ri["subcategory"]
                    mapped_categories.append(entry)

            _update_job({"step": "extracting_amounts", "message": f"Matched {len(mapped_categories)} categories, extracting amounts"})

            # =============================================
            # PASS 3: Extract amounts and build actuals_rows
            # =============================================
            actuals_rows = []
            has_multi_month_periods = False

            for idx, row in enumerate(data_rows):
                if idx >= len(row_info):
                    break
                ri = row_info[idx]
                if ri.get("skip") or ri.get("is_section_header"):
                    continue
                if not ri.get("category"):
                    continue

                category = ri["category"]
                subcategory = ri.get("subcategory")
                hierarchy_path = ri.get("hierarchy_path", "")

                for col_idx, period_tuples in period_cols.items():
                    if col_idx >= len(row):
                        continue
                    amount = _parse_amount(row[col_idx])
                    if amount is None:
                        continue

                    for period, divisor in period_tuples:
                        if divisor > 1:
                            has_multi_month_periods = True
                        actuals_rows.append({
                            "company_id": company_id,
                            "fund_id": fund_id,
                            "period": f"{period}-01",
                            "category": category,
                            "subcategory": subcategory or "",
                            "hierarchy_path": hierarchy_path or (f"{category}/{subcategory}" if subcategory else category),
                            "amount": amount / divisor,
                            "source": "csv_upload",
                        })

            if has_multi_month_periods:
                warnings.append("Quarterly/annual amounts divided evenly across constituent months")

        # --- Final checks ---
        if not actuals_rows:
            err = ("No valid data rows found after parsing. "
                   f"Unmapped labels: {unmapped_labels[:10]}" if unmapped_labels else "No valid data rows found after parsing")
            _update_job({
                "status": "failed",
                "step": "extracting_amounts",
                "error": err,
                "unmapped_labels": unmapped_labels[:20],
                "completed_at": datetime.utcnow().isoformat(),
            })
            raise HTTPException(status_code=400, detail=err)

        # --- Deduplicate rows (same conflict key can appear twice from hierarchy + parent aggregation) ---
        dedup: dict = {}
        for row in actuals_rows:
            key = (row["company_id"], row["period"], row["category"], row["subcategory"], row["hierarchy_path"], row["source"])
            dedup[key] = row  # last write wins
        actuals_rows = list(dedup.values())

        # --- Clear stale csv_upload rows for this company, then upsert ---
        # Previous uploads may have stored rows with different hierarchy_path
        # or subcategory values that won't be overwritten by the new upsert.
        # Delete old csv_upload rows for the periods we're about to write.
        # Log a sample of what we're about to write
        sample = actuals_rows[:10]
        logger.info(
            "[upload-actuals] Sample rows to upsert (first 10): %s",
            [(r["category"], r.get("subcategory", ""), r["period"], r["amount"]) for r in sample]
        )
        _update_job({"step": "upserting", "message": f"Upserting {len(actuals_rows)} rows into fpa_actuals"})

        upload_periods = sorted(set(r["period"] for r in actuals_rows))
        for period_val in upload_periods:
            sb.table("fpa_actuals") \
                .delete() \
                .eq("company_id", company_id) \
                .eq("period", period_val) \
                .eq("source", "csv_upload") \
                .execute()

        sb.table("fpa_actuals").upsert(
            actuals_rows,
            on_conflict="company_id,period,category,subcategory,hierarchy_path,source",
        ).execute()

        periods = sorted(set(r["period"][:7] for r in actuals_rows))
        categories = sorted(set(r["category"] for r in actuals_rows))

        # --- Build grid_commands so frontend updates the grid in one pass ---
        grid_commands = []
        for row in actuals_rows:
            grid_commands.append({
                "action": "edit",
                "company_id": row["company_id"],
                "field": row["category"],
                "period": row["period"][:7],
                "value": row["amount"],
                "source": row.get("source", "csv_upload"),
            })

        # --- Mark completed ---
        _update_job({
            "status": "completed",
            "step": "completed",
            "message": f"Ingested {len(actuals_rows)} rows across {len(periods)} periods",
            "rows_ingested": len(actuals_rows),
            "periods_found": periods,
            "categories_found": categories,
            "mapped_categories": mapped_categories,
            "unmapped_labels": unmapped_labels,
            "warnings": warnings,
            "skipped": {
                "separators": skipped_separators,
                "computed": skipped_computed,
                "empty": skipped_empty,
            },
            "completed_at": datetime.utcnow().isoformat(),
        })

        # Build period_columns_debug so frontend/logs can show what was detected
        period_columns_debug = []
        for col_idx, tuples in sorted(period_cols.items()):
            header_label = headers[col_idx] if col_idx < len(headers) else f"col{col_idx}"
            period_columns_debug.append({
                "column": col_idx,
                "header": header_label,
                "periods": [{"period": p, "divisor": d} for p, d in tuples],
            })

        return {
            "ingested": len(actuals_rows),
            "job_id": job_id,
            "periods": periods,
            "categories": categories,
            "subcategories_created": subcategories_created,
            "mapped_categories": mapped_categories,
            "unmapped_labels": unmapped_labels,
            "skipped_rows": {
                "separators": skipped_separators,
                "computed": skipped_computed,
                "empty": skipped_empty,
            },
            "warnings": warnings,
            "grid_commands": grid_commands,
            "period_columns": period_columns_debug,
        }

    except HTTPException:
        raise  # Re-raise HTTP errors (already marked job as failed above)
    except Exception as e:
        logger.error(f"[upload-actuals] Unexpected error for job {job_id}: {e}", exc_info=True)
        _update_job({
            "status": "failed",
            "step": "failed",
            "error": str(e),
            "completed_at": datetime.utcnow().isoformat(),
        })
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/upload-jobs")
async def list_upload_jobs(
    company_id: str = Query(...),
    status: Optional[str] = Query(None),
    limit: int = Query(20),
):
    """List recent upload jobs for a company. Mirrors document status polling."""
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")

    query = (
        sb.table("fpa_upload_jobs")
        .select("*")
        .eq("company_id", company_id)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if status:
        query = query.eq("status", status)

    result = query.execute()
    return {"jobs": result.data or []}


@router.get("/upload-jobs/{job_id}")
async def get_upload_job(job_id: str):
    """Get a single upload job by ID. Use to poll status after upload."""
    from app.core.supabase_client import get_supabase_client

    sb = get_supabase_client()
    if not sb:
        raise HTTPException(status_code=503, detail="Database unavailable")

    result = sb.table("fpa_upload_jobs").select("*").eq("id", job_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Job not found")
    return result.data[0]


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
# Forecast chart builder
# ---------------------------------------------------------------------------

def _build_forecast_charts(rows: list, boundary_index: int = 0) -> list:
    """Build chart payloads from forecast/rolling-forecast rows."""
    if not rows:
        return []

    periods = [r.get("period", "") for r in rows]
    charts = []

    # Revenue & EBITDA line chart
    rev = [r.get("revenue", 0) for r in rows]
    ebitda = [r.get("ebitda", 0) for r in rows]
    if any(v for v in rev):
        charts.append({
            "type": "line",
            "title": "Revenue & EBITDA Forecast",
            "renderType": "tableau",
            "data": {
                "labels": periods,
                "datasets": [
                    {"label": "Revenue", "data": rev},
                    {"label": "EBITDA", "data": ebitda},
                ],
                "boundary_index": boundary_index,
            },
        })

    # Cash balance & runway
    cash = [r.get("cash_balance", 0) for r in rows]
    runway = [r.get("runway_months", 0) for r in rows]
    if any(v for v in cash):
        charts.append({
            "type": "line",
            "title": "Cash Balance & Runway",
            "renderType": "tableau",
            "data": {
                "labels": periods,
                "datasets": [
                    {"label": "Cash Balance", "data": cash},
                    {"label": "Runway (months)", "data": runway, "yAxis": "right"},
                ],
                "boundary_index": boundary_index,
            },
        })

    # OpEx breakdown stacked bar
    rd = [r.get("rd_spend", 0) for r in rows]
    sm = [r.get("sm_spend", 0) for r in rows]
    ga = [r.get("ga_spend", 0) for r in rows]
    if any(v for v in rd) or any(v for v in sm) or any(v for v in ga):
        charts.append({
            "type": "stacked_bar",
            "title": "OpEx Breakdown",
            "renderType": "tableau",
            "data": {
                "labels": periods,
                "datasets": [
                    {"label": "R&D", "data": rd},
                    {"label": "S&M", "data": sm},
                    {"label": "G&A", "data": ga},
                ],
            },
        })

    return charts


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
        result["charts"] = _build_forecast_charts(
            result.get("rows", []),
            boundary_index=result.get("boundary_index", 0),
        )

        # If forecast was computed fresh (no saved forecast), persist it so
        # the next call loads from saved rather than recomputing.
        rows = result.get("rows", [])
        boundary = result.get("boundary_index", 0)
        forecast_rows = [r for r in rows[boundary:] if r.get("source") == "forecast"]
        if forecast_rows:
            try:
                from app.services.forecast_persistence_service import ForecastPersistenceService
                fps = ForecastPersistenceService()
                # Only save if no active forecast already exists
                existing = fps.get_active_forecast(company_id)
                if not existing:
                    saved = fps.save_forecast(
                        company_id=company_id,
                        forecast=forecast_rows,
                        method="rolling_forecast",
                        seed_snapshot={"window_months": window, "granularity": granularity},
                        assumptions={"boundary_period": result.get("boundary_period")},
                        name="Rolling Forecast (auto-saved)",
                        activate=True,
                        created_by="rolling_forecast_endpoint",
                    )
                    result["_persistence"] = {
                        "forecast_id": saved.get("id"),
                        "rows_written": len(forecast_rows),
                    }
                    # Write to grid if empty
                    if saved.get("id"):
                        from app.services.analysis_persistence_service import AnalysisPersistenceService
                        aps = AnalysisPersistenceService()
                        if aps._grid_is_empty(company_id):
                            grid_rows = fps.write_forecast_to_actuals(
                                saved["id"], source="rolling_forecast_applied",
                            )
                            result["_persistence"]["wrote_to_grid"] = True
                            result["_persistence"]["grid_rows"] = grid_rows
            except Exception as e:
                logger.warning("Rolling forecast persistence failed: %s", e)

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
    Always includes base_forecast (rolling forecast) so the scenarios view
    has the base case to display. With enrich=true, includes computed
    metrics (revenue, EBITDA, cash, runway) per branch.
    """
    # Always fetch the rolling forecast as the base scenario
    from app.services.rolling_forecast_service import RollingForecastService

    base_forecast = []
    base_charts = []
    base_boundary_index = 0
    try:
        rf_svc = RollingForecastService()
        rf_result = rf_svc.build_rolling_view(
            company_id=company_id,
            window_months=forecast_months + 12,
            granularity="monthly",
        )
        base_forecast = rf_result.get("rows", [])
        base_boundary_index = rf_result.get("boundary_index", 0)
        base_charts = _build_forecast_charts(base_forecast, base_boundary_index)
    except Exception as e:
        logger.warning("Could not load base forecast for scenario tree: %s", e)

    if enrich:
        from app.services.scenario_branch_service import ScenarioBranchService
        svc = ScenarioBranchService()
        tree = svc.get_enriched_tree(company_id, forecast_months)
        tree["base_forecast"] = base_forecast
        tree["charts"] = base_charts
        tree["boundary_index"] = base_boundary_index
        return tree

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

    return {
        "company_id": company_id,
        "branches": roots,
        "base_forecast": base_forecast,
        "charts": base_charts,
        "boundary_index": base_boundary_index,
    }


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

    # Persist expected-value forecast to branch (+ grid if empty)
    ev_forecast = result.get("expected_value")
    if ev_forecast and isinstance(ev_forecast, list):
        periods = [r.get("period") for r in ev_forecast if isinstance(r, dict)]
        persist = _persist_fpa_output(
            company_id=req.company_id,
            analysis_type="scenario_comparison_ev",
            assumptions={
                "branch_ids": req.branch_ids,
                "forecast_months": req.forecast_months,
                "start_period": req.start_period,
            },
            trajectory=ev_forecast,
            periods=periods,
            summary={
                "branches_compared": len(req.branch_ids),
                "capital_impact": result.get("capital_impact"),
            },
            branch_name="Scenario Comparison EV",
        )
        result["_persistence"] = persist

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
        nl_parser, classifier, workflow_builder, executor, model_editor, regression_service = _get_nl_services()
        # Parse query
        parsed_query = nl_parser.parse(request.query)

        # Classify query
        handler = await classifier.route(parsed_query)
        
        # Build workflow
        workflow = workflow_builder.build(parsed_query, handler)
        
        # Execute workflow
        from app.services.fpa_executor import ExecutorContext
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
        *_, model_editor, _ = _get_nl_services()
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
        *_, model_editor, _ = _get_nl_services()
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
        *_, model_editor, _ = _get_nl_services()
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
        *_, model_editor, _ = _get_nl_services()
        result = await model_editor.update_assumptions(model_id, assumptions)
        return result
    except Exception as e:
        logger.error(f"Error updating assumptions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/{model_id}/execute")
async def execute_model(model_id: str):
    """Re-run a model with current formulas/assumptions"""
    try:
        *_, model_editor, _ = _get_nl_services()
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
    """Run regression analysis and persist results to a scenario branch.

    For monte_carlo and sensitivity: when ``data.company_id`` is present the
    backend pulls latest actuals from Supabase so the frontend doesn't need
    to scrape the grid.  If ``data.branch_id`` is also set, branch-adjusted
    values override the base actuals.

    All analysis results are always persisted:
    - A scenario branch is created with the assumptions used
    - MC/time_series trajectories are saved as forecast lines
    - If the grid is empty, forecast rows are written to fpa_actuals
    """
    try:
        *_, regression_service = _get_nl_services()

        # --- Auto-populate from Supabase when company_id is provided ---
        company_id = request.data.get("company_id")
        branch_id = request.data.get("branch_id")
        company_data = None
        if company_id and request.regression_type in ("monte_carlo", "sensitivity"):
            from app.services.company_data_pull import pull_company_data, apply_branch_overrides
            company_data = pull_company_data(company_id)
            company_data = apply_branch_overrides(company_data, branch_id)

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
            # Start from pulled actuals, let explicit request values override
            base_scenario = {}
            if company_data:
                base_scenario = company_data.latest_with_overrides(request.data.get("base_scenario", {}))
            else:
                base_scenario = request.data.get("base_scenario", {})
            distributions = request.data.get("distributions", {})
            # Derive distributions from actual historical variance
            if not distributions and company_data:
                for key in ("revenue", "cogs", "opex_total", "ebitda"):
                    variance = company_data.historical_variance(key)
                    if variance:
                        distributions[key] = {"min": variance["min"], "max": variance["max"]}
            iterations = request.options.get("iterations", 1000) if request.options else 1000
            result = await regression_service.monte_carlo_simulation(base_scenario, distributions, iterations)
        elif request.regression_type == "sensitivity":
            # Start from pulled actuals, let explicit request values override
            base_inputs = {}
            if company_data:
                base_inputs = company_data.latest_with_overrides(request.data.get("base_inputs", {}))
            else:
                base_inputs = request.data.get("base_inputs", {})
            variable_ranges = request.data.get("variable_ranges", {})
            # Default variable ranges from latest values
            if not variable_ranges and company_data:
                for key in ("revenue", "cogs", "opex_total", "ebitda"):
                    val = company_data.latest.get(key)
                    if val:
                        variable_ranges[key] = {"min": val * 0.7, "max": val * 1.3, "steps": 10}
            result = await regression_service.sensitivity_analysis(base_inputs, variable_ranges, None)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown regression type: {request.regression_type}")

        # --- Persist results to branch (+ grid if empty) ---
        persist_meta = {}
        if company_id:
            from app.services.analysis_persistence_service import AnalysisPersistenceService
            aps = AnalysisPersistenceService()

            if request.regression_type == "monte_carlo":
                persist_meta = aps.persist_monte_carlo(
                    company_id=company_id,
                    mc_result=result,
                    branch_name=request.branch_name,
                    parent_branch_id=request.parent_branch_id,
                )
            elif request.regression_type == "sensitivity":
                persist_meta = aps.persist_sensitivity(
                    company_id=company_id,
                    sensitivity_result=result,
                    base_inputs=base_inputs,
                    branch_name=request.branch_name,
                    parent_branch_id=request.parent_branch_id,
                )
            elif request.regression_type == "time_series":
                # time_series forecast produces a trajectory
                trajectory = []
                forecast_values = result.get("forecast", [])
                for i, val in enumerate(forecast_values):
                    trajectory.append({"period": f"forecast_{i}", "revenue": val})
                persist_meta = aps.persist_analysis_result(
                    company_id=company_id,
                    analysis_type="time_series_forecast",
                    assumptions={"historical_data_points": len(request.data.get("historical_data", []))},
                    branch_name=request.branch_name,
                    parent_branch_id=request.parent_branch_id,
                    trajectory=trajectory if trajectory else None,
                    summary=result,
                )
            else:
                # linear / exponential — point-in-time, branch only
                persist_meta = aps.persist_analysis_result(
                    company_id=company_id,
                    analysis_type=request.regression_type,
                    assumptions=request.data,
                    branch_name=request.branch_name,
                    parent_branch_id=request.parent_branch_id,
                    summary=result,
                )

        # Return analysis result + persistence metadata
        if isinstance(result, dict):
            result["_persistence"] = persist_meta
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

        # ── Persist to branch + grid (if empty) ─────────────────────
        persist = {}
        if request.company_id and forecast:
            branch_assumptions: Dict[str, Any] = {
                "forecast_periods": request.forecast_periods,
                "granularity": request.granularity,
            }
            if request.growth_rate is not None:
                branch_assumptions["growth_rate"] = request.growth_rate
            if request.base_data:
                branch_assumptions["base_data"] = request.base_data
            if request.assumptions:
                branch_assumptions.update(request.assumptions)
            periods = [r.get("period") for r in forecast if isinstance(r, dict)]
            persist = _persist_fpa_output(
                company_id=request.company_id,
                analysis_type="forecast_projection",
                assumptions=branch_assumptions,
                trajectory=forecast,
                periods=periods,
                branch_name="Forecast Projection",
            )

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
            "charts": _build_forecast_charts(forecast, boundary_index=0),
            "_persistence": persist,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating forecast: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
