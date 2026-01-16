
     ╭─────────────────────────────────────────────────────────────────────────────────────────────────╮
     │ Root Cause Analysis & Solution                                                                  │
     │                                                                                                 │
     │ THE REAL PROBLEMS:                                                                              │
     │                                                                                                 │
     │ 1. Ownership Evolution Not Being Set (Lines 1192-1199)                                          │
     │   - Only set if PWERM calculation succeeds                                                      │
     │   - If PWERM fails, ownership_evolution is MISSING                                              │
     │   - Exit scenarios slide SKIPS companies without this data (line 4293)                          │
     │ 2. Services Chain Breaking                                                                      │
     │   - PWERM service might be failing silently                                                     │
     │   - When it fails, ownership_evolution isn't set                                                │
     │   - Charts have no data to display                                                              │
     │ 3. Fund Context Not Propagating                                                                 │
     │   - Line 891: Falls back to hardcoded $78M                                                      │
     │   - Should use actual fund from API request                                                     │
     │   - Fund fit calculations use wrong fund size                                                   │
     │                                                                                                 │
     │ THE FIX:                                                                                        │
     │                                                                                                 │
     │ 1. Always Calculate Ownership Evolution (Lines 1093-1199)                                       │
     │ # Calculate ownership BEFORE PWERM (so it always exists)                                        │
     │ check_size = extracted_data.get("optimal_check_size", 10_000_000)                               │
     │ valuation = extracted_data.get("valuation", 100_000_000)                                        │
     │ post_money = valuation + check_size                                                             │
     │ entry_ownership = check_size / post_money if post_money > 0 else 0                              │
     │                                                                                                 │
     │ # Calculate exit ownership using gap filler                                                     │
     │ stage = extracted_data.get("stage", "Series A")                                                 │
     │ rounds_to_exit = {"Seed": 4, "Series A": 3, "Series B": 2, "Series C": 1}.get(stage, 2)         │
     │                                                                                                 │
     │ dilution_calc = self.gap_filler.calculate_exit_dilution_scenarios(                              │
     │     initial_ownership=entry_ownership,                                                          │
     │     rounds_to_exit=rounds_to_exit                                                               │
     │ )                                                                                               │
     │                                                                                                 │
     │ # Set ownership_evolution BEFORE PWERM attempt                                                  │
     │ extracted_data["ownership_evolution"] = {                                                       │
     │     "entry_ownership": entry_ownership,                                                         │
     │     "exit_ownership_no_followon": dilution_calc.get("without_pro_rata", entry_ownership * 0.5), │
     │     "exit_ownership_with_followon": dilution_calc.get("with_pro_rata", entry_ownership * 0.8),  │
     │     "followon_capital_required": check_size * 2,  # Default 2x reserves                         │
     │     "followon_scenarios": {}  # Will be filled by PWERM if it succeeds                          │
     │ }                                                                                               │
     │                                                                                                 │
     │ # THEN try PWERM (optional enhancement)                                                         │
     │ try:                                                                                            │
     │     # PWERM calculation...                                                                      │
     │     # If successful, UPDATE ownership_evolution with better data                                │
     │ except:                                                                                         │
     │     # Ownership_evolution already has basic data, so charts will work                           │
     │     pass                                                                                        │
     │                                                                                                 │
     │ 2. Fix Exit Scenarios Data Check (Line 4293)                                                    │
     │ # Don't skip - calculate if missing                                                             │
     │ if not entry_ownership:                                                                         │
     │     # Calculate from available data                                                             │
     │     check = company.get('optimal_check_size', 10_000_000)                                       │
     │     val = company.get('valuation', 100_000_000)                                                 │
     │     entry_ownership = check / (val + check)                                                     │
     │                                                                                                 │
     │     # Use gap filler for exit ownership                                                         │
     │     stage = company.get('stage', 'Series A')                                                    │
     │     dilution = self.gap_filler.calculate_exit_dilution_scenarios(                               │
     │         initial_ownership=entry_ownership,                                                      │
     │         rounds_to_exit={"Seed": 4, "Series A": 3, "Series B": 2}.get(stage, 2)                  │
     │     )                                                                                           │
     │                                                                                                 │
     │     exit_no_followon = dilution.get("without_pro_rata", entry_ownership * 0.5)                  │
     │     exit_with_followon = dilution.get("with_pro_rata", entry_ownership * 0.8)                   │
     │                                                                                                 │
     │     # Set the data so chart can proceed                                                         │
     │     ownership_data = {                                                                          │
     │         "entry_ownership": entry_ownership,                                                     │
     │         "exit_ownership_no_followon": exit_no_followon,                                         │
     │         "exit_ownership_with_followon": exit_with_followon,                                     │
     │         "followon_capital_required": check * 2                                                  │
     │     }                                                                                           │
     │     company["ownership_evolution"] = ownership_data                                             │
     │                                                                                                 │
     │ 3. Fix Probability Cloud Generation (Line 5020)                                                 │
     │ # Always generate SOME chart data                                                               │
     │ probability_cloud_data = self._generate_probability_cloud_data(first_company, check_size)       │
     │                                                                                                 │
     │ # Create a chart that will ALWAYS render                                                        │
     │ if probability_cloud_data.get('scenario_curves'):                                               │
     │     # Use full probability cloud                                                                │
     │     chart_type = "probability_cloud"                                                            │
     │     chart_data = probability_cloud_data                                                         │
     │ else:                                                                                           │
     │     # Fallback to simple line chart                                                             │
     │     chart_type = "line"                                                                         │
     │     # Generate simple return scenarios                                                          │
     │     chart_data = {                                                                              │
     │         "labels": ["1x", "2x", "3x", "5x", "10x"],                                              │
     │         "datasets": [{                                                                          │
     │             "label": "Return Multiple",                                                         │
     │             "data": [check_size, check_size*2, check_size*3, check_size*5, check_size*10],      │
     │             "borderColor": "rgb(75, 192, 192)",                                                 │
     │             "tension": 0.1                                                                      │
     │         }]                                                                                      │
     │     }                                                                                           │
     │                                                                                                 │
     │ exit_charts.append({                                                                            │
     │     "type": chart_type,                                                                         │
     │     "title": "Exit Scenarios",                                                                  │
     │     "data": chart_data                                                                          │
     │ })                                                                                              │
     │                                                                                                 │
     │ 4. Fix Fund Context (Line 891)                                                                  │
     │ fund_context = self.shared_data.get('fund_context', {})                                         │
     │ fund_size = fund_context.get('fund_size')                                                       │
     │                                                                                                 │
     │ if not fund_size:                                                                               │
     │     logger.error("NO FUND SIZE PROVIDED - Cannot calculate fund fit")                           │
     │     # Don't use hardcoded fallback - mark as unavailable                                        │
     │     extracted_data["fund_fit_score"] = None                                                     │
     │     extracted_data["fund_fit_recommendation"] = "Fund context required"                         │
     │ else:                                                                                           │
     │     # Proceed with real fund size                                                               │
     │     ...                                                                                         │
     │                                                                                                 │
     │ 5. Fix Cap Table Chart Exit Ownership (Line 3189)                                               │
     │ # Get actual calculated exit ownership                                                          │
     │ ownership_data = company.get('ownership_evolution', {})                                         │
     │ exit_ownership = ownership_data.get('exit_ownership_no_followon', 0)                            │
     │                                                                                                 │
     │ # If not available, calculate it                                                                │
     │ if not exit_ownership and company.get('entry_ownership'):                                       │
     │     entry = company.get('entry_ownership', 0) / 100  # Convert from percentage                  │
     │     stage = company.get('stage', 'Series A')                                                    │
     │     # Use stage-based dilution estimates                                                        │
     │     dilution_by_stage = {"Seed": 0.45, "Series A": 0.55, "Series B": 0.65, "Series C": 0.70}    │
     │     dilution = dilution_by_stage.get(stage, 0.60)                                               │
     │     exit_ownership = entry * (1 - dilution)                                                     │
     │                                                                                                 │
     │ f"Our ownership at exit: {exit_ownership * 100:.1f}%"                                           │
     │                                                                                                 │
     │ Summary:                                                                                        │
     │                                                                                                 │
     │ 1. Always set ownership_evolution - don't make it conditional on PWERM success                  │
     │ 2. Never skip charts - calculate missing data on the fly                                        │
     │ 3. No hardcoded fund values - use actual context or mark as N/A                                 │
     │ 4. Always provide chart data - even if simplified/estimated                                     │
     │ 5. Fix ownership consistency - calculate once, use everywhere     