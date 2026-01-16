 Root Cause Analysis & Fix Plan                                                                            │
     │                                                                                                           │
     │ THE REAL PROBLEMS:                                                                                        │
     │                                                                                                           │
     │ 1. Missing key_metrics Initialization                                                                     │
     │   - Company data extraction NEVER creates a key_metrics dict                                              │
     │   - Gross margin is set directly on company object (line 810)                                             │
     │   - Other skills expect company.get("key_metrics", {}) but key_metrics is None                            │
     │   - Fix: Initialize key_metrics dict in company data extraction                                           │
     │ 2. Exit Modeling Error Propagation                                                                        │
     │   - When ValuationEngineService fails, it raises an exception (line 3340)                                 │
     │   - This prevents the scenarios dict from being created                                                   │
     │   - Subsequent code that uses scenarios then fails                                                        │
     │   - Fix: Handle ValuationEngineService errors gracefully, create fallback scenarios                       │
     │ 3. No Error Isolation in Skill Chain                                                                      │
     │   - When one skill fails, it corrupts the entire pipeline                                                 │
     │   - Skills don't handle missing/invalid data from previous skills                                         │
     │   - Fix: Each skill should validate inputs and provide defaults                                           │
     │                                                                                                           │
     │ ACTUAL FIXES NEEDED:                                                                                      │
     │                                                                                                           │
     │ 1. Initialize key_metrics dict (line ~700 in _execute_company_fetch):                                     │
     │ extracted_data["key_metrics"] = {                                                                         │
     │     "gross_margin": extracted_data.get("gross_margin", 0.7),                                              │
     │     "burn_rate": extracted_data.get("burn_rate"),                                                         │
     │     "runway_months": extracted_data.get("runway_months"),                                                 │
     │     "ltv_cac_ratio": extracted_data.get("ltv_cac_ratio", 3.0)                                             │
     │ }                                                                                                         │
     │ 2. Handle ValuationEngineService failures (line 3337-3340):                                               │
     │   - Don't raise, create fallback scenarios instead                                                        │
     │   - Use simple multiplier-based scenarios if PWERM fails                                                  │
     │ 3. Add defensive checks in deal comparison (line 1290):                                                   │
     │   - Check if key_metrics exists before accessing                                                          │
     │   - Provide sensible defaults                                                                             │
     │                                                                                                           │
     │ These are structural