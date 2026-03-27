"""PE Model Ingestion Service — reads multi-sheet Excel LBO models and extracts structured data.

One LLM call: sends all sheets as markdown tables → gets back structured JSON matching
the PE extraction schema.  No regex heuristics — every PE fund formats differently,
the LLM reads financial grids natively.

Usage:
    svc = PEModelIngestionService(model_router)
    pe_data = await svc.ingest(file_path)
    # pe_data is a dict with: transaction, sources_uses, operating_model,
    # debt_structure, debt_schedule, returns
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

PE_EXTRACTION_SCHEMA = {
    "transaction": {
        "company_name": "str — target company name",
        "entry_ev": "float — enterprise value at entry ($)",
        "entry_ebitda": "float — LTM or projected EBITDA at entry ($)",
        "entry_multiple": "float — EV / EBITDA at entry",
        "equity_check": "float — total equity invested by sponsor ($)",
        "management_rollover": "float — management/founder equity rollover amount ($), null if none",
        "rollover_pct": "float — management rollover as % of total equity (e.g. 0.25 = 25%), null if none",
        "hold_period": "int — expected hold period in years",
        "sponsor": "str — PE firm / sponsor name if found",
    },
    "sources_uses": {
        "sources": [{"name": "str", "amount": "float", "pct": "float"}],
        "uses": [{"name": "str", "amount": "float", "pct": "float"}],
        "total": "float — total transaction value",
    },
    "operating_model": {
        "periods": ["str — year labels: 2024, 2025, ..."],
        "revenue": ["float — revenue per period"],
        "ebitda": ["float — EBITDA per period"],
        "ebitda_margin": ["float — EBITDA margin % per period"],
        "capex": ["float — capital expenditure per period"],
        "fcf": ["float — free cash flow per period"],
        "revenue_growth": ["float — YoY revenue growth % per period"],
    },
    "debt_structure": {
        "tranches": [{
            "name": "str — e.g. Senior Secured, Second Lien, Mezzanine",
            "amount": "float — initial principal ($)",
            "rate": "str — interest rate (e.g. 'SOFR+400', '8.5%', 'L+350')",
            "maturity": "str — maturity date or years",
            "amort": "str — amortization schedule (e.g. '1% quarterly', 'bullet')",
            "covenants": "str — key covenants if shown",
        }],
        "total_debt": "float — sum of all tranches",
        "entry_leverage": "float — total debt / entry EBITDA",
    },
    "debt_schedule": {
        "periods": ["str — year labels matching operating_model"],
        "beginning_balance": ["float — total debt at start of each period"],
        "mandatory_amort": ["float — scheduled repayments"],
        "optional_prepayment": ["float — cash sweep / voluntary paydown"],
        "ending_balance": ["float — total debt at end of each period"],
        "interest_expense": ["float — total interest per period"],
        "leverage_ratio": ["float — net debt / EBITDA per period"],
        "per_tranche": [{
            "name": "str — tranche name matching debt_structure.tranches",
            "ending_balance": ["float — per-period ending balance for this tranche"],
        }],
    },
    "returns": {
        "base": {
            "exit_year": "int",
            "exit_ebitda": "float",
            "exit_multiple": "float",
            "exit_ev": "float",
            "equity_value": "float",
            "irr": "float — as decimal (0.25 = 25%)",
            "moic": "float",
        },
        "bull": {
            "exit_year": "int", "exit_ebitda": "float", "exit_multiple": "float",
            "exit_ev": "float", "equity_value": "float", "irr": "float", "moic": "float",
        },
        "bear": {
            "exit_year": "int", "exit_ebitda": "float", "exit_multiple": "float",
            "exit_ev": "float", "equity_value": "float", "irr": "float", "moic": "float",
        },
        "sensitivity_matrix": {
            "row_label": "str — e.g. 'Exit Multiple'",
            "col_label": "str — e.g. 'EBITDA Growth'",
            "row_values": ["float — exit multiples"],
            "col_values": ["float — growth rates"],
            "irr_grid": [["float — IRR for each (row, col) pair"]],
            "moic_grid": [["float — MOIC for each (row, col) pair"]],
        },
    },
}


def _schema_as_text() -> str:
    """Render extraction schema as compact JSON for the system prompt."""
    return json.dumps(PE_EXTRACTION_SCHEMA, indent=2)


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
    """Ingest a PE/LBO model Excel file → structured JSON for memo generation."""

    def __init__(self, model_router):
        self.model_router = model_router

    async def ingest(self, file_path: str) -> Dict[str, Any]:
        """Read Excel file, send to LLM for extraction, validate and normalize.

        Returns structured dict matching PE_EXTRACTION_SCHEMA.
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
            "You are a senior PE associate extracting structured data from an LBO model. "
            "Read ALL sheets carefully — data is spread across multiple tabs. "
            "Cross-reference numbers between sheets to ensure consistency.\n\n"
            "EXTRACTION RULES:\n"
            "- Extract EVERY number you can find that maps to the schema below.\n"
            "- Dollar amounts in millions: if the model says '500' and context suggests millions, output 500000000.\n"
            "- Percentages: output as decimals (25% → 0.25) UNLESS the field says 'margin %' — then output 25.0.\n"
            "- For ebitda_margin, revenue_growth fields: output as percentage numbers (25.0 means 25%).\n"
            "- If a field isn't in the model, use null.\n"
            "- For the sensitivity matrix: map the 2D grid exactly as shown. Row/col labels should be the axis values.\n"
            "- For debt tranches: capture EVERY tranche (senior, second lien, mezz, sub notes, revolver, etc.).\n"
            "- For management rollover: look in sources & uses or equity section for founder/management rollover equity.\n"
            "- For per-tranche debt schedules: if the model shows each tranche's balance over time, extract per_tranche.\n"
            "- If bull/bear cases aren't explicit, use null for those scenarios.\n\n"
            "OUTPUT: Return ONLY valid JSON matching this schema:\n"
            f"{_schema_as_text()}\n\n"
            "NO markdown fences, NO commentary — just the JSON object."
        )

        user_prompt = (
            "Extract structured PE/LBO model data from these Excel sheets:\n\n"
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
            "[PE_INGEST] Extraction complete — company=%s, entry_ev=%s, tranches=%d, periods=%d, valid=%s, warnings=%d, errors=%d",
            pe_data.get("transaction", {}).get("company_name", "?"),
            pe_data.get("transaction", {}).get("entry_ev", "?"),
            len(pe_data.get("debt_structure", {}).get("tranches", [])),
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
        """Validate and normalize extracted PE data — ensure numeric types, fill defaults."""

        # Transaction
        txn = data.get("transaction") or {}
        for key in ("entry_ev", "entry_ebitda", "equity_check", "management_rollover"):
            txn[key] = ensure_numeric(txn.get(key), 0)
        txn["rollover_pct"] = ensure_numeric(txn.get("rollover_pct"), 0)
        txn["entry_multiple"] = ensure_numeric(txn.get("entry_multiple"), 0)
        txn["hold_period"] = int(ensure_numeric(txn.get("hold_period"), 5))
        # Derive entry_multiple if not extracted
        if not txn["entry_multiple"] and txn["entry_ev"] and txn["entry_ebitda"]:
            txn["entry_multiple"] = round(txn["entry_ev"] / txn["entry_ebitda"], 1)
        # Derive rollover_pct from amounts if not extracted directly
        if not txn["rollover_pct"] and txn["management_rollover"] and txn["equity_check"]:
            total_equity = txn["equity_check"] + txn["management_rollover"]
            if total_equity > 0:
                txn["rollover_pct"] = round(txn["management_rollover"] / total_equity, 4)
        data["transaction"] = txn

        # Sources & Uses
        su = data.get("sources_uses") or {}
        for side in ("sources", "uses"):
            items = su.get(side) or []
            for item in items:
                item["amount"] = ensure_numeric(item.get("amount"), 0)
                item["pct"] = ensure_numeric(item.get("pct"), 0)
            su[side] = items
        su["total"] = ensure_numeric(su.get("total"), 0)
        data["sources_uses"] = su

        # Operating model — ensure all arrays are numeric
        om = data.get("operating_model") or {}
        for key in ("revenue", "ebitda", "ebitda_margin", "capex", "fcf", "revenue_growth"):
            arr = om.get(key) or []
            om[key] = [ensure_numeric(v, 0) for v in arr]
        om["periods"] = om.get("periods") or []
        data["operating_model"] = om

        # Debt structure
        ds = data.get("debt_structure") or {}
        for tranche in (ds.get("tranches") or []):
            tranche["amount"] = ensure_numeric(tranche.get("amount"), 0)
        ds["total_debt"] = ensure_numeric(ds.get("total_debt"), 0)
        ds["entry_leverage"] = ensure_numeric(ds.get("entry_leverage"), 0)
        data["debt_structure"] = ds

        # Debt schedule
        sched = data.get("debt_schedule") or {}
        for key in ("beginning_balance", "mandatory_amort", "optional_prepayment",
                     "ending_balance", "interest_expense", "leverage_ratio"):
            arr = sched.get(key) or []
            sched[key] = [ensure_numeric(v, 0) for v in arr]
        sched["periods"] = sched.get("periods") or []
        # Per-tranche schedules (if model has them)
        per_tranche = sched.get("per_tranche") or []
        for pt in per_tranche:
            pt["ending_balance"] = [ensure_numeric(v, 0) for v in (pt.get("ending_balance") or [])]
        sched["per_tranche"] = per_tranche
        data["debt_schedule"] = sched

        # Returns
        returns = data.get("returns") or {}
        for case in ("base", "bull", "bear"):
            r = returns.get(case)
            if r and isinstance(r, dict):
                for key in ("exit_ebitda", "exit_ev", "equity_value", "irr", "moic", "exit_multiple"):
                    r[key] = ensure_numeric(r.get(key), 0)
                r["exit_year"] = int(ensure_numeric(r.get("exit_year"), 0))
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

        return data
