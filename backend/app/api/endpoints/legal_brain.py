"""
Legal / GC Brain API Endpoints
Same architecture as cfo_brain.py but with General Counsel system prompt
and legal-clause-focused tools. Handles contract review, clause extraction,
obligation tracking, cross-reference to financial services, and ERP attribution.
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
)
from app.services.model_router import set_provider_affinity
from app.utils.json_serializer import safe_json_dumps, clean_for_json, serialize_stream_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["legal-brain"])


# ---------------------------------------------------------------------------
# GC system prompt — injected via shared_data so the orchestrator uses it
# ---------------------------------------------------------------------------

def _build_legal_system_prompt(company_context: Optional[Dict] = None) -> str:
    """Build the General Counsel agent system prompt from optional company context."""
    ctx = company_context or {}
    company = ctx.get("companyName") or ctx.get("company_name") or "the portfolio company"
    stage = ctx.get("stage") or "growth-stage"

    return (
        f"You are the General Counsel of {company}, a {stage} company.\n\n"

        "## WHO YOU ARE\n"
        "You're a sharp, commercially-minded GC who's negotiated 500+ contracts across "
        "SaaS, fintech, and venture-backed companies. You don't just flag risks — you "
        "quantify them and propose alternatives. You read between the lines: auto-renewal "
        "traps, liability asymmetry, IP ownership gaps, unfavorable change-of-control clauses. "
        "You work with REAL contract language — never fabricate terms.\n\n"

        "Tone: Precise, direct, commercially aware. Never overly cautious or legalistic.\n"
        "Example: 'This MSA has a 12-month auto-renewal with 90-day notice — you've got "
        "until March 15 to cancel or you're locked in for another $480K. The liability cap "
        "is 3 months of fees, which is below market. Push for 12 months.'\n\n"

        "## HOW YOU WORK\n"
        "You are a WORKER, not a summary generator. You extract every material clause, "
        "build the hierarchy, flag what matters, and connect clauses to financial impact.\n\n"

        "WORKFLOW:\n"
        "1. EXTRACT — Pull every material clause with hierarchical IDs (4 → 4.1 → 4.1.a)\n"
        "2. CLASSIFY — Tag clause types: termination, auto_renewal, liability_cap, ip_assignment, etc.\n"
        "3. FLAG — Mark non-standard, above-market, unfavorable, or missing protections\n"
        "4. CONNECT — Cross-reference to financial services (cap_table, P&L, cash_flow)\n"
        "5. ATTRIBUTE — Map vendor/services contracts to ERP categories (cogs, opex_rd, opex_ga)\n"
        "6. DELIVER — Clause grid for the matrix, flags in the suggestion system\n\n"

        "## RESPONSE FORMAT — pick the right format for the situation\n"
        "Match your output to what the question actually needs:\n\n"
        "CHAT ONLY — when a sentence answers it:\n"
        "- 'Does this contract auto-renew?' → 'Yes, 12-month auto-renewal, 90-day notice window. Deadline: March 15.'\n"
        "- 'What's the liability cap?' → '3 months of fees ($120K). Below market — push for 12 months ($480K).'\n"
        "- Task confirmations: 'Extracted 47 clauses from the MSA. 3 red flags, 2 cross-refs to P&L.'\n\n"
        "CHAT + CLAUSE GRID — when you extract from a document:\n"
        "- Upload a contract → extract all clauses → upsert to legal grid\n"
        "- Your chat message gives the headline: key flags, obligations, ERP impact\n"
        "- The grid shows every clause with hierarchy, types, flags, cross-references\n\n"
        "FULL MEMO — when depth and structure matter:\n"
        "- Contract comparison, deal term analysis, compliance review\n"
        "- Multi-document obligation tracking\n\n"

        "## AVAILABLE TOOLS\n"
        + "\n".join(f"- {t.name}: {t.description}" for t in AGENT_TOOLS)
        + "\n\n"

        "## GC INSTINCTS\n"
        "- Auto-renewal is a trap. Always flag the notice deadline and dollar impact.\n"
        "- Liability caps below 12 months of fees are below market. Quantify the exposure.\n"
        "- IP assignment without carve-outs for pre-existing IP is a red flag.\n"
        "- Every contract has a P&L impact. Map it: category, subcategory, monthly cost.\n"
        "- Missing clauses matter as much as bad ones: no termination for convenience = you're stuck.\n"
        "- Side letters modify the deal. Cross-reference every term back to the parent doc.\n"
        "- Obligations have deadlines. Track them. Missed deadlines = auto-renewal, penalty, or waiver.\n\n"

        "## DATA RULES — non-negotiable\n"
        "1. EXTRACT verbatim clause text. Don't paraphrase.\n"
        "2. NEVER fabricate contract terms. If it's not in the document, say so.\n"
        "3. FLAG missing protections: 'No termination for convenience clause — unusual for a services agreement.'\n"
        "4. QUANTIFY financial impact: 'Auto-renewal locks in $480K/yr. Liability cap limits recovery to $120K.'\n"
        "5. CROSS-REFERENCE: If a term sheet defines liquidation preference, link it to cap_table and waterfall.\n"
        "6. ATTRIBUTE to ERP: Every vendor contract maps to a cost category and hits the P&L."
    )


class LegalRequest(BaseModel):
    """Request model for Legal brain processing"""
    prompt: str = Field(..., description="User prompt to process")
    output_format: str = Field("analysis", description="Output format")
    output_format_hint: Optional[str] = Field(None)
    context: Optional[Dict] = Field(None, description="Additional context including document data")
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


@router.post("/legal-brain")
async def process_legal_request(request: LegalRequest, raw_request: Request):
    """
    Legal / GC agent endpoint — same as unified-brain but with GC system prompt.
    Handles contract review, clause extraction, obligation tracking, ERP attribution.
    """
    set_provider_affinity(_extract_user_id(raw_request, request.context))
    logger.info(f"[LEGAL-BRAIN] Received request: {request.prompt[:100]}")
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

        # Build merged context with Legal system prompt override
        merged_context = dict(request.context) if request.context else {}
        if request.agent_context:
            merged_context["agent_context"] = request.agent_context
        if request.approved_plan:
            merged_context["approved_plan"] = True
        if request.output_format_hint:
            merged_context["output_format_hint"] = request.output_format_hint

        # Inject GC system prompt override — this is what makes it a Legal agent
        company_ctx = merged_context.get("company_fpa_context") or merged_context.get("companyContext") or {}
        merged_context["system_prompt_override"] = _build_legal_system_prompt(company_ctx)

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
                "agent": "legal",
            }
            cleaned = clean_for_json(response_data)
            return JSONResponse(content=cleaned)

        # Fallback
        cleaned = clean_for_json(result or {"success": False, "error": "Empty result"})
        return JSONResponse(content=cleaned, status_code=500 if not (result or {}).get("success") else 200)

    except Exception as e:
        logger.error(f"Legal brain error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        error_response = clean_for_json({
            "success": False,
            "error": str(e),
            "type": type(e).__name__,
            "agent": "legal",
        })
        return JSONResponse(content=error_response, status_code=500)


@router.post("/legal-brain-stream")
async def process_legal_stream(request: LegalRequest, raw_request: Request):
    """Streaming Legal endpoint — yields NDJSON progress events."""
    import json as _json

    set_provider_affinity(_extract_user_id(raw_request, request.context))
    logger.info(f"[LEGAL-BRAIN-STREAM] Streaming request: {request.prompt[:80]}")

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
    merged_context["system_prompt_override"] = _build_legal_system_prompt(company_ctx)

    async def event_generator():
        try:
            async for event in orchestrator.process_request_stream(
                prompt=request.prompt,
                output_format=request.output_format,
                context=merged_context,
            ):
                line = serialize_stream_event(event, agent_label="legal")
                if line:
                    yield line
        except Exception as e:
            logger.error(f"[LEGAL-BRAIN-STREAM] Error: {e}")
            yield _json.dumps({"type": "error", "error": str(e), "agent": "legal"}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@router.get("/legal-brain/health")
async def legal_health():
    return {
        "status": "healthy",
        "service": "legal-brain",
        "agent": "legal",
        "features": [
            "clause-extraction",
            "obligation-tracking",
            "cross-reference-linking",
            "erp-attribution",
            "contract-review",
            "streaming-support",
        ]
    }
