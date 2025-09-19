#!/usr/bin/env python3
"""Comprehensive test for cap table generation in deck"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import get_unified_orchestrator
from decimal import Decimal

def print_cap_table_detailed(cap_table_data):
    """Print detailed cap table information"""
    print("\n" + "="*80)
    print("CAP TABLE DETAILED ANALYSIS")
    print("="*80)
    
    if not cap_table_data:
        print("❌ No cap table data found")
        return
    
    # Print historical rounds
    if 'history' in cap_table_data or 'rounds' in cap_table_data:
        print("\n📊 FUNDING HISTORY:")
        print("-" * 40)
        
        rounds = cap_table_data.get('history', cap_table_data.get('rounds', []))
        for i, round_data in enumerate(rounds):
            print(f"\n Round {i+1}: {round_data.get('round_name', 'Unknown')}")
            print(f"  Date: {round_data.get('date', 'N/A')}")
            print(f"  Pre-money: ${round_data.get('pre_money_valuation', 0):,.0f}")
            print(f"  Investment: ${round_data.get('investment_amount', 0):,.0f}")
            print(f"  Post-money: ${round_data.get('post_money_valuation', 0):,.0f}")
            
            # Show ownership changes
            if 'post_money_ownership' in round_data:
                print(f"  Post-round ownership:")
                for investor, ownership in round_data['post_money_ownership'].items():
                    if isinstance(ownership, (int, float, Decimal)):
                        print(f"    • {investor}: {ownership:.2%}")
                    else:
                        print(f"    • {investor}: {ownership}")
            
            if 'new_investors' in round_data:
                print(f"  New investors: {', '.join(round_data['new_investors'])}")
    
    # Print current cap table
    if 'current_cap_table' in cap_table_data:
        print("\n📈 CURRENT CAP TABLE:")
        print("-" * 40)
        
        current = cap_table_data['current_cap_table']
        if isinstance(current, dict):
            total_ownership = 0
            for investor, ownership in current.items():
                if isinstance(ownership, (int, float, Decimal)):
                    print(f"  {investor}: {ownership:.2%}")
                    total_ownership += float(ownership)
                else:
                    print(f"  {investor}: {ownership}")
            print(f"\n  Total: {total_ownership:.2%}")
    
    # Print current ownership (alternative format)
    elif 'current_ownership' in cap_table_data:
        print("\n📈 CURRENT OWNERSHIP:")
        print("-" * 40)
        
        total_ownership = 0
        for investor, ownership in cap_table_data['current_ownership'].items():
            if isinstance(ownership, (int, float, Decimal)):
                print(f"  {investor}: {ownership:.2%}")
                total_ownership += float(ownership)
            else:
                print(f"  {investor}: {ownership}")
        print(f"\n  Total: {total_ownership:.2%}")
    
    # Print exit scenarios
    if 'final_cap_table_at_exit' in cap_table_data:
        print("\n💰 EXIT SCENARIOS:")
        print("-" * 40)
        
        exit_data = cap_table_data['final_cap_table_at_exit']
        if isinstance(exit_data, dict):
            for scenario_name, distributions in exit_data.items():
                if isinstance(distributions, dict):
                    print(f"\n  {scenario_name}:")
                    for investor, amount in distributions.items():
                        if isinstance(amount, (int, float)):
                            print(f"    • {investor}: ${amount:,.0f}")
                        else:
                            print(f"    • {investor}: {amount}")
    
    # Print waterfall data
    if 'waterfall_data' in cap_table_data:
        print("\n🏔️ LIQUIDATION WATERFALL:")
        print("-" * 40)
        
        waterfall = cap_table_data['waterfall_data']
        if isinstance(waterfall, list):
            for scenario in waterfall[:3]:  # First 3 scenarios
                if isinstance(scenario, dict):
                    exit_value = scenario.get('exit_value', 0)
                    print(f"\n  Exit at ${exit_value:,.0f}:")
                    
                    if 'distributions' in scenario:
                        for dist in scenario['distributions']:
                            investor = dist.get('investor', 'Unknown')
                            amount = dist.get('amount', 0)
                            ownership = dist.get('ownership', 0)
                            print(f"    • {investor}: ${amount:,.0f} ({ownership:.1%})")
    
    # Print key metrics
    if 'total_raised' in cap_table_data:
        print("\n📊 KEY METRICS:")
        print("-" * 40)
        print(f"  Total raised: ${cap_table_data['total_raised']:,.0f}")
    
    if 'num_rounds' in cap_table_data:
        print(f"  Number of rounds: {cap_table_data['num_rounds']}")
    
    if 'founder_dilution' in cap_table_data:
        dilution = cap_table_data['founder_dilution']
        if isinstance(dilution, (int, float, Decimal)):
            print(f"  Founder dilution: {dilution:.2%}")
        else:
            print(f"  Founder dilution: {dilution}")
    
    if 'total_pro_rata_deployed' in cap_table_data:
        print(f"  Pro-rata deployed: ${cap_table_data['total_pro_rata_deployed']:,.0f}")
    
    # Print fund performance metrics
    if 'fund_performance_metrics' in cap_table_data:
        print("\n📈 FUND PERFORMANCE:")
        print("-" * 40)
        
        metrics = cap_table_data['fund_performance_metrics']
        if isinstance(metrics, dict):
            for metric_name, value in metrics.items():
                if isinstance(value, (int, float)):
                    if 'multiple' in metric_name.lower() or 'roi' in metric_name.lower():
                        print(f"  {metric_name}: {value:.2f}x")
                    elif 'irr' in metric_name.lower() or 'rate' in metric_name.lower():
                        print(f"  {metric_name}: {value:.1%}")
                    else:
                        print(f"  {metric_name}: ${value:,.0f}")
                else:
                    print(f"  {metric_name}: {value}")

async def test_cap_table_generation():
    """Test cap table generation with detailed output"""
    orchestrator = get_unified_orchestrator()
    
    # Test prompt requesting cap table
    prompt = "Create a pitch deck for @Ramp with detailed cap table analysis showing all funding rounds and ownership evolution"
    
    print(f"Testing prompt: {prompt}")
    print("-" * 80)
    
    try:
        # Clear cache for fresh results
        orchestrator._tavily_cache.clear()
        
        # Process request with deck format
        result = await orchestrator.process_request(
            prompt=prompt,
            output_format='deck',
            context={
                'deckType': 'pitch',
                'includeValuation': True,
                'includeCapTable': True,
                'detailedCapTable': True
            }
        )
        
        # Check structure
        print("\n📋 RESULT STRUCTURE:")
        print(f"  Top-level keys: {list(result.keys())[:10]}")
        
        # Check for slides
        slides = result.get('results', {}).get('slides', [])
        if slides:
            print(f"\n✅ Generated {len(slides)} slides")
            
            # Find cap table slide
            cap_table_slide = None
            for slide in slides:
                if 'cap' in slide.get('template', '').lower() or \
                   'cap' in slide.get('content', {}).get('title', '').lower():
                    cap_table_slide = slide
                    print(f"  ✅ Found cap table slide: {slide.get('content', {}).get('title')}")
                    break
            
            if cap_table_slide and 'cap_table' in cap_table_slide.get('content', {}):
                print("\n📊 CAP TABLE IN SLIDE:")
                cap_data = cap_table_slide['content']['cap_table']
                print_cap_table_detailed(cap_data)
        
        # Check valuation engine data
        val_engine = result.get('results', {}).get('data', {}).get('valuation-engine', {})
        if val_engine and 'cap_table' in val_engine:
            print("\n📊 CAP TABLE FROM VALUATION ENGINE:")
            print_cap_table_detailed(val_engine['cap_table'])
        
        # Check deck storytelling data
        deck_data = result.get('results', {}).get('data', {}).get('deck-storytelling', {})
        if deck_data:
            deck_content = deck_data.get('deck_content', {})
            
            # Check narrative for cap table
            if 'narrative' in deck_content:
                for section in deck_content['narrative']:
                    if isinstance(section, dict) and 'cap_table' in str(section).lower():
                        print("\n📝 CAP TABLE IN NARRATIVE:")
                        if 'cap_table' in section:
                            print_cap_table_detailed(section['cap_table'])
                        elif 'content' in section:
                            print(f"  {section['content'][:500]}...")
        
        # Save full result
        with open('cap_table_test_result.json', 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print("\n✅ Full result saved to cap_table_test_result.json")
        
        # Check if cap table was generated
        has_cap_table = False
        if val_engine and 'cap_table' in val_engine:
            has_cap_table = True
        
        if has_cap_table:
            print("\n✅ CAP TABLE SUCCESSFULLY GENERATED")
        else:
            print("\n❌ NO CAP TABLE FOUND IN RESULTS")
            print("\nAvailable data keys:")
            for skill, data in result.get('results', {}).get('data', {}).items():
                print(f"  {skill}: {list(data.keys())[:10] if isinstance(data, dict) else type(data)}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_cap_table_generation())