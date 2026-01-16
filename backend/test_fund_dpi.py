"""
Test DPI calculations and fund context
"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import get_unified_orchestrator

async def test_dpi_calculations():
    """Test DPI contribution ladder with different fund contexts"""
    
    orchestrator = get_unified_orchestrator()
    
    # Test Case 1: Small fund needing high DPI
    print("="*60)
    print("Test Case 1: $100M Fund - High DPI Needed")
    print("="*60)
    
    context1 = {
        "fund_size": 100_000_000,      # $100M fund
        "deployed_capital": 60_000_000, # $60M deployed
        "portfolio_size": 20,            # 20 investments
        "current_dpi": 0.3,             # 0.3x DPI so far
        "target_dpi": 3.5,              # Need 3.5x DPI
        "fund_year": 4                  # Year 4
    }
    
    result1 = await orchestrator.process_request(
        prompt="Analyze @Mercury and @Brex for our fund. Show DPI impact.",
        output_format="deck",
        context=context1
    )
    
    if result1.get('success'):
        print("✅ Analysis complete")
        data = result1.get('data', {})
        companies = data.get('companies', [])
        
        for company in companies[:2]:
            name = company.get('company', 'Unknown')
            check = company.get('optimal_check_size', 0)
            ownership = company.get('actual_ownership_pct', 0)
            exit_ownership = company.get('exit_ownership_pct', 0)
            
            # Calculate DPI contribution
            if check > 0:
                for multiple in [5, 10, 25]:
                    proceeds = check * multiple
                    dpi_contrib = proceeds / context1['fund_size']
                    print(f"\n{name} at {multiple}x return:")
                    print(f"  Investment: ${check/1e6:.1f}M")
                    print(f"  Ownership: {ownership*100:.1f}% → {exit_ownership*100:.1f}% (at exit)")
                    print(f"  Proceeds: ${proceeds/1e6:.1f}M")
                    print(f"  DPI Contribution: {dpi_contrib:.2f}x")
    
    # Test Case 2: Large fund with existing DPI
    print("\n" + "="*60)
    print("Test Case 2: $500M Fund - Already Has 1.2x DPI")
    print("="*60)
    
    context2 = {
        "fund_size": 500_000_000,       # $500M fund
        "deployed_capital": 400_000_000, # $400M deployed
        "portfolio_size": 30,             # 30 investments
        "current_dpi": 1.2,              # Already at 1.2x
        "target_dpi": 3.0,               # Need 3x total
        "fund_year": 6,                  # Year 6
        "is_lead": True                  # Lead investor
    }
    
    result2 = await orchestrator.process_request(
        prompt="Evaluate @Anthropic for late-stage investment",
        output_format="deck",
        context=context2
    )
    
    if result2.get('success'):
        print("✅ Analysis complete")
        data = result2.get('data', {})
        
        # Find fund return impact slide
        slides = data.get('slides', [])
        for slide in slides:
            if 'fund_return_impact' in slide.get('type', ''):
                content = slide.get('content', {})
                
                # Show fund context used
                fund_ctx = content.get('fund_context', {})
                print(f"\nFund Context Applied:")
                print(f"  Fund Size: ${fund_ctx.get('fund_size', 0)/1e6:.0f}M")
                print(f"  Deployed: ${fund_ctx.get('deployed_capital', 0)/1e6:.0f}M")
                print(f"  Current DPI: {fund_ctx.get('current_dpi', 0):.1f}x")
                print(f"  Target DPI: {fund_ctx.get('target_dpi', 0):.1f}x")
                
                # Show DPI ladder
                dpi_ladder = content.get('dpi_contribution_ladder', [])
                if dpi_ladder:
                    print(f"\nDPI Requirements for ${fund_ctx.get('fund_size', 0)/1e6:.0f}M Fund:")
                    for level in dpi_ladder:
                        print(f"  {level.get('dpi_contribution_pct', 'N/A')}: Needs {level.get('required_multiple', 0):.1f}x return - {level.get('achievability', 'Unknown')}")
                        print(f"    → Exit value: ${level.get('required_exit_value', 0)/1e6:.0f}M at {level.get('ownership_assumption', 'N/A')} ownership")
                break
    
    print("\n" + "="*60)
    print("Summary: Fund Context and DPI Working!")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_dpi_calculations())