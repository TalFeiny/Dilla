"""
CFO Brain API Endpoints
Same architecture as unified_brain.py but with CFO system prompt and FPA-focused tools.
Separate agent for FP&A, budgeting, cash flow, variance analysis, and scenario planning.
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Dict, Optional
from pydantic import BaseModel, Field
import logging

from app.services.unified_mcp_orchestrator import (
    get_unified_orchestrator,
    OutputFormat
)
from app.services.model_router import set_provider_affinity
from app.utils.json_serializer import safe_json_dumps, clean_for_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["cfo-brain"])


# ---------------------------------------------------------------------------
# CFO system prompt — injected via shared_data so the orchestrator uses it
# ---------------------------------------------------------------------------

def _build_cfo_system_prompt(company_context: Optional[Dict] = None) -> str:
    """Build the CFO agent system prompt from optional company context."""
    ctx = company_context or {}
    company = ctx.get("companyName") or ctx.get("company_name") or "the portfolio company"
    stage = ctx.get("stage") or "growth-stage"

    def fmt(n):
        if not n:
            return None
        n = float(n)
        if n >= 1e9:
            return f"${n / 1e9:.1f}B"
        if n >= 1e6:
            return f"${n / 1e6:.1f}M"
        if n >= 1e3:
            return f"${n / 1e3:.0f}K"
        return f"${n:.0f}"

    snapshot_parts = [
        fmt(ctx.get("currentARR") or ctx.get("current_arr")) and f"ARR: {fmt(ctx.get('currentARR') or ctx.get('current_arr'))}",
        fmt(ctx.get("currentBurn") or ctx.get("current_burn")) and f"Monthly burn: {fmt(ctx.get('currentBurn') or ctx.get('current_burn'))}",
        fmt(ctx.get("cashBalance") or ctx.get("cash_balance")) and f"Cash: {fmt(ctx.get('cashBalance') or ctx.get('cash_balance'))}",
        ctx.get("runwayMonths") or ctx.get("runway_months") and f"Runway: {ctx.get('runwayMonths') or ctx.get('runway_months')} months",
        ctx.get("headcount") and f"Headcount: {ctx.get('headcount')}",
    ]
    snapshot = ", ".join([p for p in snapshot_parts if p])

    return (
        f"You are the CFO of {company}, a {stage} company.\n"
        f"{('Current snapshot: ' + snapshot + '.') if snapshot else ''}\n\n"

        "## WHO YOU ARE\n"
        "You're an opinionated, direct CFO who's been through 3 downturns and 2 IPOs. "
        "You don't hedge with corporate speak — you give sharp, actionable financial insight. "
        "You lead with the number that matters most, explain what it means for the business, "
        "and say what to do about it. You work with REAL numbers — never fabricate data.\n\n"

        "Tone: Confident, concise, occasionally blunt. Never bureaucratic.\n"
        "Example: 'Burn's up 18% but revenue only grew 6%. At this rate you've got 11 months "
        "of runway, not the 16 you're telling the board. Cut S&M 20% or raise in Q2.'\n\n"

        "## HOW YOU WORK\n"
        "You are a WORKER, not a report generator. You use tools to get data, do the analysis, "
        "and deliver results. You think about what tools to call, in what order, and you chain "
        "them together to answer the actual question.\n\n"

        "WORKFLOW:\n"
        "1. UNDERSTAND what the user actually needs — is it a quick answer, a task, or a deep analysis?\n"
        "2. FETCH the right data — call the tools that get you the numbers. Multiple companies? Call the tool for each.\n"
        "3. ANALYZE — don't just parrot tool output. Compute ratios, spot trends, compare periods, find the story.\n"
        "4. DELIVER in the right format (see RESPONSE FORMAT below).\n\n"

        "When you need data across multiple companies or periods, make multiple tool calls. "
        "Don't stop at one company when the user asked about the portfolio. "
        "Don't give a table when a sentence would do. Don't write a memo when a chat reply answers it.\n\n"

        "## RESPONSE FORMAT — pick the right format for the situation\n"
        "Match your output to what the question actually needs:\n\n"
        "CHAT ONLY — when a sentence answers it:\n"
        "- 'What's our burn rate?' → '~$280K/mo, up 12% from Q3. 14 months of runway.'\n"
        "- 'Can we afford another hire?' → 'Yes, adds ~$15K/mo. Shortens runway from 14 to 12 months.'\n"
        "- Task confirmations: 'Ingested 847 rows across 12 months. Grid updated.'\n\n"
        "CHAT + CHART/MEMO — when data tells a story:\n"
        "- Any comparison over time → line or bar chart\n"
        "- OpEx breakdown or cost structure → stacked bar or waterfall\n"
        "- Scenario analysis → bull_bear_base chart\n"
        "- Budget vs actuals → waterfall chart showing variance\n"
        "- 'How are we doing?' with actuals loaded → P&L summary + trend chart\n"
        "Your chat message gives the headline insight. The chart/memo shows the evidence.\n"
        "Don't wait for 'show me a chart' — if a visual answers faster than text, generate it.\n\n"
        "FULL MEMO — when depth and structure matter:\n"
        "- Board updates, runway analysis, scenario comparisons, formal deliverables\n"
        "- Multi-section analysis that needs narrative + charts + tables together\n"
        "- Your chat message is a 1-2 sentence summary pointing to the memo.\n\n"
        "WORKING STYLE:\n"
        "- Show what you're doing as you work. When you call tools, the user sees your progress.\n"
        "- For multi-step analysis, share key findings as you go — don't go silent then dump everything.\n"
        "- If you discover something unexpected mid-analysis, flag it: 'Burn spiked 40% in November — want me to dig in?'\n"
        "- Match the depth of your answer to the depth of the question.\n"
        "- When the user steers you ('dig into costs', 'now forecast that'), follow their lead — don't restart from scratch.\n\n"

        "## TOOLS — FP&A\n"
        "- fpa_pnl: Full P&L waterfall (actuals + forecast)\n"
        "- fpa_variance: Budget vs actuals with status flags, monthly trend\n"
        "- fpa_forecast: Generate forecast from actuals (monthly/quarterly/annual)\n"
        "- fpa_regression: Statistical forecasting (linear, exponential, time series, Monte Carlo, sensitivity)\n"
        "- fpa_scenario_create: Create scenario branch with assumptions\n"
        "- fpa_scenario_tree: Full scenario tree for a company\n"
        "- fpa_scenario_compare: Side-by-side branch comparison with probability-weighted EV\n"
        "- fpa_cash_flow: Monthly cash flow model (revenue → COGS → gross profit → OpEx → EBITDA → FCF → cash → runway)\n"
        "- fpa_budget_create: Create a new budget (company_id, name, fiscal_year)\n"
        "- fpa_budget_list: List budgets for a company\n"
        "- fpa_budget_lines: Budget line items\n"
        "- fpa_upload_actuals: Ingest actuals from structured time series data\n"
        "- fpa_upload_budget: Upload budget line items to an existing budget\n"
        "- fpa_actuals: Company actuals data\n"
        "- fpa_scenario_delete: Delete a scenario branch and descendants\n"
        "- fpa_rolling_forecast: Rolling actuals+forecast stitched timeline (monthly/quarterly/annual)\n"
        "- fpa_xero_sync: Pull latest actuals from Xero into fpa_actuals\n\n"

        "## TOOLS — TRANSFER PRICING\n"
        "- tp_group_overview: TP overview — entities, IC transactions, benchmark status, reports\n"
        "- tp_search_comparables: Find comparable companies (portfolio, yfinance, web). OECD 5-factor scoring\n"
        "- tp_analyze_transaction: Full TP analysis — method selection, PLI computation, IQR, arm's-length\n"
        "- tp_generate_report: OECD-compliant reports — benchmark, local_file, master_file, cbcr, full_pack\n\n"

        "## TOOLS — INVESTOR & CAP TABLE\n"
        "- cap_table_evolution: Dilution through all funding rounds with Sankey visualization\n"
        "- liquidation_waterfall: Liquidation waterfall at specific exit values\n"
        "- run_round_modeling: Next round — dilution, waterfall, valuation step-up\n"
        "- run_exit_modeling: Exit scenarios (IPO, M&A) with fund ownership impact\n"
        "- anti_dilution_modeling: Ratchet / broad-based anti-dilution scenarios\n"
        "- debt_conversion_modeling: SAFEs, convertible notes, debt conversion\n\n"

        "## TOOLS — SHARED\n"
        "- valuation-engine: DCF, comparables\n"
        "- financial-analyzer: Ratios, projections\n"
        "- scenario-generator: Monte Carlo, sensitivity\n"
        "- chart-generator: cashflow, stress_test, bar_comparison, stacked_bar, revenue_forecast, bull_bear_base, heatmap\n"
        "- memo-writer: monthly_close, variance_narrative, runway_analysis, cash_flow_memo, board_deck_financials, "
        "investor_update_financials, quarterly_review, budget_proposal, hiring_plan, fundraising_model, scenario_comparison\n"
        "- nl-matrix-controller: Edit grid cells, push computed values\n"
        "- deck-storytelling: Board deck with financial slides\n"
        "- excel-generator: Financial model export\n\n"

        "## CFO INSTINCTS\n"
        "- Runway is the heartbeat. Always know how many months are left.\n"
        "- Variance tells you where reality diverged from the plan. Chase the biggest delta.\n"
        "- Unit economics reveal whether growth is healthy or just expensive.\n"
        "- Every recommendation has a cash impact. Quantify it.\n"
        "- If the data tells a story, tell it. Don't hide behind tables.\n\n"

        "## DATA RULES — non-negotiable\n"
        "1. COUNT before you claim. Get exact numbers right.\n"
        "2. NEVER dismiss available data. Work with what you have.\n"
        "3. Mark estimates: 'Revenue ~$2.1M (est. from 3-month trend, 80% confidence)'.\n"
        "4. No blanket disclaimers when data exists. No 'insufficient data' cop-outs.\n"
        "5. If you have partial data, analyze it. 7 out of 32 is enough to find patterns."
    )


class CFORequest(BaseModel):
    """Request model for CFO brain processing"""
    prompt: str = Field(..., description="User prompt to process")
    output_format: str = Field("analysis", description="Output format")
    output_format_hint: Optional[str] = Field(None)
    context: Optional[Dict] = Field(None, description="Additional context including company FPA data")
    agent_context: Optional[Dict] = Field(None, description="Conversation continuity context")
    approved_plan: Optional[bool] = Field(None)
    options: Optional[Dict] = Field(default_factory=dict)


def _extract_user_id(raw_request: Request, context: Optional[Dict] = None) -> str:
    """Best-effort user ID for provider affinity."""
    import uuid as _uuid
    if context and context.get("user_id"):
        return context["user_id"]
    auth = raw_request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and len(auth) > 40:
        return auth[7:39]
    return str(_uuid.uuid4())


@router.post("/cfo-brain")
async def process_cfo_request(request: CFORequest, raw_request: Request):
    """
    CFO agent endpoint — same as unified-brain but with CFO system prompt.
    Handles FP&A, budgeting, cash flow, variance, and scenario planning.
    """
    set_provider_affinity(_extract_user_id(raw_request, request.context))
    logger.info(f"[CFO-BRAIN] Received request: {request.prompt[:100]}")
    try:
        # Validate output format
        output_format_str = request.output_format.lower().replace('-', '_')
        try:
            output_format = OutputFormat(output_format_str)
        except ValueError:
            format_map = {
                'spreadsheet': OutputFormat.STRUCTURED,
                'deck': OutputFormat.STRUCTURED,
                'matrix': OutputFormat.STRUCTURED,
                'docs': OutputFormat.STRUCTURED,
                'analysis': OutputFormat.STRUCTURED,
                'json': OutputFormat.JSON,
                'markdown': OutputFormat.STRUCTURED,
            }
            output_format = format_map.get(output_format_str, OutputFormat.STRUCTURED)

        orchestrator = get_unified_orchestrator()
        readiness_info = getattr(orchestrator, "readiness_status", lambda: {"ready": True})()
        if not readiness_info.get("ready", True):
            raise HTTPException(status_code=503, detail="Orchestrator not ready")

        # Build merged context with CFO system prompt override
        merged_context = dict(request.context) if request.context else {}
        if request.agent_context:
            merged_context["agent_context"] = request.agent_context
        if request.approved_plan:
            merged_context["approved_plan"] = True
        if request.output_format_hint:
            merged_context["output_format_hint"] = request.output_format_hint

        # Inject CFO system prompt override — this is what makes it a CFO agent
        company_ctx = merged_context.get("company_fpa_context") or merged_context.get("companyContext") or {}
        merged_context["system_prompt_override"] = _build_cfo_system_prompt(company_ctx)

        # Process through the same orchestrator
        result = await orchestrator.process_request(
            prompt=request.prompt,
            output_format=request.output_format,
            context=merged_context,
        )

        # Clean numpy/inf
        from app.utils.numpy_converter import convert_numpy_to_native

        def convert_inf_to_none(obj):
            if isinstance(obj, float):
                if obj == float('inf') or obj == float('-inf') or obj != obj:
                    return None
            elif isinstance(obj, dict):
                return {k: convert_inf_to_none(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_inf_to_none(item) for item in obj]
            return obj

        if result:
            result = convert_numpy_to_native(result)
            result = convert_inf_to_none(result)

        if result and result.get('success'):
            formatted_results = result.get('results') or result.get('result')

            if isinstance(formatted_results, dict):
                requested_format = (request.output_format or "").strip().lower()
                inferred_format = formatted_results.get('format') or formatted_results.get('type')
                if not inferred_format and requested_format:
                    inferred_format = requested_format
                if inferred_format:
                    formatted_results.setdefault('format', inferred_format)
                    formatted_results.setdefault('type', inferred_format)

            response_data = {
                "success": True,
                "result": formatted_results,
                "agent": "cfo",
            }
            cleaned = clean_for_json(response_data)
            return JSONResponse(content=cleaned)

        # Fallback
        cleaned = clean_for_json(result or {"success": False, "error": "Empty result"})
        return JSONResponse(content=cleaned, status_code=500 if not (result or {}).get("success") else 200)

    except Exception as e:
        logger.error(f"CFO brain error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        error_response = clean_for_json({
            "success": False,
            "error": str(e),
            "type": type(e).__name__,
            "agent": "cfo",
        })
        return JSONResponse(content=error_response, status_code=500)


@router.post("/cfo-brain-stream")
async def process_cfo_stream(request: CFORequest, raw_request: Request):
    """Streaming CFO endpoint — yields NDJSON progress events."""
    import json as _json

    set_provider_affinity(_extract_user_id(raw_request, request.context))
    logger.info(f"[CFO-BRAIN-STREAM] Streaming request: {request.prompt[:80]}")

    orchestrator = get_unified_orchestrator()
    readiness_info = getattr(orchestrator, "readiness_status", lambda: {"ready": True})()
    if not readiness_info.get("ready", True):
        raise HTTPException(status_code=503, detail="Orchestrator not ready")

    merged_context = dict(request.context) if request.context else {}
    if request.agent_context:
        merged_context["agent_context"] = request.agent_context
    if request.approved_plan:
        merged_context["approved_plan"] = True
    if request.output_format_hint:
        merged_context["output_format_hint"] = request.output_format_hint

    company_ctx = merged_context.get("company_fpa_context") or merged_context.get("companyContext") or {}
    merged_context["system_prompt_override"] = _build_cfo_system_prompt(company_ctx)

    async def event_generator():
        try:
            async for event in orchestrator.process_request_stream(
                prompt=request.prompt,
                output_format=request.output_format,
                context=merged_context,
            ):
                event_type = event.get("type", "unknown")
                if event_type == "progress":
                    yield _json.dumps({"type": "progress", "stage": event.get("stage"), "message": event.get("message"), "plan_steps": event.get("plan_steps")}) + "\n"
                elif event_type == "memo_section":
                    yield _json.dumps({"type": "memo_section", "section": clean_for_json(event.get("section", {}))}) + "\n"
                elif event_type == "chart_data":
                    yield _json.dumps({"type": "chart_data", "chart": clean_for_json(event.get("chart", {}))}) + "\n"
                elif event_type == "complete":
                    from app.utils.numpy_converter import convert_numpy_to_native
                    result = event.get("result", {})
                    if result:
                        result = convert_numpy_to_native(result)
                    cleaned = clean_for_json({"type": "complete", "success": True, "result": result, "agent": "cfo"})
                    yield _json.dumps(cleaned) + "\n"
                elif event_type == "error":
                    yield _json.dumps({"type": "error", "error": event.get("error"), "agent": "cfo"}) + "\n"
        except Exception as e:
            logger.error(f"[CFO-BRAIN-STREAM] Error: {e}")
            yield _json.dumps({"type": "error", "error": str(e), "agent": "cfo"}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@router.get("/cfo-brain/health")
async def cfo_health():
    return {
        "status": "healthy",
        "service": "cfo-brain",
        "agent": "cfo",
        "features": [
            "fpa-pnl",
            "fpa-variance",
            "fpa-forecast",
            "fpa-scenarios",
            "fpa-cash-flow",
            "budget-management",
            "streaming-support",
        ]
    }
