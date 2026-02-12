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
    "value_explanations": "object: { [metric_key]: string } - per-metric doc-sourced reasoning, e.g. arr: 'Q3 exceeded target; doc states $1.2M ARR'",
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
        "latest_update": "string (one-line summary)",
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
    },
    "value_explanations": "object: { [metric_key]: string } - per-metric doc-sourced reasoning, e.g. arr: 'Q3 exceeded target; doc states $1.2M ARR'. For extrapolated values include doc excerpt and inference.",
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
    "value_explanations": "object: { [metric_key]: string } - per-metric doc-sourced reasoning. For extrapolated values include doc excerpt and inference.",
}


def _iso_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _text_from_file(path: str, suffix: str) -> str:
    """
    Extract plain text from a file. Supports PDF (pypdf) and DOCX (python-docx).
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
            return "\n\n".join(text_parts).strip() or ""

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
        "You are a VC document analyst. Extract structured **signals** from company updates, board decks, and board transcripts. "
        "Prioritize qualitative signals that explain progress and risk; extract financial numbers only when explicitly stated. "
        "Return a single JSON object. Use null for unknown; use empty arrays for missing lists."
    )
    user_parts = [
        f"Document type: {document_type}.",
        "Extract signals first: product_updates, achievements, challenges, risks, asks, defensive_language, key_milestones.",
        "Then operational_metrics: new_hires (prefer objects with role/department e.g. 'Senior PM, product'), headcount, customer_count when stated.",
        "Then extracted_entities: competitors_mentioned, industry_terms, partners_mentioned.",
        "Extract business_model, sector, category when inferable from context (needed for valuation and analysis).",
        "Extract red_flags: array of explicit concerns, risks, or concerning language.",
        "Extract implications: array of 'reading between the lines' items (e.g. 'option pool likely expanded given senior product hire').",
        "If the document states ARR, burn, runway, cash, or growth rate, add them to financial_metrics and set period_date if a period is indicated.",
        "For each extracted metric, add a short doc-sourced explanation to value_explanations, e.g. arr: 'Q3 exceeded target; doc states $1.2M ARR'.",
        "For extrapolated values (e.g. option pool from senior hires), include the doc excerpt and inference in value_explanations.",
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
        user_parts.insert(1, f"Reference (same company): {memo_context}")
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
        "For each extracted metric (arr, revenue, runway, valuation, tam_usd, sam_usd, som_usd, etc.), add a short doc-sourced explanation to value_explanations, e.g. arr: 'Memo states $2M ARR as of Q2'; tam_usd: 'Memo cites Gartner 2024 TAM $42B'. "
        "Return a single JSON object. Use null when unknown."
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
        "For each extracted metric, add a short doc-sourced explanation to value_explanations, e.g. arr: 'Doc states $1.2M ARR'."
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

    if doc_type in ("monthly_update", "board_deck", "board_transcript"):
        schema_desc = json.dumps(COMPANY_UPDATE_SIGNAL_SCHEMA, indent=2)
        system_prompt, user_prompt = _signal_first_prompt(text, document_type, schema_desc, memo_context)
        empty = _empty_signal_extraction()
    elif doc_type == "investment_memo":
        schema_desc = json.dumps(INVESTMENT_MEMO_SCHEMA, indent=2)
        system_prompt, user_prompt = _memo_prompt(text, schema_desc)
        empty = _empty_memo_extraction()
    else:
        schema_desc = json.dumps(DOCUMENT_EXTRACTION_SCHEMA, indent=2)
        system_prompt, user_prompt = _flat_prompt(text, document_type, schema_desc)
        empty = _empty_extraction()

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

        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```\s*$", "", raw)
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return _normalize_extraction(parsed, document_type=document_type)
        return empty
    except Exception as e:
        logger.exception("extract_document_structured failed: %s", e)
        if doc_type in ("monthly_update", "board_deck", "board_transcript"):
            out = _empty_signal_extraction()
        elif doc_type == "investment_memo":
            out = _empty_memo_extraction()
        else:
            out = _empty_extraction()
        out["_extraction_error"] = str(e)
        return out


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
    if doc_type in ("monthly_update", "board_deck", "board_transcript"):
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
        }
        out["period_date"] = out.get("period_date") if isinstance(out.get("period_date"), str) else None
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
            doc_repo.update(
                document_id,
                {
                    "status": "failed",
                    "processing_summary": {"error": "No text extracted from document", "updated_at": _iso_now()},
                },
            )
            return {"success": False, "document_id": document_id, "error": "No text extracted from document"}

        update_progress("extracting_structured", "Running AI extraction")
        memo_context: Optional[str] = None
        if (document_type or "").strip().lower() in ("monthly_update", "board_deck", "board_transcript") and company_id:
            memo_context = _get_memo_context_for_company(doc_repo, company_id, fund_id)
        loop = asyncio.new_event_loop()
        try:
            extracted_data = loop.run_until_complete(
                _extract_document_structured_async(
                    raw_text, document_type or "other", memo_context=memo_context
                )
            )
        finally:
            loop.close()

        processing_summary = {
            "step": "completed",
            "message": "Extraction completed",
            "updated_at": _iso_now(),
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
