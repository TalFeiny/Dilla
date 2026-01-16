# Numpy Serialization Fix - Data Flow

## The Problem
Database queries (especially Supabase) return `numpy.int64`, `numpy.float64` types that Python's standard JSON serializer cannot handle.

## The Error
```
TypeError("'numpy.int64' object is not iterable")
TypeError('vars() argument must have __dict__ attribute')
```

## The Solution - Three-Layer Defense

### Layer 1: `ensure_numeric()` in data_validator.py
**When**: Called by `validate_company_data()` for ALL numeric fields
**What**: Converts numpy types to Python float/int
**Flow**: 
```
Database query → company_data → validate_company_data() → ensure_numeric() → Python types
```

### Layer 2: `safe_get_value()` in data_validator.py  
**When**: Used when getting values from company dictionaries
**What**: Converts numpy types to Python types
**Flow**:
```
company.get('field') → safe_get_value() → Python type
```

### Layer 3: `clean_for_json()` in json_serializer.py
**When**: Before JSON serialization
**What**: Final safety net - converts any remaining numpy types before JSON encoding
**Flow**:
```
Deck data → clean_for_json() → JSONResponse → Safe JSON
```

## Critical Points

1. **`validate_company_data()` is called at**:
   - Line 338: After fetching from database
   - Line 2256: After data extraction  
   - Line 15797: After inference enrichment

2. **`ensure_numeric()` is called for**:
   - All numeric fields (revenue, valuation, growth_rate, etc.)
   - Both actual values and inferred values

3. **`clean_for_json()` is called**:
   - Before returning JSONResponse in unified_brain.py
   - This is the FINAL safety check

## Testing the Fix

The fix ensures numpy types are converted AT THE SOURCE (database queries) and protected throughout the entire pipeline.

