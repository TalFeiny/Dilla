  The Problem:

  We're trying to use projected_funding_path and projected_liq_pref_y3 but these fields don't actually exist in any
  service output! They would need to come from:

  1. PrePostCapTable service - which models ownership evolution through rounds
  2. ValuationEngineService - which has PWERM calculations
  3. IntelligentGapFiller - which infers missing metrics

  But we're not actually calling these services for future funding projections.

  What We Should Do:

  Instead of hardcoding or guessing, we should:
  1. Use the PrePostCapTable service to model future funding rounds
  2. Use the actual scenarios data that already includes dilution
  3. Use the waterfall_results that already exist
  4. Stop trying to access fields that don't exist

  The scenario data from the exit-modeler already factors in dilution and future rounds - we don't need to calculate it
  again. We should just use what's there!

╭───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ Ready to code?                                                                                                            │
│                                                                                                                           │
│ Here is Claude's plan:                                                                                                    │
│ ╭───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮ │
│ │ Fix the Scenario Analysis slide to use only actual data that exists:                                                  │ │
│ │                                                                                                                       │ │
│ │ 1. Remove references to non-existent fields like projected_funding_path and projected_liq_pref_y3                     │ │
│ │ 2. Use the actual scenario data from exit-modeler which already includes:                                             │ │
│ │   - Dilution-adjusted proceeds (our_proceeds)                                                                         │ │
│ │   - Fund-level DPI contribution (dpi_contribution)                                                                    │ │
│ │   - IRR calculations (irr)                                                                                            │ │
│ │ 3. For the liquidation preference line, either:                                                                       │ │
│ │   - Keep it static at current total_funding                                                                           │ │
│ │   - Or call PrePostCapTable service to get actual projections                                                         │ │
│ │ 4. Clean up the chart to only show data we actually have                                                              │ │
│ ╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯ │
│                                                                                                                           │
│ Would you like to proceed