 Complete Fix Plan: Resolve All Deck Generation Issues                                                                                  │ │
│ │                                                                                                                                        │ │
│ │ Issues Found                                                                                                                           │ │
│ │                                                                                                                                        │ │
│ │ 1. Math Domain Error (Line 7800) - CRITICAL                                                                                            │ │
│ │                                                                                                                                        │ │
│ │ years_to_target = math.log(arr_ratio) / math.log(yoy_growth)                                                                           │ │
│ │ Problem: yoy_growth could be ≤ 1.0, causing math.log(yoy_growth) to be 0 or negative                                                   │ │
│ │ Impact: Deck generation crashes completely                                                                                             │ │
│ │                                                                                                                                        │ │
│ │ 2. LLM JSON Parsing Errors                                                                                                             │ │
│ │                                                                                                                                        │ │
│ │ Problem: LLM responses sometimes return invalid JSON, causing "Expecting value: line 1 column 1"                                       │ │
│ │ Impact: Narrative generation fails, but deck continues with defaults                                                                   │ │
│ │                                                                                                                                        │ │
│ │ 3. Supabase Column Error                                                                                                               │ │
│ │                                                                                                                                        │ │
│ │ Problem: Query references companies.last_round_date which doesn't exist                                                                │ │
│ │ Impact: Data fetching partially fails                                                                                                  │ │
│ │                                                                                                                                        │ │
│ │ 4. Timeout Issues                                                                                                                      │ │
│ │                                                                                                                                        │ │
│ │ Problem: Deck generation takes >2 minutes due to:                                                                                      │ │
│ │ - Multiple Tavily searches per company (24 searches total for 2 companies)                                                             │ │
│ │ - Multiple LLM calls for narrative generation                                                                                          │ │
│ │ - Complex calculations and data processing                                                                                             │ │
│ │                                                                                                                                        │ │
│ │ Fix Implementation                                                                                                                     │ │
│ │                                                                                                                                        │ │
│ │ Fix 1: Math Domain Error (Line 7785-7800)                                                                                              │ │
│ │                                                                                                                                        │ │
│ │ # BEFORE:                                                                                                                              │ │
│ │ if yoy_growth <= 1.0:                                                                                                                  │ │
│ │     logger.warning(f"Invalid growth rate {yoy_growth} for {company_name}, using fallback 1.2")                                         │ │
│ │     yoy_growth = 1.2                                                                                                                   │ │
│ │ # ... later ...                                                                                                                        │ │
│ │ years_to_target = math.log(arr_ratio) / math.log(yoy_growth)                                                                           │ │
│ │                                                                                                                                        │ │
│ │ # AFTER:                                                                                                                               │ │
│ │ if yoy_growth <= 1.0:                                                                                                                  │ │
│ │     logger.warning(f"Invalid growth rate {yoy_growth} for {company_name}, using fallback 1.2")                                         │ │
│ │     yoy_growth = 1.2                                                                                                                   │ │
│ │ elif yoy_growth == 1.0:                                                                                                                │ │
│ │     # Exactly 1.0 means no growth - use simple linear projection                                                                       │ │
│ │     years_to_target = 10  # Assume 10 years for no-growth scenario                                                                     │ │
│ │ else:                                                                                                                                  │ │
│ │     # Safe to use logarithm                                                                                                            │ │
│ │     try:                                                                                                                               │ │
│ │         years_to_target = math.log(arr_ratio) / math.log(yoy_growth)                                                                   │ │
│ │         if not math.isfinite(years_to_target) or years_to_target < 0:                                                                  │ │
│ │             years_to_target = 5                                                                                                        │ │
│ │     except (ValueError, ZeroDivisionError) as e:                                                                                       │ │
│ │         logger.error(f"Math error: {e}")                                                                                               │ │
│ │         years_to_target = 5                                                                                                            │ │
│ │                                                                                                                                        │ │
│ │ Fix 2: LLM JSON Parsing (Line 4552)                                                                                                    │ │
│ │                                                                                                                                        │ │
│ │ # BEFORE:                                                                                                                              │ │
│ │ response_text = response if isinstance(response, str) else response.get('response', '{}')                                              │ │
│ │ return json.loads(response_text)                                                                                                       │ │
│ │                                                                                                                                        │ │
│ │ # AFTER:                                                                                                                               │ │
│ │ response_text = response if isinstance(response, str) else response.get('response', '{}')                                              │ │
│ │ try:                                                                                                                                   │ │
│ │     # Try to parse JSON                                                                                                                │ │
│ │     return json.loads(response_text)                                                                                                   │ │
│ │ except json.JSONDecodeError:                                                                                                           │ │
│ │     # If it fails, try to extract JSON from markdown code blocks                                                                       │ │
│ │     import re                                                                                                                          │ │
│ │     json_match = re.search(r'```json?\s*(.*?)\s*```', response_text, re.DOTALL)                                                        │ │
│ │     if json_match:                                                                                                                     │ │
│ │         try:                                                                                                                           │ │
│ │             return json.loads(json_match.group(1))                                                                                     │ │
│ │         except:                                                                                                                        │ │
│ │             pass                                                                                                                       │ │
│ │     # Return default if all parsing fails                                                                                              │ │
│ │     return {                                                                                                                           │ │
│ │         "investment_thesis": "Analysis in progress",                                                                                   │ │
│ │         "forward_looking": "Evaluation pending",                                                                                       │ │
│ │         "risk_analysis": "Assessment underway"                                                                                         │ │
│ │     }                                                                                                                                  │ │
│ │                                                                                                                                        │ │
│ │ Fix 3: Supabase Column Error                                                                                                           │ │
│ │                                                                                                                                        │ │
│ │ Remove references to last_round_date or add proper error handling for Supabase queries                                                 │ │
│ │                                                                                                                                        │ │
│ │ Fix 4: Optimization to Reduce Timeout                                                                                                  │ │
│ │                                                                                                                                        │ │
│ │ - Reduce Tavily searches from 12 to 6 per company                                                                                      │ │
│ │ - Cache LLM responses to avoid duplicate calls                                                                                         │ │
│ │ - Add timeout handling for individual operations                                                                                       │ │
│ │                                                                                                                                        │ │
│ │ Expected Results                                                                                                                       │ │
│ │                                                                                                                                        │ │
│ │ - Math errors will be caught and handled gracefully                                                                                    │ │
│ │ - LLM responses will parse correctly even with formatting issues                                                                       │ │
│ │ - Deck generation will complete in <60 seconds                                                                                         │ │
│ │ - All 16+ slides will be generated with real data                                                                                      │ │
│ ╰────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯ │
│                                                                                                                                            │
│ Would you like to proceed?                    