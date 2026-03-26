"""
Cap Table CSV Parser

Parses cap table CSVs into cap_table_entries rows. Modelled after the FPA
actuals CSV pipeline in fpa_query.py — same amount parsing, header cleaning,
and fuzzy matching patterns but tuned for cap table column layouts.

Handles CSVs in two orientations:
  1. Row-per-shareholder (most common):
     Shareholder | Class | Shares | Price | Round | ...
  2. Row-per-instrument (debt-heavy):
     Instrument | Holder | Type | Principal | Rate | Maturity | ...

Also handles messy exports from Carta, Pulley, Captable.io, spreadsheets.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_DEBT_INSTRUMENT_TYPES = frozenset({
    "debt", "convertible", "pik", "revenue_based", "mezzanine", "revolver",
})

# ---------------------------------------------------------------------------
# Column header detection
# ---------------------------------------------------------------------------

# Each tuple: (set of possible header names, canonical field name)
_COLUMN_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # --- Specific patterns BEFORE greedy ones to avoid mis-matches ---

    # Ownership % (before shareholder_name — "owner" would grab "Ownership %")
    (re.compile(r"own(?:ership)?\s*(?:pct|%|percent)|%\s*own|fully\s*diluted\s*%", re.I), "ownership_pct"),
    # Shareholder / holder (removed "owner" — conflicts with "Ownership %")
    (re.compile(r"share\s*holder|holder|investor|name|stakeholder|party|lender|creditor", re.I), "shareholder_name"),
    # Stakeholder type
    (re.compile(r"stakeholder\s*type|type\s*of\s*(?:holder|investor)|role|category", re.I), "stakeholder_type"),
    # Share class / instrument
    (re.compile(r"share\s*class|class|series|instrument|security|type\s*of\s*(?:share|stock|instrument)", re.I), "share_class"),
    # Instrument type (equity/debt/convertible...)
    (re.compile(r"instrument\s*type|security\s*type|asset\s*class", re.I), "instrument_type"),
    # Number of shares
    (re.compile(r"(?:num(?:ber)?\s*(?:of\s*)?)?shares|units|quantity|amount\s*of\s*shares", re.I), "num_shares"),
    # Exercise / conversion price (before price_per_share — "Conversion Price" would match generic "price")
    (re.compile(r"exercise\s*price|conversion\s*price|strike|hurdle", re.I), "exercise_price"),
    # Price per share
    (re.compile(r"price\s*(?:per\s*(?:share|unit))?|pps|issue\s*price|cost\s*(?:per\s*share)?", re.I), "price_per_share"),
    # Investment amount (if given directly instead of shares*price)
    (re.compile(r"invest(?:ment)?\s*(?:amount)?|total\s*invest|committed|amount\s*invested|consideration", re.I), "investment_amount_direct"),
    # Round
    (re.compile(r"round|funding\s*round|series\s*name|tranche|stage", re.I), "round_name"),
    # Date
    (re.compile(r"(?:invest(?:ment)?|issue|closing|grant)\s*date|date", re.I), "investment_date"),
    # Liquidation preference
    (re.compile(r"liq(?:uidation)?\s*pref|preference\s*multiple", re.I), "liquidation_pref"),
    # Participating
    (re.compile(r"participat", re.I), "participating"),
    # Anti-dilution
    (re.compile(r"anti[\s\-]?dilution", re.I), "anti_dilution"),
    # Voting
    (re.compile(r"voting", re.I), "voting_rights"),
    # Board seat
    (re.compile(r"board", re.I), "board_seat"),
    # Pro rata
    (re.compile(r"pro[\s\-]?rata", re.I), "pro_rata_rights"),
    # Vesting cliff
    (re.compile(r"cliff", re.I), "vesting_cliff_months"),
    # Vesting total
    (re.compile(r"vest(?:ing)?\s*(?:period|months|total|duration|schedule)", re.I), "vesting_total_months"),
    # Vested %
    (re.compile(r"vested\s*(?:pct|%|percent)", re.I), "vested_pct"),
    # --- Debt fields ---
    # Outstanding principal
    (re.compile(r"principal|outstanding|balance|face\s*value|notional|loan\s*amount|facility\s*(?:size|amount)", re.I), "outstanding_principal"),
    # PIK / cash rate (before interest_rate — bare "rate" would grab "PIK Rate")
    (re.compile(r"pik\s*rate", re.I), "pik_rate"),
    (re.compile(r"cash\s*rate", re.I), "cash_rate"),
    # Interest rate / coupon (after pik/cash so those win first)
    (re.compile(r"interest\s*rate|coupon|rate|yield|spread|margin", re.I), "interest_rate"),
    # Maturity
    (re.compile(r"maturity|due\s*date|expir(?:y|ation)|term\s*end", re.I), "maturity_date"),
    # Seniority
    (re.compile(r"seniority|priority|rank", re.I), "seniority"),
    # Secured
    (re.compile(r"secured|collateral(?:ized)?", re.I), "secured"),
    # Collateral
    (re.compile(r"collateral\s*(?:desc|detail|type)", re.I), "collateral"),
    # Covenants
    (re.compile(r"covenant", re.I), "covenants_text"),
    # --- Convertible / SAFE ---
    # Conversion discount
    (re.compile(r"(?:conversion\s*)?discount", re.I), "conversion_discount"),
    # Valuation cap
    (re.compile(r"(?:valuation\s*)?cap", re.I), "valuation_cap"),
    # MFN
    (re.compile(r"mfn|most\s*favou?red", re.I), "mfn"),
    # --- Warrant ---
    # Warrant coverage
    (re.compile(r"(?:warrant\s*)?coverage", re.I), "warrant_coverage_pct"),
    # Expiry
    (re.compile(r"expir(?:y|ation)\s*date", re.I), "expiry_date"),
    # --- RBF ---
    (re.compile(r"repayment\s*cap|repayment\s*multiple", re.I), "repayment_cap"),
    (re.compile(r"revenue\s*share", re.I), "revenue_share_pct"),
    # Notes
    (re.compile(r"notes?|comments?|memo", re.I), "notes"),
]


# ---------------------------------------------------------------------------
# Share class / instrument type fuzzy matching
# ---------------------------------------------------------------------------

_SHARE_CLASS_MAP: List[Tuple[re.Pattern, str, str]] = [
    # (pattern, share_class, instrument_type)
    # Preferred series
    (re.compile(r"preferred\s*f|series\s*f", re.I), "preferred_f", "equity"),
    (re.compile(r"preferred\s*e|series\s*e", re.I), "preferred_e", "equity"),
    (re.compile(r"preferred\s*d|series\s*d", re.I), "preferred_d", "equity"),
    (re.compile(r"preferred\s*c|series\s*c", re.I), "preferred_c", "equity"),
    (re.compile(r"preferred\s*b|series\s*b", re.I), "preferred_b", "equity"),
    (re.compile(r"preferred\s*a|series\s*a", re.I), "preferred_a", "equity"),
    (re.compile(r"preferred|pref", re.I), "preferred_a", "equity"),
    # Common
    (re.compile(r"common|ordinary|founder", re.I), "common", "equity"),
    # Options / RSU
    (re.compile(r"option|esop|iso|nso|rsu|restricted\s*stock", re.I), "options", "option"),
    # Warrants
    (re.compile(r"warrant", re.I), "warrants", "warrant"),
    # SAFE
    (re.compile(r"safe|simple\s*agreement", re.I), "safe", "safe"),
    # Convertible note
    (re.compile(r"convert(?:ible)?\s*note|convert(?:ible)?\s*debt|convert(?:ible)?\s*loan", re.I), "convertible_note", "convertible"),
    # PIK
    (re.compile(r"pik|payment[\s\-]in[\s\-]kind", re.I), "pik", "pik"),
    # Revenue-based
    (re.compile(r"revenue[\s\-]based|rbf|royalty", re.I), "revenue_share", "revenue_based"),
    # Mezzanine
    (re.compile(r"mezzanine|mezz", re.I), "mezzanine", "mezzanine"),
    # Venture debt
    (re.compile(r"venture\s*debt", re.I), "venture_debt", "debt"),
    # Revolver
    (re.compile(r"revolv(?:ing|er)|rcf|line\s*of\s*credit", re.I), "revolver", "revolver"),
    # Term loan
    (re.compile(r"term\s*loan|senior\s*(?:debt|loan)|subordinated|sub\s*debt", re.I), "term_loan", "debt"),
    # Generic debt
    (re.compile(r"debt|loan|bond|note(?!s?\s*$)", re.I), "term_loan", "debt"),
]

_STAKEHOLDER_TYPE_MAP: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"founder|co[\s\-]?founder", re.I), "founder"),
    (re.compile(r"employee|team|staff", re.I), "employee"),
    (re.compile(r"advisor|adviser|consultant|mentor", re.I), "advisor"),
    (re.compile(r"investor|fund|vc|pe|angel|venture|capital|partner|lp", re.I), "investor"),
    (re.compile(r"lender|bank|creditor|debt\s*holder", re.I), "lender"),
]


# ---------------------------------------------------------------------------
# Amount / value parsing (mirrors fpa_query._parse_amount)
# ---------------------------------------------------------------------------

def _parse_amount(raw: str, as_percentage: bool = False) -> Optional[float]:
    """Parse a cell value as a number. Handles currency, commas, parens, K/M/B, European notation.

    Args:
        raw: Raw cell string.
        as_percentage: If True, keep percentage values as-is (20% → 20.0).
                       If False (default), percentage sign is stripped but value is NOT divided.
    """
    if not raw:
        return None
    s = raw.strip()
    if not s or s == "-" or s == "—" or s.lower() in ("n/a", "na", "none", "null", ""):
        return None

    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]

    # Strip currency symbols and whitespace
    s = re.sub(r"[$€£¥₹\s]", "", s)

    # Detect European notation: "1.234.567,89"
    if re.match(r"^-?[\d.]+,\d{1,2}$", s):
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")

    # Strip trailing %
    pct = s.endswith("%")
    if pct:
        s = s[:-1]

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

    # Percentage normalization: DB stores as whole numbers (20 = 20%)
    if as_percentage and not pct and val <= 1:
        # No % sign and value <= 1 → treat as decimal (0.20 → 20.0)
        val *= 100

    return -val if neg else val


def _parse_date(raw: str) -> Optional[str]:
    """Parse a date string into YYYY-MM-DD. Returns None if unparseable."""
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None

    for fmt in (
        "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y",
        "%b %d, %Y", "%B %d, %Y", "%b %Y", "%B %Y",
        "%Y-%m", "%m/%Y", "%d-%b-%Y", "%d %b %Y",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _parse_bool(raw: str) -> Optional[bool]:
    """Parse a boolean from common CSV representations."""
    if not raw:
        return None
    s = raw.strip().lower()
    if s in ("yes", "y", "true", "1", "x", "✓", "✔"):
        return True
    if s in ("no", "n", "false", "0", "", "-", "—"):
        return False
    return None


def _clean_header(raw: str) -> str:
    """Strip noise from a column header."""
    h = raw.strip()
    h = re.sub(r"\s*\(.*?\)\s*$", "", h)
    h = re.sub(r"\s+", " ", h).strip()
    return h


# ---------------------------------------------------------------------------
# Column mapping
# ---------------------------------------------------------------------------

def _detect_columns(headers: List[str]) -> Dict[int, str]:
    """Map column indices to canonical field names."""
    mapping: Dict[int, str] = {}
    used_fields: set = set()

    cleaned = [_clean_header(h) for h in headers]

    for col_idx, header in enumerate(cleaned):
        if not header:
            continue
        for pattern, field_name in _COLUMN_PATTERNS:
            if field_name in used_fields:
                continue
            if pattern.search(header):
                mapping[col_idx] = field_name
                used_fields.add(field_name)
                break

    # If no shareholder column detected, assume first text column
    if "shareholder_name" not in used_fields and cleaned:
        mapping[0] = "shareholder_name"

    return mapping


def _match_share_class(raw: str) -> Tuple[str, str]:
    """Match a raw share class string to (share_class, instrument_type)."""
    if not raw:
        return "common", "equity"
    for pattern, sc, it in _SHARE_CLASS_MAP:
        if pattern.search(raw):
            return sc, it
    return raw.lower().replace(" ", "_"), "equity"


def _match_stakeholder_type(raw: str) -> str:
    """Match a raw stakeholder type to canonical type."""
    if not raw:
        return "other"
    for pattern, st in _STAKEHOLDER_TYPE_MAP:
        if pattern.search(raw):
            return st
    return "other"


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def parse_cap_table_csv(file_content: bytes | str) -> List[dict]:
    """Parse a cap table CSV and return a list of cap_table_entries dicts.

    Args:
        file_content: Raw CSV bytes or string.

    Returns:
        List of dicts ready for CapTableLedger.bulk_upsert().
    """
    if isinstance(file_content, bytes):
        # Try UTF-8, fall back to latin-1
        try:
            text = file_content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = file_content.decode("latin-1")
    else:
        text = file_content

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)

    if len(rows) < 2:
        logger.warning("[cap-table-csv] CSV has fewer than 2 rows")
        return []

    # --- Pass 1: Detect columns ---
    headers = rows[0]
    col_map = _detect_columns(headers)

    if not col_map:
        logger.warning("[cap-table-csv] Could not detect any columns from headers: %s", headers)
        return []

    logger.info(
        "[cap-table-csv] Detected columns: %s",
        {i: (headers[i], f) for i, f in col_map.items()},
    )

    # --- Pass 2: Parse rows ---
    entries: List[dict] = []

    for row_idx, row in enumerate(rows[1:], start=2):
        # Skip empty rows
        if not any(cell.strip() for cell in row):
            continue

        # Skip section headers / totals
        raw_first = row[0].strip().lower() if row else ""
        if raw_first in ("total", "totals", "grand total", ""):
            # Check if truly empty or a section header with no data
            has_data = False
            for ci, field in col_map.items():
                if field in ("num_shares", "price_per_share", "outstanding_principal",
                             "investment_amount_direct") and ci < len(row):
                    if _parse_amount(row[ci]) is not None:
                        has_data = True
                        break
            if not has_data:
                continue

        # Extract fields
        entry: Dict[str, Any] = {}

        for col_idx, field_name in col_map.items():
            if col_idx >= len(row):
                continue
            raw = row[col_idx].strip()
            if not raw:
                continue

            if field_name == "shareholder_name":
                entry["shareholder_name"] = raw

            elif field_name == "stakeholder_type":
                entry["stakeholder_type"] = _match_stakeholder_type(raw)

            elif field_name == "share_class":
                entry["_raw_security"] = raw  # preserve for dedup
                sc, it = _match_share_class(raw)
                entry["share_class"] = sc
                # Only set instrument_type from share_class if not explicitly provided
                if "instrument_type" not in entry:
                    entry["instrument_type"] = it

            elif field_name == "instrument_type":
                # Explicit instrument type column
                _, it = _match_share_class(raw)
                entry["instrument_type"] = it

            elif field_name in ("num_shares", "price_per_share", "outstanding_principal",
                                "investment_amount_direct", "liquidation_pref",
                                "participation_cap", "valuation_cap", "qualified_financing",
                                "exercise_price", "repayment_cap"):
                val = _parse_amount(raw)
                if val is not None:
                    entry[field_name] = val

            elif field_name in ("interest_rate", "conversion_discount",
                                "warrant_coverage_pct", "vested_pct",
                                "pik_rate", "cash_rate", "revenue_share_pct"):
                val = _parse_amount(raw, as_percentage=True)
                if val is None and raw:
                    # Fallback: extract from complex rate strings
                    # e.g., "SOFR + 350 bps (7.83% all-in)" → 7.83
                    pct_m = re.search(r"(\d+\.?\d*)\s*%", raw)
                    if pct_m:
                        val = float(pct_m.group(1))
                    else:
                        # "350 bps" → 3.5%
                        bps_m = re.search(r"(\d+\.?\d*)\s*(?:bps|basis\s*points?)", raw, re.I)
                        if bps_m:
                            val = float(bps_m.group(1)) / 100
                if val is not None:
                    entry[field_name] = val

            elif field_name == "round_name":
                entry["round_name"] = raw

            elif field_name in ("investment_date", "maturity_date", "expiry_date"):
                d = _parse_date(raw)
                if d:
                    entry[field_name] = d

            elif field_name in ("participating", "voting_rights", "board_seat",
                                "pro_rata_rights", "secured", "cross_default",
                                "auto_convert", "mfn", "cashless_exercise"):
                b = _parse_bool(raw)
                if b is not None:
                    entry[field_name] = b

            elif field_name in ("anti_dilution", "seniority", "coupon_type",
                                "amortization_type", "pik_toggle_type",
                                "collateral", "underlying_class", "notes"):
                entry[field_name] = raw

            elif field_name == "covenants_text":
                # Store as JSONB with a text key
                entry["covenants"] = {"raw": raw}

            elif field_name == "vesting_cliff_months":
                val = _parse_amount(raw)
                if val is not None:
                    entry["vesting_cliff_months"] = int(val)

            elif field_name == "vesting_total_months":
                val = _parse_amount(raw)
                if val is not None:
                    entry["vesting_total_months"] = int(val)

            elif field_name == "ownership_pct":
                val = _parse_amount(raw, as_percentage=True)
                if val is not None:
                    entry["ownership_pct"] = val

        # Skip rows without a shareholder name
        if not entry.get("shareholder_name"):
            continue

        # --- Post-processing ---

        # If investment_amount_direct given but no shares/price, back-fill
        direct_amt = entry.pop("investment_amount_direct", None)
        if direct_amt is not None:
            if not entry.get("num_shares") and not entry.get("price_per_share"):
                # For debt instruments, put it in outstanding_principal
                it = entry.get("instrument_type", "equity")
                if it in _DEBT_INSTRUMENT_TYPES:
                    entry.setdefault("outstanding_principal", direct_amt)
                else:
                    # Set shares=1, price=amount so investment_amount computes
                    # Flag so downstream consumers don't use for dilution math
                    entry["num_shares"] = 1
                    entry["price_per_share"] = direct_amt
                    entry["notes"] = (entry.get("notes", "") + " [shares_estimated]").strip()
            elif entry.get("price_per_share") and not entry.get("num_shares"):
                pps = entry["price_per_share"]
                if pps > 0:
                    entry["num_shares"] = direct_amt / pps
            elif entry.get("num_shares") and not entry.get("price_per_share"):
                ns = entry["num_shares"]
                if ns > 0:
                    entry["price_per_share"] = direct_amt / ns

        # If no instrument_type set, infer from share_class
        if "instrument_type" not in entry:
            sc = entry.get("share_class", "common")
            _, it = _match_share_class(sc)
            entry["instrument_type"] = it

        # If no stakeholder_type, infer from share_class / instrument_type
        if "stakeholder_type" not in entry:
            it = entry.get("instrument_type", "equity")
            sc = entry.get("share_class", "")
            if it in _DEBT_INSTRUMENT_TYPES:
                entry["stakeholder_type"] = "lender"
            elif sc == "options":
                entry["stakeholder_type"] = "employee"
            elif sc == "common" and entry.get("round_name", "").lower() in ("", "founding", "incorporation"):
                entry["stakeholder_type"] = "founder"
            else:
                entry["stakeholder_type"] = _match_stakeholder_type(
                    entry.get("shareholder_name", "")
                )

        # Set is_debt_instrument
        entry["is_debt_instrument"] = entry.get("instrument_type", "equity") in _DEBT_INSTRUMENT_TYPES

        # Defaults for required numeric fields
        entry.setdefault("num_shares", 0)
        entry.setdefault("price_per_share", 0)

        entries.append(entry)

    # --- Dedup: keep last occurrence per identity key ---
    # Use raw security name (if available) to distinguish different instruments
    # from the same holder (e.g., Term Loan vs DDTL from same bank)
    seen: Dict[tuple, int] = {}
    for i, e in enumerate(entries):
        security = e.pop("_raw_security", None) or e.get("share_class")
        key = (e.get("shareholder_name"), security, e.get("round_name"))
        seen[key] = i  # last wins
    if len(seen) < len(entries):
        deduped = [entries[i] for i in sorted(seen.values())]
        logger.info("[cap-table-csv] Deduped %d → %d entries", len(entries), len(deduped))
        entries = deduped

    logger.info("[cap-table-csv] Parsed %d entries from %d data rows", len(entries), len(rows) - 1)
    return entries
