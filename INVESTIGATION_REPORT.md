# 🔍 INVESTIGATION REPORT - 3 Critical Bugs

## 🔴 Bug #1: Deck Generation Crash - `None - 6`

**Location:** `intelligent_gap_filler.py` line 378

**Error:**
```python
months_of_burn = self._months_between_rounds(
    prev_round.get("date"),
    last_round.get("date")
) - 6  # ❌ CRASH: None - 6 when dates are missing
```

**Root Cause:**
- `_months_between_rounds()` returns `None` when dates are missing/invalid
- Code then does `None - 6` = TypeError

**Impact:**
- **CRITICAL:** Crashes deck generation completely
- Returns 0 slides to frontend

**Fix Required:**
```python
months_between = self._months_between_rounds(
    prev_round.get("date"),
    last_round.get("date")
)
# Handle None before subtracting
months_of_burn = (months_between - 6) if months_between is not None else 12  # Default to 12 months burn
```

---

## 🔴 Bug #2: TAM Logging Crash - Format None Values

**Location:** `unified_mcp_orchestrator.py` lines 1076-1078

**Error:**
```
ERROR: unsupported format string passed to NoneType.__format__
```

**Crash Line:**
```python
logger.info(f"[TAM]   - SAM: ${tam_result['tam_calculation'].get('sam', 0)/1e9:.1f}B")
```

**Root Cause:**
- `.get('sam', 0)` returns the DEFAULT only if the KEY is missing
- If `'sam': None` (key exists, value is None), it returns None
- Then `None/1e9` = TypeError
- Then `None:.1f` = format error

**Example:**
```python
data = {'sam': None}  # Key exists, value is None
x = data.get('sam', 0)  # Returns None, NOT 0!
result = x / 1e9  # TypeError!
```

**Impact:**
- **HIGH:** TAM calculation fails silently
- Market size data not attached to companies
- Deck generation proceeds but missing critical TAM slides

**Fix Required:**
```python
sam = tam_result['tam_calculation'].get('sam') or 0  # Use 'or 0' to handle None
logger.info(f"[TAM]   - SAM: ${sam/1e9:.1f}B")

# OR use the safe getter:
sam = self._get_field_safe(tam_result['tam_calculation'], 'sam')
logger.info(f"[TAM]   - SAM: ${sam/1e9:.1f}B")
```

---

## 🟡 Bug #3: Confusing Debug Logs - "Base ARR median"

**Location:** `intelligent_gap_filler.py` lines 641-644

**The Confusion:**
```python
print(f"\n[GAP FILLER] Stage mapping for {company_data.get('name', 'unknown')}:")
print(f"  Original stage: {stage}")
print(f"  Mapped to: {stage_key}")
print(f"  Base ARR median: ${benchmarks.get('arr_median', 0):,.0f}")  # ❌ MISLEADING
```

Then later (line 816):
```python
print(f"  After time/geo/investor adjustments: ${benchmark_revenue:,.0f}")
```

**The Problem:**
- Logs say "Base ARR median: $2,000,000"
- Looks like it's NOT applying adjustments
- **BUT IT IS** - the adjustments are shown later at line 816
- The debug output is just poorly structured

**Example from logs:**
```
[GAP FILLER] Stage mapping for unknown:
  Original stage: Series A
  Mapped to: Series A
  Base ARR median: $2,000,000  ← Looks like final value
  ... (50 lines later)
  After time/geo/investor adjustments: $8,400,000  ← ACTUAL value used
```

**Impact:**
- **LOW:** Confusing logs make debugging harder
- NOT a functional bug - adjustments ARE being applied
- Just a logging clarity issue

**Fix Required:**
```python
print(f"\n[GAP FILLER] Revenue inference for {company_data.get('name', 'unknown')}:")
print(f"  Stage: {stage_key}")
print(f"  Benchmark (before adjustments): ${benchmarks.get('arr_median', 0):,.0f}")
# ... apply adjustments ...
print(f"  ✅ FINAL INFERRED REVENUE: ${benchmark_revenue:,.0f}")
print(f"  Adjustments: Time={time_multiplier:.2f}x, Geo={geo_mult:.2f}x, Quality={quality_mult:.2f}x")
```

---

## 📊 TAM Search Analysis

**What searches were executed:**

1. **Claimy TAM searches:**
   - ✅ "Claimy industry sector vertical market size TAM Gartner IDC"
   - ✅ "Music Industry market size TAM 2024 2025 billion Gartner"
   - ✅ "Claimy market opportunity TAM addressable"

2. **Trig TAM searches:**
   - ✅ "Trig industry sector vertical market size TAM Gartner IDC"
   - ✅ "Trig market opportunity TAM addressable"

**Results:**
- Claimy: Extracted $1.0B from "Kobalt Music"
- Trig: Extracted $150.2B from "Grand View Research" (vertical software market)

**The searches ARE working** - data is being found. The issue is the TAM calculation crashes when trying to LOG it because of None values.

---

## 🎯 Priority Fix Order

### 1. **CRITICAL** - Fix Deck Generation Crash (Bug #1)
**Impact:** Complete deck generation failure
**Time:** 5 minutes
**File:** `intelligent_gap_filler.py` line 378

### 2. **HIGH** - Fix TAM Logging Crash (Bug #2)
**Impact:** TAM data lost, incomplete decks
**Time:** 10 minutes
**File:** `unified_mcp_orchestrator.py` lines 1076-1090

### 3. **LOW** - Improve Debug Logging (Bug #3)
**Impact:** Developer confusion only
**Time:** 5 minutes
**File:** `intelligent_gap_filler.py` lines 641-820

---

## 🔧 Proposed Fixes

### Fix #1: Safe months_between handling
```python
# Line 378 in intelligent_gap_filler.py
months_between = self._months_between_rounds(
    prev_round.get("date"),
    last_round.get("date")
)
months_of_burn = (months_between - 6) if months_between is not None and months_between > 6 else 12
```

### Fix #2: Safe TAM value extraction
```python
# Lines 1076-1078 in unified_mcp_orchestrator.py
sam = tam_result['tam_calculation'].get('sam') or 0
som = tam_result['tam_calculation'].get('som') or 0
labor_tam = tam_result['tam_calculation'].get('labor_value_capturable') or 0

logger.info(f"[TAM]   - SAM: ${sam/1e9:.1f}B")
logger.info(f"[TAM]   - SOM: ${som/1e9:.1f}B")
logger.info(f"[TAM]   - Labor TAM: ${labor_tam/1e9:.1f}B")
```

### Fix #3: Clearer logging
```python
# Line 641-820 in intelligent_gap_filler.py
print(f"\n[GAP FILLER] Inferring revenue for {company_data.get('name', 'unknown')}:")
print(f"  Stage: {stage_key}")
print(f"  Base benchmark: ${benchmarks.get('arr_median', 0):,.0f}")
# ... apply adjustments ...
print(f"  Time multiplier: {time_multiplier:.2f}x")
print(f"  Geography/Investor/Quality: {quality_mult:.2f}x")
print(f"  ✅ FINAL INFERRED REVENUE: ${benchmark_revenue:,.0f}")
```

---

## ✅ Summary

**What's Actually Broken:**
1. ✅ Deck generation crashes on `None - 6`
2. ✅ TAM logging crashes on `None/1e9`
3. ❌ Debug logs are confusing but functionally correct

**What's Working:**
- ✅ TAM searches are finding data
- ✅ Revenue adjustments ARE being applied
- ✅ The zero-defense helpers we added are working elsewhere

**Next Step:**
Apply the 3 fixes above and test again.


