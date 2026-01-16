# Current Deck Structure - As Of Dec 2024

## ✅ COMPLETE Deck Structure (WORKING)

### Slide Order and Structure

### 1. Title Slide ✅
```python
{
    "type": "title",
    "content": {
        "title": "Investment Analysis Report",
        "subtitle": "Analysis of {len(companies)} companies",
        "date": "September 2025"
    }
}
```

### 2. Executive Summary ✅
```python
{
    "type": "summary",
    "content": {
        "title": "Executive Summary",
        "bullets": [
            "Analyzing {len(companies)} companies",
            "Combined funding: ${total_funding}",
            "Average valuation: ${avg_valuation}",
            "Total revenue: ${total_revenue}",
            "Sectors: {sectors_list}"
        ]
    },
    "chart": {
        "type": "bar",
        "title": "Key Metrics Overview",
        "data": {
            "labels": ["Total Funding", "Avg Valuation", "Total Revenue"],
            "datasets": [{
                "label": "Amount (USD)",
                "data": [total_funding, avg_valuation, total_revenue],
                "backgroundColor": ["#4285F4", "#DB4437", "#0F9D58"]
            }]
        }
    }
}
```

### 3-4. Company Profiles (one per company) ✅
**For Each Company (typically 2 companies)**
```python
{
    "type": "company",
    "content": {
        "title": "{company_name}",
        "subtitle": "{sector} | {business_model}",
        "business_model": business_model,
        "sector": sector,
        "metrics": {
            "Stage": stage,
            "Revenue": revenue_with_citation,
            "Valuation": valuation_with_citation,
            "Revenue Multiple": revenue_multiple,
            "Total Funding": total_funding,
            "Team Size": team_size,
            "Founded": founded_year,
            "Growth Rate": growth_rate,
            "Gross Margin": gross_margin,
            "TAM": tam,
            "Market Penetration": penetration,
            "Base Case Exit": base_exit,
            "Bull Case Exit": bull_exit,
            "Bear Case Exit": bear_exit,
            "Expected Exit": expected_exit,
            "LTV/CAC": ltv_cac,
            "Payback Period": payback_months,
            "Runway": runway_months,
            "Burn Rate": burn_rate
        },
        "website": website_url,
        "description": product_description,
        "qualitative_analysis": {
            "strategy": product_description,
            "target_market": target_market,
            "customers": customers_list,
            "competitors": competitors_list,
            "competitive_advantage": competitive_advantage,
            "technology_stack": tech_stack,
            "recent_news": recent_news_top3,
            "founders": founders_list
        },
        "scenarios": {
            "bear": {...},
            "base": {...},
            "bull": {...}
        },
        "projections": {
            "current_revenue": revenue,
            "base_case": base_scenario,
            "bull_case": bull_scenario,
            "bear_case": bear_scenario,
            "expected_exit": expected_exit,
            "growth_rate": growth_rate,
            "revenue_multiple": revenue_multiple
        }
    }
}
```

### 5. Investment Thesis (one per company) ✅
```python
{
    "type": "investment_thesis",
    "content": {
        "title": "Investment Thesis: {company_name}",
        "recommendation": "STRONG BUY|CONSIDER|PASS",
        "scores": {
            "Competitive Moat": "{moat_score}%",
            "Growth Momentum": "{momentum_score}%",
            "Fund Fit Score": "{fund_fit_score}%",
            "Expected Ownership": "{ownership_pct}%"
        },
        "bullets": [
            "💰 Proposed Investment: ${check_size}",
            "💰 Total with Reserves: ${total_capital_required}",
            "📊 Current Ownership Target: {ownership_pct}%",
            "📊 Exit Ownership (post-dilution): {exit_ownership_pct}%",
            "📈 Expected Multiple: {expected_multiple}x",
            "💵 Expected Exit Value: ${exit_proceeds}",
            "⏱ Expected Hold Period: {holding_period} years",
            "🎯 IRR Target: {expected_irr}%"
        ],
        "risks": [
            "GPU cost dependency",
            "Early stage risk",
            "Market competition"
        ],
        "opportunities": [
            "AI market expansion",
            "Enterprise traction",
            "Strong team"
        ]
    }
}
```

### 6. 🆕 Cap Table Comparison (if 2+ companies) ✅
```python
{
    "type": "cap_table_comparison",
    "content": {
        "title": "Cap Table Comparison",
        "subtitle": "{company1} vs {company2}",
        "metrics": {
            "{company1}": {
                "Founder %": "{founder_pct1}%",
                "Total Raised": "${total_funding1}",
                "Our Stake": "{our_stake1}%"
            },
            "{company2}": {
                "Founder %": "{founder_pct2}%",
                "Total Raised": "${total_funding2}",
                "Our Stake": "{our_stake2}%"
            }
        },
        "devices": [
            {
                "type": "side_by_side_sankey",
                "company1_data": {
                    "nodes": [...],  // Sankey nodes for company 1
                    "links": [...]   // Sankey links showing equity flow
                },
                "company2_data": {
                    "nodes": [...],  // Sankey nodes for company 2
                    "links": [...]   // Sankey links showing equity flow
                },
                "company1_name": "{company1}",
                "company2_name": "{company2}"
            }
        ]
    }
}
```
**Features:**
- Side-by-side Sankey diagrams showing ownership flow
- Visualizes dilution through funding rounds
- Shows our proposed investment position
- Compares founder retention between companies

### 7. Scenario Analysis (one per company) ✅
```python
{
    "type": "scenario_analysis",
    "content": {
        "title": "Scenario Analysis: {company_name}",
        "subtitle": "Bull, Base, and Bear Case Projections",
        "bullets": [
            "🎯 Base Case (50% probability): ${base_exit} exit",
            "🚀 Bull Case (25% probability): ${bull_exit} exit",
            "⚠️ Bear Case (25% probability): ${bear_exit} exit",
            "📊 Expected Value: ${expected_exit}"
        ],
        "chart_data": {
            "type": "line",
            "title": "Exit Valuation Scenarios",
            "data": {
                "labels": ["Current", "Exit"],
                "datasets": [
                    {
                        "label": "Bull Case",
                        "data": [valuation, bull_exit],
                        "borderColor": "#0F9D58"
                    },
                    {
                        "label": "Base Case",
                        "data": [revenue, base_y1, base_y3, base_y5],
                        "borderColor": "#4285F4"
                    },
                    {
                        "label": "Bear Case",
                        "data": [revenue, bear_y1, bear_y3, bear_y5],
                        "borderColor": "#DB4437"
                    }
                ]
            }
        },
        "metrics": {
            "Base IRR": "{base_irr}%",
            "Bull IRR": "{bull_irr}%",
            "Bear IRR": "{bear_irr}%",
            "Expected IRR": "{expected_irr}%"
        },
        "waterfall_analysis": {...},
        "breakpoints": {
            "Liquidation Preference": "${total_funding}",
            "Common Stock Participation": "${total_funding * 1.5}",
            "Full Recovery": "${valuation}",
            "Bear Exit": "${bear_exit}",
            "Base Exit": "${base_exit}"
        }
    }
}
```

### 8. Pincer Market Sizing (one per company, if TAM data exists) ✅
```python
{
    "type": "pincer_market",
    "content": {
        "title": "Pincer Market Sizing: {company_name}",
        "subtitle": "Independent TAM Validation",
        "metrics": {
            "Top-Down TAM": "${top_down_tam}",
            "Bottom-Up TAM": "${bottom_up_tam}",
            "Consensus TAM": "${tam}",
            "Methodology": tam_methodology
        },
        "chart_data": {
            "type": "bar",
            "data": {
                "labels": ["Top-Down", "Bottom-Up", "Consensus"],
                "datasets": [{
                    "label": "TAM (USD)",
                    "data": [top_down_tam, bottom_up_tam, consensus_tam],
                    "backgroundColor": ["#4285F4", "#0F9D58", "#F4B400"]
                }]
            }
        }
    }
}
```

### 9. TAM Analysis (one per company) ✅
```python
{
    "type": "tam_analysis",
    "content": {
        "title": "Market Opportunity: {company_name}",
        "subtitle": "{sector} | {business_model} Model",
        "bullets": [
            "📊 TAM: ${tam}",
            "🎯 SAM: ${sam}",
            "💰 SOM: ${som}",
            "📈 Market CAGR: {growth_rate}%",
            "🏆 Current Penetration: {penetration}%",
            "🚀 5Y Potential: {potential}% of TAM"
        ],
        "metrics": {
            "TAM": "${tam}",
            "SAM": "${sam}",
            "SOM": "${som}",
            "Growth": "{cagr}%",
            "Methodology": methodology,
            "Confidence": confidence_level
        },
        "chart_data": {
            "type": "waterfall",
            "title": "Market Sizing Breakdown",
            "data": {...}
        }
    }
}
```

### After All Companies:

### 10. Company Comparison (only if >1 company) ✅
```python
{
    "type": "comparison",
    "content": {
        "title": "Company Comparison",
        "companies": [
            {
                "name": company_name,
                "valuation": valuation,
                "revenue": revenue,
                "stage": stage
            }
        ],
        "chart_data": {
            "type": "bar",
            "title": "Valuation Comparison",
            "data": {
                "labels": [company_names],
                "datasets": [{
                    "label": "Valuation (USD)",
                    "data": [valuations],
                    "backgroundColor": "#4285F4"
                }]
            }
        }
    }
}
```

### 11. Market Analysis ✅
```python
{
    "type": "market_analysis",
    "content": {
        "title": "Market Analysis",
        "subtitle": "Funding & Revenue Metrics",
        "chart_data": {
            "type": "line",
            "title": "Revenue vs Funding Trend",
            "data": {
                "labels": [company_names],
                "datasets": [
                    {
                        "label": "Revenue",
                        "data": [revenues],
                        "borderColor": "#4285F4"
                    },
                    {
                        "label": "Total Funding",
                        "data": [fundings],
                        "borderColor": "#DB4437"
                    }
                ]
            }
        }
    }
}
```

### 12. Stage Distribution ✅
```python
{
    "type": "stage_distribution",
    "content": {
        "title": "Stage Distribution",
        "chart_data": {
            "type": "pie",
            "title": "Companies by Stage",
            "data": {
                "labels": [stages],
                "datasets": [{
                    "data": [counts],
                    "backgroundColor": ["#4285F4", "#DB4437", "#F4B400", "#0F9D58", "#AB47BC"]
                }]
            }
        }
    }
}
```

### 13. Cap Table Evolution (DEPRECATED - replaced by #6) ❌
```python
{
    "type": "cap_table",
    "content": {
        "title": "Cap Table Evolution - {first_company}",
        "subtitle": "Ownership dilution through funding rounds",
        "bullets": [
            "Current founders ownership: {current}%",
            "Post-Series A: {post_a}%",
            "Post-Series B: {post_b}%",
            "At exit (projected): {at_exit}%"
        ],
        "chart_data": {
            "type": "waterfall",
            "title": "Ownership Dilution",
            "data": {...}
        },
        "metrics": {
            "Founders": "{founders}%",
            "Employees": "{esop}%",
            "Investors": "{investors}%"
        }
    }
}
```

### 14. Cap Table Detailed (Investment Opportunity - DEPRECATED) ❌
```python
{
    "type": "cap_table_detailed",
    "content": {
        "title": "Investment Opportunity - {company_name}",
        "subtitle": "Proposed ${check} investment for {ownership}% ownership",
        "metrics": {
            "Proposed Check": "${check}",
            "Our Ownership": "{ownership}%",
            "Entry Valuation": "${valuation}",
            "ARR": "${arr}",
            "TAM": "${tam}",
            "Revenue Multiple": "{multiple}x"
        },
        "chart_data": {
            "type": "treemap",
            "title": "Post-Investment Cap Table",
            "data": {
                "name": "Total Equity",
                "children": [
                    {
                        "name": "Founders & Team",
                        "value": founder_ownership,
                        "children": [...]
                    },
                    {
                        "name": "Investors",
                        "value": investor_ownership,
                        "children": [...]
                    },
                    {
                        "name": "ESOP Pool",
                        "value": 10,
                        "children": [...]
                    }
                ]
            }
        }
    }
}
```

### 13-14. Portfolio Valuation Charts
```python
{
    "type": "chart",
    "content": {
        "title": "Portfolio Valuation Comparison",
        "subtitle": "Current valuations across analyzed companies",
        "chart_data": {
            "type": "bar",
            "title": "Company Valuations",
            "data": {
                "labels": [company_names],
                "datasets": [{
                    "label": "Valuation (USD)",
                    "data": [valuations],
                    "backgroundColor": "#4285F4"
                }]
            }
        }
    }
}

{
    "type": "chart",
    "content": {
        "title": "Revenue Analysis",
        "subtitle": "Annual revenue across portfolio companies",
        "chart_data": {
            "type": "bar",
            "title": "Revenue Comparison",
            "data": {
                "labels": [company_names],
                "datasets": [{
                    "label": "Annual Revenue",
                    "data": [revenues],
                    "backgroundColor": "#0F9D58"
                }]
            }
        }
    }
}
```

### 15+. Citation Slides (10 citations per slide)
```python
{
    "type": "citations",
    "content": {
        "title": "Sources & References (1/3)",
        "citations": [
            {
                "id": 0,
                "source": "url",
                "date": "date",
                "content": "snippet"
            }
        ],
        "bullets": [
            "1. TechCrunch - July 2024",
            "2. Forbes - August 2024",
            ...
        ]
    }
}
```

### Additional Analysis Slides (if enough companies)

### GPU Cost Analysis
```python
{
    "type": "analysis",
    "content": {
        "title": "GPU Cost & Unit Economics Analysis",
        "subtitle": "AI Infrastructure Costs",
        "bullets": [],
        "metrics": {
            "{company_name}": {
                "GPU Cost/Transaction": "${cost}",
                "Monthly GPU Costs": "${monthly}",
                "Compute Intensity": "high|medium|low",
                "Investment Thesis": "thesis"
            }
        }
    }
}
```

### Business Model Analysis
```python
{
    "type": "analysis",
    "content": {
        "title": "Business Model Deep Dive",
        "subtitle": "Category Classification & Valuation Multiples",
        "bullets": [],
        "metrics": {...}
    }
}
```

### Fund Fit Scoring
```python
{
    "type": "scoring",
    "content": {
        "title": "Fund Fit Analysis",
        "subtitle": "Investment Scoring & Recommendations",
        "bullets": [],
        "metrics": {...}
    }
}
```

## Total Slide Count

For 3 companies, typical deck has:
- 2 intro slides (title, summary)
- 15-18 company slides (5-6 per company)
- 5-6 comparison/analysis slides
- 2 chart slides
- 2-3 citation slides
- **Total: ~25-30 slides**

## Status Update - December 2024

### ✅ COMPLETED FEATURES
1. **Cap Table Comparison Slide** - Side-by-side Sankey diagrams showing equity flow
2. **Multi-company support** - Processing 2+ companies correctly
3. **Citations** - Working correctly with proper attribution
4. **Chart data** - All charts rendering properly with real data
5. **TAM calculations** - Working with IntelligentGapFiller
6. **Layout** - Responsive and properly sized

### 🆕 NEW FEATURES ADDED
- **Slide #6: Cap Table Comparison** 
  - Side-by-side Sankey diagrams
  - Shows ownership dilution through rounds
  - Compares founder retention
  - Visualizes our proposed investment
  - Uses TableauLevelCharts component

### 📊 TYPICAL DECK STRUCTURE (Consolidated - 10-12 slides)
1. Title Slide
2. Executive Summary
3. **Company Comparison** (Side-by-side profiles)
4. **Investment Comparison** (Side-by-side thesis)
5. **Cap Table Comparison** (Side-by-side Sankey)
6. **Scenario Comparison** (Combined analysis)
8. Market Analysis
9. Comparison Charts
10. Citations

**Total: ~15-20 slides**

### 🔧 TECHNICAL IMPROVEMENTS
- Removed duplicate cap table slides
- Fixed slide ordering (cap table at position 6)
- Frontend handles `cap_table_comparison` type
- Proper Sankey data transformation
- Side-by-side visualization device

---
Generated: December 2024
Updated: Cap Table Comparison Feature Complete