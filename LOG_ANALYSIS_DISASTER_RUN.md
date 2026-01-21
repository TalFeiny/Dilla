# Log Analysis: Disaster Run - Root Cause Analysis

## Executive Summary

The run completed but with **hundreds of warnings and critical data quality issues** that degrade output quality. The deck was generated (22 slides) but contains invalid data, broken calculations, and missing information.

---

## Critical Issues Found

### 1. **Hundreds of Invalid Exit Value Warnings** (Lines 1-204)

**Problem**: 200+ warnings: `[PWERM_NORMALIZE] Invalid exit_value in scenario: Liquidation/Strategic Acquisition/Microcap Regional IPO/Roll-up/PE Buyout`

**Root Cause**: 
- Scenarios are being created with `exit_value = 0` or missing `exit_value`
- The `_normalize_pwerm_scenario()` function at line 25112-25113 validates `exit_value <= 0` and logs warnings
- These scenarios are being normalized but have no actual exit value, making them useless for PWERM calculations

**Impact**: 
- PWERM valuations are calculated with invalid scenarios
- Exit scenario analysis is meaningless
- Probability distributions are skewed

**Location**: `backend/app/services/unified_mcp_orchestrator.py:25112-25113`

---

### 2. **Cap Table Calculation Failures** (Lines 370-380)

**Problem**: Cap table totals don't add up to 100%:
- Round 2: 96.53% → normalized to 100%
- Round 2 after ESOP: 87.68% → normalized to 100%  
- Round 3: 81.85% → normalized to 100%
- Round 3 after ESOP: 98.48% → normalized to 100%

**Root Cause**:
- The cap table calculation logic in `pre_post_cap_table.py` is incorrectly calculating ownership percentages
- ESOP expansion is being added incorrectly
- Investor ownership is being miscalculated
- The system is "normalizing" (forcing to 100%) instead of fixing the calculation

**Impact**:
- All cap table slides show incorrect ownership percentages
- Dilution calculations are wrong
- Investor ownership is inaccurate

**Location**: `backend/app/services/pre_post_cap_table.py:_calculate_full_cap_table_history_impl()`

---

### 3. **Probability Normalization Failures** (Lines 365-392)

**Problem**: Exit scenario probabilities sum incorrectly:
- Lawhive: Sums to 2.3349 (expected 1.0) → normalized
- @Wexler: Sums to 1.9919 (expected 1.0) → normalized

**Root Cause**:
- The `_adjust_probabilities()` function in `pwerm_comprehensive.py` is multiplying probabilities incorrectly
- Probability adjustments for growth_rate, burn_rate, runway are being applied incorrectly
- The normalization happens AFTER the fact, masking the underlying bug

**Impact**:
- Exit scenario probabilities are meaningless
- PWERM valuations are based on incorrect probability distributions
- Risk analysis is unreliable

**Location**: `backend/app/services/pwerm_comprehensive.py:_adjust_probabilities()`

---

### 4. **Missing Revenue Data** (Lines 358, 384)

**Problem**: 
- `ERROR: No inferred_revenue for Lawhive - using emergency fallback`
- `ERROR: No inferred_revenue for @Wexler - using emergency fallback`

**Root Cause**:
- Revenue extraction from company data is failing
- The system falls back to `$1,000,000` emergency estimate
- This makes all revenue-based calculations (margins, growth, valuations) inaccurate

**Impact**:
- Revenue projections are wrong
- Margin calculations are based on fake data
- Valuation models are using incorrect inputs

**Location**: `backend/app/services/intelligent_gap_filler.py` (revenue extraction logic)

---

### 5. **Missing Investor Names in Sankey Diagram**

**Problem**: User complaint: "at least just list the investors" - the Sankey diagram shows generic fund flow nodes but NO actual investor names from funding rounds.

**Root Cause**:
- The Sankey diagram code at lines 18400-18589 creates nodes for fund flows (Deployed, Remaining, Target DPI) but doesn't extract or display actual investor names
- Investor extraction happens in `pre_post_cap_table.py` (lines 1106-1132) but isn't being passed to the Sankey diagram
- The Sankey is showing fund-level flows, not company-level investor details

**Impact**:
- Users can't see who invested in the companies
- Missing critical information for investment analysis
- Sankey diagram is less useful than it should be

**Location**: 
- Sankey generation: `backend/app/services/unified_mcp_orchestrator.py:18400-18589`
- Investor extraction: `backend/app/services/pre_post_cap_table.py:1106-1132`

---

### 6. **Service Instantiation Warnings** (Lines 206, 226, 232, 252)

**Problem**: Multiple warnings about creating new service instances:
- `[IntelligentGapFiller] Creating new ValuationEngineService - consider passing shared instance from orchestrator`
- `[IntelligentGapFiller] Creating new PrePostCapTable instance - this will cause cache misses`

**Root Cause**:
- Services are being instantiated multiple times instead of being shared
- This causes cache misses and duplicate calculations
- Performance degradation

**Impact**:
- Slower execution
- Cache misses (94% hit rate, but could be better)
- Duplicate work

---

## Data Flow Issues

### Scenario Generation → Normalization → Validation

```
1. Scenarios created with exit_value=0
   ↓
2. _normalize_pwerm_scenario() called
   ↓
3. Validation fails (exit_value <= 0)
   ↓
4. Warning logged, but scenario still used
   ↓
5. PWERM calculation uses invalid scenario
```

**Fix Needed**: Scenarios should be created with valid exit_values, or filtered out before normalization.

---

### Cap Table Calculation → Validation → Normalization

```
1. Cap table calculated for each round
   ↓
2. Validation checks if total = 100%
   ↓
3. Validation fails (e.g., 96.53%)
   ↓
4. System "normalizes" by scaling all values
   ↓
5. Original calculation error is hidden
```

**Fix Needed**: Fix the calculation logic instead of normalizing. The calculation is wrong.

---

### Probability Adjustment → Normalization

```
1. Probabilities adjusted based on company factors
   ↓
2. Total probability = 2.33 (should be 1.0)
   ↓
3. System normalizes by dividing by 2.33
   ↓
4. Original adjustment logic is wrong
```

**Fix Needed**: Fix the probability adjustment multipliers. They're too aggressive.

---

## What Actually Worked

1. ✅ Deck generation completed (22 slides)
2. ✅ Citations extracted (43 citations)
3. ✅ Slide structure is valid
4. ✅ Cache hit rate is 94% (good, but could be better)
5. ✅ API endpoint returned successfully

---

## Recommendations (Priority Order)

### P0 - Critical (Fix Immediately)

1. **Fix exit_value generation**: Ensure all scenarios have valid exit_values before normalization
2. **Fix cap table calculations**: Debug why totals don't add to 100% - fix the math, don't normalize
3. **Fix probability adjustments**: Review multipliers in `_adjust_probabilities()` - they're too high
4. **Add investor names to Sankey**: Extract investor names from funding rounds and display in Sankey nodes

### P1 - High Priority

5. **Fix revenue extraction**: Debug why `inferred_revenue` is missing - improve extraction logic
6. **Share service instances**: Pass shared instances to avoid duplicate instantiation
7. **Improve error handling**: Don't use "emergency fallbacks" silently - log errors and fail gracefully

### P2 - Medium Priority

8. **Improve validation**: Fail fast on invalid data instead of normalizing
9. **Add data quality checks**: Validate data at each step, not just at the end
10. **Improve logging**: Reduce noise from repeated warnings (aggregate or suppress duplicates)

---

## Code Locations to Fix

1. **Exit Value Issues**: 
   - `backend/app/services/unified_mcp_orchestrator.py:25071-25117` (`_normalize_pwerm_scenario`)
   - `backend/app/services/pwerm_comprehensive.py` (scenario generation)

2. **Cap Table Issues**:
   - `backend/app/services/pre_post_cap_table.py:541-1132` (`_calculate_full_cap_table_history_impl`)

3. **Probability Issues**:
   - `backend/app/services/pwerm_comprehensive.py:454-524` (`_adjust_probabilities`)

4. **Revenue Issues**:
   - `backend/app/services/intelligent_gap_filler.py` (revenue extraction)

5. **Sankey Investor Issues**:
   - `backend/app/services/unified_mcp_orchestrator.py:18400-18589` (Sankey generation)
   - `backend/app/services/pre_post_cap_table.py:1106-1132` (investor extraction)

---

## Conclusion

The run "succeeded" but produced **low-quality output** due to:
- Invalid scenario data (exit_values = 0)
- Broken cap table math (totals don't add up)
- Incorrect probability distributions
- Missing revenue data
- Missing investor information in visualizations

**The system is masking errors with normalization instead of fixing root causes.** This creates a false sense of success while producing unreliable results.
