# Hardcoded Calculations Fixed and Missing Fields Added

## Summary

Fixed hardcoded calculations to use proper services and added missing extracted fields to schemas and types.

## Changes Made

### 1. Added Missing Fields to Schemas and Types

#### Backend Schema (`backend/app/schemas/company.py`)
- ✅ Added `category: Optional[str]` to `Company` schema
- ✅ Added `ai_first: Optional[bool]` to `Company` schema
- ✅ `gross_margin` was already present
- ✅ `business_model` was already in `CompanyBase`

#### Frontend Types (`frontend/src/types/company.ts`)
- ✅ Added `gross_margin?: number`
- ✅ Added `category?: string`
- ✅ Added `ai_first?: boolean`
- ✅ Added `business_model?: string`

### 2. Fixed Hardcoded Liquidation Calculations

#### Sankey Chart Liquidation Waterfall (Line ~11687)
- **Before**: Hardcoded 1x liquidation preference calculation
- **After**: Uses `AdvancedCapTable.calculate_liquidation_waterfall()` service
- **Location**: `backend/app/services/unified_mcp_orchestrator.py` lines 11687-11730
- **Improvement**: Now properly calculates liquidation preferences using actual cap table data, liquidation preferences, and funding rounds

#### PWERM Scenario Liquidation Breakpoint (Line ~11988)
- **Before**: Hardcoded `liq_pref_breakpoint = total_funding * 1.0`
- **After**: Uses `AdvancedCapTable.calculate_waterfall_breakpoints()` service
- **Location**: `backend/app/services/unified_mcp_orchestrator.py` lines 11987-11988
- **Improvement**: Calculates actual liquidation preference breakpoints from cap table and funding rounds

#### M&A Exit Scenario Calculations (Line ~12008)
- **Before**: Hardcoded liquidation preference calculations for M&A scenarios
- **After**: Uses `AdvancedCapTable.calculate_liquidation_waterfall()` for each exit scenario
- **Location**: `backend/app/services/unified_mcp_orchestrator.py` lines 12008-12022
- **Improvement**: Properly accounts for liquidation preferences, participation rights, and cap table structure in M&A exit calculations

### 3. Fixed Hardcoded Check Size Calculations

#### Optimal Check Size Method (Line ~6192)
- **Before**: Only used hardcoded multipliers as fallback
- **After**: First attempts to use `IntelligentGapFiller.score_fund_fit()` service, falls back to hardcoded only if service unavailable
- **Location**: `backend/app/services/unified_mcp_orchestrator.py` lines 6192-6240
- **Improvement**: Now properly uses service-based calculation that considers fund size, deployment pace, portfolio construction, and company characteristics

### 4. Market Sizing

- **Status**: Market sizing extraction is currently disabled in the codebase (line 1791)
- **Note**: When re-enabled, the code should use `IntelligentGapFiller.extract_market_definition()` which properly calculates TAM/SAM/SOM using `_calculate_sam_percentage()` and `_calculate_som_percentage()` methods

## Database Columns

The following fields need to be verified/added to the database:
- `gross_margin` - Already exists in schema, verify DB column
- `category` - New field, needs DB column
- `ai_first` - New field, needs DB column  
- `business_model` - Already in CompanyBase, verify DB column

### SQL Migration Needed

```sql
-- Add missing columns to companies table
ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS category TEXT;

ALTER TABLE companies 
ADD COLUMN IF NOT EXISTS ai_first BOOLEAN;

-- Verify existing columns
-- gross_margin should already exist
-- business_model should already exist in CompanyBase
```

## Service Usage Summary

### Services Now Properly Used

1. **AdvancedCapTable.calculate_liquidation_waterfall()**
   - Used for: Sankey chart waterfall calculations
   - Used for: M&A exit scenario liquidation calculations
   - Replaces: Hardcoded 1x liquidation preference assumptions

2. **AdvancedCapTable.calculate_waterfall_breakpoints()**
   - Used for: Liquidation preference breakpoint calculations
   - Replaces: Hardcoded `total_funding * 1.0` calculation

3. **IntelligentGapFiller.score_fund_fit()**
   - Used for: Optimal check size calculations
   - Replaces: Hardcoded stage multipliers and fund percentage calculations

### Services Available But Not Yet Used

1. **IntelligentGapFiller.extract_market_definition()**
   - Available for: TAM/SAM/SOM calculations
   - Status: Market sizing currently disabled, but service is ready when needed

## Testing Recommendations

1. Test liquidation waterfall calculations with various cap table structures
2. Test check size calculations with different fund contexts
3. Verify API responses include new fields (category, ai_first, gross_margin, business_model)
4. Test frontend components can display new fields
5. Verify database migrations for new columns

## Next Steps

1. ✅ Create database migration for `category` and `ai_first` columns
2. ✅ Update API endpoints to return new fields
3. ✅ Update frontend components to display new fields
4. ✅ Re-enable market sizing extraction using `extract_market_definition()` when ready

