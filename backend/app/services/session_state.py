"""
SessionState — A thin read-only lens over shared_data.

Grid-agnostic: reads whatever columns exist in the grid snapshot.
Works for any business type — portfolio companies, invoices, contracts,
employees, deals, whatever the grid contains.

Provides:
- fingerprint(): dense per-row field checklist for LLM context (cached until mutation)
- Typed property accessors for common keys
- Jurisdiction/market maps derived from currency + geography signals
- Scoreboard counters derived from tool_results (generic per-tool counts)

TaskPlanner — LLM-powered + deterministic task queue generation.

Reads SessionState + extracted entities to produce a list of Task-compatible
task dicts. Tool catalog is injected dynamically, not hardcoded.

CompletionChecker — Python replacement for the REFLECT LLM call.

Evaluates goals against the scoreboard. Pure Python, zero LLM tokens.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Currency → Jurisdiction mapping (no API needed — static market signals)
# ---------------------------------------------------------------------------

_CURRENCY_TO_JURISDICTION: dict[str, str] = {
    "USD": "US", "GBP": "UK", "EUR": "EU", "CHF": "CH", "CAD": "CA",
    "AUD": "AU", "JPY": "JP", "SGD": "SG", "HKD": "HK", "INR": "IN",
    "BRL": "BR", "ILS": "IL", "SEK": "SE", "NOK": "NO", "DKK": "DK",
    "KRW": "KR", "CNY": "CN", "NZD": "NZ", "AED": "AE", "ZAR": "ZA",
}

_LOCATION_TO_JURISDICTION: dict[str, str] = {
    "san francisco": "US", "new york": "US", "sf": "US", "nyc": "US",
    "boston": "US", "austin": "US", "seattle": "US", "la": "US",
    "los angeles": "US", "miami": "US", "chicago": "US", "denver": "US",
    "london": "UK", "cambridge": "UK", "edinburgh": "UK", "manchester": "UK",
    "berlin": "EU", "paris": "EU", "amsterdam": "EU", "munich": "EU",
    "stockholm": "EU", "dublin": "EU", "helsinki": "EU", "lisbon": "EU",
    "barcelona": "EU", "zurich": "CH", "geneva": "CH",
    "toronto": "CA", "vancouver": "CA", "montreal": "CA",
    "sydney": "AU", "melbourne": "AU",
    "singapore": "SG", "tokyo": "JP", "seoul": "KR",
    "bangalore": "IN", "mumbai": "IN", "delhi": "IN",
    "tel aviv": "IL", "sao paulo": "BR",
    "dubai": "AE", "abu dhabi": "AE",
    "beijing": "CN", "shanghai": "CN", "shenzhen": "CN",
    "hong kong": "HK",
}

# Jurisdiction → likely currency (reverse map)
_JURISDICTION_TO_CURRENCY: dict[str, str] = {
    "US": "USD", "UK": "GBP", "EU": "EUR", "CH": "CHF",
    "JP": "JPY", "CA": "CAD", "AU": "AUD", "IN": "INR",
    "IL": "ILS", "SG": "SGD", "BR": "BRL", "KR": "KRW",
    "CN": "CNY", "HK": "HKD", "AE": "AED",
}


def _infer_jurisdiction(row: dict) -> str:
    """Derive market jurisdiction from currency, location, or geography fields.
    Returns 2-letter code or '' if unknown. No API calls — pure signal extraction.
    """
    # 1. Explicit currency field → strongest signal
    ccy = (row.get("currency") or row.get("reporting_currency") or "").upper().strip()
    if ccy and ccy in _CURRENCY_TO_JURISDICTION:
        return _CURRENCY_TO_JURISDICTION[ccy]

    # 2. Location / geography / hq_location field
    for loc_key in ("hq_location", "location", "geography", "hq", "geo", "country"):
        loc = (row.get(loc_key) or "").lower().strip()
        if not loc:
            continue
        if loc in _LOCATION_TO_JURISDICTION:
            return _LOCATION_TO_JURISDICTION[loc]
        for city, code in _LOCATION_TO_JURISDICTION.items():
            if city in loc:
                return code
        loc_up = loc.upper()
        for country_kw, code in [
            ("US", "US"), ("UNITED STATES", "US"), ("AMERICA", "US"),
            ("UK", "UK"), ("UNITED KINGDOM", "UK"), ("BRITAIN", "UK"), ("ENGLAND", "UK"),
            ("CANADA", "CA"), ("AUSTRALIA", "AU"), ("INDIA", "IN"),
            ("GERMANY", "EU"), ("FRANCE", "EU"), ("NETHERLANDS", "EU"),
            ("ISRAEL", "IL"), ("SINGAPORE", "SG"), ("JAPAN", "JP"),
            ("BRAZIL", "BR"), ("CHINA", "CN"), ("KOREA", "KR"),
        ]:
            if country_kw in loc_up:
                return code

    return ""


def _is_real_value(v: Any) -> bool:
    """True if v is a meaningful non-empty value."""
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v not in ("", "N/A", "Unknown", "null", "None")
    if isinstance(v, (list, dict)):
        return bool(v)
    return bool(v)


def _fmt_money(v: Any, currency: str = "") -> str:
    """Format a monetary value compactly: $12.5M, £3.2M, etc."""
    if not _is_real_value(v):
        return ""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return str(v)[:10]
    prefix = {"GBP": "£", "EUR": "€", "CHF": "CHF ", "JPY": "¥"}.get(currency.upper(), "$")
    if n >= 1_000_000_000:
        return f"{prefix}{n / 1e9:.1f}B"
    if n >= 1_000_000:
        return f"{prefix}{n / 1e6:.1f}M"
    if n >= 1_000:
        return f"{prefix}{n / 1e3:.0f}K"
    return f"{prefix}{n:.0f}"


def _cell_has_value(v: Any) -> bool:
    """Check if a cell value is non-empty."""
    val = v.get("value", v) if isinstance(v, dict) else v
    return bool(val) and val != "N/A" and val != "Unknown" and val != ""


# ---------------------------------------------------------------------------
# SessionState — Grid-agnostic read-only lens
# ---------------------------------------------------------------------------

class SessionState:
    """Read-only lens over shared_data. Same dict reference, not a copy.

    Grid-agnostic: discovers columns dynamically from the grid snapshot.
    Works for any data type — companies, invoices, contracts, whatever.
    """

    def __init__(self, shared_data: dict) -> None:
        self._data = shared_data  # SAME reference, not a copy
        self._dirty = True
        self._cached_fingerprint = ""

    # -- Typed property accessors ------------------------------------------

    @property
    def companies(self) -> list:
        return self._data.get("companies", [])

    @property
    def matrix_context(self) -> dict:
        return self._data.get("matrix_context") or {}

    @property
    def grid_rows(self) -> list:
        gs = self.matrix_context.get("gridSnapshot") or {}
        rows = gs.get("rows", []) if isinstance(gs, dict) else gs if isinstance(gs, list) else []
        return rows

    @property
    def grid_columns(self) -> list:
        """Discover column names from the grid snapshot."""
        gs = self.matrix_context.get("gridSnapshot") or {}
        if isinstance(gs, dict):
            cols = gs.get("columns") or gs.get("columnDefs") or []
            if cols:
                return [c.get("name") or c.get("field") or c.get("headerName", "") for c in cols if isinstance(c, dict)]
        # Fallback: union of all cell keys across rows
        all_keys: set[str] = set()
        for row in self.grid_rows:
            cells = row.get("cells") or row.get("cellValues") or {}
            all_keys.update(cells.keys())
        return sorted(all_keys)

    @property
    def grid_row_names(self) -> list:
        """Get the primary identifier for each row (company name, entity name, etc.)."""
        return (
            self.matrix_context.get("companyNames")
            or self.matrix_context.get("company_names")
            or self.matrix_context.get("rowNames")
            or self.matrix_context.get("row_names")
            or []
        )

    # Keep backward-compat alias
    @property
    def grid_company_names(self) -> list:
        return self.grid_row_names

    @property
    def portfolio_size(self) -> int:
        return len(self.grid_row_names)

    @property
    def fund_metrics(self) -> dict:
        fm = self._data.get("fund_metrics", {})
        return fm.get("metrics", fm) if isinstance(fm, dict) else {}

    @property
    def fund_context(self) -> dict:
        return self._data.get("fund_context", {})

    @property
    def needs_auto_enrich(self) -> bool:
        return bool(self._data.get("needs_auto_enrich"))

    @property
    def auto_enrich_fields(self) -> list:
        return self._data.get("auto_enrich_fields", [])

    @property
    def session_corrections(self) -> list:
        return self._data.get("session_corrections", [])

    # -- Mutation tracking -------------------------------------------------

    def mark_dirty(self) -> None:
        """Call after each tool execution to invalidate the fingerprint cache."""
        self._dirty = True

    # -- Fingerprint -------------------------------------------------------

    def fingerprint(self) -> str:
        """Dense per-row state fingerprint. Cached until mark_dirty()."""
        if not self._dirty:
            return self._cached_fingerprint
        self._cached_fingerprint = self._build_fingerprint()
        self._dirty = False
        return self._cached_fingerprint

    def _build_fingerprint(self) -> str:
        """Build a dense mode-aware state summary for LLM context.

        Dispatches to mode-specific fingerprints so the LLM gets relevant
        situational awareness regardless of which mode the user is in.
        """
        grid_mode = self._data.get("grid_mode", "portfolio")

        if grid_mode == "pnl":
            return self._fingerprint_pnl()
        elif grid_mode == "legal":
            return self._fingerprint_legal()
        else:
            return self._fingerprint_portfolio()

    # ── PNL / CFO fingerprint ─────────────────────────────────────────

    def _fingerprint_pnl(self) -> str:
        """Actual P&L grid state for CFO agent situational awareness."""
        lines: list[str] = []

        # ── Company UUID — tools need this, not a name ──
        company_id = self._data.get("company_id")
        if company_id:
            lines.append(f"COMPANY_ID: {company_id}")

        # ── Company snapshot from company_fpa_context ──
        cfpa = self._data.get("company_fpa_context")
        if cfpa and isinstance(cfpa, dict):
            cname = cfpa.get("companyName") or cfpa.get("company_name")
            if cname:
                lines.append(f"COMPANY: {cname}")

        # ── Read grid data (primary: grid_rows, fallback: fpa_pnl_result) ──
        pnl_result = self._data.get("fpa_pnl_result")
        pnl_periods: list = []
        forecast_start_idx: int = 0
        if pnl_result and isinstance(pnl_result, dict) and not pnl_result.get("error"):
            pnl_periods = pnl_result.get("periods", [])
            forecast_start_idx = pnl_result.get("forecastStartIndex", len(pnl_periods))

        items: list[tuple[str, dict[str, float], bool]] = []
        for row in self.grid_rows:
            name = row.get("rowName") or row.get("companyName") or row.get("name") or ""
            if not name:
                continue
            cells = row.get("cells") or row.get("cellValues") or {}
            computed = bool(row.get("isComputed") or row.get("computed"))
            vals: dict[str, float] = {}
            for k, cell in cells.items():
                v = cell.get("value", cell) if isinstance(cell, dict) else cell
                if v is not None:
                    try:
                        vals[k] = float(v)
                    except (TypeError, ValueError):
                        pass
            if vals or computed:
                items.append((name, vals, computed))

        # Fallback to pnl_result rows
        if not items and pnl_result and isinstance(pnl_result, dict):
            for row in pnl_result.get("rows", []):
                name = row.get("id") or row.get("category") or row.get("label") or ""
                if not name:
                    continue
                computed = bool(row.get("isComputed") or row.get("computed"))
                raw = row.get("values") or row.get("data") or {}
                vals = {}
                if isinstance(raw, dict):
                    for k, v in raw.items():
                        if v is not None:
                            try:
                                vals[k] = float(v)
                            except (TypeError, ValueError):
                                pass
                elif isinstance(raw, list) and pnl_periods:
                    for i, v in enumerate(raw):
                        if i < len(pnl_periods) and v is not None:
                            try:
                                vals[pnl_periods[i]] = float(v)
                            except (TypeError, ValueError):
                                pass
                if vals or computed:
                    items.append((name, vals, computed))

        if not items:
            lines.append("P&L GRID: empty — no line items loaded")
            lines.append("CHARTS: use generate_chart (line, bar, waterfall, sankey, probability_cloud, heatmap, bubble)")
            return "\n".join(lines)

        # ── Ordered periods + actuals/forecast split ─────────────────
        all_p: set[str] = set()
        for _, v, _ in items:
            all_p.update(v.keys())
        ordered = [p for p in pnl_periods if p in all_p] if pnl_periods else []
        ordered += sorted(all_p - set(ordered))

        actual_set = set(pnl_periods[:forecast_start_idx]) if pnl_periods and forecast_start_idx > 0 else set(ordered)
        forecast_set = set(pnl_periods[forecast_start_idx:]) if pnl_periods and forecast_start_idx > 0 else set()

        _MONTHS = {"01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun",
                    "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"}

        def _pl(p: str) -> str:
            s = p.split("-")
            return f"{_MONTHS[s[1]]}'{s[0][2:]}" if len(s) >= 2 and s[1] in _MONTHS else p[:7]

        # ── Grid: line items × months ────────────────────────────────
        filled = sum(len(v) for _, v, _ in items)
        lines.append(f"P&L GRID ({len(items)} items × {len(ordered)} months, {filled}/{len(items) * len(ordered)} cells)")
        for name, vals, computed in items:
            parts = [f"{_pl(p)} {_fmt_money(vals[p])}" if p in vals else f"{_pl(p)} -" for p in ordered]
            if len(parts) > 8:
                parts = parts[:6] + ["..."] + parts[-2:]
            lines.append(f"  {name}: {' | '.join(parts)}{' (computed)' if computed else ''}")

        # ── Boundary ─────────────────────────────────────────────────
        a, f = sorted(actual_set), sorted(forecast_set)
        b = []
        if a:
            b.append(f"ACTUALS: {_pl(a[0])}-{_pl(a[-1])}")
        b.append(f"FORECAST: {_pl(f[0])}-{_pl(f[-1])}" if f else "FORECAST: empty")
        lines.append(" | ".join(b))

        # ── Forecast methodology (how & why) ─────────────────────────
        fc = self._data.get("fpa_forecast_result")
        if fc and isinstance(fc, dict) and not fc.get("error"):
            method = fc.get("method", "?")
            reasoning = fc.get("method_reasoning", "")
            explanation = fc.get("explanation", "")
            seeds = fc.get("seeded_from", {})

            method_line = f"FORECAST METHOD: {method}"
            if reasoning:
                method_line += f" — {reasoning}"
            lines.append(method_line)

            seed_parts = []
            for k in ("revenue", "growth_rate", "burn_rate", "cash_balance"):
                sv = seeds.get(k)
                if sv is not None:
                    if k == "growth_rate":
                        try:
                            seed_parts.append(f"{k}={float(sv):.0%}")
                        except (TypeError, ValueError):
                            pass
                    else:
                        seed_parts.append(f"{k}={_fmt_money(sv)}")
            if seed_parts:
                lines.append(f"  Seeds: {', '.join(seed_parts)}")
            if explanation:
                lines.append(f"  Why: {explanation[:200]}")

            drivers = fc.get("driver_impacts")
            if drivers and isinstance(drivers, list):
                lines.append("  Drivers: " + " | ".join(f"{d.get('driver','?')}: {d.get('impact','?')}" for d in drivers[:3]))

        # ── Charts ───────────────────────────────────────────────────
        lines.append("CHARTS: use generate_chart (line, bar, waterfall, sankey, probability_cloud, heatmap, bubble)")

        return "\n".join(lines)

    # ── Legal fingerprint ─────────────────────────────────────────────

    def _fingerprint_legal(self) -> str:
        """Contract register + extracted clauses/obligations for legal reasoning.

        Emits: COMPANY_ID (if resolved), DOCUMENTS (id→clause mapping),
        per-clause contract register with terms/flags/obligations.
        """
        lines: list[str] = []

        # ── Company UUID — may have been resolved from document records ──
        company_id = self._data.get("company_id")
        if company_id:
            lines.append(f"COMPANY_ID: {company_id}")

        # ── Document → Clause mapping — tools need these IDs ─────────
        doc_ids = self._data.get("legal_document_ids") or []
        clause_ids = self._data.get("legal_clause_ids") or []
        doc_clause_map = self._data.get("legal_doc_clause_map") or {}
        if doc_ids:
            lines.append(f"DOCUMENTS ({len(doc_ids)}, {len(clause_ids)} clauses)")
            for did in doc_ids[:10]:
                clauses = doc_clause_map.get(did, [])
                lines.append(f"  doc:{did[:12]}… → {len(clauses)} clauses")

        # ── Legal column mapping (normalized key → display key) ──────
        _COL_MAP = {
            "documentname": "name", "contracttype": "type",
            "party": "party", "counterparty": "counterparty",
            "status": "status", "effectivedate": "effective",
            "expirydate": "expiry", "totalvalue": "totalValue",
            "annualvalue": "annualValue", "keyterms": "keyTerms",
            "flags": "flags", "obligations": "obligations",
            "nextdeadline": "nextDeadline", "reasoning": "reasoning",
        }

        # ── Extract contracts from grid rows ─────────────────────────
        contracts: list[dict[str, str]] = []
        for row in self.grid_rows:
            row_name = row.get("rowName") or row.get("companyName") or row.get("name") or ""
            cells = row.get("cells") or row.get("cellValues") or {}
            c: dict[str, str] = {"_row_name": row_name}
            # Carry clause_id and document_id from the row
            rid = row.get("rowId") or row.get("id") or ""
            if rid.startswith("legal:"):
                c["_clause_id"] = rid.replace("legal:", "")
            did = row.get("documentId") or ""
            if did:
                c["_document_id"] = did
            for cell_key, cell_val in cells.items():
                val = cell_val.get("value", cell_val) if isinstance(cell_val, dict) else cell_val
                norm = cell_key.lower().replace(" ", "").replace("_", "")
                if norm in _COL_MAP and _is_real_value(val):
                    c[_COL_MAP[norm]] = str(val)
            contracts.append(c)

        # Fallback: row_map
        if not contracts or all(len(c) <= 1 for c in contracts):
            for name, data in self._build_row_map().items():
                c = {"_row_name": name}
                for raw, mapped in _COL_MAP.items():
                    val = data.get(raw) or data.get(mapped)
                    if _is_real_value(val):
                        c[mapped] = str(val)
                contracts.append(c)

        if not contracts or all(len(c) <= 1 for c in contracts):
            lines.append("CONTRACTS: none loaded")
            lines.append("CHARTS: use generate_chart (bar, sankey, heatmap, waterfall)")
            return "\n".join(lines)

        # ── Contract register ────────────────────────────────────────
        total = len(contracts)
        filled = sum(1 for c in contracts for k in c if not k.startswith("_"))
        lines.append(f"CLAUSES ({total}, {filled}/{total * len(_COL_MAP)} fields)")

        deadlines: list[str] = []
        total_annual: float = 0.0

        for c in contracts:
            doc = c.get("name") or c.get("_row_name") or "Unknown"
            ctype = c.get("type", "")
            if ctype:
                doc = f"{doc} ({ctype})"

            # Prefix with clause_id so agent can reference specific clauses
            clause_prefix = ""
            if c.get("_clause_id"):
                clause_prefix = f"[{c['_clause_id'][:8]}…] "

            parts: list[str] = []
            cp = c.get("counterparty") or c.get("party")
            if cp:
                parts.append(f"{'Counterparty' if c.get('counterparty') else 'Party'}: {cp}")
            if c.get("status"):
                parts.append(c["status"])
            if c.get("expiry"):
                parts.append(f"Expires: {c['expiry']}")
            if c.get("annualValue"):
                parts.append(f"{_fmt_money(c['annualValue'])}/yr")
                try:
                    total_annual += float(str(c["annualValue"]).replace("$", "").replace(",", ""))
                except (TypeError, ValueError):
                    pass
            elif c.get("totalValue"):
                parts.append(f"Total: {_fmt_money(c['totalValue'])}")
            if c.get("keyTerms"):
                parts.append(f"TERMS: {c['keyTerms'][:120]}")
            if c.get("flags"):
                parts.append(f"FLAGS: {c['flags']}")
            if c.get("obligations"):
                parts.append(f"OBLIGATIONS: {c['obligations'][:120]}")

            lines.append(f"  {clause_prefix}{doc} — {' | '.join(parts)}" if parts else f"  {clause_prefix}{doc}")

            if c.get("nextDeadline"):
                deadlines.append(f"{doc}: {c['nextDeadline']}")
            elif c.get("expiry"):
                deadlines.append(f"{doc}: expires {c['expiry']}")

        # ── Deadlines + exposure ─────────────────────────────────────
        if deadlines:
            lines.append(f"DEADLINES: {' | '.join(deadlines[:5])}")
        if total_annual > 0:
            lines.append(f"EXPOSURE: {_fmt_money(total_annual)}/yr total")

        # ── Bridge results if available ──────────────────────────────
        cap_result = self._data.get("legal_cap_table_result")
        if cap_result and isinstance(cap_result, dict) and cap_result.get("success"):
            lines.append(f"CAP TABLE BRIDGE: built ({cap_result.get('share_count', '?')} entries)")
        pnl_result = self._data.get("contract_pnl_result")
        if pnl_result and isinstance(pnl_result, dict) and not pnl_result.get("error"):
            lines.append(f"PNL BRIDGE: {pnl_result.get('periods_written', '?')} periods attributed")

        # ── Charts ───────────────────────────────────────────────────
        lines.append("CHARTS: use generate_chart (bar, sankey, heatmap, waterfall)")

        return "\n".join(lines)

    # ── Portfolio fingerprint (original logic) ────────────────────────

    def _fingerprint_portfolio(self) -> str:
        """State summary for portfolio mode — grid rows, field checklist, fund metrics."""
        lines: list[str] = []

        row_map = self._build_row_map()
        total = len(row_map)

        if not total:
            lines.append("STATE: empty — no rows in grid or shared_data")
            return "\n".join(lines)

        # ── Discover all columns across all rows ───────────────────────
        all_columns: set[str] = set()
        for data in row_map.values():
            for k in data:
                if not k.startswith("_"):
                    all_columns.add(k)

        skip_cols = {"company", "name", "company_name", "row_name"}
        display_cols = sorted(all_columns - skip_cols)

        # ── Per-row field status ───────────────────────────────────────
        lines.append(f"ROWS ({total}) — Legend: +=has data, -=missing")

        col_labels = [c[:8] for c in display_cols[:20]]
        header = f"  {'name':<20} " + " ".join(f"{l:<8}" for l in col_labels)
        lines.append(header)

        jurisdiction_counts: dict[str, list[str]] = {}
        currencies_seen: dict[str, int] = {}
        missing_per_col: dict[str, int] = {c: 0 for c in display_cols[:20]}

        for name, data in row_map.items():
            markers: list[str] = []
            for col in display_cols[:20]:
                val = data.get(col)
                if val is not None and _is_real_value(val):
                    inferred_val = data.get(f"inferred_{col}")
                    if inferred_val and val == inferred_val:
                        markers.append("~")
                    else:
                        markers.append("+")
                elif data.get(f"inferred_{col}") and _is_real_value(data.get(f"inferred_{col}")):
                    markers.append("~")
                else:
                    markers.append("-")
                    missing_per_col[col] = missing_per_col.get(col, 0) + 1

            jur = _infer_jurisdiction(data)
            ccy = (data.get("currency") or data.get("reporting_currency") or "").upper()
            if not ccy and jur:
                ccy = _JURISDICTION_TO_CURRENCY.get(jur, "")
            if jur:
                jurisdiction_counts.setdefault(jur, []).append(name)
            if ccy:
                currencies_seen[ccy] = currencies_seen.get(ccy, 0) + 1

            marker_str = " ".join(f"{m:<8}" for m in markers)
            lines.append(f"  {name:<20} {marker_str}")

        # ── Jurisdiction map ─────────────────────────────────────────────
        if jurisdiction_counts:
            lines.append("")
            jur_parts = []
            for jur, names in sorted(jurisdiction_counts.items(), key=lambda x: -len(x[1])):
                pct = len(names) / total * 100
                jur_parts.append(f"{jur}:{len(names)}({pct:.0f}%)")
            lines.append(f"JURISDICTIONS: {' '.join(jur_parts)}")
            if currencies_seen:
                ccy_parts = [f"{c}:{n}" for c, n in sorted(currencies_seen.items(), key=lambda x: -x[1])]
                lines.append(f"CURRENCIES: {' '.join(ccy_parts)}")

        # ── Data quality summary ─────────────────────────────────────────
        sparse = [c for c, cnt in missing_per_col.items() if cnt > total * 0.3]
        if sparse:
            lines.append("")
            lines.append(f"GAPS: {', '.join(f'{c}({missing_per_col[c]}/{total} missing)' for c in sparse)}")
            self._data["needs_auto_enrich"] = True
            self._data["auto_enrich_fields"] = sparse

        # ── Freshness status ─────────────────────────────────────────────
        fresh_count = 0
        stale_count = 0
        for _name, _data in row_map.items():
            _fa = _data.get("_fetched_at")
            if _fa:
                try:
                    from datetime import datetime as _dt, timezone as _tz
                    _age = (_dt.now(_tz.utc) - _dt.fromisoformat(_fa)).total_seconds()
                    if _age <= 300:
                        fresh_count += 1
                    else:
                        stale_count += 1
                except Exception:
                    stale_count += 1
            else:
                stale_count += 1
        if fresh_count > 0:
            lines.append(f"FRESHNESS: {fresh_count} fresh (<5min), {stale_count} stale/unfetched")

        # ── Fund metrics (if present) ────────────────────────────────────
        fm = self.fund_metrics
        if fm:
            fm_parts = []
            for key, fmt in [("tvpi", "{:.2f}x"), ("dpi", "{:.2f}x"), ("irr", "{:.1f}%")]:
                if fm.get(key):
                    fm_parts.append(f"{key.upper()}={fmt.format(fm[key])}")
            if fm_parts:
                lines.append(f"FUND: {', '.join(fm_parts)}")

        return "\n".join(lines)

    # ── Shared: build row map from grid + enriched ────────────────────

    def _build_row_map(self) -> dict[str, dict]:
        """Merge grid rows + shared_data companies into a unified row map."""
        row_map: dict[str, dict] = {}

        for row in self.grid_rows:
            name = (
                row.get("companyName") or row.get("company_name")
                or row.get("rowName") or row.get("name") or ""
            )
            if not name:
                continue
            cells = row.get("cells") or row.get("cellValues") or {}
            merged = row_map.setdefault(name, {"_source": "grid"})
            for k, v in cells.items():
                val = v.get("value", v) if isinstance(v, dict) else v
                if _is_real_value(val):
                    merged[k.lower()] = val

        for c in self.companies:
            name = c.get("company") or c.get("name") or ""
            if not name:
                continue
            merged = row_map.setdefault(name, {"_source": "enriched"})
            merged["_source"] = "enriched"
            for k, v in c.items():
                if k.startswith("_"):
                    continue
                if _is_real_value(v):
                    merged[k] = v

        return row_map

    # -- Intelligence gates ------------------------------------------------

    def row_data(self, name: str) -> Optional[dict]:
        """Find a row by name in shared_data or grid rows."""
        return self._find_company(name)

    def row_fill_rate(self, name: str) -> float:
        """Return 0.0-1.0 indicating what fraction of columns have data."""
        row = self._find_company(name)
        if not row:
            return 0.0
        cols = [k for k in row if not k.startswith("_")]
        if not cols:
            return 0.0
        filled = sum(1 for k in cols if _is_real_value(row.get(k)))
        return filled / len(cols)

    def company_needs(self, name: str) -> Dict[str, bool]:
        """What does this row still need? Returns action → bool map.

        Generic: checks fill rate and freshness rather than specific fields.
        """
        row = self._find_company(name)
        if not row:
            return {"fetch": True, "enrich": True, "valuation": True,
                    "cap_table": True, "scenarios": True, "memo": True}

        fill_rate = self.row_fill_rate(name)

        # Check freshness
        fetched_at = row.get("_fetched_at")
        is_stale = True
        if fetched_at:
            try:
                from datetime import datetime, timezone
                age_seconds = (datetime.now(timezone.utc) - datetime.fromisoformat(fetched_at)).total_seconds()
                is_stale = age_seconds > 300  # 5 min TTL
            except Exception:
                pass

        return {
            "fetch": fill_rate < 0.3 and is_stale,
            "enrich": fill_rate < 0.7 and is_stale,
            "valuation": not _is_real_value(row.get("valuation")) and not _is_real_value(row.get("scenario_analysis")),
            "cap_table": not _is_real_value(row.get("cap_table")) and not _is_real_value(row.get("cap_table_history")),
            "scenarios": not _is_real_value(row.get("scenarios")) and not _is_real_value(row.get("scenario_analysis")),
            "memo": True,
        }

    def companies_needing(self, action: str, names: Optional[List[str]] = None) -> List[str]:
        """Filter a list of names to those that actually need `action`."""
        if names is None:
            names = [
                c.get("company") or c.get("name") or ""
                for c in self.companies
            ] + list(self.grid_row_names)
            names = list(dict.fromkeys(n for n in names if n))

        return [n for n in names if self.company_needs(n).get(action, True)]

    def _find_company(self, name: str) -> Optional[dict]:
        """Find a row by name in shared_data or grid rows."""
        name_lower = name.lower().strip().lstrip("@")
        for c in self.companies:
            cn = (c.get("company") or c.get("name") or "").lower().strip()
            if cn == name_lower or cn.startswith(name_lower):
                return c
        for row in self.grid_rows:
            cn = (
                row.get("companyName") or row.get("company_name")
                or row.get("rowName") or row.get("name") or ""
            ).lower().strip()
            if cn == name_lower or cn.startswith(name_lower):
                cells = row.get("cells") or row.get("cellValues") or {}
                flat = {}
                for k, v in cells.items():
                    flat[k.lower()] = v.get("value", v) if isinstance(v, dict) else v
                return flat
        return None

    # -- Analysis manifest persistence ------------------------------------

    def analysis_manifest(self) -> dict:
        """Return a lightweight manifest of which derived data exists."""
        manifest: dict[str, Any] = {}
        # Scan shared_data for any dict/list values that look like analysis output
        skip_keys = {"companies", "matrix_context", "fund_metrics", "fund_context",
                      "agent_tasks", "session_corrections", "tool_results"}
        for key, val in self._data.items():
            if key.startswith("_") or key in skip_keys:
                continue
            if isinstance(val, dict) and val:
                manifest[key] = list(val.keys())
            elif isinstance(val, list) and val:
                manifest[key] = f"{len(val)} items"
        return manifest

    def restore_manifest(self, manifest: dict) -> None:
        """Restore analysis data presence markers from a previous session."""
        for key, info in manifest.items():
            if not self._data.get(key):
                self._data[f"_stale_{key}"] = info
        self._dirty = True


# ---------------------------------------------------------------------------
# Scoreboard — Generic tool execution counters
# ---------------------------------------------------------------------------

@dataclass
class Scoreboard:
    """Generic counters derived from tool_results. Pure Python, no LLM.

    Tracks execution count per tool name. No hardcoded tool-specific fields.
    """
    tool_counts: Dict[str, int] = field(default_factory=dict)
    total_count: int = 0
    memo_section_count: int = 0
    auto_suggest_count: int = 0

    def count(self, tool_name: str) -> int:
        """Get execution count for a specific tool."""
        return self.tool_counts.get(tool_name, 0)

    @classmethod
    def from_tool_results(cls, tool_results: list[dict]) -> "Scoreboard":
        sb = cls()
        for r in tool_results:
            tool = r.get("tool", "")
            if tool:
                sb.tool_counts[tool] = sb.tool_counts.get(tool, 0) + 1
                sb.total_count += 1
            output = r.get("output", {})
            if isinstance(output, dict):
                sb.auto_suggest_count += output.get("auto_suggestions_count", 0)
                side_sections = output.get("memo_sections")
                if isinstance(side_sections, list):
                    sb.memo_section_count += len(side_sections)
        return sb

    # Backward-compat properties for any code that reads old field names
    @property
    def fetch_count(self) -> int:
        return (
            self.tool_counts.get("fetch_company_data", 0)
            + self.tool_counts.get("resolve_data_gaps", 0)
            + self.tool_counts.get("batch_enrich", 0)
            + self.tool_counts.get("enrich_portfolio", 0)
            + self.tool_counts.get("lightweight_diligence", 0)
        )

    @property
    def valuation_count(self) -> int:
        return (
            self.tool_counts.get("run_valuation", 0)
            + self.tool_counts.get("batch_valuate", 0)
        )

    @property
    def memo_count(self) -> int:
        count = sum(
            self.tool_counts.get(t, 0) for t in (
                "generate_memo", "run_report", "write_to_memo",
                "generate_ic_memo", "generate_followon_memo",
                "generate_lp_report", "generate_gp_update",
                "generate_comparison_report",
            )
        )
        # Promote: if tools auto-emitted memo sections, reflect that
        if self.memo_section_count >= 2 and count == 0:
            count = 1
        return count

    @property
    def chart_count(self) -> int:
        return self.tool_counts.get("generate_chart", 0)

    @property
    def suggest_count(self) -> int:
        return (
            self.tool_counts.get("suggest_grid_edit", 0)
            + self.tool_counts.get("suggest_action", 0)
            + self.auto_suggest_count
        )


# ---------------------------------------------------------------------------
# CompletionChecker — Replaces the REFLECT LLM call
# ---------------------------------------------------------------------------

class CompletionChecker:
    """Evaluates extracted goals against the scoreboard. Pure Python."""

    _prev_tool_count: int = 0

    @classmethod
    def is_complete(
        cls,
        goals: list[dict],
        scoreboard: Scoreboard,
        portfolio_size: int,
        tool_results: list[dict],
    ) -> Tuple[bool, str]:
        """Return (is_sufficient, reason).

        Goals have a "check" field like "tool_count > 0",
        "run_valuation_count >= portfolio_size", etc.
        Evaluates against generic tool counters + backward-compat names.
        """
        current_tool_count = len(tool_results)

        if not goals:
            if tool_results:
                cls._prev_tool_count = current_tool_count
                return True, "no goals but tools have run"
            return False, "no tools called yet"

        # Stale scoreboard detection
        if current_tool_count > 0 and current_tool_count == cls._prev_tool_count:
            logger.info("[COMPLETION] Scoreboard unchanged — breaking stale loop")
            cls._prev_tool_count = 0
            return True, "scoreboard unchanged — no further progress possible"
        cls._prev_tool_count = current_tool_count

        # Build eval environment: generic tool counts + backward-compat names
        env: Dict[str, int] = {
            "total_count": scoreboard.total_count,
            "portfolio_size": portfolio_size,
            # Backward-compat names
            "fetch_count": scoreboard.fetch_count,
            "valuation_count": scoreboard.valuation_count,
            "memo_count": scoreboard.memo_count,
            "memo_section_count": scoreboard.memo_section_count,
            "chart_count": scoreboard.chart_count,
            "suggest_count": scoreboard.suggest_count,
        }
        # Add per-tool counts: e.g. "run_valuation_count", "fetch_company_data_count"
        for tool_name, count in scoreboard.tool_counts.items():
            env[f"{tool_name}_count"] = count

        for goal in goals:
            check = goal.get("check", "")
            if not check:
                continue
            try:
                if not _safe_eval_check(check, env):
                    desc = goal.get("description", check)
                    return False, f"goal not met: {desc}"
            except Exception:
                continue

        return True, "all goals satisfied"


def _safe_eval_check(expr: str, env: dict) -> bool:
    """Evaluate a simple comparison expression like 'fetch_count > 0'.

    Only supports: var > N, var >= N, var == N, var < N, var <= N.
    No arbitrary code execution.
    """
    expr = expr.strip()

    m = re.match(r'^(\w+)\s*(>=|<=|>|<|==|!=)\s*(\w+)$', expr)
    if not m:
        return True  # Can't parse → assume satisfied

    left_name, op, right_name = m.groups()
    left = env.get(left_name, 0)
    right = env.get(right_name) if right_name in env else _try_int(right_name)

    if right is None:
        return True

    ops = {
        ">": lambda a, b: a > b,
        ">=": lambda a, b: a >= b,
        "<": lambda a, b: a < b,
        "<=": lambda a, b: a <= b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }
    return ops[op](left, right)


def _try_int(s: str) -> Optional[int]:
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# TaskLedger — Plan-driven per-task completion tracking
# ---------------------------------------------------------------------------

def _fuzzy_entity_match(goal_entity: str, candidate: str) -> bool:
    """Match entity names flexibly: 'dynelectro' matches 'dynelectro technologies'."""
    if not goal_entity or not candidate:
        return False
    if goal_entity == candidate:
        return True
    return goal_entity in candidate or candidate in goal_entity


@dataclass
class TaskGoal:
    """A single goal the agent must satisfy, derived from the TaskPlanner's plan."""
    id: str
    description: str
    tool_match: str          # exact tool name that satisfies this goal
    entity: Optional[str]    # row/entity name, or None for global
    status: str = "pending"  # pending | done
    depends_on: List[str] = field(default_factory=list)


class TaskLedger:
    """Deterministic per-task completion gate.

    Created from plan tasks. Updated after each tool execution via exact
    tool name matching (no alias tables). Fuzzy entity matching still
    handles name variations.
    """

    def __init__(self, goals: List[TaskGoal]) -> None:
        self.goals = goals
        self._attempt_counts: Dict[str, int] = {}

    @classmethod
    def from_plan_tasks(cls, tasks: List["Task"]) -> "TaskLedger":
        """Build a ledger from the TaskPlanner's actual plan."""
        goals: List[TaskGoal] = []
        for t in tasks:
            entity = (
                t.inputs.get("company_name")
                or t.inputs.get("company")
                or t.inputs.get("company_id")
                or t.inputs.get("name")
                or t.inputs.get("entity")
                or None
            )
            goals.append(TaskGoal(
                id=t.id,
                description=t.label or t.tool,
                tool_match=t.tool,
                entity=entity,
                depends_on=list(t.depends_on) if t.depends_on else [],
            ))
        logger.info(f"[TASK_LEDGER] Created {len(goals)} goals from TaskPlanner plan")
        return cls(goals)

    def update(self, tool_results: List[Dict[str, Any]]) -> None:
        """After tool execution, mark matching goals as done.

        Exact tool name matching. Fuzzy entity matching for name variations.
        Stale-loop breaker after 2 consecutive unmatched attempts.
        """
        pending_before = {g.id for g in self.goals if g.status != "done"}

        for tr in tool_results:
            tool = tr.get("tool", "")
            inputs = tr.get("input", {})
            output = tr.get("output", {})

            for goal in self.goals:
                if goal.status == "done":
                    continue

                # Exact tool name match
                if goal.tool_match != tool:
                    continue

                # For entity-specific goals, verify the entity was processed
                if goal.entity:
                    entity_lower = goal.entity.lower().strip().lstrip("@")
                    entity_found = False

                    # Check inputs for entity name
                    for key in ("company_name", "company", "company_id", "name",
                                "entity", "target", "acquirer"):
                        val = inputs.get(key, "")
                        if isinstance(val, str):
                            val_lower = val.lower().strip().lstrip("@")
                            if _fuzzy_entity_match(entity_lower, val_lower):
                                entity_found = True
                                break

                    # Check inputs for entity lists (batch tools)
                    if not entity_found:
                        for key in ("companies", "entities", "names"):
                            val = inputs.get(key, [])
                            if isinstance(val, list):
                                for v in val:
                                    if isinstance(v, str) and _fuzzy_entity_match(entity_lower, v.lower().strip().lstrip("@")):
                                        entity_found = True
                                        break

                    # Check output for entity name
                    if not entity_found and isinstance(output, dict):
                        for key in ("companies", "results", "company_data", "entities"):
                            out_val = output.get(key)
                            if isinstance(out_val, dict) and any(
                                _fuzzy_entity_match(entity_lower, k.lower().strip().lstrip("@")) for k in out_val
                            ):
                                entity_found = True
                                break
                            elif isinstance(out_val, list):
                                for item in out_val:
                                    if isinstance(item, dict):
                                        cn = (item.get("company") or item.get("name") or
                                              item.get("company_name") or item.get("entity") or "")
                                        if _fuzzy_entity_match(entity_lower, cn.lower().strip().lstrip("@")):
                                            entity_found = True
                                            break

                    if not entity_found:
                        continue

                goal.status = "done"
                logger.info(f"[TASK_LEDGER] Goal '{goal.id}' marked done (tool={tool})")

        # --- Stale-loop breaker ---
        still_pending = {g.id for g in self.goals if g.status != "done"}
        tools_called = {tr.get("tool", "") for tr in tool_results}

        for goal in self.goals:
            if goal.status == "done":
                self._attempt_counts.pop(goal.id, None)
                continue
            if goal.id not in pending_before:
                continue

            if goal.tool_match in tools_called and goal.id in still_pending:
                self._attempt_counts[goal.id] = self._attempt_counts.get(goal.id, 0) + 1
                attempts = self._attempt_counts[goal.id]
                if attempts >= 2:
                    goal.status = "done"
                    logger.warning(
                        f"[TASK_LEDGER] Goal '{goal.id}' force-completed after {attempts} "
                        f"stale attempts (tool ran but entity match failed — likely name mismatch "
                        f"for '{goal.entity}')"
                    )
                else:
                    logger.info(
                        f"[TASK_LEDGER] Goal '{goal.id}' stale attempt {attempts}/2 "
                        f"(tool ran, entity '{goal.entity}' not matched)"
                    )

    def is_complete(self) -> bool:
        """True when ALL goals are satisfied."""
        return all(g.status == "done" for g in self.goals)

    def pending_goals(self) -> List[TaskGoal]:
        return [g for g in self.goals if g.status != "done"]

    def pending_summary(self) -> str:
        """Dense one-line status for REASON prompt injection."""
        parts = []
        for g in self.goals:
            icon = "✓" if g.status == "done" else "○"
            parts.append(f"{icon} {g.id}")
        return " | ".join(parts)

    def next_actions(self) -> List[Dict[str, Any]]:
        """Return tool call dicts for goals whose dependencies are all satisfied.

        Only returns "ready" goals — pending goals whose depends_on are all done.
        """
        done_ids = {g.id for g in self.goals if g.status == "done"}
        actions: List[Dict[str, Any]] = []
        seen_tools: set = set()

        for goal in self.goals:
            if goal.status == "done":
                continue

            if goal.depends_on and not all(dep in done_ids for dep in goal.depends_on):
                continue

            key = (goal.tool_match, goal.entity or "")
            if key in seen_tools:
                continue
            seen_tools.add(key)

            # Build generic inputs from entity
            inputs: Dict[str, Any] = {}
            if goal.entity:
                # Use company_name as default entity key — tools can remap
                inputs["company_name"] = goal.entity

            actions.append({
                "tool": goal.tool_match,
                "input": inputs,
            })

        return actions


# ---------------------------------------------------------------------------
# TaskPlanner — LLM-powered + deterministic task queue
# ---------------------------------------------------------------------------

@dataclass
class Task:
    """A single planned task. Compatible with PlanStep creation."""
    id: str
    tool: str
    inputs: Dict[str, Any] = field(default_factory=dict)
    label: str = ""
    depends_on: List[str] = field(default_factory=list)

    def to_action(self) -> dict:
        return {
            "action": "call_tool",
            "tool": self.tool,
            "input": self.inputs,
            "reasoning": self.label,
        }


class TaskPlanner:
    """LLM-powered task decomposition with deterministic fallbacks.

    Grid-agnostic: the tool catalog is injected at call time from the
    registered tool registry. No hardcoded tool list. The system prompt
    is generic CFO, not VC-specific.

    Primary path: builds a structured prompt with the tool catalog +
    fingerprint + entities, asks the LLM to decompose into a task DAG.

    Fallback: uses classification.suggested_chain to build a plan from
    the already-classified intent.
    """

    @staticmethod
    def build_tool_catalog(tools: list) -> str:
        """Build a compact tool catalog string from registered tool objects.

        Each tool should have .name and .description attributes.
        If no tools provided, returns a generic placeholder.
        """
        if not tools:
            return "TOOLS: (no tools registered — use classification chain)"
        lines = ["TOOLS (use these exact names):"]
        for t in tools:
            name = getattr(t, "name", str(t))
            desc = getattr(t, "description", "")
            inputs_hint = ""
            schema = getattr(t, "input_schema", None) or getattr(t, "parameters", None)
            if schema and isinstance(schema, dict):
                props = schema.get("properties", {})
                if props:
                    input_parts = []
                    for k, v in list(props.items())[:5]:
                        input_parts.append(f"{k}: {v.get('type', 'any')}")
                    inputs_hint = f" Inputs: {{{', '.join(input_parts)}}}"
            lines.append(f"- {name}: {desc[:120]}{inputs_hint}")
        return "\n".join(lines)

    # Keep TOOL_CATALOG as empty string for backward compat — populated dynamically
    TOOL_CATALOG = ""

    @staticmethod
    def build_decomposition_prompt(
        prompt: str,
        fingerprint: str,
        entities: Dict[str, Any],
        goals: list[dict],
        tool_catalog: str = "",
    ) -> str:
        """Build the LLM prompt for task decomposition."""
        company_names = entities.get("companies", [])
        goals_json = json.dumps(goals) if goals else "[]"
        companies_json = json.dumps(company_names) if company_names else "[]"

        catalog = tool_catalog or TaskPlanner.TOOL_CATALOG or "(no tool catalog provided)"

        return f"""Decompose this user request into a task DAG.

USER REQUEST: {prompt}

ENTITIES: {companies_json}

CURRENT STATE:
{fingerprint}

USER GOALS: {goals_json}

{catalog}

RULES (FOLLOW EXACTLY — NO EXCEPTIONS):
1. READ THE FINGERPRINT. If a field shows + or ~, DO NOT re-fetch it. Skip straight to analysis. If it shows -, you MUST fill it before proceeding.
2. For missing data: use bulk tools for 3+ entities, parallel per-entity tools for 1-2.
3. Tasks with no dependencies MUST run in parallel. Same depends_on = parallel.
4. For N entities needing the same tool: emit N separate tasks with the same depends_on — they execute in parallel automatically.
5. Only include report/memo generation when the user EXPLICITLY asks for a written deliverable.
6. Completion criteria use scoreboard variables: total_count, [tool_name]_count, portfolio_size.
7. MINIMAL PLAN. Fewest tools to satisfy goals. No unnecessary steps.
8. For bulk operations: use batch tools instead of N individual calls when available.
9. NEVER emit an empty plan. If you don't understand the request, emit at least one exploratory tool call.
10. The user needs numbers and analysis, not excuses. Be aggressive about fetching, computing, and delivering results.

Return ONLY a JSON object:
{{
  "entities": {{"companies": ["name1", ...]}},
  "tasks": [
    {{"id": "t1", "tool": "tool_name", "inputs": {{}}, "label": "short description", "depends_on": []}},
    {{"id": "t2", "tool": "tool_name", "inputs": {{}}, "label": "short description", "depends_on": ["t1"]}}
  ],
  "completion": [
    {{"check": "total_count > 0", "description": "At least one tool executed"}},
    {{"check": "run_valuation_count >= 3", "description": "Valuations complete"}}
  ]
}}

NO MARKDOWN. NO EXPLANATION. JUST THE JSON OBJECT."""

    @staticmethod
    def parse_decomposition(raw: str) -> Optional[Tuple[List[Task], List[dict]]]:
        """Parse LLM decomposition response into Tasks + completion criteria."""
        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r'^```\w*\n?', '', cleaned)
                cleaned = re.sub(r'\n?```$', '', cleaned)

            data = json.loads(cleaned)
            if not isinstance(data, dict) or "tasks" not in data:
                return None

            tasks = []
            for t in data["tasks"]:
                if not isinstance(t, dict) or "tool" not in t:
                    continue
                tasks.append(Task(
                    id=t.get("id", f"t{len(tasks)}"),
                    tool=t["tool"],
                    inputs=t.get("inputs", {}),
                    label=t.get("label", t["tool"]),
                    depends_on=t.get("depends_on", []),
                ))

            completion = data.get("completion", [])
            if not isinstance(completion, list):
                completion = []

            return (tasks, completion) if tasks else None

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"[TASK_PLANNER] Failed to parse LLM decomposition: {e}")
            return None

    @staticmethod
    def plan_from_classification(
        classification: Any,
        state: SessionState,
        entities: Optional[Dict[str, Any]] = None,
    ) -> Optional[List[Task]]:
        """Build a task list from QueryClassification.suggested_chain.

        Generic: populates inputs from entity names without assuming
        which key each tool expects. Tools remap as needed.
        """
        if not classification or not getattr(classification, 'suggested_chain', None):
            return None

        chain = classification.suggested_chain
        entities = entities or {}
        entity_names: list[str] = entities.get("companies", [])

        if not chain:
            return None

        tasks: list[Task] = []
        prev_ids: list[str] = []

        for idx, tool_name in enumerate(chain):
            task_id = f"chain_{idx}"
            inputs: Dict[str, Any] = {}

            # Populate inputs generically
            if entity_names:
                if len(entity_names) == 1:
                    inputs["company_name"] = entity_names[0]
                else:
                    # For tools that take a list, pass companies
                    inputs["companies"] = entity_names[:20]

            depends = list(prev_ids) if prev_ids else []

            tasks.append(Task(
                id=task_id, tool=tool_name,
                inputs=inputs, label=tool_name,
                depends_on=depends,
            ))
            prev_ids = [task_id]

        return tasks if tasks else None

    @staticmethod
    def plan(
        prompt: str,
        state: SessionState,
        entities: Optional[Dict[str, Any]] = None,
        classification: Optional[Any] = None,
        goals: Optional[list[dict]] = None,
    ) -> Optional[List[Task]]:
        """Return a task list from classification chain, or None if LLM needed."""
        entities = entities or {}

        result = TaskPlanner.plan_from_classification(classification, state, entities)
        if result:
            logger.info(f"[TASK_PLANNER] Built {len(result)} tasks from classification chain")
            return result

        # No classification → need LLM decomposition
        return None

    @staticmethod
    async def plan_async(
        prompt: str,
        state: SessionState,
        entities: Optional[Dict[str, Any]] = None,
        goals: Optional[list[dict]] = None,
        model_router: Optional[Any] = None,
        tool_catalog: str = "",
    ) -> Optional[Tuple[List[Task], List[dict]]]:
        """Async LLM-powered task decomposition.

        One LLM call: sees the tool catalog + fingerprint + entities,
        returns a complete task DAG with dependencies and completion criteria.
        """
        if not model_router:
            return None

        entities = entities or {}
        fingerprint = state.fingerprint() if state else "STATE: empty"

        decomp_prompt = TaskPlanner.build_decomposition_prompt(
            prompt=prompt,
            fingerprint=fingerprint,
            entities=entities,
            goals=goals or [],
            tool_catalog=tool_catalog,
        )

        try:
            response = await model_router.get_completion(
                prompt=decomp_prompt,
                system_prompt=(
                    "You are a task decomposer for a strategic CFO agent. "
                    "Your job: break the user's request into the MINIMUM set of parallel tool calls "
                    "that gets them answers FAST. Never hedge. Never suggest 'maybe'. Never pad with "
                    "unnecessary steps. Read the fingerprint — if data exists, skip the fetch. "
                    "If data is missing, fetch it NOW. Parallelize everything that can be parallelized. "
                    "Return ONLY valid JSON. No markdown. No explanation. No prose. JUST THE JSON."
                ),
                capability="fast",
                max_tokens=800,
                temperature=0.0,
                json_mode=True,
                caller_context="task_planner_decompose",
            )

            raw = response.get("response", "{}") if isinstance(response, dict) else str(response)
            return TaskPlanner.parse_decomposition(raw)

        except Exception as e:
            logger.warning(f"[TASK_PLANNER] Async decomposition failed: {e}")
            return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _matches_any(text: str, patterns: list[str]) -> bool:
    """Check if text contains any of the given patterns."""
    return any(p in text for p in patterns)


# ---------------------------------------------------------------------------
# AgentTaskTracker — Dense progress string for agent loop context
# ---------------------------------------------------------------------------

class AgentTaskTracker:
    """Tracks task progress and produces a dense status string for LLM context."""

    def __init__(self, shared_data: Dict[str, Any]) -> None:
        self._sd = shared_data

    @property
    def tasks(self) -> List[Dict[str, Any]]:
        return self._sd.get("agent_tasks", [])

    def add(self, task_id: str, label: str, tool: str = "") -> None:
        tasks = self._sd.setdefault("agent_tasks", [])
        tasks.append({"id": task_id, "label": label, "tool": tool, "status": "pending"})

    def mark_running(self, task_id: str) -> None:
        for t in self.tasks:
            if t["id"] == task_id:
                t["status"] = "running"

    def mark_done(self, task_id: str) -> None:
        for t in self.tasks:
            if t["id"] == task_id:
                t["status"] = "done"

    def mark_failed(self, task_id: str) -> None:
        for t in self.tasks:
            if t["id"] == task_id:
                t["status"] = "failed"

    def summary_for_context(self) -> str:
        """Return a dense ~1-line status for LLM context injection."""
        if not self.tasks:
            return "No tasks yet"
        icons = {"done": "✓", "running": "→", "pending": "○", "failed": "✗"}
        parts = []
        for t in self.tasks:
            icon = icons.get(t["status"], "?")
            label = t.get("label") or t.get("tool") or t["id"]
            parts.append(f"{icon} {label}")
        return " | ".join(parts)


# ---------------------------------------------------------------------------
# SessionMemo — Compressed findings for context between LLM calls
# ---------------------------------------------------------------------------

class SessionMemo:
    """Append-only compressed findings that survive across agent loop turns.

    Generic compression: extracts key fields from any tool result dict.
    No tool-specific compression methods — handles everything uniformly.

    This prevents context rot: 10 tool calls ≈ 50K tokens of raw JSON.
    With SessionMemo: 10 tool calls ≈ 500 tokens of compressed findings.
    """

    def __init__(self, max_entries: int = 30) -> None:
        self._entries: List[str] = []
        self._max_entries = max_entries

    def add(self, tool: str, inputs: dict, result: dict) -> None:
        """Auto-compress a tool result into a 1-2 line finding."""
        entry = self._compress(tool, inputs, result)
        if entry:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]

    def add_raw(self, entry: str) -> None:
        """Add a raw memo entry (e.g. from LLM synthesis)."""
        if entry and entry.strip():
            self._entries.append(entry.strip())
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]

    def context(self, max_tokens: int = 800) -> str:
        """Return compressed findings for LLM context injection."""
        if not self._entries:
            return ""
        lines = ["FINDINGS (compressed from prior tools):"]
        total_chars = 0
        for entry in reversed(self._entries):
            if total_chars + len(entry) > max_tokens * 4:
                break
            lines.append(f"  - {entry}")
            total_chars += len(entry)
        return "\n".join(lines)

    @property
    def entries(self) -> List[str]:
        return list(self._entries)

    def _compress(self, tool: str, inputs: dict, result: dict) -> str:
        """Generic compression: extract key findings from any tool result."""
        if not isinstance(result, dict):
            return f"[{tool}] completed"

        # Handle errors
        if result.get("error"):
            return f"[{tool}] FAILED: {str(result['error'])[:80]}"

        # Extract entity name from inputs
        entity = (
            inputs.get("company_name") or inputs.get("company")
            or inputs.get("name") or inputs.get("entity")
            or inputs.get("query") or ""
        )
        entity_str = f" {entity}:" if entity else ""

        # Extract key numeric values from result
        key_values: list[str] = []
        for key, val in result.items():
            if key.startswith("_") or key in ("error", "status", "timing", "raw", "debug"):
                continue
            if isinstance(val, (int, float)) and val != 0:
                # Format monetary-looking values
                if any(kw in key.lower() for kw in ("revenue", "valuation", "nav", "value", "amount", "price", "cost")):
                    key_values.append(f"{key}={_fmt_money(val)}")
                elif any(kw in key.lower() for kw in ("rate", "pct", "percent", "margin", "irr", "yield")):
                    key_values.append(f"{key}={val:.1f}%")
                elif any(kw in key.lower() for kw in ("multiple", "tvpi", "dpi", "moic")):
                    key_values.append(f"{key}={val:.2f}x")
                else:
                    key_values.append(f"{key}={val}")
            elif isinstance(val, str) and val and len(val) < 50 and val not in ("N/A", "Unknown"):
                key_values.append(f"{key}={val}")
            elif isinstance(val, list):
                key_values.append(f"{key}=[{len(val)} items]")
            elif isinstance(val, dict) and val:
                key_values.append(f"{key}={{{len(val)} keys}}")

            if len(key_values) >= 5:
                break

        if key_values:
            return f"[{tool}]{entity_str} {', '.join(key_values)}"

        # Fallback: count output keys
        keys = [k for k in result.keys() if k not in ("error", "status", "timing")]
        return f"[{tool}]{entity_str} completed ({', '.join(keys[:5])})"
