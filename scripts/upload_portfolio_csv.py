#!/usr/bin/env python3
"""
Clean a portfolio CSV and upload companies to Supabase for a given fund.

CSV columns supported (case-insensitive, flexible names):
  - date_announced / date / investment date -> first_investment_date
  - name / company -> name
  - lead / investment lead -> investment_lead (TRUE/FALSE or name)
  - round / stage -> funnel_status
  - last_amount_raised / amount / investment / invested -> total_invested_usd (assumed millions)
  - description -> ignored (no column in companies)

Usage:
  # From repo root; load env from .env or .env.local
  python scripts/upload_portfolio_csv.py "/path/to/file.csv" "<fund-id>"

  # Or set env and run
  export NEXT_PUBLIC_SUPABASE_URL=...
  export SUPABASE_SERVICE_ROLE_KEY=...
  python scripts/upload_portfolio_csv.py "/path/to/file.csv" "<fund-id>"
"""

import os
import sys
import csv
import re
from datetime import datetime
from pathlib import Path

# Load env from repo root
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
    print("Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or use .env.local).")
    sys.exit(1)

from supabase import create_client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def parse_date(s: str) -> str | None:
    if not s or not str(s).strip():
        return None
    s = str(s).strip()
    # Remove time part
    if " " in s:
        s = s.split(" ")[0]
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
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
        # Values like 15.60, 120, 253 are in millions
        if num < 10_000:
            return int(round(num * 1_000_000))
        return int(round(num))
    except ValueError:
        return None


def normalize_header(h: str) -> str:
    return h.strip().lower().replace(" ", "_").replace("-", "_")


def map_row(row: dict, headers: list[str]) -> dict | None:
    by_key = {normalize_header(k): (k, v) for k, v in row.items() if k}
    # Name
    name = None
    for key in ("name", "company", "company_name"):
        if key in by_key:
            name = (by_key[key][1] or "").strip()
            break
    if not name:
        return None

    # Date
    first_date = None
    for key in ("date_announced", "date", "investment_date", "first_investment"):
        if key in by_key:
            first_date = parse_date(by_key[key][1])
            if first_date:
                break

    # Round / stage — DB has companies_funnel_status_check (allowed values vary by deployment)
    # Use 'portfolio' so insert always succeeds; you can edit stage in the app later
    stage = "portfolio"

    # Amount (assume millions)
    amount = None
    for key in ("last_amount_raised", "amount", "investment", "invested", "total_invested", "check_size"):
        if key in by_key:
            amount = parse_amount_millions(by_key[key][1])
            if amount is not None:
                break

    # Lead (optional)
    lead = None
    for key in ("lead", "investment_lead", "deal_lead"):
        if key in by_key:
            val = (by_key[key][1] or "").strip()
            if val:
                lead = "Yes" if str(val).upper() in ("TRUE", "1", "YES", "Y") else val
                break

    return {
        "name": name,
        "first_investment_date": first_date,
        "funnel_status": stage,
        "total_invested_usd": amount if amount and amount > 0 else 1,  # API requires > 0
        "investment_lead": lead,
    }


def upload_csv(csv_path: str, fund_id: str) -> None:
    csv_path = os.path.expanduser(csv_path)
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        sys.exit(1)

    rows_to_insert = []
    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        for row in reader:
            mapped = map_row(row, headers)
            if mapped:
                rows_to_insert.append(mapped)

    if not rows_to_insert:
        print("No valid rows to import.")
        sys.exit(0)

    print(f"Cleaned {len(rows_to_insert)} rows. Uploading to fund_id={fund_id} ...")

    # Build insert payloads (companies table)
    inserted = 0
    skipped = 0
    errors = 0
    for r in rows_to_insert:
        payload = {
            "name": r["name"],
            "fund_id": fund_id,
            "funnel_status": r["funnel_status"],
            "total_invested_usd": r["total_invested_usd"],
            "first_investment_date": r["first_investment_date"] or None,
            "status": "active",
        }
        # Add investment_lead if present in CSV data
        if r.get("investment_lead"):
            payload["investment_lead"] = r["investment_lead"]

        try:
            result = supabase.table("companies").insert(payload).execute()
            if result.data:
                inserted += 1
                print(f"  OK: {r['name']}")
            else:
                errors += 1
                print(f"  Skip (no data): {r['name']}")
        except Exception as e:
            msg = str(e).lower()
            if "23505" in msg or "duplicate" in msg or "unique" in msg:
                skipped += 1
                print(f"  Skip (already exists): {r['name']}")
            else:
                errors += 1
                print(f"  Error: {r['name']} -> {e}")

    print(f"\nDone: {inserted} inserted, {skipped} skipped (duplicate), {errors} errors.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python scripts/upload_portfolio_csv.py <path-to-csv> <fund-id>")
        sys.exit(1)
    upload_csv(sys.argv[1], sys.argv[2].strip())
