"""
Flexible date parsing for FPA period strings.

Periods come in as YYYY-MM, YYYY-MM-DD, or YYYY-MM-DDTHH:MM:SS.
Every service that touches period strings should use these helpers
instead of raw date.fromisoformat().
"""

from datetime import date, datetime
from typing import Optional


def parse_period_to_date(period: str) -> date:
    """Parse a period string (YYYY-MM or YYYY-MM-DD) into a date.

    Always returns the first day of the month for YYYY-MM inputs.
    Raises ValueError only if the string is truly unparseable.
    """
    s = period.strip()
    # YYYY-MM → append -01
    if len(s) == 7 and s[4] == "-":
        return date.fromisoformat(f"{s}-01")
    # YYYY-MM-DD or longer (trim time component)
    return date.fromisoformat(s[:10])


def parse_period_to_date_safe(period: str) -> Optional[date]:
    """Like parse_period_to_date but returns None instead of raising."""
    try:
        return parse_period_to_date(period)
    except (ValueError, IndexError, AttributeError):
        return None


def normalize_period(raw: str) -> str:
    """Normalize any date-like string to YYYY-MM format.

    Handles: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, YYYY-MM, etc.
    """
    s = raw.strip()
    if len(s) >= 7 and s[4] == "-":
        return s[:7]
    return s
