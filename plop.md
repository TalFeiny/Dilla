 Fix Plan for Market Sizing & Investment Case System                                                                   │ │
│ │                                                                                                                       │ │
│ │ Issues Identified                                                                                                     │ │
│ │                                                                                                                       │ │
│ │ 1. TAM using labor pool ($18.7T) instead of software market - Not using the bottom-up or segment TAM methods          │ │
│ │ 2. Missing cap table generation - Even though funding data exists                                                     │ │
│ │ 3. Variable errors - upside_growth undefined, should be actual_upside_growth                                          │ │
│ │ 4. No business model categorization - AI-first companies not properly categorized                                     │ │
│ │ 5. Return analysis incomplete - Due to undefined variables                                                            │ │
│ │                                                                                                                       │ │
│ │ Fixes to Implement                                                                                                    │ │
│ │                                                                                                                       │ │
│ │ 1. Fix TAM Calculation Priority (intelligent_gap_filler.py)                                                           │ │
│ │                                                                                                                       │ │
│ │ - Ensure primary_tam uses bottom-up or segment TAM, NOT labor pool                                                    │ │
│ │ - Add fallback logic: bottom-up → segment research → capped labor pool (max $500B)                                    │ │
│ │ - Fix market sizing to search for "{vertical} software market size" without "TAM" keyword                             │ │
│ │                                                                                                                       │ │
│ │ 2. Fix Variable Errors (intelligent_gap_filler.py)                                                                    │ │
│ │                                                                                                                       │ │
│ │ - Change upside_growth to actual_upside_growth in scenarios['upside']                                                 │ │
│ │ - Ensure all final_ownership variables use correct variants (base/upside/downside)                                    │ │
│ │ - Add safety checks for division by zero in ownership calculations                                                    │ │
│ │                                                                                                                       │ │
│ │ 3. Fix Cap Table Generation (unified_mcp_orchestrator.py)                                                             │ │
│ │                                                                                                                       │ │
│ │ - Ensure funding_rounds are passed to ValuationEngine even for single rounds                                          │ │
│ │ - Handle bootstrapped companies (no funding = organic growth scenario)                                                │ │
│ │ - Fix investors KeyError by using .get() instead of direct access                                                     │ │
│ │                                                                                                                       │ │
│ │ 4. Improve Business Model Detection (unified_mcp_orchestrator.py)                                                     │ │
│ │                                                                                                                       │ │
│ │ - Add AI-first detection for companies like ArtificialSocieties                                                       │ │
│ │ - Check for AI/ML keywords in description before defaulting to SaaS                                                   │ │
│ │ - Properly categorize: ai_first → roll_up → saas → marketplace → services                                             │ │
│ │                                                                                                                       │ │
│ │ 5. Add Market Search Execution (intelligent_gap_filler.py)                                                            │ │
│ │                                                                                                                       │ │
│ │ - Actually call search_for_market_tam() when segment TAM is needed                                                    │ │
│ │ - Add citation tracking for market data sources                                                                       │ │
│ │ - Log when using bottom-up vs researched TAM                                                                          │ │
│ │                                                                                                                       │ │
│ │ Testing Strategy                                                                                                      │ │
│ │                                                                                                                       │ │
│ │ - Test with @ArtificialSocieties again to verify TAM < $100B                                                          │ │
│ │ - Verify cap table shows $5.3M seed round                                                                             │ │
│ │ - Check investment scenarios show realistic returns                                                                   │ │
│ │ - Ensure citations include market research sources                                                                    │ │
│ ╰──────────────────────────────────────────────