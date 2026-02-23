"""
Document process service: backend-agnostic single-doc extraction.
Runs full flow in-process: download from storage, extract text (PDF/DOCX),
extract structured data via model_router + JSON schema, update metadata repo.
No subprocess.
"""

import asyncio
import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from app.abstractions.document_metadata import DocumentMetadataRepo
from app.abstractions.storage import DocumentBlobStorage

logger = logging.getLogger(__name__)

# Startup check: pypdf required for PDF extraction
def _check_pypdf() -> None:
    try:
        from pypdf import PdfReader  # noqa: F401
    except ImportError:
        logger.warning(
            "pypdf not installed; PDF text extraction will fail. "
            "Run: pip install pypdf>=4.0.0"
        )


_check_pypdf()  # Run on module load

# OCR availability flag
_OCR_AVAILABLE = False
try:
    import pytesseract  # noqa: F401
    from pdf2image import convert_from_path  # noqa: F401
    _OCR_AVAILABLE = True
except ImportError:
    logger.info(
        "pytesseract/pdf2image not installed; OCR fallback disabled. "
        "Run: pip install pytesseract pdf2image  (and install Tesseract + Poppler system deps)"
    )

# Document extraction JSON schema (fields we ask the model to return) – used for other doc types
# Note: memos, updates, board decks, board transcripts use signal/memo schemas below
# Flat schema for pitch_deck, other — market_size only in investment_memo
DOCUMENT_EXTRACTION_SCHEMA = {
    "company_name": "string or null",
    "revenue": "number or null (USD)",
    "arr": "number or null (USD)",
    "stage": "string e.g. Seed, Series A",
    "total_funding": "number or null (USD)",
    "valuation": "number or null (USD)",
    "key_metrics": "array of strings",
    "summary": "string",
    "sector": "string or null",
    "target_market": "string or null",
    "business_model": "string or null",
    "red_flags": "array of strings (concerns, risks, concerning language)",
    "value_explanations": "object: { [metric_key]: string } — '\"source quote\" → why → metric change'. e.g. arr: '\"Q3 exceeded plan\" → accelerating sales → ARR up to $1.2M'",
}

# Company-update signal schema – for monthly_update, board_deck, board_transcript
# SERVICE_ALIGNED: business_model, sector, category for valuation/analysis
# new_hires: prefer structured array e.g. [{"role": "Senior PM", "department": "product"}] or string array
COMPANY_UPDATE_SIGNAL_SCHEMA = {
    "company_name": "string or null (optional)",
    "summary": "string (optional)",
    "business_model": "string or null (e.g. SaaS, AI-first, services, rollup—for valuation multiples)",
    "sector": "string or null (e.g. Fintech, Healthcare)",
    "category": "string or null (e.g. saas, ai_first, fintech—for business model detection)",
    "business_updates": {
        "product_updates": "array of strings",
        "achievements": "array of strings",
        "challenges": "array of strings",
        "risks": "array of strings",
        "key_milestones": "array of strings",
        "asks": "array of strings",
        "latest_update": "string (one-line summary of what changed this period — NOT a generic company description)",
        "defensive_language": "array of strings (hedging, caveats, excuses)",
    },
    "operational_metrics": {
        "new_hires": "array of strings or objects. Prefer objects: [{role, department}] e.g. 'Senior PM, product'",
        "headcount": "number or null",
        "customer_count": "number or null",
        "enterprise_customers": "number or null",
        "smb_customers": "number or null",
    },
    "extracted_entities": {
        "competitors_mentioned": "array of strings",
        "industry_terms": "array of strings",
        "partners_mentioned": "array of strings",
    },
    "red_flags": "array of strings (explicit concerns, risks, concerning language)",
    "implications": "array of strings (reading between the lines: inferred items e.g. 'option pool likely expanded given senior product hire')",
    "period_date": "string (ISO date when document period is indicated)",
    "financial_metrics": {
        "arr": "number or null (USD)",
        "revenue": "number or null (USD)",
        "mrr": "number or null (USD)",
        "burn_rate": "number or null (USD)",
        "runway_months": "number or null",
        "cash_balance": "number or null (USD)",
        "gross_margin": "number or null (0-1 or 0-100)",
        "growth_rate": "number or null (e.g. 0.5 for 50%)",
        "customer_count": "number or null",
    },
    "impact_estimates": {
        "_description": "For EACH qualitative signal above, estimate its material impact on core financial metrics. This is the transformation layer — qualitative info becomes quantitative suggestions.",
        "estimated_arr_impact": "number or null (USD delta, e.g. +500000 if 'landed Fortune 500 client', -300000 if 'lost key customer')",
        "estimated_burn_impact": "number or null (USD/mo delta, e.g. +60000 if '3 new hires', -100000 if 'cut 20% of team')",
        "estimated_runway_impact": "number or null (months delta, e.g. -3 if 'burn increased significantly', +12 if 'raised $5M')",
        "estimated_headcount_impact": "number or null (delta, e.g. +5 if 'hired 5 engineers', -10 if 'RIF'd 10 people')",
        "estimated_cash_impact": "number or null (USD delta, e.g. +5000000 if 'closed Series B')",
        "estimated_valuation_impact": "number or null (USD delta, e.g. +20000000 if 'raised at 3x last round')",
        "estimated_growth_rate_change": "number or null (pct point delta, e.g. +0.1 if 'accelerating growth', -0.05 if 'growth slowing')",
        "impact_reasoning": "object: { [metric_key]: string } — '\"verbatim quote\" → why → metric change'. e.g. '\"landed 3 enterprise logos\" → ~$200K ACV each → ARR +$600K'",
    },
    "value_explanations": "object: { [metric_key]: string } — '\"source quote\" → why → metric change'. e.g. arr: '\"hit $1.2M ARR\" → explicit figure → ARR is $1.2M'; burn_rate: '\"hired 5 senior engineers\" → ~$25K/mo each → burn +$125K/mo'",
}

# Investment memo schema – for investment_memo
INVESTMENT_MEMO_SCHEMA = {
    "company_name": "string or null",
    "investment_date": "string or null (ISO)",
    "round": "string e.g. Series A",
    "valuation_pre_money": "number or null (USD)",
    "deal_terms_summary": "string or null",
    "memo_assumptions": "object (nested key assumptions from the memo)",
    "revenue": "number or null (USD)",
    "arr": "number or null (USD)",
    "runway_months": "number or null",
    "stage": "string or null",
    "total_funding": "number or null (USD)",
    "valuation": "number or null (USD)",
    "key_metrics": "array of strings",
    "summary": "string",
    "sector": "string or null",
    "target_market": "string or null",
    "business_model": "string or null",
    "market_size": {
        "tam_usd": "number or null (USD)",
        "sam_usd": "number or null (USD)",
        "som_usd": "number or null (USD)",
        "tam_description": "string or null",
        "methodology": "string or null",
    },
    "red_flags": "array of strings (concerns, risks)",
    "value_explanations": "object: { [metric_key]: string } — '\"source quote\" → why → metric change'. e.g. arr: '\"Memo states $2M ARR\" → explicit figure → ARR is $2M'",
}


def _iso_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _ocr_pdf(path: str) -> str:
    """
    OCR a PDF using pytesseract + pdf2image.
    Converts each page to an image and runs Tesseract OCR.
    Returns extracted text or empty string on failure.
    """
    if not _OCR_AVAILABLE:
        logger.warning("OCR requested but pytesseract/pdf2image not installed")
        return ""
    try:
        import pytesseract
        from pdf2image import convert_from_path

        logger.info("Running OCR on PDF: %s", path)
        images = convert_from_path(path, dpi=300)
        text_parts: list[str] = []
        for i, img in enumerate(images):
            try:
                page_text = pytesseract.image_to_string(img, lang="eng")
                if page_text and page_text.strip():
                    text_parts.append(page_text.strip())
            except Exception as e:
                logger.debug("OCR failed on page %d: %s", i + 1, e)
        result = "\n\n".join(text_parts).strip()
        if result:
            logger.info("OCR extracted %d chars from %d pages", len(result), len(images))
        else:
            logger.warning("OCR produced no text from %d pages", len(images))
        return result
    except Exception as e:
        logger.exception("OCR failed for %s: %s", path, e)
        return ""


# Minimum chars to consider pypdf extraction successful (avoids header-only extracts)
_MIN_TEXT_THRESHOLD = 50


def _text_from_file(path: str, suffix: str) -> str:
    """
    Extract plain text from a file. Supports PDF (pypdf with OCR fallback) and DOCX (python-docx).
    For PDFs: tries pypdf first, falls back to OCR if text is empty or too short.
    Returns empty string for unsupported types or on error.
    """
    path_obj = Path(path)
    if not path_obj.exists():
        logger.warning("_text_from_file: path does not exist %s", path)
        return ""

    ext = (suffix or path_obj.suffix or "").lower().lstrip(".")
    text_parts: list[str] = []

    try:
        if ext in ("pdf",):
            from pypdf import PdfReader
            reader = PdfReader(path)
            for page in reader.pages:
                try:
                    t = page.extract_text()
                    if t:
                        text_parts.append(t)
                except Exception as e:
                    logger.debug("pypdf page extract: %s", e)
            text = "\n\n".join(text_parts).strip()

            # If pypdf got enough text, use it
            if len(text) >= _MIN_TEXT_THRESHOLD:
                return text

            # Otherwise try OCR fallback
            logger.info(
                "pypdf extracted only %d chars (threshold %d), attempting OCR fallback",
                len(text), _MIN_TEXT_THRESHOLD,
            )
            ocr_text = _ocr_pdf(path)
            if ocr_text:
                return ocr_text

            # Return whatever pypdf got (may be empty)
            return text

        if ext in ("docx", "doc"):
            try:
                from docx import Document as DocxDocument
                doc = DocxDocument(path)
                return "\n\n".join(p.text for p in doc.paragraphs if p.text).strip()
            except ImportError:
                logger.warning("python-docx not installed; cannot extract .docx text")
                return ""

        logger.warning("_text_from_file: unsupported extension %s", ext)
        return ""
    except Exception as e:
        logger.exception("_text_from_file failed for %s: %s", path, e)
        return ""


def _get_memo_context_for_company(
    document_repo: DocumentMetadataRepo,
    company_id: str,
    fund_id: Optional[str] = None,
) -> Optional[str]:
    """
    Get a short reference context string from the latest investment memo for this company.
    Used when processing monthly_update/board_deck so extraction can be "relative to memo".
    """
    filters: Dict[str, Any] = {
        "company_id": company_id,
        "document_type": "investment_memo",
        "status": "completed",
    }
    if fund_id:
        filters["fund_id"] = fund_id
    docs = document_repo.list_(filters=filters, limit=20, offset=0)
    if not docs:
        return None
    # Sort by processed_at desc and take latest
    with_ts = [(d, (d.get("processed_at") or "") or "0") for d in docs]
    with_ts.sort(key=lambda x: x[1], reverse=True)
    doc = with_ts[0][0]
    extracted = doc.get("extracted_data") or {}
    if isinstance(extracted, str):
        try:
            extracted = json.loads(extracted)
        except Exception:
            extracted = {}
    if not isinstance(extracted, dict):
        return None
    fm = extracted.get("financial_metrics") or {}
    arr = extracted.get("arr") or fm.get("arr")
    runway = extracted.get("runway_months") or fm.get("runway_months")
    rev = extracted.get("revenue") or fm.get("revenue")
    val = extracted.get("valuation_pre_money") or extracted.get("valuation") or fm.get("valuation")
    processed_at = doc.get("processed_at") or ""
    parts = ["Baseline from investment memo (same company):"]
    if arr is not None:
        parts.append(f" ARR ${arr:,.0f}" if isinstance(arr, (int, float)) else f" ARR {arr}")
    if runway is not None:
        parts.append(f", runway {runway} months")
    if rev is not None:
        parts.append(f", revenue ${rev:,.0f}" if isinstance(rev, (int, float)) else f", revenue {rev}")
    if val is not None:
        parts.append(f", valuation ${val:,.0f}" if isinstance(val, (int, float)) else f", valuation {val}")
    if processed_at:
        parts.append(f", as of {processed_at[:10]}")
    return "".join(parts) if len(parts) > 1 else None


def _signal_first_prompt(text: str, document_type: str, schema_desc: str, memo_context: Optional[str] = None) -> tuple:
    """Build system and user prompt for signal-first extraction (monthly_update / board_deck / board_transcript)."""
    system_prompt = (
        "You are a VC document analyst and transformation engine. Extract structured signals from company updates, board decks, and board transcripts. "
        "You have TWO jobs:\n"
        "1. EXTRACT: Pull explicit numbers from text into financial_metrics (ARR, burn, headcount, etc.).\n"
        "2. TRANSFORM: Read qualitative prose — even when NO numbers are stated — and estimate the numeric impact in impact_estimates.\n"
        "The transform step is the critical one. Most board updates are prose, not spreadsheets. "
        "Every qualitative signal (hire, product launch, expansion, customer win/loss, risk, pivot) implies a financial impact — estimate it. "
        "RULE: impact_estimates MUST have at least 2 non-null numeric values. A document with zero impact estimates is a failure. "
        "RULE: impact_reasoning MUST attribute each estimate to a source quote: '\"quote\" → why → metric change'. "
        "Return a single JSON object. Use null for truly unknown; use empty arrays for missing lists.\n"
        "CURRENCY CONVERSION (always convert to USD before storing any numeric value):\n"
        "- £ (GBP) → multiply by 1.27\n"
        "- € (EUR) → multiply by 1.09\n"
        "- ¥ (JPY) → divide by 154\n"
        "- ₹ (INR) → divide by 84\n"
        "- Note the original currency and amount in value_explanations (e.g. '£2M → $2.54M USD')."
    )
    user_parts = [
        f"Document type: {document_type}.",
        "Extract signals: product_updates, achievements, challenges, risks, asks, defensive_language, key_milestones.",
        "Then operational_metrics: new_hires (prefer objects with role/department e.g. 'Senior PM, product'), headcount, customer_count.",
        "Then extracted_entities: competitors_mentioned, industry_terms, partners_mentioned.",
        "Extract business_model, sector, category when inferable from context (needed for valuation and analysis).",
        "Extract red_flags: array of explicit concerns, risks, or concerning language.",
        "Extract implications: array of 'reading between the lines' items (e.g. 'option pool likely expanded given senior product hire').",
        "",
        "PATH 1 — Explicit numbers → financial_metrics:",
        "Any number stated in the text ('we hit $1.2M ARR', 'burn is ~$80K/mo', '45 employees') goes DIRECTLY into financial_metrics.",
        "",
        "PATH 2 — Qualitative signals → impact_estimates:",
        "Most updates are prose with NO explicit numbers. Reason from signal to magnitude using the methodology below.",
        "For each estimate, impact_reasoning MUST follow: '\"verbatim quote\" → why → metric change'.",
        "MANDATORY: At least 2 non-null impact_estimates per document. Rough is better than null.",
        "",
        "=== IMPACT REASONING METHODOLOGY ===",
        "Work through these steps for every qualitative signal before producing a number:",
        "",
        "STEP 1 — CLASSIFY the signal:",
        "  Revenue signals: customer win/loss/expansion, pricing change, new segment, churn, upsell, product launch",
        "  Cost signals: hiring, departures, office moves, vendor changes, raises, layoffs",
        "  Balance sheet signals: fundraise, debt, large purchases, runway changes",
        "  Growth trajectory signals: market expansion, pivot, acceleration/deceleration, PMF indicators",
        "",
        "STEP 2 — ANCHOR to company scale:",
        "  If a BASELINE ANCHOR is provided above, USE IT. All estimates must be proportional to the company\'s actual size.",
        "  A \'big enterprise deal\' means ~$50-100K for a $500K ARR startup, but ~$500K-2M for a $50M ARR company.",
        "  If no baseline exists, infer approximate scale from clues in the document itself:",
        "    - Team size, customer logos, round stage, office mentions all signal scale",
        "    - 10-person Series A startup is likely $500K-3M ARR",
        "    - 200-person post-Series C company is likely $20-80M ARR",
        "  State your assumed scale in impact_reasoning so the estimate is auditable.",
        "",
        "STEP 3 — SIZE the impact as a proportion of scale:",
        "  Revenue impacts — think in % of current ARR:",
        "    Single new SMB customer: +1-3% of ARR    |  Single enterprise deal: +5-15% of ARR",
        "    New segment/market entry: +10-25% over 12mo  |  Key customer lost: -3-10% of ARR",
        "    Pricing increase: +5-15% of ARR  |  New product/feature upsell: +5-20% over 12mo",
        "  Burn impacts — think in per-head monthly cost:",
        "    Junior hire: +$8-15K/mo  |  Senior/exec hire: +$15-30K/mo  |  Departure: reverse",
        "    Batch hiring (\'scaling the team\'): estimate headcount x avg cost for role level",
        "  Growth rate changes — percentage-point shifts:",
        "    Acceleration (strong PMF): +5-15 ppt  |  Deceleration (churn, pivot): -5-20 ppt",
        "    Segment shift (SMB to enterprise): -5-10 ppt short-term",
        "",
        "STEP 4 — CONVERT to dollar amount and show your math:",
        "  proportion x anchored scale = dollar impact.",
        "  In impact_reasoning, format as: \'\"verbatim quote\" → [reasoning at assumed scale] → [metric] [direction] $Y\'",
        "",
        "=== EXAMPLES (full reasoning chain) ===",
        "",
        "Quote: \'We expanded into the enterprise segment\'",
        "  Signal: new segment entry (revenue). Anchor: ~$2M ARR from baseline. Size: +10-20% of ARR.",
        "  estimated_arr_impact: +300000",
        "  impact_reasoning: \'\"expanded into enterprise segment\" → new segment at ~$2M baseline, +10-20% yr1 → ARR +$300K\'",
        "",
        "Quote: \'Signed LOI with two Fortune 500 companies\'",
        "  Signal: customer win (revenue), LOI not closed. F500 contracts $200-400K. Discount: LOI-to-close ~60%.",
        "  estimated_arr_impact: +400000",
        "  impact_reasoning: \'\"signed LOI with two Fortune 500\" → 2 x ~$300K ACV, ~60% close rate → ARR +$400K\'",
        "",
        "Quote: \'Our head of engineering left last month\'",
        "  Signal: senior departure (cost). Per-head: senior eng leader ~$25K/mo fully loaded.",
        "  estimated_burn_impact: -25000, estimated_headcount_impact: -1",
        "  impact_reasoning: \'\"head of engineering left\" → senior eng exec ~$25K/mo loaded → burn -$25K/mo, headcount -1\'",
        "",
        "Quote: \'Pivoting from SMB to mid-market\'",
        "  Signal: segment shift (growth). Short-term churn from SMB base, slower mid-market cycles.",
        "  estimated_growth_rate_change: -0.10, estimated_arr_impact: -100000",
        "  impact_reasoning: \'\"pivoting from SMB to mid-market\" → 5-15% SMB churn + slower cycles → growth -10 ppt, ARR -$100K near-term\'",
        "",
        "Quote: \'Burn is ~$80K/mo\'",
        "  EXPLICIT number — put 80000 in BOTH financial_metrics.burn_rate AND estimated_burn_impact.",
        "",
        "For each extracted metric, add to value_explanations: '\"source quote\" → why → metric change'.",
        "For extrapolated values, include the doc excerpt and inference in value_explanations.",
        "",
        "Schema (JSON):",
        schema_desc,
        "",
        "Document text:",
        "---",
        (text[:120000] if len(text) > 120000 else text),
        "---",
        "Return only the JSON object, no markdown or explanation.",
    ]
    if memo_context:
        user_parts.insert(1, f"BASELINE ANCHOR (same company, use for scaling all estimates): {memo_context}")
    user_prompt = "\n".join(user_parts)
    return system_prompt, user_prompt


def _memo_prompt(text: str, schema_desc: str) -> tuple:
    """Build system and user prompt for investment memo extraction."""
    system_prompt = (
        "You are a VC document analyst. Extract structured data from an investment memo. "
        "Capture company_name, investment_date, round, valuation_pre_money, deal_terms_summary, "
        "and memo_assumptions (nested object of key assumptions). "
        "Include financial baseline when stated: ARR, revenue, runway_months. "
        "Extract market_size (tam_usd, sam_usd, som_usd) when stated, with tam_description/methodology if available. "
        "Extract red_flags as array of explicit concerns, risks, or concerning language. "
        "For each extracted metric, add to value_explanations: '\"source quote\" → why → metric change', e.g. arr: '\"$2M ARR as of Q2\" → explicit figure → ARR is $2M'. "
        "Return a single JSON object. Use null when unknown.\n"
        "CURRENCY CONVERSION (always convert to USD before storing any numeric value):\n"
        "- £ (GBP) → multiply by 1.27\n"
        "- € (EUR) → multiply by 1.09\n"
        "- ¥ (JPY) → divide by 154\n"
        "- ₹ (INR) → divide by 84\n"
        "- Note the original currency and amount in value_explanations (e.g. '£2M → $2.54M USD')."
    )
    user_prompt = (
        f"Extract and return a JSON object matching this schema:\n{schema_desc}\n\n"
        f"Document text:\n---\n{text[:120000]}\n---\n\n"
        "Return only the JSON object, no markdown or explanation."
    )
    return system_prompt, user_prompt


def _flat_prompt(text: str, document_type: str, schema_desc: str) -> tuple:
    """Build system and user prompt for flat schema (pitch_deck / other)."""
    system_prompt = (
        "You are a VC document analyst. Extract structured data from the given document text. "
        "Return a single JSON object with exactly these keys (use null when unknown): "
        "company_name, revenue, arr, stage, total_funding, valuation, key_metrics (array of strings), "
        "summary, sector, target_market, business_model. "
        "Numbers must be numeric (no currency symbols in values). key_metrics is an array of short strings. "
        "For each extracted metric, add to value_explanations: '\"source quote\" → why → metric change', e.g. arr: '\"$1.2M ARR\" → explicit figure → ARR is $1.2M'.\n"
        "CURRENCY CONVERSION (always convert to USD before storing any numeric value):\n"
        "- £ (GBP) → multiply by 1.27\n"
        "- € (EUR) → multiply by 1.09\n"
        "- ¥ (JPY) → divide by 154\n"
        "- ₹ (INR) → divide by 84\n"
        "- Note the original currency and amount in value_explanations (e.g. '£2M → $2.54M USD')."
    )
    user_prompt = (
        f"Document type: {document_type}\n\n"
        f"Extract and return a JSON object matching this schema:\n{schema_desc}\n\n"
        f"Document text:\n---\n{text[:120000]}\n---\n\n"
        "Return only the JSON object, no markdown or explanation."
    )
    return system_prompt, user_prompt


async def _extract_document_structured_async(
    text: str,
    document_type: str,
    memo_context: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Call model_router with a prompt and JSON schema to extract structured data from document text.
    Branches by document_type: monthly_update/board_deck use signal schema; investment_memo uses memo schema; else flat.
    Returns a dict suitable for extracted_data (normalized so financial_metrics and period_date exist where applicable).
    """
    from app.services.model_router import get_model_router, ModelCapability

    router = get_model_router()
    doc_type = (document_type or "other").strip().lower()

    if doc_type == "investment_memo":
        schema_desc = json.dumps(INVESTMENT_MEMO_SCHEMA, indent=2)
        system_prompt, user_prompt = _memo_prompt(text, schema_desc)
        empty = _empty_memo_extraction()
    else:
        # ALL non-memo docs use signal-first extraction — extracts business_updates,
        # operational_metrics, impact_estimates, financial_metrics, etc.
        schema_desc = json.dumps(COMPANY_UPDATE_SIGNAL_SCHEMA, indent=2)
        system_prompt, user_prompt = _signal_first_prompt(text, document_type, schema_desc, memo_context)
        empty = _empty_signal_extraction()

    try:
        result = await router.get_completion(
            prompt=user_prompt,
            system_prompt=system_prompt,
            capability=ModelCapability.STRUCTURED,
            max_tokens=4096,
            temperature=0.2,
            json_mode=True,
            caller_context="document_process_service.extract_structured",
        )
        raw = (result.get("response") or "").strip()
        if not raw:
            return empty

        parsed = _extract_json_object(raw)
        if isinstance(parsed, dict):
            return _normalize_extraction(parsed, document_type=document_type)
        return empty
    except Exception as e:
        logger.exception("extract_document_structured failed: %s", e)
        if doc_type == "investment_memo":
            out = _empty_memo_extraction()
        else:
            out = _empty_signal_extraction()
        out["_extraction_error"] = str(e)
        return out


def _extract_json_object(raw: str) -> dict:
    """Robustly extract a JSON object from an LLM response.

    Handles preamble text, code fences, and the ``[`` prefill artefact
    that can cause Claude to emit ``[PROCESSING DOCUMENT...]`` before the
    actual JSON payload.
    """
    # 1. Strip code fences anywhere in the string
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()

    # 2. Try direct parse first (fast path)
    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 3. Locate the first '{' and try to parse from there
    start = cleaned.find("{")
    if start != -1:
        # Find matching closing brace by trying successively shorter slices
        depth = 0
        end = None
        for i in range(start, len(cleaned)):
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end is not None:
            try:
                return json.loads(cleaned[start:end])
            except json.JSONDecodeError:
                pass

    raise json.JSONDecodeError("No JSON object found in response", raw, 0)


def _empty_extraction(error: Optional[str] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "company_name": None,
        "revenue": None,
        "arr": None,
        "stage": None,
        "total_funding": None,
        "valuation": None,
        "key_metrics": [],
        "summary": "",
        "sector": None,
        "target_market": None,
        "business_model": None,
        "value_explanations": {},
    }
    if error:
        out["_extraction_error"] = error
    return out


def _empty_signal_extraction(error: Optional[str] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "company_name": None,
        "summary": "",
        "business_updates": {
            "product_updates": [],
            "achievements": [],
            "challenges": [],
            "risks": [],
            "key_milestones": [],
            "asks": [],
            "latest_update": "",
            "defensive_language": [],
        },
        "operational_metrics": {
            "new_hires": [],
            "headcount": None,
            "customer_count": None,
            "enterprise_customers": None,
            "smb_customers": None,
        },
        "extracted_entities": {
            "competitors_mentioned": [],
            "industry_terms": [],
            "partners_mentioned": [],
        },
        "red_flags": [],
        "implications": [],
        "period_date": None,
        "financial_metrics": {},
        "value_explanations": {},
    }
    if error:
        out["_extraction_error"] = error
    return out


def _empty_memo_extraction(error: Optional[str] = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "company_name": None,
        "investment_date": None,
        "round": None,
        "valuation_pre_money": None,
        "deal_terms_summary": None,
        "memo_assumptions": {},
        "revenue": None,
        "arr": None,
        "runway_months": None,
        "stage": None,
        "total_funding": None,
        "valuation": None,
        "key_metrics": [],
        "summary": "",
        "sector": None,
        "target_market": None,
        "business_model": None,
        "market_size": None,
        "red_flags": [],
        "value_explanations": {},
    }
    if error:
        out["_extraction_error"] = error
    return out


def _ensure_numeric(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return float(val)
    try:
        s = str(val).replace(",", "").replace("$", "").strip()
        return float(s) if s else None
    except (ValueError, TypeError):
        return None


def _normalize_extraction(d: Dict[str, Any], document_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Normalize extraction output for DB: ensure financial_metrics and period_date exist;
    map flat revenue/arr into financial_metrics for backward compatibility.
    """
    doc_type = (document_type or "other").strip().lower()

    # —— Signal shape (monthly_update / board_deck / board_transcript) ——
    if doc_type != "investment_memo":
        out = dict(d)
        bu = out.get("business_updates")
        if not isinstance(bu, dict):
            out["business_updates"] = (_empty_signal_extraction().get("business_updates") or {}).copy()
        else:
            for key in ("product_updates", "achievements", "challenges", "risks", "key_milestones", "asks", "defensive_language"):
                if key in out["business_updates"] and not isinstance(out["business_updates"][key], list):
                    out["business_updates"][key] = []
            if "latest_update" not in out["business_updates"]:
                out["business_updates"]["latest_update"] = ""
        om = out.get("operational_metrics")
        if not isinstance(om, dict):
            out["operational_metrics"] = (_empty_signal_extraction().get("operational_metrics") or {}).copy()
        ee = out.get("extracted_entities")
        if not isinstance(ee, dict):
            out["extracted_entities"] = (_empty_signal_extraction().get("extracted_entities") or {}).copy()
        fm = out.get("financial_metrics")
        if not isinstance(fm, dict):
            fm = {}
        out["financial_metrics"] = {
            "arr": _ensure_numeric(fm.get("arr")),
            "revenue": _ensure_numeric(fm.get("revenue")),
            "mrr": _ensure_numeric(fm.get("mrr")),
            "burn_rate": _ensure_numeric(fm.get("burn_rate")),
            "runway_months": _ensure_numeric(fm.get("runway_months")),
            "cash_balance": _ensure_numeric(fm.get("cash_balance")),
            "gross_margin": _ensure_numeric(fm.get("gross_margin")),
            "growth_rate": _ensure_numeric(fm.get("growth_rate")),
            "customer_count": _ensure_numeric(fm.get("customer_count")),
        }

        out["period_date"] = out.get("period_date") if isinstance(out.get("period_date"), str) else None
        # Preserve impact_estimates from LLM extraction (transformation layer)
        ie = out.get("impact_estimates")
        if isinstance(ie, dict):
            out["impact_estimates"] = {
                "estimated_arr_impact": _ensure_numeric(ie.get("estimated_arr_impact")),
                "estimated_burn_impact": _ensure_numeric(ie.get("estimated_burn_impact")),
                "estimated_runway_impact": _ensure_numeric(ie.get("estimated_runway_impact")),
                "estimated_headcount_impact": _ensure_numeric(ie.get("estimated_headcount_impact")),
                "estimated_cash_impact": _ensure_numeric(ie.get("estimated_cash_impact")),
                "estimated_valuation_impact": _ensure_numeric(ie.get("estimated_valuation_impact")),
                "estimated_growth_rate_change": _ensure_numeric(ie.get("estimated_growth_rate_change")),
                "impact_reasoning": ie.get("impact_reasoning") if isinstance(ie.get("impact_reasoning"), dict) else {},
            }
        else:
            out["impact_estimates"] = None
        # Unified shape for suggestions: add company_info, growth_metrics, runway_and_cash
        out["company_info"] = {
            "name": out.get("company_name"),
            "sector": out.get("sector"),
            "stage": out.get("stage"),
            "valuation": out.get("valuation"),
            "funding_raised": out.get("total_funding") or out.get("total_raised"),
            "industry": out.get("sector"),
            "business_model": out.get("business_model"),
            "category": out.get("category"),
        }
        g = _ensure_numeric(out["financial_metrics"].get("growth_rate"))
        growth_annual = (g * 100 if g is not None and g <= 2 else g) if g is not None else None
        out["growth_metrics"] = {
            "current_arr": out["financial_metrics"].get("arr"),
            "revenue_growth_annual_pct": growth_annual,
            "revenue_growth_monthly_pct": None,
        }
        out["runway_and_cash"] = {
            "runway_months": out["financial_metrics"].get("runway_months"),
            "cash_in_bank": out["financial_metrics"].get("cash_balance"),
            "burn_rate": out["financial_metrics"].get("burn_rate"),
        }
        # Canonical: market_size, red_flags, implications for suggestions/analysis
        out["red_flags"] = [x for x in (out.get("red_flags") or []) if isinstance(x, str)]
        out["implications"] = [x for x in (out.get("implications") or []) if isinstance(x, str)]
        ms = out.get("market_size")
        if isinstance(ms, dict) and any(ms.get(k) is not None for k in ("tam_usd", "sam_usd", "som_usd")):
            out["market_size"] = {
                "tam_usd": _ensure_numeric(ms.get("tam_usd")),
                "sam_usd": _ensure_numeric(ms.get("sam_usd")),
                "som_usd": _ensure_numeric(ms.get("som_usd")),
                "tam_description": ms.get("tam_description") if isinstance(ms.get("tam_description"), str) else None,
                "methodology": ms.get("methodology") if isinstance(ms.get("methodology"), str) else None,
            }
        else:
            out["market_size"] = None
        ve = out.get("value_explanations") if isinstance(out.get("value_explanations"), dict) else {}
        out["value_explanations"] = ve
        if ve:
            logger.debug("value_explanations (signal): %s", list(ve.keys()))
        return out

    # —— Memo shape ——
    if doc_type == "investment_memo":
        keys = set(INVESTMENT_MEMO_SCHEMA.keys())
        out = {}
        for k in keys:
            v = d.get(k)
            if k == "key_metrics" and not isinstance(v, list):
                out[k] = [str(x) for x in (v or [])] if isinstance(v, (list, tuple)) else []
            elif k == "memo_assumptions":
                out[k] = v if isinstance(v, dict) else {}
            elif k in ("revenue", "arr", "total_funding", "valuation", "valuation_pre_money", "runway_months") and v is not None:
                out[k] = _ensure_numeric(v)
            else:
                out[k] = v if isinstance(v, (str, int, float, list, dict, type(None))) else (str(v) if v is not None else None)
        fm = {
            "arr": out.get("arr") or _ensure_numeric(d.get("arr")),
            "revenue": out.get("revenue") or _ensure_numeric(d.get("revenue")),
            "runway_months": out.get("runway_months") or _ensure_numeric(d.get("runway_months")),
            "burn_rate": None,
            "cash_balance": None,
            "gross_margin": None,
            "growth_rate": None,
        }
        out["financial_metrics"] = fm
        out["period_date"] = out.get("investment_date") or _iso_now()[:10]
        out["company_info"] = {
            "name": out.get("company_name"),
            "sector": out.get("sector"),
            "stage": out.get("stage"),
            "valuation": out.get("valuation") or out.get("valuation_pre_money"),
            "funding_raised": out.get("total_funding"),
            "industry": out.get("sector"),
        }
        out["growth_metrics"] = {
            "current_arr": out.get("arr"),
            "revenue_growth_annual_pct": None,
            "revenue_growth_monthly_pct": None,
        }
        out["business_updates"] = {
            "latest_update": (out.get("summary") or "")[:2000] if out.get("summary") else "",
            "product_updates": out.get("key_metrics") if isinstance(out.get("key_metrics"), list) else [],
            "achievements": [],
            "challenges": [],
            "risks": [],
            "key_milestones": [],
            "asks": [],
            "defensive_language": [],
        }
        out["runway_and_cash"] = {
            "runway_months": out.get("runway_months") or fm.get("runway_months"),
            "cash_in_bank": None,
            "burn_rate": None,
        }
        # Canonical: market_size, red_flags for suggestions/analysis
        out["red_flags"] = [x for x in (out.get("red_flags") or d.get("red_flags") or []) if isinstance(x, str)]
        ms = out.get("market_size") or d.get("market_size")
        if isinstance(ms, dict) and any(ms.get(k) is not None for k in ("tam_usd", "sam_usd", "som_usd")):
            out["market_size"] = {
                "tam_usd": _ensure_numeric(ms.get("tam_usd")),
                "sam_usd": _ensure_numeric(ms.get("sam_usd")),
                "som_usd": _ensure_numeric(ms.get("som_usd")),
                "tam_description": ms.get("tam_description") if isinstance(ms.get("tam_description"), str) else None,
                "methodology": ms.get("methodology") if isinstance(ms.get("methodology"), str) else None,
            }
        else:
            out["market_size"] = None
        ve = out.get("value_explanations") if isinstance(out.get("value_explanations"), dict) else {}
        out["value_explanations"] = ve
        if ve:
            logger.debug("value_explanations (memo): %s", list(ve.keys()))
        return out

    # —— Flat shape (other doc types) ——
    keys = set(DOCUMENT_EXTRACTION_SCHEMA.keys())
    out = {}
    for k in keys:
        v = d.get(k)
        if k == "key_metrics" and not isinstance(v, list):
            out[k] = [str(x) for x in (v or [])] if isinstance(v, (list, tuple)) else []
        elif k == "red_flags" and isinstance(v, list):
            out[k] = [x for x in v if isinstance(x, str)]
        elif k == "market_size" and isinstance(v, dict):
            out[k] = v  # normalized below
        elif k in ("revenue", "arr", "total_funding", "valuation") and v is not None:
            out[k] = _ensure_numeric(v)
        else:
            out[k] = v if isinstance(v, (str, int, float, list, dict, type(None))) else (str(v) if v is not None else None)
    out["financial_metrics"] = {
        "arr": out.get("arr"),
        "revenue": out.get("revenue"),
        "mrr": None,
        "burn_rate": None,
        "runway_months": None,
        "cash_balance": None,
        "gross_margin": None,
        "growth_rate": None,
    }
    out["period_date"] = _iso_now()[:10]
    # Unified shape for suggestions/analysis: company_info and growth_metrics
    out["company_info"] = {
        "name": out.get("company_name"),
        "sector": out.get("sector"),
        "stage": out.get("stage"),
        "valuation": out.get("valuation"),
        "funding_raised": out.get("total_funding"),
        "industry": out.get("sector"),
    }
    out["growth_metrics"] = {
        "current_arr": out.get("arr"),
        "revenue_growth_annual_pct": None,
        "revenue_growth_monthly_pct": None,
    }
    # business_updates placeholder so suggestions can read latest_update from summary
    out["business_updates"] = {
        "latest_update": (out.get("summary") or "")[:2000] if out.get("summary") else "",
        "product_updates": out.get("key_metrics") if isinstance(out.get("key_metrics"), list) else [],
        "achievements": [],
        "challenges": [],
        "risks": [],
        "key_milestones": [],
        "asks": [],
        "defensive_language": [],
    }
    out["runway_and_cash"] = {"runway_months": None, "cash_in_bank": None, "burn_rate": None}
    out["operational_metrics"] = {"new_hires": [], "headcount": None, "customer_count": None}
    # Canonical: market_size, red_flags
    out["red_flags"] = [x for x in (out.get("red_flags") or d.get("red_flags") or []) if isinstance(x, str)]
    ms = out.get("market_size") or d.get("market_size")
    if isinstance(ms, dict) and any(ms.get(k) is not None for k in ("tam_usd", "sam_usd", "som_usd")):
        out["market_size"] = {
            "tam_usd": _ensure_numeric(ms.get("tam_usd")),
            "sam_usd": _ensure_numeric(ms.get("sam_usd")),
            "som_usd": _ensure_numeric(ms.get("som_usd")),
            "tam_description": ms.get("tam_description") if isinstance(ms.get("tam_description"), str) else None,
            "methodology": ms.get("methodology") if isinstance(ms.get("methodology"), str) else None,
        }
    else:
        out["market_size"] = None
    ve = out.get("value_explanations") if isinstance(out.get("value_explanations"), dict) else {}
    out["value_explanations"] = ve
    if ve:
        logger.debug("value_explanations (flat): %s", list(ve.keys()))
    return out


def run_document_process(
    document_id: str,
    storage_path: str,
    document_type: str = "other",
    *,
    storage: DocumentBlobStorage,
    document_repo: DocumentMetadataRepo,
    company_id: Optional[str] = None,
    fund_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Download document from storage, extract text, run structured extraction in-process,
    update metadata via repo. Progress is written to processing_summary at each step.
    Returns { "success": bool, "document_id": str, "result"?: dict, "error"?: str }.
    """
    doc_repo = document_repo
    tmp_path: Optional[str] = None

    # ── Idempotency guard: atomic claim prevents duplicate processing ──
    try:
        current_doc = doc_repo.get(document_id)
        if current_doc:
            current_status = current_doc.get("status")
            if current_status == "completed":
                logger.info(
                    "[DOC_PROCESS] Document %s already completed — returning cached result",
                    document_id,
                )
                return {
                    "success": True,
                    "document_id": document_id,
                    "result": {
                        "extracted_data": current_doc.get("extracted_data", {}),
                        "processing_summary": current_doc.get("processing_summary", {}),
                    },
                }
            if current_status == "processing":
                logger.info(
                    "[DOC_PROCESS] Document %s already processing — skipping duplicate run",
                    document_id,
                )
                return {
                    "success": True,
                    "document_id": document_id,
                    "result": None,
                    "message": "Already processing",
                }
            # Atomic claim: transition pending → processing in one DB call.
            # If another caller races us, only one will get True.
            if current_status == "pending":
                claimed = doc_repo.claim_for_processing(document_id)
                if not claimed:
                    logger.info(
                        "[DOC_PROCESS] Document %s lost claim race — another caller is processing it",
                        document_id,
                    )
                    return {
                        "success": True,
                        "document_id": document_id,
                        "result": None,
                        "message": "Already claimed by another processor",
                    }
                logger.info("[DOC_PROCESS] Document %s claimed for processing", document_id)
    except Exception as e:
        logger.warning("[DOC_PROCESS] Idempotency check failed for %s: %s", document_id, e)
        # Continue processing — better to risk a duplicate than to block entirely

    def update_progress(step: str, message: str = "") -> None:
        try:
            doc_repo.update(
                document_id,
                {
                    "status": "processing",
                    "processing_summary": {
                        "step": step,
                        "message": message,
                        "updated_at": _iso_now(),
                    },
                },
            )
        except Exception as e:
            logger.warning("Could not update progress: %s", e)

    try:
        update_progress("downloading", "Downloading file from storage")
        content = storage.download(storage_path)
        if not content:
            doc_repo.update(
                document_id,
                {
                    "status": "failed",
                    "processing_summary": {"error": "Empty file from storage", "updated_at": _iso_now()},
                },
            )
            return {"success": False, "document_id": document_id, "error": "Empty file from storage"}

        suffix = Path(storage_path).suffix or ".pdf"
        fd, tmp_path = tempfile.mkstemp(suffix=suffix, prefix="doc_")
        try:
            os.write(fd, content)
        finally:
            os.close(fd)

        update_progress("extracting_text", "Extracting text from document")
        raw_text = _text_from_file(tmp_path, suffix)
        raw_text_preview = (raw_text[:5000] + "…") if len(raw_text) > 5000 else raw_text

        if not raw_text.strip():
            error_detail = "No text extracted from document"
            if suffix.lower().lstrip(".") == "pdf":
                error_detail = (
                    "No text extracted from PDF. "
                    "The file may be image-only (scanned) or password-protected. "
                    f"OCR available: {_OCR_AVAILABLE}."
                )
            doc_repo.update(
                document_id,
                {
                    "status": "failed",
                    "processing_summary": {
                        "error": error_detail,
                        "updated_at": _iso_now(),
                        "ocr_available": _OCR_AVAILABLE,
                    },
                },
            )
            logger.warning("[DOC_PROCESS] %s for document %s (path=%s)", error_detail, document_id, storage_path)
            return {"success": False, "document_id": document_id, "error": error_detail}

        update_progress("extracting_structured", "Running AI extraction")
        memo_context: Optional[str] = None
        if (document_type or "").strip().lower() != "investment_memo" and company_id:
            memo_context = _get_memo_context_for_company(doc_repo, company_id, fund_id)
        # Use asyncio.run() instead of manually creating/closing event loops.
        # asyncio.run() is cheaper, avoids resource leaks, and handles cleanup properly.
        extracted_data = asyncio.run(
            _extract_document_structured_async(
                raw_text, document_type or "other", memo_context=memo_context
            )
        )

        # Check for extraction errors and log them
        extraction_error = extracted_data.get("_extraction_error")
        if extraction_error:
            logger.warning(
                "[DOC_PROCESS] Extraction completed with error for %s: %s",
                document_id, extraction_error,
            )

        # Count how many useful fields were extracted
        field_count = sum(
            1 for k, v in extracted_data.items()
            if v is not None and k not in ("_extraction_error", "value_explanations", "period_date")
            and not (isinstance(v, (list, dict)) and len(v) == 0)
            and not (isinstance(v, str) and not v.strip())
        )
        logger.info(
            "[DOC_PROCESS] Extracted %d non-empty fields from document %s",
            field_count, document_id,
        )

        processing_summary = {
            "step": "completed",
            "message": f"Extraction completed — {field_count} fields extracted"
                       + (f" (warning: {extraction_error})" if extraction_error else ""),
            "updated_at": _iso_now(),
            "fields_extracted": field_count,
            "text_length": len(raw_text),
        }
        update_payload: Dict[str, Any] = {
            "status": "completed",
            "processed_at": _iso_now(),
            "document_type": document_type or "other",
            "extracted_data": extracted_data,
            "issue_analysis": {},
            "comparables_analysis": {},
            "processing_summary": processing_summary,
            "raw_text_preview": raw_text_preview,
        }
        if company_id is not None:
            update_payload["company_id"] = company_id
        if fund_id is not None:
            update_payload["fund_id"] = fund_id
        doc_repo.update(document_id, update_payload)

        # Persist extracted metrics as individual pending_suggestions rows
        # so the badge-based suggestion pipeline picks them up automatically.
        if company_id and fund_id and extracted_data:
            try:
                from app.services.micro_skills.suggestion_emitter import emit_document_suggestions
                n = emit_document_suggestions(
                    extracted_data=extracted_data,
                    company_id=company_id,
                    fund_id=fund_id,
                    document_id=document_id,
                    document_name=Path(storage_path).stem,
                )
                if n:
                    logger.info("Emitted %d suggestions from document %s", n, document_id)
                else:
                    logger.info(
                        "[DOC_PROCESS] No suggestions emitted from document %s "
                        "(extracted %d fields, company_id=%s, fund_id=%s)",
                        document_id, field_count, company_id, fund_id,
                    )
            except Exception as e:
                logger.warning("Failed to emit document suggestions for %s: %s", document_id, e, exc_info=True)
        elif not company_id or not fund_id:
            logger.info(
                "[DOC_PROCESS] Skipping suggestion emission for %s: company_id=%s, fund_id=%s",
                document_id, company_id, fund_id,
            )

        # Auto-trigger cap table calculation when funding data is extracted
        if company_id and fund_id and extracted_data:
            has_funding_signal = (
                extracted_data.get("stage")
                or extracted_data.get("total_funding")
                or extracted_data.get("valuation_pre_money")
                or extracted_data.get("round")
            )
            if has_funding_signal:
                try:
                    from app.services.pre_post_cap_table import PrePostCapTable
                    from app.services.intelligent_gap_filler import IntelligentGapFiller

                    # Reconstruct funding rounds from flat extracted fields
                    gap_filler = IntelligentGapFiller()
                    synthetic_rounds = gap_filler.generate_stage_based_funding_rounds(extracted_data)
                    if not synthetic_rounds:
                        # Minimal single-round fallback
                        stage = extracted_data.get("stage") or extracted_data.get("round") or "Unknown"
                        amount = extracted_data.get("total_funding") or extracted_data.get("valuation_pre_money") or 0
                        if amount:
                            synthetic_rounds = [{"round": stage, "amount": amount}]

                    if synthetic_rounds:
                        cap_data = {
                            "funding_rounds": synthetic_rounds,
                            "founders": [],
                            "is_yc": False,
                            "geography": extracted_data.get("geography", "Unknown"),
                        }
                        cap_service = PrePostCapTable()
                        cap_result = cap_service.calculate_full_cap_table_history(cap_data)

                        # Persist to company_cap_tables
                        from app.core.database import get_supabase_service
                        sb = get_supabase_service()
                        if sb:
                            client = sb.get_client() if hasattr(sb, 'get_client') else sb
                            if client:
                                source = "extracted" if extracted_data.get("total_funding") else "synthetic"
                                client.table("company_cap_tables").upsert({
                                    "portfolio_id": fund_id,
                                    "company_id": company_id,
                                    "company_name": extracted_data.get("company_name", ""),
                                    "cap_table_json": cap_result.get("current_cap_table", {}),
                                    "sankey_data": cap_result.get("sankey_data"),
                                    "waterfall_data": cap_result.get("waterfall_data"),
                                    "ownership_summary": cap_result.get("ownership_summary"),
                                    "founder_ownership": cap_result.get("founder_ownership"),
                                    "total_raised": cap_result.get("total_raised"),
                                    "num_rounds": cap_result.get("num_rounds"),
                                    "source": source,
                                    "funding_data_source": f"document:{document_id}",
                                }, on_conflict="portfolio_id,company_id").execute()
                                logger.info("[DOC_CAP_TABLE] Persisted cap table for company %s from document %s", company_id, document_id)

                                # Also emit founderOwnership as a suggestion for the grid
                                founder_own = cap_result.get("founder_ownership")
                                if founder_own is not None:
                                    client.table("pending_suggestions").upsert({
                                        "fund_id": fund_id,
                                        "company_id": company_id,
                                        "column_id": "founderOwnership",
                                        "suggested_value": {"value": founder_own},
                                        "source_service": "doc_cap_table",
                                        "reasoning": f"Founder ownership from document extraction: {founder_own:.1f}%",
                                    }, on_conflict="fund_id,company_id,column_id").execute()
                except Exception as e:
                    logger.warning("[DOC_CAP_TABLE] Cap table calculation failed for document %s: %s", document_id, e, exc_info=True)

        result = {
            "success": True,
            "extracted_data": extracted_data,
            "document_metadata": {"document_type": document_type or "other"},
            "processing_summary": processing_summary,
            "raw_text_preview": raw_text_preview,
            "issue_analysis": {},
            "comparables_analysis": {},
        }
        return {"success": True, "document_id": document_id, "result": result}
    except Exception as e:
        logger.exception("Document process failed: %s", e)
        try:
            doc_repo.update(
                document_id,
                {
                    "status": "failed",
                    "processing_summary": {"error": str(e), "updated_at": _iso_now()},
                },
            )
        except Exception:
            pass
        return {"success": False, "document_id": document_id, "error": str(e)}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
