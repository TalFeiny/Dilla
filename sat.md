  The deck generation follows this order but stops early:
  1. ✅ Title Slide
  2. ✅ Executive Summary
  3. ✅ Portfolio Narrative (if 2+ companies)
  4. ✅ Scoring Matrix (if 2+ companies)
  5. ✅ Company Overview & Financials
  6. ✅ Founder & Team Analysis
  7. ✅ Path to $100M ARR
  8. ✅ Business Analysis
  9. ❌ Competitive Landscape - FAILS HERE
  10. ❌ Key Metrics Comparison
  11. ❌ TAM Pincer Analysis
  12. ❌ Cap Table Evolution
  13. ❌ Cap Table Comparison
  14. ❌ Probability Cloud
  15. ❌ Exit Scenarios (PWERM)
  16. ❌ Fund DPI Impact
  17. ❌ Follow-on Strategy
  18. ❌ Investment Recommendations
  19. ❌ Citations

╭────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Ready to code?                                                                                                                             │
│                                                                                                                                            │
│ Here is Claude's plan:                                                                                                                     │
│ ╭────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮ │
│ │ Fix Plan for Complete Deck Generation                                                                                                  │ │
│ │                                                                                                                                        │ │
│ │ 1. Fix Cap Table Generation Error (Lines 9064-9119)                                                                                    │ │
│ │                                                                                                                                        │ │
│ │ - Add null checks for funding_rounds before iteration                                                                                  │ │
│ │ - Ensure pre_post_cap_table service returns valid data                                                                                 │ │
│ │ - Add try-catch blocks around cap table slide generation                                                                               │ │
│ │                                                                                                                                        │ │
│ │ 2. Fix Competitive Landscape Generation (Lines 8125-8129)                                                                              │ │
│ │                                                                                                                                        │ │
│ │ - Add conditional check: only generate if 2+ companies exist                                                                           │ │
│ │ - Handle single company case gracefully                                                                                                │ │
│ │ - Prevent None return from breaking deck flow                                                                                          │ │
│ │                                                                                                                                        │ │
│ │ 3. Fix Decimal Operations (Lines 1400-1425)                                                                                            │ │
│ │                                                                                                                                        │ │
│ │ - Replace direct decimal operations with safe wrappers                                                                                 │ │
│ │ - Use _safe_get_value() for all numeric operations                                                                                     │ │
│ │ - Add validation before division operations                                                                                            │ │
│ │                                                                                                                                        │ │
│ │ 4. Add Error Recovery (Lines 8130-12000)                                                                                               │ │
│ │                                                                                                                                        │ │
│ │ - Wrap each slide generation in try-catch                                                                                              │ │
│ │ - Continue generating remaining slides even if one fails                                                                               │ │
│ │ - Log specific errors but don't stop entire deck                                                                                       │ │
│ │                                                                                                                                        │ │
│ │ 5. Fix Citations Bar Issue                                                                                                             │ │
│ │                                                                                                                                        │ │
│ │ - Remove duplicate citations rendering in deck-agent page                                                                              │ │
│ │ - Ensure citations only appear in dedicated slide                                                                                      │ │
│ │                                                                                                                                        │ │
│ │ 6. Implementation Steps                                                                                                                │ │
│ │                                                                                                                                        │ │
│ │ 1. Add defensive null checks throughout slide generation                                                                               │ │
│ │ 2. Wrap slide generations in try-catch blocks                                                                                          │ │
│ │ 3. Fix cap table NoneType iteration error                                                                                              │ │
│ │ 4. Make competitive landscape optional for single company                                                                              │ │
│ │ 5. Test with both single and multiple companies                                                                                        │ │
│ │ 6. Ensure all 16-18 slides generate successfully                                                                                       │ │
│ ╰────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯ │
│                                                                                                                                            │
│ Would you like to proceed?                                                                                                                 │
│                                                                                                                                            │
│ ❯ 1. Yes, and auto-accept edits                                                                                                            │
│   2. Yes, and manually approve edits                                                                                                       │
│   3. No, keep planning                                                                                                                     │
│lso no pdf
                                              