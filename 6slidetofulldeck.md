 Complete Fix Plan for Deck Generation Services                                                                                         │ │
│ │                                                                                                                                        │ │
│ │ ROOT CAUSE ANALYSIS                                                                                                                    │ │
│ │                                                                                                                                        │ │
│ │ 1. Stage Enum Mismatch (Line 2123)                                                                                                     │ │
│ │   - Using Stage[extracted_data.get("stage", "SERIES_A").replace(" ", "_").upper()]                                                     │ │
│ │   - The Stage enum values are lowercase (e.g., Stage.SERIES_A = "series_a")                                                            │ │
│ │   - Trying to access Stage["SERIES_A"] causes KeyError because it should be Stage.SERIES_A or lookup by value                          │ │
│ │ 2. Improper Revenue/Valuation Handling                                                                                                 │ │
│ │   - Not consistently using the _get_field_safe() helper method                                                                         │ │
│ │   - Some places directly access extracted_data.get("revenue", 0) instead of checking inferred values first                             │ │
│ │   - The IntelligentGapFiller calculates inferred_revenue and inferred_valuation for EVERY company                                      │ │
│ │ 3. Cap Table Service Error Handling                                                                                                    │ │
│ │   - Not handling when calculate_full_cap_table_history() returns None                                                                  │ │
│ │   - Missing try/catch blocks around cap table service calls                                                                            │ │
│ │ 4. ValuationResult Treated as Dict                                                                                                     │ │
│ │   - Line 2947 tries valuation_result.get('method_results') but ValuationResult is a dataclass                                          │ │
│ │   - Should access attributes directly like valuation_result.scenarios                                                                  │ │
│ │                                                                                                                                        │ │
│ │ FIXES TO IMPLEMENT                                                                                                                     │ │
│ │                                                                                                                                        │ │
│ │ Fix 1: Stage Enum Mapping (3 locations)                                                                                                │ │
│ │                                                                                                                                        │ │
│ │ Lines 2123, 2843, 2928                                                                                                                 │ │
│ │ Replace:                                                                                                                               │ │
│ │ stage=Stage[extracted_data.get("stage", "SERIES_A").replace(" ", "_").upper()],                                                        │ │
│ │ With:                                                                                                                                  │ │
│ │ stage=stage_map.get(extracted_data.get("stage", "Series A"), Stage.SERIES_A),                                                          │ │
│ │ (Use the existing stage_map dictionaries already defined above each usage)                                                             │ │
│ │                                                                                                                                        │ │
│ │ Fix 2: Revenue/Valuation Consistency (Line 2124)                                                                                       │ │
│ │                                                                                                                                        │ │
│ │ Replace:                                                                                                                               │ │
│ │ revenue=extracted_data.get("revenue", 0),                                                                                              │ │
│ │ With:                                                                                                                                  │ │
│ │ revenue=self._get_field_safe(extracted_data, "revenue", default=1_000_000),                                                            │ │
│ │                                                                                                                                        │ │
│ │ Fix 3: Cap Table Error Handling (Lines 2093, 8693, 9178, 10209)                                                                        │ │
│ │                                                                                                                                        │ │
│ │ Wrap all calculate_full_cap_table_history() calls:                                                                                     │ │
│ │ try:                                                                                                                                   │ │
│ │     cap_table_history = self.cap_table_service.calculate_full_cap_table_history(extracted_data)                                        │ │
│ │     if not cap_table_history:                                                                                                          │ │
│ │         cap_table_history = {"history": [], "ownership_evolution": {}}                                                                 │ │
│ │ except Exception as e:                                                                                                                 │ │
│ │     logger.warning(f"Cap table calculation failed: {e}")                                                                               │ │
│ │     cap_table_history = {"history": [], "ownership_evolution": {}}                                                                     │ │
│ │                                                                                                                                        │ │
│ │ Fix 4: ValuationResult Access (Find and fix the .get() call)                                                                           │ │
│ │                                                                                                                                        │ │
│ │ Search for where ValuationResult is being treated as a dict and fix to use attribute access                                            │ │
│ │                                                                                                                                        │ │
│ │ Fix 5: Ensure Inferred Values Are Used Properly                                                                                        │ │
│ │                                                                                                                                        │ │
│ │ Update all ValuationRequest creations to use _get_field_safe() for:                                                                    │ │
│ │ - revenue                                                                                                                              │ │
│ │ - valuation                                                                                                                            │ │
│ │ - growth_rate                                                                                                                          │ │
│ │ - gross_margin                                                                                                                         │ │
│ │                                                                                                                                        │ │
│ │ IMPLEMENTATION ORDER                                                                                                                   │ │
│ │                                                                                                                                        │ │
│ │ 1. Fix Stage enum usage (prevents PWERM failures)                                                                                      │ │
│ │ 2. Fix revenue/valuation to use inferred values properly                                                                               │ │
│ │ 3. Add error handling to cap table service calls                                                                                       │ │
│ │ 4. Fix ValuationResult attribute access                                                                                                │ │
│ │ 5. Test complete flow                                                                                                                  │ │
│ │                                                                                                                                        │ │
│ │ This will make all services work properly by:                                                                                          │ │
│ │ - Using the correct Stage enum values                                                                                                  │ │
│ │ - Properly utilizing the IntelligentGapFiller's calculated inferred values                                                             │ │
│ │ - Handling service failures gracefully                                                                                                 │ │
│ │ - Accessing dataclass attributes correctly                                                                                             │ │
│ ╰────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯ │
│                                                              