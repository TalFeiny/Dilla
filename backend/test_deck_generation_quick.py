#!/usr/bin/env python3
"""Quick test of deck generation with new DPI and cap table slides"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_deck_generation():
    """Test that deck generation works with new slides"""
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test prompt with fund context
    prompt = "Analyze @Mercury and @Brex for our 234M fund with 109M remaining to deploy, currently at 0.5 DPI"
    
    # Mock context
    context = {
        'fund_size': 234_000_000,
        'remaining_capital': 109_000_000,
        'current_dpi': 0.5
    }
    
    print("Testing deck generation flow...")
    print(f"Prompt: {prompt}")
    print(f"Context: {json.dumps(context, indent=2)}")
    
    # Test entity extraction
    entities = await orchestrator._extract_entities(prompt)
    print(f"\nExtracted entities: {json.dumps(entities, indent=2)}")
    
    # Verify fund context parsing
    if entities:
        print(f"\n✅ Entity extraction working")
        print(f"  - Companies: {entities.get('companies', [])}")
        print(f"  - Fund size: ${entities.get('fund_size', 0)/1e6:.0f}M")
        print(f"  - Remaining: ${entities.get('remaining_capital', 0)/1e6:.0f}M")
    
    # Test helper methods are accessible
    try:
        # Test portfolio composition
        test_context = {'fund_size': 234_000_000}
        portfolio = orchestrator._parse_portfolio_composition(test_context, [])
        assert portfolio['total_companies'] > 0
        print("\n✅ Portfolio composition method working")
        
        # Test DPI calculation
        dpi_scenarios = orchestrator._calculate_dpi_impact_scenarios(
            companies=[],
            fund_size=234_000_000,
            deployed_capital=125_000_000,
            remaining_capital=109_000_000,
            current_dpi=0.5,
            portfolio_composition=portfolio
        )
        assert 'reserves_contribution' in dpi_scenarios
        print("✅ DPI impact calculation working")
        
        # Test forward cap table
        forward_table = orchestrator._calculate_forward_cap_table(
            {'valuation': 100_000_000, 'stage': 'Series A'},
            10_000_000,
            test_context
        )
        assert 'our_entry_ownership' in forward_table
        print("✅ Forward cap table calculation working")
        
        print("\n🎉 All deck generation components are working!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error in deck generation: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_deck_generation())
    if not result:
        print("\n⚠️ Issues found in deck generation")