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
    OutputFormat,
    AGENT_TOOLS,
    AgentTool,
)
from app.services.model_router import set_provider_affinity
from app.utils.json_serializer import safe_json_dumps, clean_for_json, serialize_stream_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["cfo-brain"])


# ---------------------------------------------------------------------------
# CFO system prompt — injected via shared_data so the orchestrator uses it
# ---------------------------------------------------------------------------

def _build_tool_list_from_registry() -> str:
    """Auto-generate tool list for system prompt from AGENT_TOOLS registry.
    Single source of truth — no more drift between prompt and registry."""
    # Group by cost_tier for readability
    groups: Dict[str, list] = {"free": [], "cheap": [], "expensive": []}
    for t in AGENT_TOOLS:
        tier = t.cost_tier if t.cost_tier in groups else "cheap"
        groups[tier].append(t)
    lines = []
    for tier, tools in groups.items():
        if not tools:
            continue
        for t in tools:
            lines.append(f"- {t.name}: {t.description}")
    return "\n".join(lines)


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

    # Build snapshot from actuals + tell agent what data sections exist
    pnl_snapshot = ""
    methodology_note = ""
    data_sections_note = ""
    company_id = ctx.get("company_id") or ctx.get("companyId")
    if company_id:
        try:
            from app.services.company_data_pull import pull_company_data
            from app.services.forecast_method_router import ForecastMethodRouter

            cd = pull_company_data(company_id)
            seed = cd.to_forecast_seed()
            parts = []
            if seed.get("revenue"):
                parts.append(f"Last month revenue: {fmt(seed['revenue'])}")
            if seed.get("gross_margin") is not None:
                parts.append(f"Gross margin: {seed['gross_margin']:.0%}")
            if seed.get("burn_rate"):
                parts.append(f"Monthly burn: {fmt(seed['burn_rate'])}")
            if seed.get("net_burn"):
                parts.append(f"Net burn: {fmt(seed['net_burn'])}")
            if seed.get("cash_balance"):
                parts.append(f"Cash: {fmt(seed['cash_balance'])}")
            if seed.get("runway_months"):
                parts.append(f"Runway: {seed['runway_months']:.0f} months")
            if seed.get("headcount"):
                parts.append(f"Headcount: {int(seed['headcount'])}")

            dq = seed.get("_data_quality", {})
            rev_months = dq.get("revenue_months", 0)
            if rev_months:
                parts.append(f"Actuals: {rev_months} months of data")
            if dq.get("has_opex_breakdown"):
                parts.append("OpEx breakdown available (R&D/S&M/G&A)")
            if dq.get("growth_trend") and dq["growth_trend"] != "unknown":
                parts.append(f"Growth trend: {dq['growth_trend']}")

            if parts:
                pnl_snapshot = "Current P&L snapshot (latest month only — call pull_company_data for full history): " + ", ".join(parts) + "."

            # Tell agent what forecast method the router auto-selected and why
            router = ForecastMethodRouter()
            method, reasoning = router.auto_select_method(company_id, seed, company_data=cd)
            methodology_note = (
                f"\n\nForecast methodology: {method}. {reasoning}. "
                "You can re-run with a different method using fpa_forecast, "
                "adjust individual drivers using run_scenario or fpa_scenario_update, "
                "run Monte Carlo simulations using fpa_regression, "
                "and create scenario branches to compare alternatives."
            )

            # Tell the agent what data is available — from metadata only, no extra DB calls
            available_sections = []
            categories = cd.metadata.get("categories", [])
            if categories:
                available_sections.append(f"P&L actuals: {len(cd.periods)} periods, categories: {', '.join(categories[:15])}")
            if cd.analytics:
                available_sections.append("Analytics: growth rates, burn analysis, margins, runway, data quality")
            # Always hint about cross-domain data available via strategic_analysis
            available_sections.append(
                "Cross-domain (cap table, drivers, KPIs, scenario branches, trajectories): "
                "call strategic_analysis when reasoning across financial domains matters"
            )

            if available_sections:
                data_sections_note = (
                    "\n\nAVAILABLE DATA (call pull_company_data for full time_series; "
                    "call strategic_analysis for cross-domain reasoning):\n- "
                    + "\n- ".join(available_sections)
                )

        except Exception:
            pnl_snapshot = ""

    # Fall back to legacy KPIs only if no P&L data from actuals
    if pnl_snapshot:
        snapshot = pnl_snapshot + methodology_note + data_sections_note
    else:
        snapshot_parts = [
            fmt(ctx.get("currentARR") or ctx.get("current_arr")) and f"ARR: {fmt(ctx.get('currentARR') or ctx.get('current_arr'))}",
            fmt(ctx.get("currentBurn") or ctx.get("current_burn")) and f"Monthly burn: {fmt(ctx.get('currentBurn') or ctx.get('current_burn'))}",
            fmt(ctx.get("cashBalance") or ctx.get("cash_balance")) and f"Cash: {fmt(ctx.get('cashBalance') or ctx.get('cash_balance'))}",
            ctx.get("runwayMonths") or ctx.get("runway_months") and f"Runway: {ctx.get('runwayMonths') or ctx.get('runway_months')} months",
            ctx.get("headcount") and f"Headcount: {ctx.get('headcount')}",
        ]
        snapshot = ", ".join([p for p in snapshot_parts if p])
        if snapshot:
            snapshot = "Current snapshot: " + snapshot + "."

    return (
        f"You are the CFO of {company}, a {stage} company.\n"
        f"{snapshot}\n\n"

        "## WHO YOU ARE\n"
        "You're an opinionated, direct CFO who's been through 3 downturns and 2 IPOs. "
        "You don't hedge with corporate speak — you give sharp, actionable financial insight. "
        "You lead with the number that matters most, explain what it means for the business, "
        "and say what to do about it. You work with REAL numbers — never fabricate data.\n\n"

        "Tone: Confident, concise, occasionally blunt. Never bureaucratic.\n"
        "Example: 'Burn's up 18% but revenue only grew 6%. At this rate you've got 11 months "
        "of runway, not the 16 you're telling the board. Cut S&M 20% or raise in Q2.'\n\n"

        "## HOW YOU TALK\n"
        "- Match depth to the question. 'What's our burn?' gets one sentence. 'Model runway under 3 scenarios' gets the full treatment.\n"
        "- If a request is ambiguous or could go multiple ways, ask ONE clarifying question before executing. Don't guess and dump.\n"
        "- Share findings as you go. After each step, give the headline. Don't go silent then wall-of-text.\n"
        "- If you discover something unexpected mid-analysis, flag it and ask whether to dig in.\n"
        "- When the user steers you, follow their lead. Don't restart from scratch.\n\n"

        "## HOW YOU GUIDE\n"
        "Users often don't know what to ask their CFO. Help them discover what matters.\n"
        "- If the user seems unsure, suggest 2-3 specific actions based on their financial data.\n"
        "- After delivering results, suggest the natural next question: 'Now that you see the P&L, want me to check which contracts are driving that COGS spike?'\n"
        "- Be proactive about signals: runway critical, burn accelerating, covenant near breach, unit economics broken — say so without being asked.\n"
        "- When you have nothing useful to add, say so briefly. Don't pad.\n\n"

        "## HOW YOU WORK\n"
        "You are a WORKER, not a report generator. You use tools, do the analysis, deliver results.\n\n"

        "DEPTH MATCHING:\n"
        "- QUICK (sentence answer): 'What's our burn?' → '~$280K/mo, up 12% from Q3. 14 months of runway.' Zero or one tool call.\n"
        "- TASK (do the thing): fetch data, run analysis, update grid. Share findings as you go. 10-30s.\n"
        "- DEEP (full analysis): board updates, scenario comparisons. Outline approach first, then step by step.\n"
        "A quick question that gets a 10-section memo is a failure. Match the response to the ask.\n\n"

        "FORMAT RULES:\n"
        "- Sentence answers it? Chat only. No memo.\n"
        "- Data tells a story? Chat headline + chart/memo evidence.\n"
        "- Formal deliverable? Brief summary pointing to memo.\n"
        "- Don't wait for 'show me a chart' — if a visual answers faster than text, generate it.\n\n"

        "## AVAILABLE TOOLS\n"
        + _build_tool_list_from_registry()
        + "\n\n"

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
        # Ensure company_id flows through so system prompt can pull real P&L data
        if not company_ctx.get("company_id"):
            company_ctx["company_id"] = merged_context.get("company_id") or merged_context.get("companyId")
        merged_context["system_prompt_override"] = _build_cfo_system_prompt(company_ctx)

        # Force grid_mode=pnl so the orchestrator routes to FP&A/forecast tools
        # instead of investor-portfolio tools.  _MODE_FALLBACK["pnl"] → "forecast"
        # means even unrecognised intents get the right tool scope.
        if not merged_context.get("grid_mode"):
            merged_context["grid_mode"] = "pnl"

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
    # Mirror non-stream: inject company_id so system prompt can pull real P&L data
    if not company_ctx.get("company_id"):
        company_ctx["company_id"] = merged_context.get("company_id") or merged_context.get("companyId")
    merged_context["system_prompt_override"] = _build_cfo_system_prompt(company_ctx)

    # Force grid_mode=pnl so orchestrator routes to FP&A/forecast tools
    if not merged_context.get("grid_mode"):
        merged_context["grid_mode"] = "pnl"

    async def event_generator():
        try:
            async for event in orchestrator.process_request_stream(
                prompt=request.prompt,
                output_format=request.output_format,
                context=merged_context,
            ):
                line = serialize_stream_event(event, agent_label="cfo")
                if line:
                    yield line
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
