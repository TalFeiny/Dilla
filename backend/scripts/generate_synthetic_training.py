#!/usr/bin/env python3
"""
Generate Synthetic GRPO Training Data
Focuses on HOW tasks are decomposed and analyzed, not the data accuracy
"""

import asyncio
import json
from typing import List, Dict, Tuple
import random
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import supabase_service
from app.services.grpo_rl_system import get_grpo_system

# Tool Calling Patterns - From 0 to 100
TOOL_CALLING_EXAMPLES = [
    {
        "level": 0,
        "prompt": "What is @Ramp's valuation?",
        "bad": """
        I don't know Ramp's valuation.
        """,
        "good": """
        Tools needed:
        1. tavily_search("Ramp valuation funding series")
        2. database_search({"company": "Ramp"})
        3. firecrawl_scrape("ramp.com/about")
        
        Executing searches...
        Result: Ramp valued at $5.8B (Series D, March 2022)
        Source: [TechCrunch], [Company announcement]
        """,
        "score_bad": 0.0,
        "score_good": 1.0
    },
    {
        "level": 10,
        "prompt": "Compare @Deel and @Brex revenue",
        "bad": """
        Tool: search("Deel Brex revenue")
        
        They both have revenue.
        """,
        "good": """
        Parallel tool execution:
        - tavily_search("Deel revenue ARR 2024")
        - tavily_search("Brex revenue ARR 2024")  
        - database_search({"companies": ["Deel", "Brex"]})
        
        Results:
        - Deel: $500M ARR (2024)
        - Brex: $300M ARR (2024)
        
        Deel growing 2x faster (100% vs 50% YoY)
        """,
        "score_bad": 0.2,
        "score_good": 0.95
    },
    {
        "level": 30,
        "prompt": "Build DCF model for @Stripe",
        "bad": """
        Tool: calculate_dcf("Stripe")
        
        DCF = $100B
        """,
        "good": """
        Tool chain execution:
        1. Data gathering (parallel):
           - tavily_search("Stripe revenue growth rate")
           - tavily_search("Stripe operating margins")
           - database_search({"company": "Stripe", "metrics": ["revenue", "growth"]})
        
        2. Financial calculations:
           - npv_calculator(cash_flows=[...], discount_rate=0.12)
           - irr_calculator(cash_flows=[...])
           - terminal_value(growth=0.03, multiple=25)
        
        3. Sensitivity analysis:
           - scenario_analyzer(base_case, bull_case, bear_case)
        
        Output: Valuation range $95B-$145B
        """,
        "score_bad": 0.1,
        "score_good": 0.98
    },
    {
        "level": 50,
        "prompt": "Create investment memo for @Canva Series A",
        "bad": """
        Tool: generate_memo("Canva")
        
        Canva is a design tool. It's good. Invest.
        """,
        "good": """
        Orchestrated tool execution:
        
        Phase 1 - Research (parallel):
        - tavily_search("Canva competitors Figma Adobe market share")
        - firecrawl_scrape("canva.com", pages=["pricing", "customers", "about"])
        - database_search({"sector": "design tools", "stage": "Series A"})
        
        Phase 2 - Analysis (sequential):
        - market_size_calculator("design software", bottom_up=True)
        - competitive_analysis(["Canva", "Figma", "Adobe"])
        - unit_economics_analyzer(cac=50, ltv=500, payback_months=12)
        
        Phase 3 - Valuation (parallel):
        - comparable_companies(sector="SaaS", growth_rate=">100%")
        - dcf_model(revenues=[...], growth_rates=[...])
        - venture_returns_model(entry=$40M, exit_scenarios=[...])
        
        Phase 4 - Document generation:
        - format_investment_memo(sections=[...])
        """,
        "score_bad": 0.05,
        "score_good": 1.0
    },
    {
        "level": 70,
        "prompt": "Analyze @Notion's product-market fit across segments",
        "bad": """
        Tool: check_pmf("Notion")
        
        Notion has PMF. Users love it.
        """,
        "good": """
        Multi-dimensional tool orchestration:
        
        Segment Analysis (parallel per segment):
        For segment in [Individuals, SMB, Enterprise]:
          - tavily_search(f"Notion {segment} adoption reviews")
          - database_search({"company": "Notion", "segment": segment})
          - sentiment_analyzer(reviews)
          - nps_calculator(survey_data)
        
        Cohort Analysis:
        - retention_analyzer(cohorts=monthly, period=24_months)
        - expansion_revenue_tracker(by_segment=True)
        
        Competitive Position:
        - feature_comparison_matrix(["Notion", "Coda", "Confluence"])
        - switching_cost_analyzer(from="Confluence", to="Notion")
        
        PMF Score Calculation:
        - weighted_pmf_score(
            retention_weight=0.4,
            nps_weight=0.2,
            growth_weight=0.4
          )
        
        Results: Strong PMF in SMB (score: 85), Growing in Enterprise (65)
        """,
        "score_bad": 0.0,
        "score_good": 1.0
    },
    {
        "level": 100,
        "prompt": "Build complete due diligence package for @Ramp acquisition",
        "bad": """
        Tool: due_diligence("Ramp")
        
        Ramp good. Buy for $10B.
        """,
        "good": """
        Comprehensive tool orchestration pipeline:
        
        === STAGE 1: Data Collection (200+ parallel calls) ===
        
        Financial Data:
        - Parallel: [tavily_search(f"Ramp {metric}") for metric in financial_metrics]
        - sec_edgar_search("Ramp", filings=["S-1", "10-K"]) 
        - pitchbook_api(company="Ramp", data=["financials", "investors"])
        
        Market Intelligence:
        - Batch process: 50 competitor searches
        - Industry reports: 20 parallel API calls
        - Customer interviews: analyze_transcripts(100_interviews)
        
        Technical Assessment:
        - github_analyzer("ramp", metrics=["commits", "contributors", "tech_stack"])
        - patent_search("Ramp", include_pending=True)
        - security_audit(infrastructure_scan=True)
        
        === STAGE 2: Analysis (50+ calculations) ===
        
        Financial Modeling:
        - dcf_model(scenarios=10, monte_carlo_runs=1000)
        - lbo_model(leverage_ratios=[3x, 4x, 5x])
        - synergy_calculator(cost_synergies + revenue_synergies)
        
        Risk Assessment:
        - risk_matrix(operational + financial + regulatory + competitive)
        - sensitivity_analysis(key_drivers=20)
        - stress_testing(recession_scenario=True)
        
        === STAGE 3: Strategic Evaluation ===
        
        Integration Planning:
        - cultural_fit_scorer(surveys + interviews)
        - system_integration_complexity(apis + databases + workflows)
        - customer_overlap_analyzer(churn_risk=True)
        
        Exit Scenarios:
        - ipo_valuation_model(comps=public_fintech)
        - strategic_buyer_analysis(identify=20_potential)
        - secondary_sale_modeling(pe_buyers=True)
        
        === STAGE 4: Package Generation ===
        
        Documents (parallel generation):
        - executive_summary(2_pages)
        - financial_model(excel_export=True)
        - risk_assessment_report(50_pages)
        - integration_playbook(100_pages)
        - board_presentation(20_slides)
        
        Total execution: 2.3 minutes for 350+ tool calls
        Output: 200-page DD package + live Excel model
        """,
        "score_bad": 0.0,
        "score_good": 1.0
    }
]

# Good vs Bad Examples of Task Decomposition
TASK_EXAMPLES = [
    {
        "prompt": "Analyze @Ramp's unit economics and path to profitability",
        "good": """
        Task Decomposition:
        1. Data Gathering (Parallel):
           - Fetch revenue data from multiple sources
           - Gather customer count and pricing
           - Find burn rate and runway info
        
        2. Unit Economic Calculation:
           - CAC = Sales & Marketing / New Customers
           - LTV = ARPU × Gross Margin × Avg Customer Lifetime
           - Payback Period = CAC / (ARPU × Gross Margin)
        
        3. Profitability Analysis:
           - Current burn rate vs growth rate
           - Time to breakeven at current trajectory
           - Scenario analysis (3 cases)
        
        4. Comparable Analysis:
           - Compare to @Brex, @Deel, @Mercury
           - Industry benchmarks for B2B SaaS
        
        Citations: [TechCrunch 2024], [Company Blog], [Industry Report]
        """,
        "bad": """
        Just multiply revenue by 10 for valuation.
        They'll be profitable eventually.
        No sources needed.
        """,
        "focus": "task_decomposition"
    },
    {
        "prompt": "Create a DCF model for @Stripe",
        "good": """
        Financial Model Structure:
        
        I. Revenue Projections (5 years)
           - Payment volume growth: 35% → 25% → 20% → 15% → 12%
           - Take rate: 2.9% stable
           - Additional products: +$500M/year growing 50% YoY
        
        II. Operating Expenses
           - COGS: 25% of revenue
           - S&M: 30% → declining to 20% at maturity
           - R&D: 25% stable
           - G&A: 10% → 8% with scale
        
        III. DCF Calculation
           - WACC: 12% (risk-free 4% + equity premium 8%)
           - Terminal growth: 3%
           - Terminal multiple: 25x FCF
        
        IV. Sensitivity Analysis
           - Bull case: +20% growth, 10% WACC
           - Base case: As modeled
           - Bear case: -20% growth, 15% WACC
        
        Output: Valuation range $85B - $145B
        Sources: [Financial statements], [Analyst reports], [Market data]
        """,
        "bad": """
        Stripe worth $100B because that's what Forbes said.
        DCF = revenue × 20
        Done.
        """,
        "focus": "analysis_structure"
    },
    {
        "prompt": "Compare competitive positioning of @Notion vs @Coda vs @Airtable",
        "good": """
        # Competitive Analysis Matrix
        
        ## Market Position
        | Company | Users | Revenue | Growth | Moat |
        |---------|-------|---------|---------|------|
        | Notion | 30M | $500M | 100% | All-in-one workspace |
        | Coda | 5M | $100M | 150% | Doc-as-app platform |
        | Airtable | 10M | $300M | 80% | Database-first |
        
        ## Feature Comparison
        ✅ = Strong, ⚠️ = Medium, ❌ = Weak
        
        | Feature | Notion | Coda | Airtable |
        |---------|---------|------|----------|
        | Databases | ✅ | ⚠️ | ✅ |
        | Formulas | ⚠️ | ✅ | ✅ |
        | AI Features | ✅ | ⚠️ | ⚠️ |
        | API/Integrations | ⚠️ | ✅ | ✅ |
        
        ## Strategic Assessment
        1. **Notion**: Winning on simplicity and brand
        2. **Coda**: Most technically powerful, smaller base
        3. **Airtable**: Best for data-heavy workflows
        
        ## Investment Thesis
        - Notion: Market leader, defensible position
        - Coda: High risk/reward, potential acquisition
        - Airtable: Steady growth, enterprise focus
        
        Data from: [G2 Reviews 2024], [Company filings], [User surveys]
        """,
        "bad": """
        notion good
        coda ok
        airtable also ok
        
        notion bigger so better investment
        """,
        "focus": "output_format"
    }
]

# Reward Hacking Prevention Patterns
REWARD_HACKING_PATTERNS = [
    {
        "description": "Length hacking - just making response longer",
        "bad_pattern": "Adding filler text text text text to make response longer longer longer",
        "good_pattern": "Concise, information-dense content"
    },
    {
        "description": "Citation spamming - fake sources",
        "bad_pattern": "[Source 1] [Source 2] [Source 3]... [Source 99]",
        "good_pattern": "[TechCrunch 2024: Series B announcement] [SEC Filing: Q3 2024]"
    },
    {
        "description": "Buzzword stuffing",
        "bad_pattern": "Leveraging synergistic AI blockchain quantum web3 metaverse",
        "good_pattern": "Using machine learning for fraud detection"
    },
    {
        "description": "False precision",
        "bad_pattern": "Revenue is exactly $123,456,789.12345",
        "good_pattern": "Revenue estimated at $120-125M based on employee count"
    }
]

async def generate_training_pairs():
    """Generate diverse training pairs for GRPO"""
    
    training_data = []
    
    print("🎲 Generating synthetic training data...")
    print("=" * 50)
    
    # 1. Generate task decomposition examples
    for example in TASK_EXAMPLES:
        # Good example gets high score
        training_data.append({
            "prompt": example["prompt"],
            "response": example["good"],
            "score": 0.9 + random.uniform(0, 0.1),  # 0.9-1.0
            "feedback_type": "approve",
            "corrections": None,
            "metadata": {
                "focus": example["focus"],
                "quality": "high",
                "has_citations": True,
                "structure_score": 0.95
            }
        })
        
        # Bad example gets low score
        training_data.append({
            "prompt": example["prompt"],
            "response": example["bad"],
            "score": 0.1 + random.uniform(0, 0.2),  # 0.1-0.3
            "feedback_type": "wrong",
            "corrections": example["good"],  # What it should have been
            "metadata": {
                "focus": example["focus"],
                "quality": "low",
                "has_citations": False,
                "structure_score": 0.2
            }
        })
    
    # 2. Generate reward hacking prevention examples
    for pattern in REWARD_HACKING_PATTERNS:
        prompt = f"Analyze market opportunity for B2B SaaS"
        
        # Penalize reward hacking attempts
        training_data.append({
            "prompt": prompt,
            "response": pattern["bad_pattern"],
            "score": -0.5,  # Negative score for gaming attempts
            "feedback_type": "fix_required",
            "corrections": pattern["good_pattern"],
            "metadata": {
                "issue": "reward_hacking",
                "pattern": pattern["description"]
            }
        })
    
    # 3. Generate format preference examples
    formats = [
        ("spreadsheet", "grid.write('A1', 'Revenue Model')\ngrid.formula('B2', '=A2*1.5')"),
        ("deck", "Slide 1: Title\n- Key Point\n- Supporting Data\n\nSlide 2: Market Analysis"),
        ("analysis", "## Executive Summary\n\n### Key Findings\n1. Market growing 50% YoY\n2. TAM: $10B")
    ]
    
    for fmt, good_output in formats:
        training_data.append({
            "prompt": f"Create {fmt} for Series A startup",
            "response": good_output,
            "score": 0.85,
            "feedback_type": "approve",
            "corrections": None,
            "metadata": {
                "output_format": fmt,
                "follows_format": True
            }
        })
    
    print(f"✅ Generated {len(training_data)} training examples")
    return training_data

async def store_training_data(training_data: List[Dict]):
    """Store training data in Supabase"""
    
    print("\n💾 Storing in database...")
    
    try:
        # Store in agent_feedback table
        for data in training_data:
            result = supabase_service.client.table('agent_feedback').insert({
                'session_id': f"synthetic_{datetime.now().isoformat()}",
                'prompt': data['prompt'],
                'response': data['response'],
                'score': data['score'],
                'feedback_type': data['feedback_type'],
                'corrections': data.get('corrections'),
                'metadata': json.dumps(data.get('metadata', {})),
                'created_at': datetime.now().isoformat()
            }).execute()
            
        print(f"✅ Stored {len(training_data)} examples in database")
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        print("Saving to local file instead...")
        
        with open('synthetic_training_data.json', 'w') as f:
            json.dump(training_data, f, indent=2)
        print("✅ Saved to synthetic_training_data.json")

async def train_on_synthetic():
    """Train GRPO on the synthetic data"""
    
    print("\n🧠 Training GRPO on synthetic data...")
    
    try:
        grpo = get_grpo_system()
        result = await grpo.train_grpo(num_epochs=5, batch_size=16)
        
        if result['success']:
            print(f"✅ Training complete!")
            print(f"   Final accuracy: {result.get('final_accuracy', 0):.2%}")
            print(f"   Pairs trained: {result.get('pairs_trained', 0)}")
        else:
            print(f"⚠️ Training failed: {result.get('message')}")
            
    except Exception as e:
        print(f"❌ Training error: {e}")

async def test_reward_hacking_resistance():
    """Test if GRPO learned to resist reward hacking"""
    
    print("\n🔬 Testing reward hacking resistance...")
    
    test_cases = [
        ("Normal good response with analysis", 0.8),  # Should score high
        ("spam spam spam " * 100, -0.3),  # Should score low
        ("Comprehensive analysis with [Source] " * 50, -0.2),  # Citation spam
        ("Leveraging synergistic AI blockchain quantum", -0.4),  # Buzzword spam
    ]
    
    grpo = get_grpo_system()
    
    for response, expected_score_range in test_cases:
        scores = grpo.rank_responses(
            "Analyze startup", 
            [response, "Simple but clear analysis"]
        )
        
        actual_score = scores[0][1] if scores[0][0] == response else scores[1][1]
        
        if expected_score_range > 0:
            success = actual_score > 0.5
        else:
            success = actual_score < 0.5
            
        status = "✅" if success else "❌"
        print(f"{status} '{response[:30]}...' scored {actual_score:.3f}")

async def main():
    print("""
    ╔══════════════════════════════════════════════╗
    ║     SYNTHETIC GRPO TRAINING GENERATOR       ║
    ║                                              ║
    ║  Trains on HOW to analyze, not WHAT data    ║
    ╚══════════════════════════════════════════════╝
    """)
    
    # Generate training data
    training_data = await generate_training_pairs()
    
    # Store it
    await store_training_data(training_data)
    
    # Optional: Train immediately
    print("\n❓ Train GRPO now? (y/n): ", end="")
    if input().lower() == 'y':
        await train_on_synthetic()
        await test_reward_hacking_resistance()
    
    print("\n✅ Complete! To train later, run:")
    print("   python3 test_grpo_system.py")

if __name__ == "__main__":
    asyncio.run(main())