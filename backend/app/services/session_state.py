"""
SessionState — A thin read-only lens over shared_data.

Wraps the same dict reference (no copy). Provides:
- fingerprint(): dense per-company field checklist for LLM context (cached until mutation)
- Typed property accessors for common keys
- Jurisdiction/market maps derived from currency + geography signals
- Analysis manifest tracking which derived data exists per-company
- Scoreboard counters derived from tool_results

TaskPlanner — Deterministic task queue generation.

Reads SessionState + extracted entities to produce a list of PlanStep-compatible
task dicts. Replaces the LLM REASON call for deterministic cases (80%+ of requests).

CompletionChecker — Python replacement for the REFLECT LLM call.

Evaluates goals against the scoreboard. Pure Python, zero LLM tokens.
"""

from __future__ import annotations

import hashlib
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

# Tracked fields for per-company checklist — order matters for display
_CORE_FIELDS = ("revenue", "valuation", "stage", "sector", "tam", "team_size")
_ENRICHMENT_FIELDS = ("cap_table", "scenarios", "rev_projections")


def _infer_jurisdiction(company: dict) -> str:
    """Derive market jurisdiction from currency, location, or geography fields.
    Returns 2-letter code or '' if unknown. No API calls — pure signal extraction.
    """
    # 1. Explicit currency field → strongest signal
    ccy = (company.get("currency") or company.get("reporting_currency") or "").upper().strip()
    if ccy and ccy in _CURRENCY_TO_JURISDICTION:
        return _CURRENCY_TO_JURISDICTION[ccy]

    # 2. Location / geography / hq_location field
    for loc_key in ("hq_location", "location", "geography", "hq", "geo", "country"):
        loc = (company.get(loc_key) or "").lower().strip()
        if not loc:
            continue
        # Direct match
        if loc in _LOCATION_TO_JURISDICTION:
            return _LOCATION_TO_JURISDICTION[loc]
        # Substring match (e.g. "San Francisco, CA" → "san francisco")
        for city, code in _LOCATION_TO_JURISDICTION.items():
            if city in loc:
                return code
        # Country-level fallback
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


def _field_status(company: dict, field_name: str) -> str:
    """Return '+' (actual data), '~' (inferred), or '-' (missing) for a field."""
    # Check for actual data
    actual = company.get(field_name)
    if field_name == "revenue":
        actual = actual or company.get("arr")
    elif field_name == "sector":
        actual = actual or company.get("category") or company.get("vertical") or company.get("industry")
    elif field_name == "tam":
        actual = actual or company.get("tam_estimate") or company.get("market_size")
    elif field_name == "cap_table":
        actual = company.get("cap_table_history") or company.get("ownership_data")
    elif field_name == "scenarios":
        actual = company.get("scenario_analysis") or company.get("exit_scenarios")
    elif field_name == "rev_projections":
        actual = company.get("revenue_projections") or company.get("projected_revenue")

    if _is_real_value(actual):
        # Check if it's inferred
        inferred_val = company.get(f"inferred_{field_name}")
        if inferred_val and actual == inferred_val and not company.get(f"_actual_{field_name}"):
            return "~"
        return "+"

    # Check inferred fallback
    inferred = company.get(f"inferred_{field_name}")
    if _is_real_value(inferred):
        return "~"

    return "-"


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


# ---------------------------------------------------------------------------
# SessionState
# ---------------------------------------------------------------------------

class SessionState:
    """Read-only lens over shared_data. Same dict reference, not a copy.

    Every existing method (_execute_company_fetch, _execute_valuation, etc.)
    keeps writing ``shared_data["companies"] = ...`` exactly as before.
    SessionState just reads from the same dict and provides a dense
    fingerprint for LLM context injection: per-company field checklists,
    jurisdiction maps, sector concentrations, and analysis manifests.
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
    def grid_company_names(self) -> list:
        return (
            self.matrix_context.get("companyNames")
            or self.matrix_context.get("company_names")
            or []
        )

    @property
    def portfolio_size(self) -> int:
        return len(self.grid_company_names)

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
        """Dense per-company state fingerprint. Cached until mark_dirty()."""
        if not self._dirty:
            return self._cached_fingerprint
        self._cached_fingerprint = self._build_fingerprint()
        self._dirty = False
        return self._cached_fingerprint

    def _build_fingerprint(self) -> str:
        """Build a dense state summary with per-company field checklist,
        jurisdiction map, sector concentrations, and analysis manifest.
        ~300-500 tokens — enough for the agent to see its own progress.

        Legend: + = actual data, ~ = inferred, - = missing
        Fields: rev val stg sec tam team | cap scn proj
        """
        lines: list[str] = []

        # ── Merge all company knowledge: grid + enriched ──────────────────
        # Build a unified company map keyed by normalized name
        company_map: dict[str, dict] = {}  # name → merged data

        # 1. Grid rows (matrix context)
        rows = self.grid_rows
        for row in rows:
            name = row.get("companyName") or row.get("company_name") or ""
            if not name:
                continue
            cells = row.get("cells") or row.get("cellValues") or {}
            merged = company_map.setdefault(name, {"_source": "grid"})
            for k, v in cells.items():
                val = v.get("value", v) if isinstance(v, dict) else v
                if _is_real_value(val):
                    merged[k.lower()] = val

        # 2. Enriched companies from shared_data
        sd_companies = self.companies
        for c in sd_companies:
            name = c.get("company") or c.get("name") or ""
            if not name:
                continue
            merged = company_map.setdefault(name, {"_source": "enriched"})
            merged["_source"] = "enriched"  # upgrade source
            # Overlay all fields from enriched data
            for k, v in c.items():
                if k.startswith("_"):
                    continue
                if _is_real_value(v):
                    merged[k] = v

        # 3. Per-company analysis data from shared_data top-level keys
        analysis_keys_map: dict[str, dict[str, list[str]]] = {}  # key → {company_name: [keys]}
        for sd_key, company_field in [
            ("cap_table_history", "cap_table"),
            ("scenario_analysis", "scenarios"),
            ("revenue_projections", "rev_projections"),
            ("exit_modeling", "scenarios"),
            ("followon_strategy", "followon"),
        ]:
            sd_val = self._data.get(sd_key)
            if not sd_val:
                continue
            if isinstance(sd_val, dict):
                # Per-company keyed dict (e.g., revenue_projections[company_name])
                for comp_name in sd_val:
                    if comp_name in company_map:
                        company_map[comp_name][company_field] = sd_val[comp_name]
                    # Also track in manifest
                    analysis_keys_map.setdefault(sd_key, []).append(comp_name)
            elif isinstance(sd_val, list) and sd_val:
                # List-based (applies to all companies)
                analysis_keys_map.setdefault(sd_key, []).append("*all*")

        total = len(company_map)
        if not total:
            lines.append("STATE: empty — no companies in grid or shared_data")
            return "\n".join(lines)

        # ── Per-company field checklist ───────────────────────────────────
        lines.append(f"COMPANIES ({total}) — Legend: +=actual ~=inferred -=missing")
        lines.append(f"  {'name':<20} rev    val    stg sec tam  team | cap scn proj | jur  ccy  sector")

        # Aggregation accumulators
        jurisdiction_counts: dict[str, list[str]] = {}  # jur → [names]
        sector_counts: dict[str, list[str]] = {}        # sector → [names]
        stage_counts: dict[str, int] = {}
        missing_fields_total: dict[str, int] = {f: 0 for f in _CORE_FIELDS}
        total_rev = 0.0
        total_val = 0.0
        currencies_seen: dict[str, int] = {}

        for name, data in company_map.items():
            # Field status markers
            statuses = []
            for f in _CORE_FIELDS:
                statuses.append(_field_status(data, f))
            for f in _ENRICHMENT_FIELDS:
                statuses.append(_field_status(data, f))

            # Count missing
            for i, f in enumerate(_CORE_FIELDS):
                if statuses[i] == "-":
                    missing_fields_total[f] += 1

            # Jurisdiction
            jur = _infer_jurisdiction(data)
            ccy = (data.get("currency") or data.get("reporting_currency") or "").upper()
            if not ccy and jur:
                # Reverse-map jurisdiction to likely currency
                ccy = {"US": "USD", "UK": "GBP", "EU": "EUR", "CH": "CHF",
                        "JP": "JPY", "CA": "CAD", "AU": "AUD", "IN": "INR",
                        "IL": "ILS", "SG": "SGD", "BR": "BRL", "KR": "KRW",
                        "CN": "CNY", "HK": "HKD", "AE": "AED"}.get(jur, "")

            if jur:
                jurisdiction_counts.setdefault(jur, []).append(name)
            if ccy:
                currencies_seen[ccy] = currencies_seen.get(ccy, 0) + 1

            # Sector
            sector = (data.get("sector") or data.get("category") or
                      data.get("vertical") or data.get("industry") or "")
            if isinstance(sector, str) and sector and sector not in ("Unknown", "N/A"):
                sector_counts.setdefault(sector, []).append(name)

            # Stage
            stage = data.get("stage") or data.get("funding_stage") or ""
            if isinstance(stage, str) and stage and stage not in ("Unknown", "N/A"):
                stage_counts[stage] = stage_counts.get(stage, 0) + 1

            # Revenue & valuation for totals
            rev = data.get("revenue") or data.get("arr") or data.get("inferred_revenue") or 0
            val = data.get("valuation") or data.get("inferred_valuation") or 0
            try:
                total_rev += float(rev)
                total_val += float(val)
            except (TypeError, ValueError):
                pass

            # Compact revenue/valuation display
            rev_display = _fmt_money(rev, ccy) if rev else ""
            val_display = _fmt_money(val, ccy) if val else ""

            # Build the checklist line
            core_markers = " ".join(f"{s:<1}" for s in statuses[:len(_CORE_FIELDS)])
            enrich_markers = " ".join(f"{s:<1}" for s in statuses[len(_CORE_FIELDS):])
            sector_short = (sector[:12] if sector else "-")
            jur_display = jur or "-"
            ccy_display = ccy or "-"

            # Compact: name [markers] | [enrichment markers] | jurisdiction sector
            line = (
                f"  {name:<20} {core_markers}   | {enrich_markers}    "
                f"| {jur_display:<4} {ccy_display:<4} {sector_short}"
            )
            # Append key values inline if present
            val_parts = []
            if rev_display:
                val_parts.append(f"rev={rev_display}")
            if val_display:
                val_parts.append(f"val={val_display}")
            if val_parts:
                line += f"  ({', '.join(val_parts)})"
            lines.append(line)

        # ── Jurisdiction map (multi-market awareness) ─────────────────────
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
            # Flag multi-jurisdiction exposure
            if len(jurisdiction_counts) > 1:
                non_us = {j: n for j, n in jurisdiction_counts.items() if j != "US"}
                if non_us:
                    cross_border = []
                    for j, names in non_us.items():
                        cross_border.extend(f"{n}({j})" for n in names[:3])
                    lines.append(f"CROSS-BORDER: {', '.join(cross_border[:10])}")

        # ── Sector concentration ──────────────────────────────────────────
        if sector_counts:
            lines.append("")
            sorted_sectors = sorted(sector_counts.items(), key=lambda x: -len(x[1]))
            sec_parts = []
            for s, names in sorted_sectors[:6]:
                pct = len(names) / total * 100
                sec_parts.append(f"{s}:{len(names)}({pct:.0f}%)[{','.join(names[:3])}]")
            lines.append(f"SECTORS: {' | '.join(sec_parts)}")
            # Concentration flag
            if sorted_sectors and len(sorted_sectors[0][1]) / total > 0.4:
                lines.append(f"  FLAG: Heavy concentration in {sorted_sectors[0][0]} ({len(sorted_sectors[0][1])}/{total})")

        # ── Stage distribution ────────────────────────────────────────────
        if stage_counts:
            stage_parts = [f"{s}:{c}" for s, c in sorted(stage_counts.items(), key=lambda x: -x[1])]
            lines.append(f"STAGES: {', '.join(stage_parts)}")

        # ── Data quality summary ──────────────────────────────────────────
        sparse = [f for f, cnt in missing_fields_total.items() if cnt > total * 0.3]
        if sparse:
            lines.append("")
            lines.append(f"GAPS: {', '.join(f'{f}({missing_fields_total[f]}/{total} missing)' for f in sparse)}")
            self._data["needs_auto_enrich"] = True
            self._data["auto_enrich_fields"] = sparse

        # ── Analysis manifest (per-company granularity) ───────────────────
        if analysis_keys_map:
            lines.append("")
            for key, companies in analysis_keys_map.items():
                if "*all*" in companies:
                    lines.append(f"ANALYSIS[{key}]: all companies")
                else:
                    lines.append(f"ANALYSIS[{key}]: {', '.join(companies[:8])}")

        # ── Freshness status ──────────────────────────────────────────────
        fresh_count = 0
        stale_count = 0
        for _name, _data in company_map.items():
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

        # ── Fund metrics ──────────────────────────────────────────────────
        fm = self.fund_metrics
        if fm:
            fm_parts = []
            if fm.get("tvpi"):
                fm_parts.append(f"TVPI={fm['tvpi']:.2f}x")
            if fm.get("dpi"):
                fm_parts.append(f"DPI={fm['dpi']:.2f}x")
            if fm.get("irr"):
                fm_parts.append(f"IRR={fm['irr']:.1f}%")
            if fm_parts:
                lines.append(f"FUND: {', '.join(fm_parts)}")

        # ── Portfolio totals ──────────────────────────────────────────────
        if total_rev > 0 or total_val > 0:
            totals = []
            if total_rev > 0:
                totals.append(f"total_rev={_fmt_money(total_rev)}")
            if total_val > 0:
                totals.append(f"total_val={_fmt_money(total_val)}")
            lines.append(f"TOTALS: {', '.join(totals)}")

        return "\n".join(lines)

    # -- Intelligence gates ------------------------------------------------

    def company_needs(self, name: str) -> Dict[str, bool]:
        """What does this company still need? Returns field → bool map.

        Used by TaskPlanner to skip redundant fetches. If all core fields
        are '+' or '~', the company doesn't need a fetch — just valuation
        or analysis.
        """
        company = self._find_company(name)
        if not company:
            return {"fetch": True, "valuation": True, "cap_table": True,
                    "scenarios": True, "memo": True}

        core_status = {f: _field_status(company, f) for f in _CORE_FIELDS}
        enrich_status = {f: _field_status(company, f) for f in _ENRICHMENT_FIELDS}

        missing_core = sum(1 for s in core_status.values() if s == "-")
        has_revenue = core_status.get("revenue", "-") != "-"
        has_valuation = core_status.get("valuation", "-") != "-"

        # Check freshness — if _fetched_at exists and is recent, skip fetch
        fetched_at = company.get("_fetched_at")
        is_stale = True
        if fetched_at:
            try:
                from datetime import datetime, timezone
                age_seconds = (datetime.now(timezone.utc) - datetime.fromisoformat(fetched_at)).total_seconds()
                is_stale = age_seconds > 300  # 5 min TTL
            except Exception:
                pass

        return {
            "fetch": missing_core >= 3 and is_stale,       # 3+ core fields missing AND stale
            "enrich": missing_core >= 1 and is_stale,      # any core field missing AND stale
            "valuation": enrich_status.get("scenarios", "-") == "-" and has_revenue,
            "cap_table": enrich_status.get("cap_table", "-") == "-",
            "scenarios": enrich_status.get("scenarios", "-") == "-",
            "memo": True,  # always allowed
        }

    def companies_needing(self, action: str, names: Optional[List[str]] = None) -> List[str]:
        """Filter a list of company names to those that actually need `action`.

        action: one of 'fetch', 'enrich', 'valuation', 'cap_table', 'scenarios'
        names: if None, uses all known companies
        """
        if names is None:
            names = [
                c.get("company") or c.get("name") or ""
                for c in self.companies
            ] + list(self.grid_company_names)
            names = list(dict.fromkeys(n for n in names if n))  # dedupe, preserve order

        return [n for n in names if self.company_needs(n).get(action, True)]

    def _find_company(self, name: str) -> Optional[dict]:
        """Find a company by name in shared_data or grid rows."""
        name_lower = name.lower().strip().lstrip("@")
        # Check enriched companies first
        for c in self.companies:
            cn = (c.get("company") or c.get("name") or "").lower().strip()
            if cn == name_lower or cn.startswith(name_lower):
                return c
        # Check grid rows
        for row in self.grid_rows:
            cn = (row.get("companyName") or row.get("company_name") or "").lower().strip()
            if cn == name_lower or cn.startswith(name_lower):
                cells = row.get("cells") or row.get("cellValues") or {}
                flat = {}
                for k, v in cells.items():
                    flat[k.lower()] = v.get("value", v) if isinstance(v, dict) else v
                return flat
        return None

    # -- Analysis manifest persistence ------------------------------------

    def analysis_manifest(self) -> dict:
        """Return a lightweight manifest of which analysis data exists per company.
        Used to restore shared_data keys across requests.
        """
        manifest: dict[str, Any] = {}
        for sd_key in ("cap_table_history", "scenario_analysis", "exit_modeling",
                        "followon_strategy", "portfolio_health", "revenue_projections",
                        "fund_deployment"):
            val = self._data.get(sd_key)
            if not val:
                continue
            if isinstance(val, dict):
                manifest[sd_key] = list(val.keys())
            elif isinstance(val, list):
                manifest[sd_key] = f"{len(val)} items"
            else:
                manifest[sd_key] = True
        return manifest

    def restore_manifest(self, manifest: dict) -> None:
        """Restore analysis data presence markers from a previous session's manifest.
        Actual data must be re-fetched, but this tells the agent what WAS computed.
        """
        for key, info in manifest.items():
            if not self._data.get(key):
                # Store a sentinel so the agent knows this data existed but needs refresh
                self._data[f"_stale_{key}"] = info
        self._dirty = True


def _cell_has_value(v: Any) -> bool:
    """Check if a cell value is non-empty."""
    val = v.get("value", v) if isinstance(v, dict) else v
    return bool(val) and val != "N/A" and val != "Unknown" and val != ""


# ---------------------------------------------------------------------------
# Scoreboard — Computed from tool_results list
# ---------------------------------------------------------------------------

@dataclass
class Scoreboard:
    """Counters derived from tool_results. Pure Python, no LLM."""
    fetch_count: int = 0
    valuation_count: int = 0
    memo_count: int = 0
    memo_section_count: int = 0
    chart_count: int = 0
    suggest_count: int = 0
    auto_suggest_count: int = 0

    @classmethod
    def from_tool_results(cls, tool_results: list[dict]) -> "Scoreboard":
        sb = cls()
        for r in tool_results:
            tool = r.get("tool", "")
            output = r.get("output", {})
            if tool in ("fetch_company_data", "resolve_data_gaps"):
                sb.fetch_count += 1
            elif tool == "run_valuation":
                sb.valuation_count += 1
            elif tool in ("generate_memo", "run_report", "write_to_memo"):
                sb.memo_count += 1
            elif tool == "generate_chart":
                sb.chart_count += 1
            elif tool in ("suggest_grid_edit", "suggest_action"):
                sb.suggest_count += 1
            if isinstance(output, dict):
                sb.auto_suggest_count += output.get("auto_suggestions_count", 0)
                # Count memo_sections emitted as side effects from ANY tool
                side_sections = output.get("memo_sections")
                if isinstance(side_sections, list):
                    sb.memo_section_count += len(side_sections)
        # Promote: if tools auto-emitted memo sections, reflect that in memo_count
        # so goals like "memo_count > 0" pass without needing an explicit write_to_memo
        if sb.memo_section_count >= 2 and sb.memo_count == 0:
            sb.memo_count = 1
        return sb


# ---------------------------------------------------------------------------
# CompletionChecker — Replaces the REFLECT LLM call
# ---------------------------------------------------------------------------

class CompletionChecker:
    """Evaluates extracted goals against the scoreboard. Pure Python."""

    # Track previous scoreboard for stale-detection across iterations
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

        Goals have a "check" field like "fetch_count > 0", "valuation_count >= portfolio_size",
        "memo_count > 0". We eval these against the scoreboard.

        Early-exit: if tool_results count hasn't changed since last check,
        the loop is spinning — break instead of wasting iterations.
        """
        current_tool_count = len(tool_results)

        if not goals:
            # No goals extracted — fall back to "at least one tool ran"
            if tool_results:
                cls._prev_tool_count = current_tool_count
                return True, "no goals but tools have run"
            return False, "no tools called yet"

        # Stale scoreboard detection: if no new tools ran since last check, break
        if current_tool_count > 0 and current_tool_count == cls._prev_tool_count:
            logger.info("[COMPLETION] Scoreboard unchanged — breaking stale loop")
            cls._prev_tool_count = 0  # reset for next request
            return True, "scoreboard unchanged — no further progress possible"
        cls._prev_tool_count = current_tool_count

        env = {
            "fetch_count": scoreboard.fetch_count,
            "valuation_count": scoreboard.valuation_count,
            "memo_count": scoreboard.memo_count,
            "memo_section_count": scoreboard.memo_section_count,
            "chart_count": scoreboard.chart_count,
            "suggest_count": scoreboard.suggest_count + scoreboard.auto_suggest_count,
            "portfolio_size": portfolio_size,
        }

        for goal in goals:
            check = goal.get("check", "")
            if not check:
                continue
            try:
                if not _safe_eval_check(check, env):
                    desc = goal.get("description", check)
                    return False, f"goal not met: {desc}"
            except Exception:
                # If we can't parse the check expression, be conservative
                continue

        return True, "all goals satisfied"


def _safe_eval_check(expr: str, env: dict) -> bool:
    """Evaluate a simple comparison expression like 'fetch_count > 0'.

    Only supports: var > N, var >= N, var == N, var < N, var <= N.
    No arbitrary code execution.
    """
    expr = expr.strip()

    # Match patterns like "fetch_count > 0" or "valuation_count >= portfolio_size"
    m = re.match(r'^(\w+)\s*(>=|<=|>|<|==|!=)\s*(\w+)$', expr)
    if not m:
        return True  # Can't parse → assume satisfied (conservative)

    left_name, op, right_name = m.groups()
    left = env.get(left_name, 0)
    right = env.get(right_name) if right_name in env else _try_int(right_name)

    if right is None:
        return True  # Can't resolve → assume satisfied

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
    """Match entity names flexibly: 'dynelectro' matches 'dynelectro technologies'.

    Handles the common case where the plan says 'Dynelectro' but the tool
    output says 'Dynelectro Technologies Inc.' or vice versa.
    """
    if not goal_entity or not candidate:
        return False
    if goal_entity == candidate:
        return True
    # Substring: either contains the other
    return goal_entity in candidate or candidate in goal_entity


@dataclass
class TaskGoal:
    """A single goal the agent must satisfy, derived from the TaskPlanner's plan."""
    id: str
    description: str
    tool_match: str          # tool name that satisfies this goal
    entity: Optional[str]    # company name, or None for portfolio-wide
    status: str = "pending"  # pending | done
    depends_on: List[str] = field(default_factory=list)


class TaskLedger:
    """Deterministic per-task completion gate. Replaces flat Scoreboard checks.

    Created from prompt + entities (no LLM). Updated after each tool execution.
    The agent loop checks ``is_complete()`` instead of the old CompletionChecker.
    """

    def __init__(self, goals: List[TaskGoal]) -> None:
        self.goals = goals
        # Track (tool, entity) attempts per goal to detect stale loops
        self._attempt_counts: Dict[str, int] = {}  # goal_id -> consecutive attempts with no progress

    @classmethod
    def from_plan_tasks(cls, tasks: List["Task"]) -> "TaskLedger":
        """Build a ledger from the TaskPlanner's actual plan — no keyword matching.

        Each Task from the planner becomes a TaskGoal. Dependencies are preserved
        so next_actions() only returns tasks whose deps are satisfied.
        """
        goals: List[TaskGoal] = []
        for t in tasks:
            # Extract entity from task inputs (different tools use different keys)
            entity = (
                t.inputs.get("company_name")
                or t.inputs.get("company")
                or t.inputs.get("company_id")
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

        Also tracks repeated attempts per goal. If a tool runs for the same
        goal twice without the goal getting marked done (entity name mismatch),
        the goal is force-completed on the second attempt to break stale loops.
        """
        # Snapshot pending goal IDs before this update
        pending_before = {g.id for g in self.goals if g.status != "done"}

        for tr in tool_results:
            tool = tr.get("tool", "")
            inputs = tr.get("input", {})
            output = tr.get("output", {})

            for goal in self.goals:
                if goal.status == "done":
                    continue

                # Match by tool name
                tool_matches = False
                if goal.tool_match == tool:
                    tool_matches = True
                # resolve_data_gaps and lightweight_diligence also satisfy fetch goals
                elif goal.tool_match == "fetch_company_data" and tool in (
                    "resolve_data_gaps", "lightweight_diligence",
                    "search_company_funding", "search_company_product",
                    "search_company_team", "search_company_market",
                    "batch_enrich", "enrich_portfolio",
                ):
                    tool_matches = True
                # batch_valuate satisfies individual valuation goals
                elif goal.tool_match == "run_valuation" and tool == "batch_valuate":
                    tool_matches = True
                # Various memo tools satisfy the memo goal
                elif goal.tool_match == "generate_memo" and tool in (
                    "generate_memo", "generate_ic_memo", "generate_lp_report",
                    "generate_gp_update", "generate_comparison_report",
                    "generate_followon_memo", "generate_deck", "write_to_memo",
                    "run_report",
                ):
                    tool_matches = True

                if not tool_matches:
                    continue

                # For entity-specific goals, verify the entity was actually processed
                if goal.entity:
                    entity_lower = goal.entity.lower().strip().lstrip("@")
                    entity_found = False

                    # Check inputs for company name (fuzzy: substring match)
                    for key in ("company_name", "company", "company_id", "name"):
                        val = inputs.get(key, "")
                        if isinstance(val, str):
                            val_lower = val.lower().strip().lstrip("@")
                            if _fuzzy_entity_match(entity_lower, val_lower):
                                entity_found = True
                                break

                    # Check inputs for company lists (batch tools)
                    if not entity_found:
                        for key in ("companies",):
                            val = inputs.get(key, [])
                            if isinstance(val, list):
                                for v in val:
                                    if isinstance(v, str) and _fuzzy_entity_match(entity_lower, v.lower().strip().lstrip("@")):
                                        entity_found = True
                                        break

                    # Check output for company name (resolve_data_gaps returns results for multiple)
                    if not entity_found and isinstance(output, dict):
                        for key in ("companies", "results", "company_data"):
                            out_val = output.get(key)
                            if isinstance(out_val, dict) and any(
                                _fuzzy_entity_match(entity_lower, k.lower().strip().lstrip("@")) for k in out_val
                            ):
                                entity_found = True
                                break
                            elif isinstance(out_val, list):
                                for item in out_val:
                                    if isinstance(item, dict):
                                        cn = (item.get("company") or item.get("name") or item.get("company_name") or "")
                                        if _fuzzy_entity_match(entity_lower, cn.lower().strip().lstrip("@")):
                                            entity_found = True
                                            break

                    if not entity_found:
                        continue

                # Goal is satisfied
                goal.status = "done"
                logger.info(f"[TASK_LEDGER] Goal '{goal.id}' marked done (tool={tool})")

        # --- Stale-loop breaker ---
        # For goals that were pending before AND are still pending after,
        # check if the matching tool ran (tool_matches=True) but entity
        # didn't match. Increment attempt counter; force-complete after 2 stale hits.
        still_pending = {g.id for g in self.goals if g.status != "done"}
        tools_called = {tr.get("tool", "") for tr in tool_results}

        for goal in self.goals:
            if goal.status == "done":
                # Reset counter for completed goals
                self._attempt_counts.pop(goal.id, None)
                continue
            if goal.id not in pending_before:
                continue  # newly added goal, skip

            # Check if the tool that would satisfy this goal was called
            goal_tool_ran = (
                goal.tool_match in tools_called
                or (goal.tool_match == "fetch_company_data" and tools_called & {
                    "resolve_data_gaps", "lightweight_diligence",
                    "search_company_funding", "search_company_product",
                    "search_company_team", "search_company_market",
                    "batch_enrich", "enrich_portfolio",
                })
                or (goal.tool_match == "run_valuation" and "batch_valuate" in tools_called)
                or (goal.tool_match == "generate_memo" and tools_called & {
                    "generate_memo", "generate_ic_memo", "generate_lp_report",
                    "generate_gp_update", "generate_comparison_report",
                    "generate_followon_memo", "generate_deck", "write_to_memo",
                    "run_report",
                })
            )

            if goal_tool_ran and goal.id in still_pending:
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
        """Return goals that are not yet done."""
        return [g for g in self.goals if g.status != "done"]

    def pending_summary(self) -> str:
        """Dense one-line status for REASON prompt injection.

        Example: "✓ query_portfolio | ○ fetch(Dynelectro) | ✓ fetch(Group 14)"
        """
        parts = []
        for g in self.goals:
            icon = "✓" if g.status == "done" else "○"
            parts.append(f"{icon} {g.id}")
        return " | ".join(parts)

    def next_actions(self) -> List[Dict[str, Any]]:
        """Return tool call dicts for goals whose dependencies are all satisfied.

        Only returns "ready" goals — pending goals whose depends_on are all done.
        This respects the TaskPlanner's DAG ordering: fetch before valuation,
        valuation before memo, etc.
        """
        done_ids = {g.id for g in self.goals if g.status == "done"}
        actions: List[Dict[str, Any]] = []
        seen_tools: set = set()

        for goal in self.goals:
            if goal.status == "done":
                continue

            # Skip goals whose dependencies aren't satisfied yet
            if goal.depends_on and not all(dep in done_ids for dep in goal.depends_on):
                continue

            key = (goal.tool_match, goal.entity or "")
            if key in seen_tools:
                continue
            seen_tools.add(key)

            # Re-use the original task inputs stored in the goal
            # (from_plan_tasks preserves them via Task.inputs)
            # Fall back to building inputs from entity if needed
            inputs: Dict[str, Any] = {}
            if goal.entity:
                if goal.tool_match in ("fetch_company_data", "lightweight_diligence",
                                        "search_company_funding", "search_company_product",
                                        "search_company_team", "search_company_market",
                                        "analyze_financials"):
                    inputs["company_name"] = goal.entity
                elif goal.tool_match in ("run_valuation",):
                    inputs["company_id"] = goal.entity
                elif goal.tool_match in ("cap_table_evolution", "run_exit_modeling",
                                          "run_followon_strategy"):
                    inputs["company"] = goal.entity
                else:
                    inputs["company_name"] = goal.entity

            if goal.tool_match == "query_portfolio":
                inputs["query"] = "portfolio overview"

            actions.append({
                "tool": goal.tool_match,
                "input": inputs,
            })

        return actions


# ---------------------------------------------------------------------------
# TaskPlanner — Deterministic task queue from intent + entities
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
        """Convert to the action dict format the agent loop expects."""
        return {
            "action": "call_tool",
            "tool": self.tool,
            "input": self.inputs,
            "reasoning": self.label,
        }


class TaskPlanner:
    """LLM-powered task decomposition with deterministic fallbacks.

    Primary path: builds a structured prompt with the tool catalog +
    fingerprint + entities, asks the LLM to decompose into a task DAG.
    One LLM call → full plan. No keyword matching.

    Fallback: if LLM decomposition fails or returns garbage, uses
    classification.suggested_chain to build a plan from the already-
    classified intent.

    Returns None only when both paths fail — caller falls back to
    the per-iteration LLM REASON calls.
    """

    # Tool catalog for the decomposition LLM — compact descriptions
    TOOL_CATALOG = """TOOLS (use these exact names):
- resolve_data_gaps: Fill missing company data (benchmarks + parallel web search). Run FIRST when data is sparse. Inputs: {companies: ["name1",...], needed_fields: ["revenue","valuation",...]?}
- fetch_company_data: Full 4-search extraction + gap filling + valuation for one company. Inputs: {company_name: "str"}
- search_company_funding: 1 focused search for funding/valuation/investors. Inputs: {company_name: "str"}
- search_company_product: 1 focused search for product/business model/pricing. Inputs: {company_name: "str"}
- search_company_team: 1 focused search for founders/team/headcount. Inputs: {company_name: "str"}
- search_company_market: 1 focused search for competitors/TAM/market. Inputs: {company_name: "str"}
- run_valuation: PWERM/DCF/OPM valuation for one company. Inputs: {company_id: "str", method: "str"?}
- cap_table_evolution: Track dilution through all funding rounds. Inputs: {company: "str"}
- liquidation_waterfall: Model liquidation at exit value. Inputs: {company: "str", exit_value: float}
- run_exit_modeling: Model IPO/M&A/secondary exit scenarios. Inputs: {company: "str"}
- run_followon_strategy: Follow-on / pro-rata analysis. Inputs: {company: "str"}
- run_round_modeling: Next funding round dilution/waterfall. Inputs: {company: "str"}
- run_scenario: What-if scenario modeling. Inputs: {scenario_description: "str"}
- stress_test_portfolio: Portfolio-wide shock modeling. Inputs: {shock_type: "str", magnitude: float?}
- monte_carlo_portfolio: Monte Carlo simulation across portfolio. Inputs: {iterations: int?}
- sensitivity_matrix: 2D sensitivity analysis. Inputs: {company: "str", var_x: "str", var_y: "str"}
- calculate_fund_metrics: Fund-level NAV/IRR/DPI/TVPI/pacing. Inputs: {fund_id: "str"?}
- query_portfolio: Load/filter portfolio grid data. Inputs: {query: "str"}
- run_portfolio_health: Portfolio health dashboard. Inputs: {fund_id: "str"?}
- graduation_rates: Stage progression analysis. Inputs: {fund_id: "str"?}
- portfolio_comparison: Side-by-side N-company comparison. Inputs: {companies: ["str"], metrics: ["str"]?}
- generate_memo: Generate memo/report. Types: ic_memo, followon, lp_report, comparison, fund_analysis. Inputs: {memo_type: "str"?, prompt: "str"?}
- generate_ic_memo: Investment committee memo. Inputs: {company: "str"}
- generate_lp_report: Quarterly LP report. Inputs: {fund_id: "str"?, quarter: "str"?}
- generate_gp_update: GP strategy update. Inputs: {fund_id: "str"?}
- generate_comparison_report: Side-by-side comparison report. Inputs: {companies: ["str"]}
- generate_followon_memo: Follow-on investment memo. Inputs: {company: "str"}
- generate_deck: Investment deck/presentation. Inputs: {title: "str"?}
- generate_chart: Chart config (bar/line/scatter/sankey/waterfall/probability_cloud). Inputs: {chart_type: "str", data_source: "str"?}
- run_projection: Revenue/ARR projection with growth curves. Inputs: {company: "str"?, years: int?}
- revenue_projection: Revenue projection with decay curves. Inputs: {company: "str", years: int?}
- analyze_financials: Compute financial metrics from existing data (no web). Inputs: {company_name: "str"}
- fx_check: Check FX rates and currency impact. Inputs: {base_currency: "str"?}
- fx_portfolio_impact: Full portfolio FX exposure analysis. Inputs: {base_currency: "str"?, shock_pct: float?}
- convert_currency: Convert monetary values to target currency. Inputs: {target_currency: "str", source_currency: "str"?}
- compliance_check: Filing requirements, Form ADV, AIFMD. Inputs: {check_type: "str"?}
- run_fpa: FP&A forecast/stress test/sensitivity/regression. Inputs: {query: "str", type: "str"?}
- fund_deployment_model: J-curve/pacing/reserve modeling. Inputs: {fund_id: "str"?}
- sync_crm: Sync companies to CRM (Attio/Affinity). Inputs: {companies: ["str"]?, direction: "str"?}
- crm_search: Search CRM for companies/deals/notes. Inputs: {query: "str", entity_type: "str"?}
- crm_log_interaction: Log meeting/call/note to CRM. Inputs: {company: "str", note_type: "str", content: "str"}
- crm_pipeline_update: Update deal pipeline stage. Inputs: {company: "str", stage: "str", deal_value: float?}
- suggest_grid_edit: Suggest a cell edit on portfolio grid. Inputs: {company: "str", column: "str", value: any, reasoning: "str"}
- suggest_action: Suggest action item/warning/insight. Inputs: {type: "str", title: "str", description: "str"}
- batch_valuate: Run valuations across multiple companies in parallel. Inputs: {companies: ["str"], method: "str"?}
- batch_enrich: Enrich multiple companies in parallel. Inputs: {companies: ["str"], fields: ["str"]?}
- web_search: Search web for market data/comparables/news. Inputs: {query: "str"}
- lightweight_diligence: Quick 1-search company lookup. Inputs: {company_name: "str"}
- world_model_scenario: Multi-factor scenario with propagated effects. Inputs: {company: "str", factor_changes: dict}
- ma_workflow: M&A deal structure analysis. Inputs: {acquirer: "str", target: "str"}
- build_company_list: Search for companies matching criteria. Inputs: {criteria: "str", sector: "str"?}
- enrich_portfolio: Analyze full grid, identify gaps, compute distributions. Inputs: {fund_id: "str"?}
- market_landscape: Competitive landscape mapping. Inputs: {sector: "str", geography: "str"?}
- write_to_memo: Write a section to the analysis memo (prose + optional chart + optional table). Streams to user in real-time. Inputs: {section_title: "str"?, text: "str", chart_type: "str"?, chart_data: {}?, table: {}?}"""

    @staticmethod
    def build_decomposition_prompt(
        prompt: str,
        fingerprint: str,
        entities: Dict[str, Any],
        goals: list[dict],
    ) -> str:
        """Build the LLM prompt for task decomposition."""
        company_names = entities.get("companies", [])
        goals_json = json.dumps(goals) if goals else "[]"
        companies_json = json.dumps(company_names) if company_names else "[]"

        return f"""Decompose this user request into a task DAG.

USER REQUEST: {prompt}

ENTITIES: {companies_json}

CURRENT STATE:
{fingerprint}

USER GOALS: {goals_json}

{TaskPlanner.TOOL_CATALOG}

RULES (FOLLOW EXACTLY — NO EXCEPTIONS):
1. READ THE FINGERPRINT. If a field shows + or ~, DO NOT re-fetch it. Skip straight to analysis/valuation. If it shows -, you MUST fill it before proceeding. No excuses.
2. For missing data: resolve_data_gaps for bulk (3+ companies), parallel search_company_* for 1-2 companies. NEVER tell the user "data not available" — GO GET IT.
3. Tasks with no dependencies MUST run in parallel. Same depends_on = parallel. You are NOT allowed to serialize independent operations.
4. For N companies needing the same tool: emit N separate tasks with the same depends_on — they execute in parallel automatically. DO THIS.
5. Only include generate_memo/generate_deck when the user EXPLICITLY asks for a written deliverable. "run valuations" does NOT mean "write a memo". Read the request literally.
6. Completion criteria use scoreboard variables: fetch_count, valuation_count, memo_count, chart_count, suggest_count, portfolio_size.
7. MINIMAL PLAN. Fewest tools to satisfy goals. No unnecessary steps. No padding. Every task must directly serve a goal.
8. For portfolio-wide operations: use batch tools (batch_valuate, resolve_data_gaps) instead of N individual calls. You have batch tools — USE THEM.
9. NEVER emit an empty plan. If you don't understand the request, emit at least query_portfolio or web_search to gather context.
10. The user is a fund manager. They need numbers, not excuses. Be aggressive about fetching, computing, and delivering results.

Return ONLY a JSON object:
{{
  "entities": {{"companies": ["name1", ...], "currency": "USD"?, "sector": "str"?}},
  "tasks": [
    {{"id": "t1", "tool": "tool_name", "inputs": {{}}, "label": "short description", "depends_on": []}},
    {{"id": "t2", "tool": "tool_name", "inputs": {{}}, "label": "short description", "depends_on": ["t1"]}}
  ],
  "completion": [
    {{"check": "fetch_count > 0", "description": "Companies enriched"}},
    {{"check": "valuation_count >= 3", "description": "Valuations complete"}}
  ]
}}

NO MARKDOWN. NO EXPLANATION. JUST THE JSON OBJECT."""

    @staticmethod
    def parse_decomposition(raw: str) -> Optional[Tuple[List[Task], List[dict]]]:
        """Parse LLM decomposition response into Tasks + completion criteria."""
        try:
            # Strip markdown fences if present
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

        This is the fallback when LLM decomposition fails. Uses the
        already-classified intent + suggested tool chain to build tasks
        with dependency awareness from SessionState.
        """
        if not classification or not getattr(classification, 'suggested_chain', None):
            return None

        chain = classification.suggested_chain
        entities = entities or {}
        company_names: list[str] = entities.get("companies", [])

        if not chain:
            return None

        tasks: list[Task] = []
        prev_ids: list[str] = []

        for idx, tool_name in enumerate(chain):
            task_id = f"chain_{idx}"
            inputs: Dict[str, Any] = {}

            # Populate inputs based on tool type
            if tool_name in ("fetch_company_data", "search_company_funding",
                             "search_company_product", "search_company_team",
                             "search_company_market", "lightweight_diligence",
                             "analyze_financials", "enrich_company_proactive"):
                if company_names:
                    # For search_company_* tools, expand to parallel per-company
                    if tool_name.startswith("search_company_") and len(company_names) > 1:
                        for j, name in enumerate(company_names):
                            tasks.append(Task(
                                id=f"chain_{idx}_{j}", tool=tool_name,
                                inputs={"company_name": name},
                                label=f"{tool_name} for {name}",
                                depends_on=list(prev_ids),
                            ))
                        prev_ids = [f"chain_{idx}_{j}" for j in range(len(company_names))]
                        continue
                    else:
                        inputs["company_name"] = company_names[0]

            elif tool_name in ("run_valuation",):
                if company_names:
                    # Parallel valuations for all companies
                    for j, name in enumerate(company_names):
                        needs = state.company_needs(name) if state else {}
                        if needs.get("valuation", True):
                            tasks.append(Task(
                                id=f"chain_{idx}_{j}", tool=tool_name,
                                inputs={"company_id": name},
                                label=f"Valuation for {name}",
                                depends_on=list(prev_ids),
                            ))
                    prev_ids = [t.id for t in tasks if t.tool == tool_name]
                    continue
                else:
                    inputs["company_id"] = "portfolio"

            elif tool_name in ("resolve_data_gaps", "batch_enrich"):
                names = company_names or list(state.grid_company_names) if state else []
                if state:
                    names = state.companies_needing("enrich", names[:20])
                inputs["companies"] = names[:20]

            elif tool_name in ("cap_table_evolution", "run_exit_modeling",
                               "run_followon_strategy", "run_round_modeling"):
                if company_names:
                    inputs["company"] = company_names[0]

            elif tool_name in ("generate_memo", "generate_ic_memo", "generate_lp_report"):
                if company_names:
                    inputs["company"] = company_names[0]

            elif tool_name == "generate_comparison_report":
                inputs["companies"] = company_names[:10]

            elif tool_name in ("portfolio_comparison",):
                inputs["companies"] = company_names[:10]

            elif tool_name in ("calculate_fund_metrics", "query_portfolio",
                               "run_portfolio_health", "generate_deck",
                               "enrich_portfolio"):
                pass  # No required inputs

            elif tool_name in ("fx_check", "fx_portfolio_impact", "convert_currency"):
                inputs["base_currency"] = entities.get("currency", "USD")

            # Determine dependencies: sequential unless parallel search tools
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
        """Return a task list from classification chain, or None if LLM needed.

        Synchronous fallback: uses classification.suggested_chain to build
        a deterministic plan. The async LLM decomposition path is called
        separately by the orchestrator via plan_async().
        """
        entities = entities or {}

        # Try classification-based planning first
        result = TaskPlanner.plan_from_classification(classification, state, entities)
        if result:
            logger.info(f"[TASK_PLANNER] Built {len(result)} tasks from classification chain")
            return result

        # If no classification, use entity-based defaults
        company_names: list[str] = entities.get("companies", [])

        # Single company default: fetch → valuation
        if len(company_names) == 1:
            return _plan_company_default(company_names[0], state)

        # Multiple companies default: parallel fetch → valuation
        if len(company_names) >= 2:
            return _plan_multi_company_default(company_names, state)

        # No companies, no classification → need LLM
        return None

    @staticmethod
    async def plan_async(
        prompt: str,
        state: SessionState,
        entities: Optional[Dict[str, Any]] = None,
        goals: Optional[list[dict]] = None,
        model_router: Optional[Any] = None,
    ) -> Optional[Tuple[List[Task], List[dict]]]:
        """Async LLM-powered task decomposition.

        One LLM call: sees the full tool catalog + fingerprint + entities,
        returns a complete task DAG with dependencies and completion criteria.

        Returns (tasks, completion_criteria) or None if decomposition fails.
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
        )

        try:
            response = await model_router.get_completion(
                prompt=decomp_prompt,
                system_prompt=(
                    "You are an aggressive task decomposer for a VC fund's investment agent. "
                    "Your job: break the user's request into the MINIMUM set of parallel tool calls "
                    "that gets them answers FAST. Never hedge. Never suggest 'maybe'. Never pad with "
                    "unnecessary steps. Read the fingerprint — if data exists, skip the fetch. "
                    "If data is missing, fetch it NOW. Parallelize everything that can be parallelized. "
                    "Return ONLY valid JSON. No markdown. No explanation. No prose. JUST THE JSON."
                ),
                capability="fast",  # Cheap model — this is routing, not analysis
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
# Plan builders
# ---------------------------------------------------------------------------

def _plan_portfolio_valuation(names: list[str], state: SessionState) -> List[Task]:
    """resolve_data_gaps → parallel run_valuation × N → generate_memo.

    Intelligence gate: only resolve gaps for companies that actually need it,
    only run valuations for companies missing scenario data.
    """
    tasks: List[Task] = []

    # Gate: only enrich companies that actually need data
    needs_enrich = state.companies_needing("enrich", names[:20]) if state else names[:20]
    needs_valuation = state.companies_needing("valuation", names[:20]) if state else names[:20]

    gap_dep = []
    if needs_enrich:
        tasks.append(Task(
            id="resolve_gaps",
            tool="resolve_data_gaps",
            inputs={"companies": needs_enrich},
            label=f"Fill data gaps for {len(needs_enrich)}/{len(names)} companies (skipping {len(names) - len(needs_enrich)} already enriched)",
        ))
        gap_dep = ["resolve_gaps"]

    # Only run valuations for companies that need them
    val_targets = needs_valuation if needs_valuation else names[:20]
    for batch_i, batch_start in enumerate(range(0, len(val_targets), 5)):
        batch = val_targets[batch_start:batch_start + 5]
        for j, name in enumerate(batch):
            tasks.append(Task(
                id=f"val_{batch_i}_{j}",
                tool="run_valuation",
                inputs={"company_name": name},
                label=f"Valuation for {name}",
                depends_on=gap_dep,
            ))
    tasks.append(Task(
        id="memo",
        tool="generate_memo",
        inputs={"memo_type": "portfolio_valuation", "include_charts": True},
        label="Generate portfolio valuation memo",
        depends_on=[t.id for t in tasks if t.tool == "run_valuation"],
    ))
    return tasks


def _plan_company_deep_dive(name: str, state: Optional[SessionState] = None) -> List[Task]:
    """fetch → valuation → cap table → memo. Skips fetch if data is fresh."""
    tasks: List[Task] = []
    needs = state.company_needs(name) if state else {"fetch": True, "valuation": True}

    fetch_dep = []
    if needs.get("fetch"):
        tasks.append(Task(id="fetch", tool="fetch_company_data", inputs={"company_name": name},
                          label=f"Fetch data for {name}"))
        fetch_dep = ["fetch"]
    else:
        logger.info(f"[TASK_PLANNER] Skipping fetch for {name} — data is fresh")

    tasks.append(Task(id="valuation", tool="run_valuation", inputs={"company_name": name},
                      label=f"Run valuation on {name}", depends_on=fetch_dep))
    tasks.append(Task(id="memo", tool="generate_memo",
                      inputs={"company_name": name, "memo_type": "investment_memo"},
                      label=f"Generate memo for {name}", depends_on=["valuation"]))
    return tasks


def _plan_multi_company_compare(names: list[str], state: Optional[SessionState] = None) -> List[Task]:
    """Parallel fetch + valuation for each → comparison memo. Skips fresh companies."""
    tasks: List[Task] = []
    val_ids = []
    for i, name in enumerate(names[:10]):
        fid = f"fetch_{i}"
        vid = f"val_{i}"
        needs = state.company_needs(name) if state else {"fetch": True}
        fetch_dep = []
        if needs.get("fetch"):
            tasks.append(Task(id=fid, tool="fetch_company_data",
                              inputs={"company_name": name}, label=f"Fetch {name}"))
            fetch_dep = [fid]
        tasks.append(Task(id=vid, tool="run_valuation",
                          inputs={"company_name": name}, label=f"Valuation for {name}",
                          depends_on=fetch_dep))
        val_ids.append(vid)
    tasks.append(Task(
        id="memo", tool="generate_memo",
        inputs={"memo_type": "comparison_report", "company_names": names[:10]},
        label="Generate comparison memo", depends_on=val_ids,
    ))
    return tasks


def _plan_portfolio_overview() -> List[Task]:
    return [
        Task(id="query", tool="query_portfolio", inputs={"query": "portfolio overview"},
             label="Load portfolio data"),
        Task(id="health", tool="run_portfolio_health", inputs={},
             label="Run portfolio health check", depends_on=["query"]),
        Task(id="metrics", tool="calculate_fund_metrics", inputs={},
             label="Calculate fund metrics", depends_on=["query"]),
        Task(id="chart", tool="generate_chart",
             inputs={"type": "bar", "title": "Portfolio Overview"},
             label="Generate overview chart", depends_on=["health", "metrics"]),
    ]


def _plan_fund_metrics() -> List[Task]:
    return [
        Task(id="metrics", tool="calculate_fund_metrics", inputs={},
             label="Calculate fund metrics"),
        Task(id="chart", tool="generate_chart",
             inputs={"type": "bar", "title": "Fund Metrics"},
             label="Generate fund metrics chart", depends_on=["metrics"]),
    ]


def _plan_deck_generation(names: list[str]) -> List[Task]:
    tasks: List[Task] = []
    for i, name in enumerate(names[:5]):
        tasks.append(Task(id=f"fetch_{i}", tool="fetch_company_data",
                          inputs={"company_name": name}, label=f"Fetch {name}"))
        tasks.append(Task(id=f"val_{i}", tool="run_valuation",
                          inputs={"company_name": name}, label=f"Valuation for {name}",
                          depends_on=[f"fetch_{i}"]))
    tasks.append(Task(
        id="deck", tool="generate_deck", inputs={},
        label="Generate investment deck",
        depends_on=[t.id for t in tasks if t.tool == "run_valuation"],
    ))
    return tasks


def _plan_memo_generation(names: list[str], state: SessionState) -> List[Task]:
    tasks: List[Task] = []
    if names:
        for i, name in enumerate(names[:5]):
            tasks.append(Task(id=f"fetch_{i}", tool="fetch_company_data",
                              inputs={"company_name": name}, label=f"Fetch {name}"))
    tasks.append(Task(
        id="metrics", tool="calculate_fund_metrics", inputs={},
        label="Calculate fund metrics",
    ))
    tasks.append(Task(
        id="memo", tool="generate_memo",
        inputs={"memo_type": "investment_memo"},
        label="Generate memo",
        depends_on=[t.id for t in tasks],
    ))
    return tasks


def _plan_followon(name: str) -> List[Task]:
    return [
        Task(id="fetch", tool="fetch_company_data", inputs={"company_name": name},
             label=f"Fetch {name}"),
        Task(id="followon", tool="run_followon_strategy",
             inputs={"company_name": name}, label=f"Follow-on analysis for {name}",
             depends_on=["fetch"]),
        Task(id="round", tool="run_round_modeling",
             inputs={"company_name": name}, label=f"Round modeling for {name}",
             depends_on=["fetch"]),
        Task(id="chart", tool="generate_chart",
             inputs={"type": "waterfall", "company_name": name},
             label="Generate chart", depends_on=["followon", "round"]),
    ]


def _plan_exit_analysis(name: str) -> List[Task]:
    return [
        Task(id="fetch", tool="fetch_company_data", inputs={"company_name": name},
             label=f"Fetch {name}"),
        Task(id="exit", tool="run_exit_modeling",
             inputs={"company_name": name}, label=f"Exit modeling for {name}",
             depends_on=["fetch"]),
        Task(id="chart", tool="generate_chart",
             inputs={"type": "probability_cloud", "company_name": name},
             label="Generate probability cloud", depends_on=["exit"]),
    ]


def _plan_enrich(names: list[str]) -> List[Task]:
    tasks: List[Task] = []
    tasks.append(Task(
        id="resolve", tool="resolve_data_gaps",
        inputs={"companies": names[:20]},
        label="Resolve data gaps for portfolio",
    ))
    return tasks


def _plan_company_default(name: str, state: Optional[SessionState] = None) -> List[Task]:
    """Default for single @mention: fetch → valuation → memo. Skips fetch if fresh."""
    tasks: List[Task] = []
    needs = state.company_needs(name) if state else {"fetch": True}

    fetch_dep = []
    if needs.get("fetch"):
        tasks.append(Task(id="fetch", tool="fetch_company_data", inputs={"company_name": name},
                          label=f"Fetch data for {name}"))
        fetch_dep = ["fetch"]

    tasks.append(Task(id="valuation", tool="run_valuation", inputs={"company_name": name},
                      label=f"Run valuation on {name}", depends_on=fetch_dep))
    tasks.append(Task(id="memo", tool="generate_memo",
                      inputs={"company_name": name, "memo_type": "investment_memo"},
                      label=f"Generate memo for {name}", depends_on=["valuation"]))
    return tasks


def _plan_multi_company_default(names: list[str], state: Optional[SessionState] = None) -> List[Task]:
    """Default for multiple @mentions: parallel fetch + valuation → memo. Skips fresh."""
    tasks: List[Task] = []
    val_ids = []
    for i, name in enumerate(names[:10]):
        fid = f"fetch_{i}"
        vid = f"val_{i}"
        needs = state.company_needs(name) if state else {"fetch": True}
        fetch_dep = []
        if needs.get("fetch"):
            tasks.append(Task(id=fid, tool="fetch_company_data",
                              inputs={"company_name": name}, label=f"Fetch {name}"))
            fetch_dep = [fid]
        tasks.append(Task(id=vid, tool="run_valuation",
                          inputs={"company_name": name}, label=f"Valuation for {name}",
                          depends_on=fetch_dep))
        val_ids.append(vid)
    tasks.append(Task(
        id="memo", tool="generate_memo",
        inputs={"memo_type": "investment_memo"},
        label="Generate memo", depends_on=val_ids,
    ))
    return tasks


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
    """Tracks task progress and produces a dense status string for LLM context.

    Wraps shared_data to read/write task states. The agent loop injects
    ``summary_for_context()`` into each REASON prompt so the LLM knows
    what's done, what's running, and what's next.
    """

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
        """Return a dense ~1-line status for LLM context injection.

        Example: ``✓ fetch(Cursor) | → valuation(Anthropic) | ○ write_to_memo``
        """
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

    After each tool executes, auto-compress the output into a 1-2 line summary.
    The next LLM call gets fingerprint + memo instead of raw tool result dumps.

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
            # FIFO eviction
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]

    def add_raw(self, entry: str) -> None:
        """Add a raw memo entry (e.g. from LLM synthesis)."""
        if entry and entry.strip():
            self._entries.append(entry.strip())
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries:]

    def context(self, max_tokens: int = 800) -> str:
        """Return compressed findings for LLM context injection.
        Most recent entries first, FIFO eviction at token budget.
        """
        if not self._entries:
            return ""
        lines = ["FINDINGS (compressed from prior tools):"]
        total_chars = 0
        # Most recent first
        for entry in reversed(self._entries):
            if total_chars + len(entry) > max_tokens * 4:  # ~4 chars per token
                break
            lines.append(f"  - {entry}")
            total_chars += len(entry)
        return "\n".join(lines)

    @property
    def entries(self) -> List[str]:
        return list(self._entries)

    def _compress(self, tool: str, inputs: dict, result: dict) -> str:
        """Extract the key finding from a tool result as a 1-2 line summary."""
        if not isinstance(result, dict):
            return f"[{tool}] completed"

        # Handle error results
        if result.get("error"):
            return f"[{tool}] FAILED: {str(result['error'])[:80]}"

        company = inputs.get("company_name") or inputs.get("company") or inputs.get("name") or ""

        # Tool-specific compression
        if tool in ("fetch_company_data", "enrich_company_proactive", "lightweight_diligence"):
            return self._compress_fetch(company, result)
        elif tool == "run_valuation":
            return self._compress_valuation(company, result)
        elif tool == "resolve_data_gaps":
            return self._compress_gaps(result)
        elif tool in ("generate_memo", "run_report", "write_to_memo",
                       "generate_ic_memo", "generate_followon_memo",
                       "generate_lp_report", "generate_gp_update",
                       "generate_comparison_report"):
            return self._compress_memo(tool, result)
        elif tool == "calculate_fund_metrics":
            return self._compress_fund_metrics(result)
        elif tool in ("search_company_funding", "search_company_product",
                       "search_company_team", "search_company_market"):
            return self._compress_search(tool, company, result)
        elif tool == "analyze_financials":
            return self._compress_financials(company, result)
        elif tool in ("cap_table_evolution", "liquidation_waterfall"):
            return self._compress_cap_table(tool, company, result)
        elif tool in ("run_exit_modeling", "run_scenario"):
            return self._compress_scenario(tool, company, result)
        elif tool in ("run_followon_strategy", "run_round_modeling"):
            return self._compress_followon(tool, company, result)
        elif tool == "generate_chart":
            chart_type = inputs.get("chart_type") or inputs.get("type") or "chart"
            return f"[{tool}] Generated {chart_type} chart"
        elif tool == "generate_deck":
            return f"[{tool}] Generated investment deck"
        elif tool in ("fx_check", "fx_portfolio_impact", "convert_currency"):
            return self._compress_fx(tool, result)
        elif tool == "query_portfolio":
            count = len(result.get("companies", result.get("rows", [])))
            return f"[{tool}] Loaded {count} companies from portfolio"
        elif tool == "run_portfolio_health":
            return self._compress_portfolio_health(result)
        elif tool == "compliance_check":
            return f"[{tool}] Compliance check: {result.get('status', 'done')}"
        elif tool in ("suggest_grid_edit", "suggest_action"):
            title = result.get("title") or result.get("suggestion", {}).get("title", "")
            return f"[{tool}] {title}" if title else f"[{tool}] suggestion emitted"
        elif tool == "sync_crm":
            sr = result.get("sync_result", result)
            created = sr.get("created", 0)
            updated = sr.get("updated", 0)
            return f"[{tool}] CRM sync: {created} created, {updated} updated"
        elif tool in ("stress_test_portfolio", "monte_carlo_portfolio", "sensitivity_matrix"):
            return f"[{tool}] Simulation complete for {company or 'portfolio'}"
        elif tool == "run_fpa":
            return f"[{tool}] FP&A analysis complete"
        elif tool in ("batch_valuate", "bulk_operation"):
            count = result.get("completed", result.get("count", 0))
            return f"[{tool}] Batch operation: {count} completed"
        else:
            # Generic: count output keys
            keys = [k for k in result.keys() if k not in ("error", "status", "timing")]
            return f"[{tool}] completed ({', '.join(keys[:5])})"

    def _compress_fetch(self, company: str, result: dict) -> str:
        comp = result.get("company_data") or result
        rev = comp.get("revenue") or comp.get("arr") or comp.get("inferred_revenue")
        val = comp.get("valuation") or comp.get("inferred_valuation")
        stage = comp.get("stage") or comp.get("funding_stage") or ""
        parts = [f"{company}:"]
        if stage:
            parts.append(stage)
        if rev:
            parts.append(f"rev={_fmt_money(rev)}")
        if val:
            parts.append(f"val={_fmt_money(val)}")
        team = comp.get("team_size") or comp.get("employee_count")
        if team:
            parts.append(f"team={team}")
        return f"[fetch] {' '.join(parts)}"

    def _compress_valuation(self, company: str, result: dict) -> str:
        val = result.get("valuation") or result.get("fair_value") or result.get("result", {}).get("fair_value")
        method = result.get("method_used") or result.get("method") or "PWERM"
        multiple = result.get("revenue_multiple") or result.get("multiple")
        parts = [f"{company}:"]
        if val:
            parts.append(f"{_fmt_money(val)}")
        if multiple:
            parts.append(f"@ {multiple:.1f}x" if isinstance(multiple, (int, float)) else f"@ {multiple}")
        parts.append(f"({method})")
        return f"[valuation] {' '.join(parts)}"

    def _compress_gaps(self, result: dict) -> str:
        filled = result.get("total_fields_filled", 0)
        suggestions = result.get("total_suggestions_persisted", 0)
        companies = result.get("companies", [])
        count = len(companies) if isinstance(companies, list) else 0
        return f"[resolve_gaps] {count} companies enriched, {filled} fields filled, {suggestions} suggestions"

    def _compress_memo(self, tool: str, result: dict) -> str:
        memo_type = result.get("memo_type") or result.get("type") or tool
        sections = result.get("sections", [])
        return f"[{tool}] {memo_type} generated ({len(sections)} sections)"

    def _compress_fund_metrics(self, result: dict) -> str:
        metrics = result.get("metrics", result)
        parts = []
        for key in ("tvpi", "dpi", "irr", "nav"):
            v = metrics.get(key)
            if v is not None:
                if key in ("tvpi", "dpi"):
                    parts.append(f"{key.upper()}={v:.2f}x")
                elif key == "irr":
                    parts.append(f"IRR={v:.1f}%")
                elif key == "nav":
                    parts.append(f"NAV={_fmt_money(v)}")
        return f"[fund_metrics] {', '.join(parts)}" if parts else "[fund_metrics] calculated"

    def _compress_search(self, tool: str, company: str, result: dict) -> str:
        field_type = tool.replace("search_company_", "")
        updates = result.get("field_updates", {})
        if updates:
            keys = list(updates.keys())[:4]
            return f"[{field_type}] {company}: found {', '.join(keys)}"
        return f"[{field_type}] {company}: no new data"

    def _compress_financials(self, company: str, result: dict) -> str:
        updates = result.get("field_updates", {})
        parts = []
        for key in ("gross_margin", "burn_rate", "runway_months", "growth_rate"):
            v = updates.get(key)
            if v is not None:
                parts.append(f"{key}={v}")
        return f"[financials] {company}: {', '.join(parts)}" if parts else f"[financials] {company}: computed"

    def _compress_cap_table(self, tool: str, company: str, result: dict) -> str:
        rounds = result.get("rounds", result.get("cap_table_history", {}).get("rounds", []))
        count = len(rounds) if isinstance(rounds, list) else 0
        return f"[{tool}] {company}: {count} rounds tracked"

    def _compress_scenario(self, tool: str, company: str, result: dict) -> str:
        scenarios = result.get("scenarios", [])
        count = len(scenarios) if isinstance(scenarios, list) else 0
        return f"[{tool}] {company}: {count} scenarios modeled"

    def _compress_followon(self, tool: str, company: str, result: dict) -> str:
        rec = result.get("recommendation") or result.get("action") or ""
        return f"[{tool}] {company}: {rec}" if rec else f"[{tool}] {company}: analyzed"

    def _compress_fx(self, tool: str, result: dict) -> str:
        impact = result.get("total_impact_pct")
        currencies = result.get("currencies", [])
        if impact is not None:
            return f"[{tool}] FX impact: {impact:+.1f}%, {len(currencies)} currencies"
        return f"[{tool}] FX rates retrieved"

    def _compress_portfolio_health(self, result: dict) -> str:
        health = result.get("health", result)
        score = health.get("overall_score") or health.get("score")
        flags = health.get("flags", [])
        parts = []
        if score is not None:
            parts.append(f"score={score}")
        if flags:
            parts.append(f"{len(flags)} flags")
        return f"[portfolio_health] {', '.join(parts)}" if parts else "[portfolio_health] analyzed"
