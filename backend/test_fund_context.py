"""
Test fund context propagation and DPI calculations
"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import get_unified_orchestrator

async def test_fund_context():
    """Test that fund context is properly passed through the system"""
    
    # Create orchestrator
    orchestrator = get_unified_orchestrator()
    
    # Test different fund scenarios
    test_scenarios = [
        {
            "name": "Small Early Fund",
            "context": {
                "fund_size": 50_000_000,  # $50M fund
                "deployed_capital": 15_000_000,  # $15M deployed
                "remaining_capital": 35_000_000,  # $35M remaining
                "portfolio_size": 5,  # 5 investments made
                "current_dpi": 0.2,  # 0.2x DPI
                "target_dpi": 3.0,  # 3x target
                "fund_year": 2,  # Year 2 of fund
                "is_lead": False  # Not a lead investor
            },
            "prompt": "Analyze @Mercury and @Brex for our $50M fund"
        },
        {
            "name": "Large Late Stage Fund",
            "context": {
                "fund_size": 500_000_000,  # $500M fund
                "deployed_capital": 350_000_000,  # $350M deployed
                "remaining_capital": 150_000_000,  # $150M remaining
                "portfolio_size": 25,  # 25 investments made
                "current_dpi": 1.2,  # 1.2x DPI already
                "target_dpi": 3.0,  # 3x target
                "fund_year": 5,  # Year 5 of fund
                "is_lead": True  # Lead investor
            },
            "prompt": "Evaluate @Anthropic and @Perplexity for our $500M growth fund"
        },
        {
            "name": "Mid-size Seed Fund",
            "context": {
                "fund_size": 150_000_000,  # $150M fund
                "deployed_capital": 60_000_000,  # $60M deployed
                "remaining_capital": 90_000_000,  # $90M remaining
                "portfolio_size": 30,  # 30 investments (seed stage)
                "current_dpi": 0.0,  # No exits yet
                "target_dpi": 4.0,  # 4x target (seed fund)
                "fund_year": 3,  # Year 3
                "is_lead": True,  # Lead seed rounds
                "check_size_range": (500_000, 2_000_000)  # Seed checks
            },
            "prompt": "Analyze @Cursor and @Lovable for seed investment"
        }
    ]
    
    for scenario in test_scenarios:
        print(f"\n{'='*60}")
        print(f"Testing: {scenario['name']}")
        print(f"{'='*60}")
        
        # Process request with context
        result = await orchestrator.process_request(
            prompt=scenario['prompt'],
            output_format="deck",
            context=scenario['context']
        )
        
        if result.get('success'):
            # Check if context was properly used
            data = result.get('data', {})
            slides = data.get('slides', [])
            
            # Find the fund return impact slide
            fund_impact_slide = None
            for slide in slides:
                if 'fund_return_impact' in slide.get('type', ''):
                    fund_impact_slide = slide
                    break
            
            if fund_impact_slide:
                content = fund_impact_slide.get('content', {})
                fund_context = content.get('fund_context', {})
                
                print(f"\nFund Context in Slide:")
                print(f"  Fund Size: ${fund_context.get('fund_size', 0)/1e6:.0f}M")
                print(f"  Deployed: ${fund_context.get('deployed_capital', 0)/1e6:.0f}M")
                print(f"  Remaining: ${fund_context.get('remaining_capital', 0)/1e6:.0f}M")
                print(f"  Current DPI: {fund_context.get('current_dpi', 0):.1f}x")
                print(f"  Target DPI: {fund_context.get('target_dpi', 0):.1f}x")
                
                # Check DPI ladder
                dpi_ladder = content.get('dpi_contribution_ladder', [])
                if dpi_ladder:
                    print(f"\nDPI Contribution Ladder:")
                    for level in dpi_ladder[:3]:  # Show first 3 levels
                        print(f"  {level['dpi_contribution_pct']}: Needs {level['required_multiple']:.1f}x return ({level['achievability']})")
                
                # Check optimal check sizes
                companies = data.get('companies', [])
                if companies:
                    print(f"\nOptimal Check Sizes:")
                    for company in companies[:2]:
                        name = company.get('company', 'Unknown')
                        check = company.get('optimal_check_size', 0)
                        ownership = company.get('actual_ownership_pct', 0)
                        print(f"  {name}: ${check/1e6:.1f}M for {ownership*100:.1f}% ownership")
            else:
                print("ERROR: No fund return impact slide found")
                
        else:
            print(f"ERROR: {result.get('error', 'Unknown error')}")
    
    print(f"\n{'='*60}")
    print("Test completed!")

if __name__ == "__main__":
    asyncio.run(test_fund_context())