# PnL CSV Upload — Robustness Improvements

## Problem

CSV upload in PnL mode silently fails or drops data for anything beyond the simplest format. The portfolio CSV importer has multi-tier fuzzy matching, header cleaning, and smart normalization — the PnL parser has none of it.

A real-world CSV like this produces zero ingested rows:

```
Category              Q1 2026 (Est.)
Total Revenue         $4,200
   API Usage Revenue  $2,800
   Enterprise Training $1,400

Cost of Goods Sold (COGS)  -$2,100
   Cloud Inference Costs   -$1,650

Gross Profit          $2,100
---                   ---
Operating Expenses (OpEx)  -$14,500
   R&D / Model Training    -$10,000
   Payroll & Benefits      -$3,200

Operating Income (EBITDA)  -$12,400
Net Income / (Loss)        -$12,250
```

**Why it fails:**
- `Q1 2026 (Est.)` — not recognized as a period
- Indented rows — not detected as subcategories
- `---` separators — treated as data rows
- `Cost of Goods Sold (COGS)` — parenthetical suffix may confuse matching
- `R&D / Model Training` — subcategory not in taxonomy, dropped entirely
- `Gross Profit`, `EBITDA` — computed rows that double-count if stored alongside components

---

## Current State

### What works (`backend/app/api/endpoints/fpa_query.py`)

| Component | Status | Coverage |
|-----------|--------|----------|
| `_parse_month_header` | Monthly only | `2025-01`, `Jan-25`, `Jan 2025`, `01/2025` |
| `_match_category` | 15 regex patterns | Revenue, COGS, R&D, S&M, G&A, OpEx, EBITDA, etc. |
| `_parse_amount` | Good | `$1,500`, `(100K)`, `2.5M`, currency symbols, parens-as-negative |
| Orientation detection | Good | Auto-detects categories-as-rows vs months-as-rows |
| Upsert | Good | `ON CONFLICT (company_id, period, category, source)` |

### What's missing

| Gap | Impact |
|-----|--------|
| No quarterly/annual period support | Q1 2026, FY2025, H1 2026 all fail |
| No header cleaning | `(Est.)`, `(Actual)`, `(Budget)` suffixes break period parsing |
| No hierarchy/indentation detection | Indented subcategory rows treated as top-level, usually unmapped |
| No subcategory storage from CSV | `fpa_actuals.subcategory` column exists but CSV upload never populates it |
| No separator exclusion | `---`, `===`, blank lines with labels treated as data |
| No computed-row detection | Gross Profit, EBITDA stored alongside components = double-counting |
| No fuzzy category fallback | Unmatched labels silently dropped, no second-chance matching |
| No noise-word stripping | "Total Revenue" works, but "Total Operating Expenses (excl. D&A)" doesn't |
| European number format | `1.234.567,89` not handled (portfolio importer handles it) |

### What the portfolio importer does that we don't

The portfolio CSV import (`frontend/src/app/api/portfolio/[id]/import-csv/route.ts`) has:

1. **`normalizeHeader()`** — strips `[_\-()[\]{}#*]`, removes noise words `(the|of|in|for|our|total|current|latest|usd|eur|gbp)`, collapses whitespace
2. **3-tier matching** — exact normalized → exact lowercase → keyword regex fallback
3. **European number detection** — `1.234.567,89` → `1234567.89`
4. **`csv-field-mapper.ts`** — Levenshtein fuzzy matching with confidence scoring
5. **Unmapped data preservation** — stores in `extra_data` JSONB instead of dropping

Backend also has `difflib.SequenceMatcher` already used in `portfolio_service.py` for fuzzy company name matching.

---

## What We Need

### 1. Period Header Cleaning & Parsing

**Current:** Only handles monthly formats.

**Need:** Strip suffixes, then parse quarterly/annual/half-yearly.

```
Input                    → Cleaned           → Period(s)
"Q1 2026 (Est.)"        → "Q1 2026"         → 2026-01, 2026-02, 2026-03
"Q4 2025"               → "Q4 2025"         → 2025-10, 2025-11, 2025-12
"H1 2026"               → "H1 2026"         → 2026-01 through 2026-06
"FY2025"                → "FY2025"          → 2025-01 through 2025-12
"2025"                  → "2025"            → 2025-01 through 2025-12
"Jan-25 (Actual)"       → "Jan-25"          → 2025-01
"Feb 2025 (Budget)"     → "Feb 2025"        → 2025-02
"January - March 2025"  → "Q1 2025"         → 2025-01, 2025-02, 2025-03
```

**Quarterly/annual amounts** should be divided evenly across constituent months for storage (PnlBuilder expects monthly granularity).

**Implementation:** Enhance `_parse_month_header` to return a list of `(period, divisor)` tuples instead of a single string:
- Monthly: `[("2025-01", 1)]`
- Quarterly: `[("2026-01", 3), ("2026-02", 3), ("2026-03", 3)]`
- Annual: `[("2025-01", 12), ..., ("2025-12", 12)]`

### 2. Row Label Cleaning & Normalization

**Current:** Raw label passed directly to `_match_category`.

**Need:** Clean before matching, preserve original for subcategory naming.

```python
def _clean_label(raw: str) -> tuple[str, int]:
    """Clean a row label for matching. Returns (cleaned_label, indent_depth)."""
    # 1. Detect indentation depth (spaces or tabs)
    stripped = raw.lstrip()
    indent = len(raw) - len(stripped)
    depth = indent // 2 if indent > 0 else 0  # normalize: 2-3 spaces = depth 1

    # 2. Strip parenthetical suffixes: (COGS), (OpEx), (excl. D&A)
    # But keep the content for matching: "Cost of Goods Sold (COGS)" → try both

    # 3. Remove noise words that don't help matching:
    #    "Total", "Net", "Less", "Plus", "Sub-total", "Subtotal"
    #    But be careful: "Net Income" needs "Net" for matching

    # 4. Normalize whitespace and special chars:
    #    "R&D / Model Training Costs" → "r&d model training costs"

    return cleaned, depth
```

### 3. Hierarchy Detection

**Current:** All rows treated as flat, top-level categories.

**Need:** Detect parent/child relationships from indentation or naming patterns.

```
Category                        → depth=0, category=None (section header)
   API Usage Revenue            → depth=1, parent=revenue, subcategory="api_usage_revenue"
   Enterprise Training Services → depth=1, parent=revenue, subcategory="enterprise_training"

Operating Expenses (OpEx)       → depth=0, category=opex_total (or section header)
   R&D / Model Training Costs  → depth=1, parent=opex_rd, subcategory="model_training"
   Payroll & Benefits           → depth=1, parent=opex_ga, subcategory="payroll_benefits"
   Sales & Marketing            → depth=1, parent=opex_sm (no subcategory, IS a category)
```

**Logic:**
1. Parse indentation depth for each row
2. `depth=0` rows: match against `_CATEGORY_PATTERNS` as today
3. `depth>0` rows:
   - First try matching as a known category (e.g. "Sales & Marketing" at depth 1 is still `opex_sm`)
   - If no category match, treat as subcategory of the nearest `depth=0` parent above
   - Fuzzy-match the label against `SUBCATEGORY_TAXONOMY` from `actuals_ingestion.py`
   - If still no match, normalize the label to snake_case and store as a dynamic subcategory

**Subcategory normalization:** `"Cloud Inference Costs"` → `"cloud_inference_costs"`. Store in `fpa_actuals.subcategory`.

### 4. Row Exclusion Logic

**Current:** Only skips rows where first cell is empty.

**Need:** Skip formatting/separator/computed rows.

**Separator detection:**
```python
def _is_separator_row(row: list[str]) -> bool:
    """Skip rows that are formatting separators."""
    # All cells are dashes, equals, empty, or whitespace
    return all(re.match(r'^[\s\-=]*$', cell) for cell in row)
```

**Computed row detection:**
```python
COMPUTED_CATEGORIES = {"gross_profit", "ebitda", "net_income", "operating_income"}

# Skip computed rows ONLY when their component rows exist in the same CSV.
# e.g., skip "Gross Profit" if both "Revenue" and "COGS" rows are present.
# This prevents double-counting in the database.

COMPUTED_DEPENDENCIES = {
    "gross_profit": {"revenue", "cogs"},
    "ebitda": {"revenue", "cogs", "opex_total"} | {"revenue", "cogs", "opex_rd", "opex_sm", "opex_ga"},
    "net_income": {"revenue", "cogs"},  # if any expense categories present
}
```

**Two-pass approach:**
1. First pass: scan all rows, detect which categories are present
2. Second pass: skip computed rows whose dependencies are all present (they can be re-derived)
3. If dependencies are NOT all present, keep the computed row (it's the only source of that data)

### 5. Expanded Category Patterns

**Current patterns miss:** ERP-specific terminology, UK accounting terms, verbose labels.

**Add these patterns:**

```python
# Revenue variants
(r"(?:total\s+)?income(?!\s*tax)|turnover|sales\s*revenue|top\s*line|gross\s*revenue", "revenue"),
(r"other\s*income|non.?operating\s*income|interest\s*income|sundry\s*income", "other_income"),  # NEW category

# Expense variants
(r"payroll|salaries|wages|compensation|personnel|staff\s*costs?|people\s*costs?", "opex_ga"),
(r"depreciation|amortization|d&a|deprec", "depreciation"),  # NEW category
(r"interest\s*expense|finance\s*costs?|debt\s*service", "interest_expense"),  # NEW category
(r"tax|income\s*tax|corporation\s*tax|provision\s*for\s*tax", "tax"),  # NEW category

# UK/International variants
(r"turnover", "revenue"),
(r"cost\s*of\s*sales", "cogs"),
(r"overheads?|indirect\s*costs?", "opex_total"),
(r"establishment\s*costs?|premises|rent|occupancy", "opex_ga"),

# Operating income variants
(r"operating\s*(?:income|profit|loss)|op(?:erating)?\s*(?:income|profit)", "ebitda"),
(r"profit\s*before\s*tax|pbt|earnings\s*before\s*tax|ebt", "ebt"),
(r"profit\s*after\s*tax|pat|earnings\s*after\s*tax", "net_income"),
```

**New categories needed in `fpa_actuals`:** `other_income`, `depreciation`, `interest_expense`, `tax`, `ebt`. These complete the full P&L waterfall (Revenue → Gross Profit → EBITDA → EBIT → EBT → Net Income).

### 6. Fuzzy Category Fallback

**Current:** No match → row dropped.

**Need:** After regex patterns fail, try fuzzy matching using `difflib.SequenceMatcher`.

```python
from difflib import SequenceMatcher

# All known category labels for fuzzy matching
CATEGORY_LABELS_FOR_FUZZY = {
    "revenue": ["revenue", "sales", "income", "turnover", "top line"],
    "cogs": ["cost of goods sold", "cost of sales", "direct costs", "cogs"],
    "opex_rd": ["research and development", "r&d", "engineering", "product development"],
    "opex_sm": ["sales and marketing", "s&m", "marketing", "commercial"],
    "opex_ga": ["general and administrative", "g&a", "admin", "overhead", "payroll"],
    "opex_total": ["operating expenses", "opex", "total expenses", "overheads"],
    "ebitda": ["ebitda", "operating income", "operating profit"],
    ...
}

def _fuzzy_match_category(label: str, threshold: float = 0.65) -> Optional[str]:
    """Fuzzy match a row label to a category using SequenceMatcher."""
    label_lower = label.lower().strip()
    best_score = 0
    best_category = None

    for category, synonyms in CATEGORY_LABELS_FOR_FUZZY.items():
        for synonym in synonyms:
            score = SequenceMatcher(None, label_lower, synonym).ratio()
            # Boost if one contains the other
            if label_lower in synonym or synonym in label_lower:
                score = max(score, 0.85)
            if score > best_score:
                best_score = score
                best_category = category

    return best_category if best_score >= threshold else None
```

**Matching order:**
1. Regex patterns (fast, high confidence)
2. Fuzzy match (slower, medium confidence — logged for transparency)
3. If `depth > 0` and no match → store as dynamic subcategory under parent
4. If `depth == 0` and no match → add to `unmapped_labels` in response

### 7. Amount Parsing Improvements

**Current `_parse_amount` is mostly good. Add:**

```python
# European notation: 1.234.567,89 → 1234567.89
european = re.match(r'^-?[\d.]+(,\d{1,2})$', s)
if european:
    s = s.replace('.', '').replace(',', '.')

# Handle "bn" suffix: 1.5bn → 1,500,000,000
# Handle "mm" suffix: 200mm → 200,000,000 (common in finance)
# mm = millions in finance parlance, not millimeters

# Percentage values in P&L context: "15%" → store as-is or convert?
# For margins embedded in P&L CSVs, strip % and store as decimal
```

### 8. Upsert Logic Audit

**Current upsert is solid** — `ON CONFLICT (company_id, period, category, source)`.

**One gap:** When storing subcategories, we need to upsert with the full key. The current unique index is `(company_id, period, category, source)` — this doesn't include `subcategory`. Two subcategories under the same parent category in the same period would collide.

**Fix:** Either:
- (a) Add `subcategory` to the unique constraint: `(company_id, period, category, subcategory, source)` — **recommended**
- (b) Concatenate subcategory into category: `"opex_rd:engineering_salaries"` — hacky, breaks existing queries

**Migration needed:**
```sql
-- Drop old index
DROP INDEX IF EXISTS idx_fpa_actuals_dedup;

-- Create new index with subcategory (COALESCE handles NULLs)
CREATE UNIQUE INDEX idx_fpa_actuals_dedup
ON fpa_actuals (company_id, period, category, COALESCE(subcategory, ''), source);
```

### 9. Response Improvements

**Current:** Returns `unmapped_labels` but no detail on why.

**Improve to:**
```json
{
  "ingested": 45,
  "periods": ["2026-01", "2026-02", "2026-03"],
  "categories": ["revenue", "cogs", "opex_rd"],
  "subcategories_created": ["cloud_inference_costs", "api_usage_revenue"],
  "mapped_categories": [
    {"label": "Total Revenue", "category": "revenue", "match": "regex"},
    {"label": "Cloud Inference Costs", "category": "cogs", "subcategory": "cloud_inference_costs", "match": "hierarchy"}
  ],
  "unmapped_labels": ["Random Notes Row"],
  "skipped_rows": {
    "separators": 2,
    "computed": ["Gross Profit", "EBITDA"],
    "empty": 3
  },
  "warnings": [
    "Quarterly amounts divided by 3 for monthly storage",
    "Fuzzy-matched 'Payroll & Benefits' → opex_ga (score: 0.72)"
  ]
}
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `backend/app/api/endpoints/fpa_query.py` | All parser improvements: header cleaning, hierarchy detection, fuzzy matching, row exclusion, expanded patterns, quarterly/annual periods |
| `backend/app/services/actuals_ingestion.py` | Export `SUBCATEGORY_TAXONOMY` and `SUBCATEGORY_TO_PARENT` for import by the parser; possibly add new subcategory synonyms |
| `supabase/migrations/YYYYMMDD_fix_fpa_actuals_subcategory_upsert.sql` | Update unique index to include subcategory |
| `test-data/sample-pnl-actuals.csv` | Add more test CSVs covering edge cases |

## Files NOT Modified

| File | Why |
|------|-----|
| Frontend upload handler | Already sends raw file — all intelligence is backend |
| `PnlBuilder` | Already handles subcategories from `fpa_actuals` |
| `fetchPnlForMatrix` | Already maps PnlBuilder output to grid |

---

## Test CSVs Needed

### 1. Simple monthly (current format — must still work)
```csv
Category,Jan-25,Feb-25,Mar-25
Revenue,"$100,000","$110,000","$121,000"
COGS,"$30,000","$33,000","$36,300"
```

### 2. Quarterly with hierarchy
```csv
Category,Q1 2026,Q2 2026,Q3 2026,Q4 2026
Total Revenue,$4200,$5100,$6200,$7500
   API Revenue,$2800,$3400,$4100,$5000
   Services,$1400,$1700,$2100,$2500
Cost of Goods Sold,-$2100,-$2550,-$3100,-$3750
   Cloud Costs,-$1650,-$2000,-$2400,-$2900
Operating Expenses,-$14500,-$14800,-$15200,-$15600
   R&D,-$10000,-$10200,-$10500,-$10800
   Sales & Marketing,-$850,-$900,-$950,-$1000
   G&A,-$450,-$480,-$500,-$520
```

### 3. Xero-style export
```csv
,Jan 2025,Feb 2025,Mar 2025
Income,,
   Sales,150000,165000,180000
   Other Income,5000,5000,5000
Less Cost of Sales,,
   Direct Costs,45000,49500,54000
Gross Profit,110000,120500,131000
Less Operating Expenses,,
   Advertising,12000,13000,14000
   Rent,8000,8000,8000
   Salaries,45000,47000,49000
   Telephone & Internet,2000,2000,2000
Net Profit,-2000,5500,16000
```

### 4. UK / Sage format
```csv
,Apr-25,May-25,Jun-25
Turnover,"£250,000","£275,000","£300,000"
Cost of Sales,"£75,000","£82,500","£90,000"
Overheads,,
   Establishment Costs,"£15,000","£15,000","£15,000"
   Staff Costs,"£95,000","£100,000","£105,000"
   Admin Expenses,"£20,000","£20,000","£20,000"
```

### 5. Transposed (months as rows)
```csv
Period,Revenue,COGS,R&D,S&M,G&A
Jan 2025,500000,200000,50000,75000,30000
Feb 2025,550000,220000,50000,75000,30000
```

### 6. Annual
```csv
Category,FY2024,FY2025
Revenue,"$2,400,000","$3,600,000"
COGS,"$720,000","$1,080,000"
Operating Expenses,"$1,920,000","$2,160,000"
```

---

## Processing Pipeline (New)

```
Raw CSV
  │
  ├─ 1. Parse CSV (handle quotes, tabs, commas)
  │
  ├─ 2. Clean headers
  │     └─ Strip parenthetical suffixes: (Est.), (Actual), (Budget)
  │     └─ Parse periods: monthly → single, quarterly → 3 months, annual → 12 months
  │
  ├─ 3. Detect orientation (categories-as-rows vs months-as-rows)
  │
  ├─ 4. First pass: scan all row labels
  │     └─ Detect indentation → build parent/child tree
  │     └─ Match categories (regex → fuzzy → dynamic subcategory)
  │     └─ Identify separator rows, computed rows, section headers
  │
  ├─ 5. Second pass: determine skip logic
  │     └─ Skip separators always
  │     └─ Skip computed rows only if dependencies present
  │     └─ Skip section headers that have no amounts
  │
  ├─ 6. Third pass: extract amounts
  │     └─ For each non-skipped row × each period column
  │     └─ Divide quarterly/annual amounts by period count
  │     └─ Build actuals_rows with category + subcategory
  │
  ├─ 7. Upsert into fpa_actuals
  │     └─ ON CONFLICT (company_id, period, category, COALESCE(subcategory,''), source)
  │
  └─ 8. Return detailed response with mapping report
```
