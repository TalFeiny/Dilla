#!/usr/bin/env python3
"""
Test the compute intensity and GPU cost calculations
"""

import asyncio
from app.services.intelligent_gap_filler import IntelligentGapFiller

async def test_compute_intensity():
    """Test compute intensity detection for various company types"""
    
    gap_filler = IntelligentGapFiller()
    
    test_companies = [
        {
            "name": "Cursor",
            "data": {
                "company": "Cursor",
                "business_model": "AI-powered code editor built on VS Code",
                "sector": "DevTools",
                "category": "AI Code Assistant",
                "revenue": 10_000_000,
                "customers": 5000
            }
        },
        {
            "name": "Perplexity",
            "data": {
                "company": "Perplexity",
                "business_model": "AI-powered conversational search engine",
                "sector": "AI Search",
                "category": "Search Engine",
                "revenue": 20_000_000,
                "customers": 50000
            }
        },
        {
            "name": "Mercury",
            "data": {
                "company": "Mercury",
                "business_model": "Digital banking platform for startups",
                "sector": "FinTech",
                "category": "Banking",
                "revenue": 50_000_000,
                "customers": 10000
            }
        },
        {
            "name": "Midjourney",
            "data": {
                "company": "Midjourney",
                "business_model": "AI-powered image generation platform",
                "sector": "Generative AI",
                "category": "Image Generation",
                "revenue": 200_000_000,
                "customers": 1000000
            }
        },
        {
            "name": "AI Agent Company",
            "data": {
                "company": "AgentForce",
                "business_model": "Autonomous AI agents for workflow automation",
                "sector": "AI Automation",
                "category": "AI Agents",
                "revenue": 5_000_000,
                "customers": 500
            }
        }
    ]
    
    print("\n" + "="*80)
    print("GPU COMPUTE INTENSITY & COST ANALYSIS")
    print("="*80 + "\n")
    
    for company in test_companies:
        print(f"\n📊 Analyzing {company['name']}...")
        print("-" * 60)
        
        # Detect compute intensity
        compute_profile = gap_filler.detect_compute_intensity(company["data"])
        
        # Calculate GPU metrics
        gpu_metrics = gap_filler.calculate_gpu_adjusted_metrics(company["data"])
        
        # Calculate adjusted gross margins
        margin_analysis = await gap_filler.calculate_adjusted_gross_margin(company["data"])
        
        # Display results
        print(f"Business Model: {company['data']['business_model']}")
        print(f"\n🔥 Compute Intensity: {gpu_metrics['compute_intensity'].upper()}")
        print(f"   Category: {gpu_metrics.get('compute_category', 'Unknown')}")
        print(f"   Cost per transaction: ${gpu_metrics['cost_per_transaction']:.2f}")
        print(f"   Transaction range: ${compute_profile['cost_range'][0]} - ${compute_profile['cost_range'][1]}")
        
        print(f"\n💰 Financial Impact:")
        print(f"   Monthly GPU costs: ${gpu_metrics['monthly_gpu_costs']:,.0f}")
        print(f"   Annual GPU costs: ${gpu_metrics['annual_gpu_costs']:,.0f}")
        print(f"   GPU as % of revenue: {gpu_metrics['gpu_cost_as_percent_revenue']:.1f}%")
        
        print(f"\n📈 Margin Analysis:")
        print(f"   Base gross margin: {margin_analysis['base_gross_margin']:.0%}")
        print(f"   API penalty: -{margin_analysis['api_penalty']:.0%}")
        print(f"   GPU penalty: -{margin_analysis['gpu_penalty']:.0%}")
        print(f"   Adjusted margin: {margin_analysis['adjusted_gross_margin']:.0%}")
        
        print(f"\n💡 Valuation Impact:")
        print(f"   Valuation multiple: {margin_analysis['valuation_multiple_adjustment']:.1f}x")
        print(f"   {margin_analysis['investment_recommendation']}")
        
        # Show risk factors if any
        if margin_analysis.get('risk_factors'):
            print(f"\n⚠️  Risk Factors:")
            for risk in margin_analysis['risk_factors'][:3]:  # Show top 3
                print(f"   • {risk}")
    
    print("\n" + "="*80)
    print("COMPUTE INTENSITY TEST COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(test_compute_intensity())