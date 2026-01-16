Complete Plan: Remove ALL Hardcoded Values                                                                            │ │
│ │                                                                                                                       │ │
│ │ Every Hardcoded Value to Fix                                                                                          │ │
│ │                                                                                                                       │ │
│ │ 1. TAM/Market Data (Lines 1241-1250)                                                                                  │ │
│ │                                                                                                                       │ │
│ │ # DELETE hardcoded tam_by_sector                                                                                      │ │
│ │ # REPLACE with:                                                                                                       │ │
│ │ market_data = company.get('market_size', {})  # From IntelligentGapFiller                                             │ │
│ │ tam = market_data.get('tam', company.get('tam', 0))                                                                   │ │
│ │ sam = market_data.get('sam', company.get('sam', 0))                                                                   │ │
│ │ som = market_data.get('som', company.get('som', 0))                                                                   │ │
│ │ labor_tam = market_data.get('labor_tam', 0)                                                                           │ │
│ │                                                                                                                       │ │
│ │ 2. Customer Segmentation (Lines 2144-2158)                                                                            │ │
│ │                                                                                                                       │ │
│ │ # REMOVE revenue-based defaults                                                                                       │ │
│ │ who_they_sell_to = company.get('who_they_sell_to', '')                                                                │ │
│ │ if not who_they_sell_to:                                                                                              │ │
│ │     customers = company.get('customers', [])                                                                          │ │
│ │     if customers:                                                                                                     │ │
│ │         who_they_sell_to = ', '.join(customers[:3])                                                                   │ │
│ │     else:                                                                                                             │ │
│ │         who_they_sell_to = ""  # Empty, don't guess                                                                   │ │
│ │                                                                                                                       │ │
│ │ 3. All Valuation Defaults                                                                                             │ │
│ │                                                                                                                       │ │
│ │ Replace EVERY instance of:                                                                                            │ │
│ │ - 100_000_000 → company.get('valuation', company.get('inferred_valuation', 0))                                        │ │
│ │ - 1_000_000 → company.get('revenue', company.get('inferred_revenue', 0))                                              │ │
│ │ - 20_000_000 → company.get('total_funding', company.get('inferred_total_funding', 0))                                 │ │
│ │                                                                                                                       │ │
│ │ 4. Check Sizes (Lines 3032-3033, etc)                                                                                 │ │
│ │                                                                                                                       │ │
│ │ # WRONG: f"Our $10M investment..."                                                                                    │ │
│ │ # RIGHT:                                                                                                              │ │
│ │ check_size = company.get('optimal_check_size', 0)                                                                     │ │
│ │ f"Our ${check_size/1e6:.1f}M investment..."                                                                           │ │
│ │                                                                                                                       │ │
│ │ 5. Moat Scoring (Lines 2432-2474)                                                                                     │ │
│ │                                                                                                                       │ │
│ │ # DELETE keyword-based scoring                                                                                        │ │
│ │ # CREATE semantic scoring:                                                                                            │ │
│ │ moat_scores = {                                                                                                       │ │
│ │     'network_effects': 0,                                                                                             │ │
│ │     'switching_costs': 0,                                                                                             │ │
│ │     'data_advantages': 0,                                                                                             │ │
│ │     'economies_of_scale': 0,                                                                                          │ │
│ │     'brand_reputation': 0,                                                                                            │ │
│ │     'regulatory_moat': 0                                                                                              │ │
│ │ }                                                                                                                     │ │
│ │                                                                                                                       │ │
│ │ # Analyze based on actual business understanding                                                                      │ │
│ │ business_desc = company.get('product_description', '')                                                                │ │
│ │ customers = company.get('who_they_sell_to', '')                                                                       │ │
│ │                                                                                                                       │ │
│ │ # Network effects: look for marketplace, platform dynamics                                                            │ │
│ │ if any(indicator in business_desc.lower() for indicator in ['both sides', 'marketplace', 'connects buyers and         │ │
│ │ sellers']):                                                                                                           │ │
│ │     moat_scores['network_effects'] = 7                                                                                │ │
│ │                                                                                                                       │ │
│ │ # Data advantages: look for proprietary data                                                                          │ │
│ │ if any(indicator in business_desc.lower() for indicator in ['proprietary data', 'unique dataset', 'training data']):  │ │
│ │     moat_scores['data_advantages'] = 7                                                                                │ │
│ │                                                                                                                       │ │
│ │ # Scale advantages based on relative position                                                                         │ │
│ │ stage = company.get('stage', '')                                                                                      │ │
│ │ if stage in ['Series C', 'Series D', 'Series E']:                                                                     │ │
│ │     moat_scores['economies_of_scale'] = 6                                                                             │ │
│ │                                                                                                                       │ │
│ │ 6. Revenue Thresholds (Lines 1514-1534, 2153-2158, 2467-2474)                                                         │ │
│ │                                                                                                                       │ │
│ │ # DELETE all absolute thresholds like:                                                                                │ │
│ │ # if revenue > 50_000_000:                                                                                            │ │
│ │ # if revenue > 10_000_000:                                                                                            │ │
│ │                                                                                                                       │ │
│ │ # REPLACE with stage-relative:                                                                                        │ │
│ │ stage = company.get('stage', 'Series A')                                                                              │ │
│ │ benchmarks = self.gap_filler.benchmarks.get(stage, {})                                                                │ │
│ │ revenue_median = benchmarks.get('revenue_median', 0)                                                                  │ │
│ │                                                                                                                       │ │
│ │ if revenue > revenue_median * 2:  # Top quartile for stage                                                            │ │
│ │     category = "leader"                                                                                               │ │
│ │ elif revenue > revenue_median:  # Above median                                                                        │ │
│ │     category = "strong"                                                                                               │ │
│ │ else:                                                                                                                 │ │
│ │     category = "emerging"                                                                                             │ │
│ │                                                                                                                       │ │
│ │ 7. Fund Context (Lines 5036-5039, 5089-5093)                                                                          │ │
│ │                                                                                                                       │ │
│ │ # Use ONE consistent source:                                                                                          │ │
│ │ fund_context = self.shared_data.get('fund_context', {})                                                               │ │
│ │ fund_size = fund_context.get('fund_size', 250_000_000)                                                                │ │
│ │ # Never use different hardcoded defaults in different methods                                                         │ │
│ │                                                                                                                       │ │
│ │ 8. Market Dynamics Scoring (Lines 2379-2393)                                                                          │ │
│ │                                                                                                                       │ │
│ │ # DELETE: min(10, (market_size / 10_000_000_000) * 10)                                                                │ │
│ │ # REPLACE with percentile-based:                                                                                      │ │
│ │ all_markets = [c.get('market_size', {}).get('tam', 0) for c in companies]                                             │ │
│ │ max_market = max(all_markets) if all_markets else 1                                                                   │ │
│ │ market_score = (market_size / max_market) * 10 if max_market > 0 else 5                                               │ │
│ │                                                                                                                       │ │
│ │ 9. Entry Point Analysis (Lines 1612-1614)                                                                             │ │
│ │                                                                                                                       │ │
│ │ # DELETE hardcoded valuation ranges                                                                                   │ │
│ │ # USE stage benchmarks:                                                                                               │ │
│ │ stage_data = self.gap_filler.benchmarks.get(stage, {})                                                                │ │
│ │ typical_val = stage_data.get('valuation_median', 0)                                                                   │ │
│ │ entry_analysis = f"{stage} entry. Typical valuation: ${typical_val/1e6:.0f}M"                                         │ │
│ │                                                                                                                       │ │
│ │ 10. Business Analysis (Lines 2135-2185)                                                                               │ │
│ │                                                                                                                       │ │
│ │ # Use ONLY extracted fields:                                                                                          │ │
│ │ what_they_do = company.get('one_liner', '')                                                                           │ │
│ │ what_they_sell = company.get('product_description', '')                                                               │ │
│ │ who_they_sell_to = company.get('who_they_sell_to', '')                                                                │ │
│ │ pricing_model = company.get('pricing_model', '')                                                                      │ │
│ │ geography = company.get('geography', '')                                                                              │ │
│ │                                                                                                                       │ │
│ │ Summary                                                                                                               │ │
│ │                                                                                                                       │ │
│ │ - Remove ALL hardcoded numbers                                                                                        │ │
│ │ - Use calculated/extracted data from services                                                                         │ │
│ │ - If data missing, leave empty or mark as unknown                                                                     │ │
│ │ - Never guess or use generic defaults                                                                                 │ │
│ │ - All thresholds should be stage-relative, not absolute                                                               │ │
│ ╰──────────────────────