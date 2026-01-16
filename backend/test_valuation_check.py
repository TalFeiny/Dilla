#!/usr/bin/env python3
"""Check if valuation is being calculated"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def check_valuation():
    orchestrator = UnifiedMCPOrchestrator()
    
    try:
        response = await orchestrator.process_request({
            "prompt": "Create investment deck for @Extruct",
            "output_format": "deck"
        })
        
        # Get the companies from shared_data
        companies = orchestrator.shared_data.get("companies", [])
        
        if companies:
            for company in companies:
                name = company.get('company', 'Unknown')
                val = company.get('valuation', 0)
                inferred_val = company.get('inferred_valuation', 0)
                revenue = company.get('revenue', 0)
                inferred_rev = company.get('inferred_revenue', 0)
                
                print(f"{name}:")
                print(f"  Revenue: ${revenue:,.0f}")
                print(f"  Inferred Revenue: ${inferred_rev:,.0f}")
                print(f"  Valuation: ${val:,.0f}")
                print(f"  Inferred Valuation: ${inferred_val:,.0f}")
                
                # Check if we have GPU metrics
                if 'gpu_metrics' in company:
                    gpu = company['gpu_metrics']
                    print(f"  GPU Metrics: {gpu.get('compute_intensity', 'N/A')}")
                    
                # Check if we have AI valuation multiple
                if 'ai_adjusted_multiple' in company:
                    print(f"  AI Multiple: {company['ai_adjusted_multiple']}")
                    
        # Check the actual slides
        if "results" in response:
            slides = response["results"].get("slides", [])
            print(f"\n✅ Generated {len(slides)} slides")
            
            # Look for valuation in slides
            for slide in slides[:3]:  # Check first 3 slides
                if 'content' in slide:
                    content = slide['content']
                    if 'metrics' in content:
                        print(f"\nSlide {slide.get('type')} metrics:")
                        for key, value in content['metrics'].items():
                            if 'valuation' in str(key).lower() or 'valuation' in str(value).lower():
                                print(f"  {key}: {value}")
        else:
            print("❌ No results in response")
                
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if hasattr(orchestrator, 'session') and orchestrator.session:
            await orchestrator.session.close()

if __name__ == "__main__":
    asyncio.run(check_valuation())