[1 tool called]



## Summary: Deck Generation Issue Fixes

### ✅ **COMPLETED FIXES**

1. **Fixed Frontend API Route Issue** 
   - **Problem**: Frontend sent `output_format: 'deck'` but API route looked for `body.outputFormat` (camelCase) and defaulted to `'analysis'`
   - **Fix**: Updated `/Users/admin/code/dilla-ai/frontend/src/app/api/agent/unified-brain/route.ts` line 80 to check both `body.output_format` and `body.outputFormat`
   - **Result**: Deck requests now properly pass through to backend

2. **Fixed Series F/G Stage Mapping**
   - **Problem**: `_normalize_stage_key()` function only handled up to Series D, defaulting Series F/G to 'Seed'
   - **Fix**: Added Series E/F mapping to 'Series D+' in `/Users/admin/code/dilla-ai/backend/app/services/intelligent_gap_filler.py`
   - **Result**: Late-stage companies (Series F/G) now correctly map to Series D+ instead of Seed

### 🔄 **REMAINING ISSUE**

3. **Revenue Inference Override** (Still pending)
   - **Problem**: System infers revenue even when companies already have actual revenue data
   - **Location**: Multiple places in `intelligent_gap_filler.py` where revenue inference happens
   - **Need**: Add checks to skip inference when `company_data.get('revenue')` or `company_data.get('arr')` already exists

### 🎯 **EXPECTED RESULT**
With these fixes, deck generation should now:
- ✅ Properly receive `output_format: 'deck'` from frontend
- ✅ Add `deck-storytelling` skill to the skill chain
- ✅ Use correct stage benchmarks for Series F/G companies
- ⏳ Skip unnecessary revenue inference when data exists

The core deck generation flow should now work end-to-end.