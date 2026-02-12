#!/usr/bin/env python3
"""
Backfill existing portfolio companies from a CSV: add extra_data and matrix columns.

Use this after you already uploaded companies (names only). This script:
1. Creates matrix_columns for every CSV header so the grid shows those columns (empty cells are editable).
2. Updates each company (matched by name + fund_id) with extra_data = all CSV columns, and first_investment_date / total_invested_usd from CSV.

Run the migration first if you have not:
  - supabase/migrations/20250205_companies_extra_data.sql  (adds companies.extra_data)

Usage:
  python scripts/backfill_portfolio_csv.py "/path/to/file.csv" "<fund-id>"

  Or by fund name:
  python scripts/backfill_portfolio_csv.py "/path/to/file.csv" "Vsquared Ventures III"
"""

import os
import sys
import csv
from datetime import datetime
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[1]
for env_file in (".env.local", ".env"):
    p = _repo_root / env_file
    if p.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(p, override=True)
            break
        except ImportError:
            pass

SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
    sys.exit(1)

from supabase import create_client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def normalize_header(h: str) -> str:
    return h.strip().lower().replace(" ", "_").replace("-", "_")


def column_type(header: str) -> str:
    h = header.lower()
    if "date" in h or "announced" in h:
        return "date"
    if "amount" in h or "raised" in h or "investment" in h or "invested" in h:
        return "currency"
    if "percent" in h or "margin" in h or "ownership" in h:
        return "percentage"
    return "text"


def parse_date(s: str) -> str | None:
    if not s or not str(s).strip():
        return None
    s = str(s).strip()
    if " " in s:
        s = s.split(" ")[0]
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_amount_millions(s: str) -> int | None:
    if s is None or str(s).strip().lower() in ("", "null", "na", "n/a"):
        return None
    s = str(s).replace("$", "").replace(",", "").strip()
    if not s:
        return None
    try:
        num = float(s)
        if num <= 0:
            return None
        if num < 10_000:
            return int(round(num * 1_000_000))
        return int(round(num))
    except ValueError:
        return None


def ensure_fund_id(fund_id: str) -> str:
    if len(fund_id) == 36 and fund_id.count("-") == 4:
        return fund_id
    r = supabase.table("funds").select("id").ilike("name", f"%{fund_id}%").execute()
    if r.data and len(r.data) > 0:
        return r.data[0]["id"]
    print(f"Fund not found: {fund_id}")
    sys.exit(1)


def backfill(csv_path: str, fund_id_arg: str) -> None:
    csv_path = os.path.expanduser(csv_path)
    fund_id = ensure_fund_id(fund_id_arg)

    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        sys.exit(1)

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        headers = [h for h in (reader.fieldnames or []) if h and h.strip()]
        rows = list(reader)

    if not headers or not rows:
        print("No headers or rows in CSV.")
        sys.exit(0)

    # 1) Ensure matrix_columns exist for every CSV header (keep empty columns for later data/documents)
    name_key = normalize_header("name")
    if "company" in [normalize_header(h) for h in headers]:
        name_key = normalize_header("company")
    for raw_header in headers:
        col_id = normalize_header(raw_header)
        if col_id == name_key:
            continue
        display_name = raw_header.strip()
        col_type = column_type(raw_header)
        existing = supabase.table("matrix_columns").select("id").eq("fund_id", fund_id).eq("column_id", col_id).execute()
        if not existing.data or len(existing.data) == 0:
            supabase.table("matrix_columns").insert({
                "fund_id": fund_id,
                "column_id": col_id,
                "name": display_name,
                "type": col_type,
                "created_by": "backfill_csv",
            }).execute()
            print(f"  Column: {display_name} ({col_id})")
    print("Matrix columns ready (empty cells are editable / fillable from documents).")

    # 2) Build name -> row from CSV (use first column that looks like name)
    name_col = None
    for h in headers:
        if normalize_header(h) in ("name", "company", "company_name"):
            name_col = h
            break
    if not name_col:
        name_col = headers[0]

    updated = 0
    for row in rows:
        name = (row.get(name_col) or "").strip()
        if not name:
            continue
        extra = {}
        first_date = None
        total_invested = None
        for h in headers:
            val = (row.get(h) or "").strip()
            if not val or str(val).lower() in ("null", "na", "n/a"):
                extra[normalize_header(h)] = None
                continue
            extra[normalize_header(h)] = val
            if normalize_header(h) in ("date_announced", "date", "investment_date"):
                first_date = parse_date(val) or first_date
            if normalize_header(h) in ("last_amount_raised", "amount", "investment", "invested"):
                total_invested = parse_amount_millions(val) or total_invested

        # Find company by name + fund_id (exact match)
        r = supabase.table("companies").select("id").eq("fund_id", fund_id).eq("name", name).execute()
        if not r.data or len(r.data) == 0:
            continue
        company_id = r.data[0]["id"]
        update_payload = {"extra_data": extra}
        if first_date:
            update_payload["first_investment_date"] = first_date
        if total_invested and total_invested > 0:
            update_payload["total_invested_usd"] = total_invested
        supabase.table("companies").update(update_payload).eq("id", company_id).execute()
        updated += 1
        print(f"  Updated: {name}")

    print(f"\nDone: {updated} companies backfilled with CSV data. Refresh the portfolio grid.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/backfill_portfolio_csv.py <path-to-csv> <fund-id-or-name>")
        sys.exit(1)
    backfill(sys.argv[1], sys.argv[2].strip())
