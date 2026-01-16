#!/usr/bin/env python3
"""Test valuation calculation for both companies"""

import asyncio
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_both():
    orchestrator = UnifiedMCPOrchestrator()
    
    try:
        response = await orchestrator.process_request({
            "prompt": "Create investment deck for @Extruct and @RelevanceAI",
            "output_format": "deck"
        })
        
        # Get companies from shared_data
        companies = orchestrator.shared_data.get("companies", [])
        
        print(f"Found {len(companies)} companies:\n")
        
        for company in companies:
            name = company.get('company', 'Unknown')
            val = company.get('valuation', 0)
            inferred_val = company.get('inferred_valuation', 0)
            revenue = company.get('revenue', 0)
            inferred_rev = company.get('inferred_revenue', 0)
            stage = company.get('stage', 'Unknown')
            
            print(f"{'='*50}")
            print(f"Company: {name}")
            print(f"Stage: {stage}")
            print(f"Revenue: ${revenue:,.0f}")
            print(f"Inferred Revenue: ${inferred_rev:,.0f}")
            print(f"Valuation: ${val:,.0f}")
            print(f"Inferred Valuation: ${inferred_val:,.0f}")
            
            # Show the multiple used
            if inferred_val > 0 and inferred_rev > 0:
                multiple = inferred_val / inferred_rev
                print(f"Implied Multiple: {multiple:.1f}x")
            
            # Check GPU metrics
            if 'gpu_metrics' in company:
                gpu = company['gpu_metrics']
                intensity = gpu.get('compute_profile', {}).get('compute_intensity', 'N/A')
                gpu_cost = gpu.get('gpu_cost_as_percent_revenue', 0)
                print(f"GPU Intensity: {intensity}")
                print(f"GPU Cost %: {gpu_cost:.0f}%")
                
        # Check slides
        if "results" in response:
            slides = response["results"].get("slides", [])
            print(f"\n{'='*50}")
            print(f"✅ Generated {len(slides)} slides")
            
            # Show slide types
            slide_types = [s.get('type', 'unknown') for s in slides]
            print(f"Slide types: {', '.join(slide_types[:5])}...")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if hasattr(orchestrator, 'session') and orchestrator.session:
            await orchestrator.session.close()

if __name__ == "__main__":
    asyncio.run(test_both())