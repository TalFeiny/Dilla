# 🛡️ ZERO DEFENSE PLAN - Stop Data Overwriting

## 🔍 ROOT CAUSE

**Problem:** Division by zero and None comparison errors happen because:

1. ✅ Gap filler DOES run and sets values (line 888-899)
2. ✅ Data IS stored in `shared_data["companies"]` (line 389, 621)
3. ❌ **BUT downstream code uses `.get(field, 0)` which returns `None` if field exists but is `None`**
4. ❌ `.get(key, default)` only uses default if KEY IS MISSING, not if value is None!

**Example:**
```python
company = {"revenue": None}  # Key exists, value is None
x = company.get("revenue", 0)  # Returns None, NOT 0!
result = 100 / x  # TypeError: unsupported operand type(s)
```

## 📋 THE PLAN

### Phase 1: Create Universal Safe Getters (30 min)
**Goal:** One function per critical field that ALWAYS returns a valid number

**Critical Fields:**
- revenue
- valuation  
- total_funding
- team_size
- gross_margin
- burn_rate
- customer_count
- growth_rate
- ltv_cac_ratio

**Implementation:**
```python
def _get_field_safe(self, company: Dict, field: str) -> float:
    """Universal safe getter that checks inferred_ version first"""
    # 1. Check inferred_field first (most reliable)
    inferred = company.get(f"inferred_{field}")
    if inferred is not None:
        return self._safe_get_value(inferred)
    
    # 2. Check raw field
    raw = company.get(field)
    if raw is not None:
        return self._safe_get_value(raw)
    
    # 3. Return 0 as last resort (prevents div/0)
    return 0
```

### Phase 2: Add Defensive Checks to _safe_get_value (10 min)
**Current issue:** Returns None if value is None

**Fix:**
```python
def _safe_get_value(self, value: Any, default: Any = 0) -> Any:
    """Extract value from InferenceResult, Decimal, or return as-is"""
    # Handle None explicitly
    if value is None:
        return default
        
    # Handle InferenceResult objects
    if hasattr(value, 'value'):
        return value.value if value.value is not None else default
        
    # Handle Decimal objects - convert to float
    if isinstance(value, Decimal):
        return float(value)
        
    # Return value or default
    return value if value != 0 or isinstance(value, (int, float)) else default
```

### Phase 3: Replace ALL Unsafe Gets (60 min)
**Find and replace patterns:**

❌ **Before:**
```python
revenue = self._safe_get_value(company.get("revenue", 0))
valuation = self._safe_get_value(company.get("valuation", 0))
```

✅ **After:**
```python
revenue = self._get_field_safe(company, "revenue")
valuation = self._get_field_safe(company, "valuation")
```

**Search patterns to replace:**
- `company.get("revenue"` → `_get_field_safe(company, "revenue")`
- `company.get("valuation"` → `_get_field_safe(company, "valuation")`  
- `company.get("total_funding"` → `_get_field_safe(company, "total_funding")`
- `c.get("revenue"` → `_get_field_safe(c, "revenue")`

### Phase 4: Protect Division Operations (30 min)
**Add defensive checks before ANY division:**

❌ **Before:**
```python
burn_multiple = funding / revenue if revenue > 0 else None
```

✅ **After:**
```python
revenue = max(revenue, 1)  # Never 0
burn_multiple = funding / revenue if revenue > 0 else 0  # Never None
```

**OR use safe division helper:**
```python
def _safe_divide(self, numerator: float, denominator: float, default: float = 0) -> float:
    """Safe division that never crashes"""
    if denominator is None or denominator == 0:
        return default
    if numerator is None:
        return default
    return numerator / denominator
```

### Phase 5: Add Validation Logging (15 min)
**Add checkpoints to verify data integrity:**

```python
# After gap filling
logger.info(f"[GAP_FILL] {company}: revenue={extracted_data.get('revenue')}, inferred_revenue={extracted_data.get('inferred_revenue')}")

# Before calculations
logger.info(f"[CALC] revenue={revenue}, valuation={valuation}, funding={funding}")
```

## 🎯 SUCCESS CRITERIA

1. ✅ No more `TypeError: '>' not supported between instances of 'NoneType' and 'int'`
2. ✅ No more `ZeroDivisionError`
3. ✅ All metrics use inferred values when raw data is missing
4. ✅ Deck generation completes without errors
5. ✅ All comparisons handle None gracefully

## 📊 TESTING PLAN

1. Test with company that has NO financial data (all None)
2. Test with company that has PARTIAL data (some None)
3. Test deck generation with 2 companies
4. Monitor logs for "Using inferred value" messages
5. Verify NO zeros in final calculations (unless company is actually $0 revenue)

## 🚀 ROLLOUT ORDER

1. Implement Phase 1 (safe getters)
2. Implement Phase 2 (defensive _safe_get_value)
3. Test with one company
4. Implement Phase 3 (replace unsafe gets) - do in batches
5. Implement Phase 4 (protect divisions)
6. Implement Phase 5 (logging)
7. Full integration test


