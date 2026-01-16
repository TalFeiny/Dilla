Code-Level Fix Plan for Deck Generation (Score: 56/100 → 85+/100)                                                                      │ │
│ │                                                                                                                                        │ │
│ │ What's Already Fixed (per pluto.md)                                                                                                    │ │
│ │                                                                                                                                        │ │
│ │ ✅ Fund context uses $260M/$109M remaining                                                                                              │ │
│ │ ✅ Sankey tracks actual ownership per round                                                                                             │ │
│ │ ✅ Pre/post money formula fixed (post - investment = pre)                                                                               │ │
│ │ ✅ Uses IntelligentGapFiller's quality adjustments                                                                                      │ │
│ │ ✅ Neo noir styling partially applied                                                                                                   │ │
│ │                                                                                                                                        │ │
│ │ Critical Code Fixes Required                                                                                                           │ │
│ │                                                                                                                                        │ │
│ │ 1. Slide 2 - Executive Summary (Lines 3920-3927)                                                                                       │ │
│ │                                                                                                                                        │ │
│ │ Problem: Shows avg/combined valuation, both companies have 0.7x return and 150% growth                                                 │ │
│ │ Code Location: unified_mcp_orchestrator.py line 3925 _generate_executive_summary_bullets()                                             │ │
│ │ Fix:                                                                                                                                   │ │
│ │ - Remove avg/combined valuation calculations                                                                                           │ │
│ │ - Show individual company metrics with different growth rates                                                                          │ │
│ │ - Use actual extracted growth_rate from each company's data                                                                            │ │
│ │                                                                                                                                        │ │
│ │ 2. Slide 3/4 - Company Overview (Lines 3930-4019)                                                                                      │ │
│ │                                                                                                                                        │ │
│ │ Problem: Revenue multiple calculation shows same for both, employee counts too high                                                    │ │
│ │ Code Locations:                                                                                                                        │ │
│ │ - Line 3976-3984: Revenue multiple adds fake variance but still similar                                                                │ │
│ │ - Line 4030: Uses inferred_team_size which is way too high                                                                             │ │
│ │ Fix:                                                                                                                                   │ │
│ │ - Use actual revenue multiples without artificial adjustment                                                                           │ │
│ │ - Fix team size inference in intelligent_gap_filler.py line 1135 (reduce from 7% to 2.5% monthly growth)                               │ │
│ │                                                                                                                                        │ │
│ │ 3. Slide 5 - Path to $100M (Lines 4116-4320)                                                                                           │ │
│ │                                                                                                                                        │ │
│ │ Problem: Y-axis not in $M format, numbers cut off                                                                                      │ │
│ │ Code Location: Line 4315-4320 chart options                                                                                            │ │
│ │ Fix:                                                                                                                                   │ │
│ │ scales: {                                                                                                                              │ │
│ │   y: {                                                                                                                                 │ │
│ │     type: "linear",                                                                                                                    │ │
│ │     ticks: {                                                                                                                           │ │
│ │       callback: function(value) {                                                                                                      │ │
│ │         return '$' + value + 'M';                                                                                                      │ │
│ │       }                                                                                                                                │ │
│ │     }                                                                                                                                  │ │
│ │   }                                                                                                                                    │ │
│ │ }                                                                                                                                      │ │
│ │                                                                                                                                        │ │
│ │ 4. Slide 6 - Missing Data                                                                                                              │ │
│ │                                                                                                                                        │ │
│ │ Problem: No TAM or pricing for company                                                                                                 │ │
│ │ Code Location: Business analysis slide generation missing TAM data                                                                     │ │
│ │ Fix: Add TAM data from market_size field in extracted data                                                                             │ │
│ │                                                                                                                                        │ │
│ │ 5. Slide 7 - Market Dynamics                                                                                                           │ │
│ │                                                                                                                                        │ │
│ │ Problem: Empty sections, no ACV rationale, wrong gross margin                                                                          │ │
│ │ Code Location: Need to find where this slide is generated                                                                              │ │
│ │ Fix:                                                                                                                                   │ │
│ │ - Remove empty field displays                                                                                                          │ │
│ │ - Add ACV calculation logic                                                                                                            │ │
│ │ - Use actual gross margin from inferred_gross_margin                                                                                   │ │
│ │                                                                                                                                        │ │
│ │ 6. Slide 8 - TAM Analysis                                                                                                              │ │
│ │                                                                                                                                        │ │
│ │ Problem: No evidence/citations for numbers                                                                                             │ │
│ │ Code Location: TAM slide generation around line 4863                                                                                   │ │
│ │ Fix: Add citation references using citation_manager service                                                                            │ │
│ │                                                                                                                                        │ │
│ │ 7. Slide 9 - Cap Table (Lines 5193-5296)                                                                                               │ │
│ │                                                                                                                                        │ │
│ │ Problem: Not forward-looking, doesn't show our ownership                                                                               │ │
│ │ Code Location: Line 5270 shows post-investment but not properly                                                                        │ │
│ │ Fix:                                                                                                                                   │ │
│ │ - Add our proposed investment to cap table                                                                                             │ │
│ │ - Show dilution through future rounds                                                                                                  │ │
│ │                                                                                                                                        │ │
│ │ 8. Slide 11 - Sankey Error                                                                                                             │ │
│ │                                                                                                                                        │ │
│ │ Problem: Sankey chart not rendering                                                                                                    │ │
│ │ Code Location: deck_export_service.py Sankey generation                                                                                │ │
│ │ Fix: Check D3.js implementation, add error handling                                                                                    │ │
│ │                                                                                                                                        │ │
│ │ 9. Slide 12 - Probability Cloud (Lines 6557-6939)                                                                                      │ │
│ │                                                                                                                                        │ │
│ │ Problem: "Invalid chart structure", too much on one slide                                                                              │ │
│ │ Code Location: Line 6939 exit_scenarios_comprehensive                                                                                  │ │
│ │ Fix: Split into two slides - one for probability cloud, one for waterfall                                                              │ │
│ │                                                                                                                                        │ │
│ │ 10. Slide 13 - DPI Analysis                                                                                                            │ │
│ │                                                                                                                                        │ │
│ │ Problem: Not using actual fund context                                                                                                 │ │
│ │ Code Location: Fund return impact slide generation                                                                                     │ │
│ │ Fix: Use $234M fund with $125M deployed (not $260M/$109M)                                                                              │ │
│ │                                                                                                                                        │ │
│ │ 11. Slide 14 - Follow-on Strategy                                                                                                      │ │
│ │                                                                                                                                        │ │
│ │ Problem: Hardcoded generic text                                                                                                        │ │
│ │ Code Location: Follow-on strategy slide generation                                                                                     │ │
│ │ Fix: Use actual calculated follow-on scenarios from lines 1504-1516                                                                    │ │
│ │                                                                                                                                        │ │
│ │ 12. Slide 16 - Citations (Lines 8026-8087)                                                                                             │ │
│ │                                                                                                                                        │ │
│ │ Problem: Empty citation list                                                                                                           │ │
│ │ Code Location: Line 8027 gets citations from citation_manager                                                                          │ │
│ │ Fix: Ensure citation_manager is populated during data extraction                                                                       │ │
│ │                                                                                                                                        │ │
│ │ File-by-File Changes                                                                                                                   │ │
│ │                                                                                                                                        │ │
│ │ unified_mcp_orchestrator.py                                                                                                            │ │
│ │                                                                                                                                        │ │
│ │ 1. Line 3925: Fix executive summary to show individual metrics                                                                         │ │
│ │ 2. Line 3976-3984: Remove artificial revenue multiple variance                                                                         │ │
│ │ 3. Line 4138-4166: Ensure different growth rates per company                                                                           │ │
│ │ 4. Line 4315-4320: Fix Y-axis formatting for Path to $100M                                                                             │ │
│ │ 5. Line 5270: Add forward-looking cap table with our investment                                                                        │ │
│ │ 6. Line 6939: Split probability cloud into separate slides                                                                             │ │
│ │ 7. Line 8027: Ensure citations are captured and displayed                                                                              │ │
│ │                                                                                                                                        │ │
│ │ intelligent_gap_filler.py                                                                                                              │ │
│ │                                                                                                                                        │ │
│ │ 1. Line 1135: Change team_growth_rate from 0.07 to 0.025                                                                               │ │
│ │ 2. Line 266: Fix base growth rate to avoid all companies getting 1.5                                                                   │ │
│ │                                                                                                                                        │ │
│ │ deck_export_service.py                                                                                                                 │ │
│ │                                                                                                                                        │ │
│ │ 1. Fix Sankey chart rendering in _add_cap_table_slide()                                                                                │ │
│ │ 2. Add proper citation formatting with [1][2][3] style                                                                                 │ │
│ │ 3. Fix probability cloud chart structure                                                                                               │ │
│ │                                                                                                                                        │ │
│ │ Success Metrics                                                                                                                        │ │
│ │                                                                                                                                        │ │
│ │ - No duplicate values between companies                                                                                                │ │
│ │ - All charts render without errors                                                                                                     │ │
│ │ - Citations with clickable URLs                                                                                                        │ │
│ │ - Professional neo noir styling throughout                                                                                             │ │
│ │ - Meaningful insights on every slide                                                                                                   │ │
│ │ - Score improvement to 85+/100                                                                                                         │ │
│ ╰────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯ │
│                                                                                                                                            │
│ Would you like to proceed?                                                                                                                 │
│                                                                                                                                            │
│ ❯ 1. Yes, and auto-accept edits                                                                                                            │
│   2. Yes, and manually approve edits                                                                                                       │
│   3. No, keep planning                                                                                                                     │
│                                                   