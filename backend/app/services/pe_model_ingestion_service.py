"""PE Model Ingestion Service — reads multi-sheet Excel models and extracts structured data.

One LLM call: sends all sheets as markdown tables → gets back structured JSON matching
a flexible extraction schema that adapts to ANY deal type (LBO, structured equity,
growth equity, real asset, venture debt, infrastructure, credit, distressed, etc.).

Usage:
    svc = PEModelIngestionService(model_router)
    pe_data = await svc.ingest(file_path)
    # pe_data is a dict with: deal_profile, instruments, sources_uses,
    # operating_model, returns, debt_schedule
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.data_validator import ensure_numeric

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Extraction schema — sent to the LLM as the target JSON structure
# ---------------------------------------------------------------------------

EXTRACTION_SCHEMA = {
    "deal_profile": {
        "deal_type": "str — lbo, growth_equity, structured_equity, real_asset, venture_debt, credit, infrastructure, distressed, etc.",
        "strategy": "str — 1-2 sentence description of the investment strategy",
        "target_name": "str — company or asset name",
        "sponsor": "str or null — fund / sponsor name",
        "hold_period": "int — years",
        "total_investment": "float ($)",
        "primary_metric": "str — must match a key in operating_model.metrics (e.g. 'EBITDA', 'NOI', 'Revenue')",
    },
    "instruments": [
        {
            "type": "str — senior_debt, second_lien, mezzanine, preferred_equity, common_equity, warrant, convertible_note, revolver, unitranche, pik_note, earnout, seller_note, etc.",
            "name": "str — descriptive name",
            "amount": "float ($) or null",
            "pct_of_total": "float (decimal) or null",
            "terms": {"<term_name>": "<term_value> — all relevant terms as key-value pairs"},
        }
    ],
    "sources_uses": {
        "sources": [{"name": "str", "amount": "float ($)"}],
        "uses": [{"name": "str", "amount": "float ($)"}],
    },
    "operating_model": {
        "periods": ["str — period labels"],
        "metrics": {
            "<MetricName>": {
                "values": ["float — one per period"],
                "format": "dollar | pct | multiple | number",
            }
        },
    },
    "returns": {
        "scenarios": {
            "<scenario_name>": {
                "<metric_name>": "float"
            }
        },
        "sensitivity_matrix": {
            "row_label": "str",
            "col_label": "str",
            "row_values": ["float"],
            "col_values": ["float"],
            "irr_grid": [["float"]],
            "moic_grid": [["float"]],
        },
    },
    "debt_schedule": {
        "periods": ["str"],
        "total_balance": ["float ($)"],
        "per_instrument": [{"name": "str", "ending_balance": ["float ($)"]}],
        "interest_expense": ["float ($)"],
        "leverage_ratio": ["float or null"],
    },
}


def _schema_as_text() -> str:
    """Render extraction schema as compact JSON for the system prompt."""
    return json.dumps(EXTRACTION_SCHEMA, indent=2)


# ---------------------------------------------------------------------------
# Excel → markdown text (reuses existing pandas/openpyxl pattern)
# ---------------------------------------------------------------------------

def _read_excel_sheets(file_path: str) -> Dict[str, str]:
    """Read all sheets from an Excel file, return {sheet_name: markdown_table}.

    Reuses the same openpyxl + pandas pattern from document_process_service.
    """
    import pandas as pd

    path = Path(file_path)
    ext = path.suffix.lower().lstrip(".")

    if ext == "csv":
        df = pd.read_csv(file_path, dtype=str, na_filter=False)
        return {"Sheet1": _df_to_markdown(df, "Sheet1")}

    engine = "openpyxl" if ext == "xlsx" else "xlrd"
    try:
        xls = pd.ExcelFile(file_path, engine=engine)
    except ImportError:
        xls = pd.ExcelFile(file_path, engine="openpyxl")

    sheets: Dict[str, str] = {}
    for name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=name, dtype=str, na_filter=False)
        if not df.empty:
            sheets[name] = _df_to_markdown(df, name)

    return sheets


def _df_to_markdown(df, sheet_name: str, max_rows: int = 2000) -> str:
    """Convert a pandas DataFrame to a readable markdown table for the LLM."""
    lines = [f"## Sheet: {sheet_name} ({df.shape[0]} rows x {df.shape[1]} cols)"]

    # Column headers
    headers = [str(c) for c in df.columns]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    # Data rows
    for _, row in df.head(max_rows).iterrows():
        cells = [str(v).strip() for v in row.values]
        lines.append("| " + " | ".join(cells) + " |")

    if df.shape[0] > max_rows:
        lines.append(f"*({df.shape[0] - max_rows} more rows omitted)*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# The service
# ---------------------------------------------------------------------------

class PEModelIngestionService:
    """Ingest any investment model Excel file → structured JSON for memo generation."""

    def __init__(self, model_router):
        self.model_router = model_router

    async def ingest(self, file_path: str) -> Dict[str, Any]:
        """Read Excel file, send to LLM for extraction, validate and normalize.

        Returns structured dict matching EXTRACTION_SCHEMA.
        """
        import asyncio

        # Step 1: Read all sheets as markdown
        logger.info("[PE_INGEST] Reading Excel file: %s", file_path)
        sheets = _read_excel_sheets(file_path)
        if not sheets:
            raise ValueError(f"No readable sheets found in {file_path}")

        logger.info("[PE_INGEST] Read %d sheets: %s", len(sheets), list(sheets.keys()))

        # Step 2: Build the prompt with all sheet data
        sheets_text = "\n\n".join(sheets.values())

        # Cap at ~80K chars to stay within context limits
        if len(sheets_text) > 80_000:
            logger.warning("[PE_INGEST] Sheet text truncated from %d to 80K chars", len(sheets_text))
            sheets_text = sheets_text[:80_000]

        system_prompt = (
            "You are a senior investment analyst extracting structured data from a financial model. "
            "This could be ANY type of investment — LBO, growth equity, structured equity, "
            "real asset, venture debt, infrastructure, credit, distressed, etc. "
            "Do NOT assume the deal type. Read the model and determine what it is.\n\n"
            "Read ALL sheets carefully — data is spread across multiple tabs. "
            "Cross-reference numbers between sheets to ensure consistency.\n\n"
            "EXTRACTION RULES:\n"
            "1. DEAL TYPE: Identify the investment type from the model structure and terminology.\n"
            "2. INSTRUMENTS: Extract EVERY financial instrument (debt tranches, equity layers, "
            "warrants, convertibles, mezz, preferred, etc.). Include all terms shown for each.\n"
            "3. OPERATING METRICS: Extract ALL projected metrics. Use the EXACT metric names "
            "from the model. Each metric needs values[] and format (dollar|pct|multiple|number).\n"
            "4. RETURNS: Extract all scenario returns. Include every return metric shown.\n"
            "5. primary_metric in deal_profile MUST match a key in operating_model.metrics.\n\n"
            "NUMBER FORMAT:\n"
            "- Dollar amounts: if model says '500' in millions context, output 500000000.\n"
            "- Percentages in returns (IRR, yields): decimals (25% -> 0.25).\n"
            "- Percentages in operating metrics with format='pct': numbers (25.0 = 25%).\n"
            "- If a field doesn't exist, use null.\n\n"
            f"OUTPUT: Return ONLY valid JSON matching this schema:\n{_schema_as_text()}\n\n"
            "NO markdown fences, NO commentary — just the JSON object."
        )

        user_prompt = (
            "Extract structured investment model data from these Excel sheets:\n\n"
            f"{sheets_text}"
        )

        from app.services.model_router import ModelCapability

        logger.info("[PE_INGEST] Sending %d chars to LLM for extraction", len(user_prompt))
        response = await asyncio.wait_for(
            self.model_router.get_completion(
                prompt=user_prompt,
                system_prompt=system_prompt,
                capability=ModelCapability.ANALYSIS,
                max_tokens=8000,
                temperature=0.1,
                caller_context="pe_model_ingestion",
            ),
            timeout=120,
        )

        raw = response.get("response", "") if isinstance(response, dict) else str(response)

        # Step 3: Parse, normalize, validate
        pe_data = self._parse_extraction(raw)
        pe_data = self._normalize(pe_data)

        # Step 4: Validate extracted data for sanity
        from app.services.pe_extraction_validator import validate_pe_extraction
        validation = validate_pe_extraction(pe_data)
        pe_data["_validation"] = validation

        logger.info(
            "[PE_INGEST] Extraction complete — target=%s, deal_type=%s, instruments=%d, periods=%d, valid=%s, warnings=%d, errors=%d",
            pe_data.get("deal_profile", {}).get("target_name", "?"),
            pe_data.get("deal_profile", {}).get("deal_type", "?"),
            len(pe_data.get("instruments") or []),
            len(pe_data.get("operating_model", {}).get("periods", [])),
            validation["valid"],
            len(validation["warnings"]),
            len(validation["errors"]),
        )

        return pe_data

    @staticmethod
    def _parse_extraction(raw: str) -> Dict[str, Any]:
        """Parse LLM JSON output, handling markdown fences and common issues."""
        text = raw.strip()

        # Strip markdown code fences
        if text.startswith("```"):
            first_newline = text.index("\n") if "\n" in text else 3
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find the first { and last }
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
            logger.error("[PE_INGEST] Failed to parse extraction JSON: %s", text[:500])
            raise ValueError("LLM did not return valid JSON for PE model extraction")

    @staticmethod
    def _normalize(data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize extracted data — ensure numeric types, fill defaults."""

        # Deal profile
        dp = data.get("deal_profile") or {}
        dp["hold_period"] = int(ensure_numeric(dp.get("hold_period"), 5))
        dp["total_investment"] = ensure_numeric(dp.get("total_investment"), 0)
        dp.setdefault("deal_type", "unknown")
        dp.setdefault("target_name", "Unknown Target")
        dp.setdefault("primary_metric", "")
        data["deal_profile"] = dp

        # Instruments
        instruments = data.get("instruments") or []
        for inst in instruments:
            inst["amount"] = ensure_numeric(inst.get("amount"), 0)
            inst["pct_of_total"] = ensure_numeric(inst.get("pct_of_total"), 0)
            # Leave terms as-is (mixed types — rates are strings)
        data["instruments"] = instruments

        # Sources & Uses
        su = data.get("sources_uses") or {}
        for side in ("sources", "uses"):
            items = su.get(side) or []
            for item in items:
                item["amount"] = ensure_numeric(item.get("amount"), 0)
            su[side] = items
        data["sources_uses"] = su

        # Operating model — flexible metrics dict
        om = data.get("operating_model") or {}
        om["periods"] = om.get("periods") or []
        metrics = om.get("metrics") or {}
        clean_metrics = {}
        for metric_name, metric_data in metrics.items():
            if metric_name.startswith("_"):
                continue
            # Handle LLM returning plain arrays instead of {values, format} dicts
            if isinstance(metric_data, list):
                metric_data = {"values": metric_data, "format": "number"}
            if not isinstance(metric_data, dict):
                continue
            metric_data["values"] = [ensure_numeric(v, 0) for v in (metric_data.get("values") or [])]
            metric_data.setdefault("format", "number")
            clean_metrics[metric_name] = metric_data
        om["metrics"] = clean_metrics
        data["operating_model"] = om

        # Auto-detect primary_metric if not set
        if not dp["primary_metric"] and clean_metrics:
            # Prefer EBITDA > NOI > Revenue > first metric
            for candidate in ("EBITDA", "ebitda", "NOI", "noi", "Revenue", "revenue"):
                if candidate in clean_metrics:
                    dp["primary_metric"] = candidate
                    break
            if not dp["primary_metric"]:
                dp["primary_metric"] = next(iter(clean_metrics))

        # Returns — flexible scenarios dict
        returns = data.get("returns") or {}
        scenarios = returns.get("scenarios") or {}
        clean_scenarios = {}
        for sc_name, sc_data in scenarios.items():
            if sc_name.startswith("_") or not isinstance(sc_data, dict):
                continue
            clean_sc = {}
            for k, v in sc_data.items():
                clean_sc[k] = ensure_numeric(v, 0)
            clean_scenarios[sc_name] = clean_sc
        returns["scenarios"] = clean_scenarios

        # Sensitivity matrix
        sm = returns.get("sensitivity_matrix")
        if sm and isinstance(sm, dict):
            sm["row_values"] = [ensure_numeric(v, 0) for v in (sm.get("row_values") or [])]
            sm["col_values"] = [ensure_numeric(v, 0) for v in (sm.get("col_values") or [])]
            irr_grid = sm.get("irr_grid") or []
            sm["irr_grid"] = [[ensure_numeric(v, 0) for v in row] for row in irr_grid]
            moic_grid = sm.get("moic_grid") or []
            sm["moic_grid"] = [[ensure_numeric(v, 0) for v in row] for row in moic_grid]
        data["returns"] = returns

        # Debt schedule
        sched = data.get("debt_schedule") or {}
        for key in ("total_balance", "interest_expense", "leverage_ratio"):
            arr = sched.get(key) or []
            sched[key] = [ensure_numeric(v, 0) for v in arr]
        sched["periods"] = sched.get("periods") or []
        per_instrument = sched.get("per_instrument") or []
        for pi in per_instrument:
            pi["ending_balance"] = [ensure_numeric(v, 0) for v in (pi.get("ending_balance") or [])]
        sched["per_instrument"] = per_instrument
        data["debt_schedule"] = sched

        return data
