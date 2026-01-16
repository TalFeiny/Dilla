#!/usr/bin/env python3
"""Test service integration after fixes"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_service_integration():
    """Test that all services are properly integrated"""
    print("=" * 80)
    print("TESTING SERVICE INTEGRATION")
    print("=" * 80)
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test with @Inven and @Farsight
    prompt = "Compare @Inven and @Farsight for our $250M fund"
    
    print(f"\nPrompt: {prompt}")
    print("-" * 40)
    
    # Clear cache
    orchestrator._tavily_cache.clear()
    orchestrator._company_cache.clear()
    
    # Process request
    result = await orchestrator.process_request(
        prompt=prompt,
        output_format="deck",
        context={}
    )
    
    # Check results
    if result and result.get('success'):
        results = result.get('results', {})
        
        print("\n✅ SUCCESS - Results received")
        print(f"Format: {results.get('format')}")
        print(f"Slides: {len(results.get('slides', []))}")
        
        # Check for PWERM results in shared_data
        pwerm_results = orchestrator.shared_data.get('pwerm_results', {})
        exit_scenarios = orchestrator.shared_data.get('exit_scenarios', [])
        
        print(f"\n📊 PWERM Results: {len(pwerm_results)} companies")
        for company_name, pwerm_data in pwerm_results.items():
            if isinstance(pwerm_data, dict):
                if 'bull' in pwerm_data:
                    print(f"  {company_name}:")
                    print(f"    - Bull MOIC: {pwerm_data['bull'].get('moic', 0):.1f}x")
                    print(f"    - Base MOIC: {pwerm_data['base'].get('moic', 0):.1f}x")
                    print(f"    - Bear MOIC: {pwerm_data['bear'].get('moic', 0):.1f}x")
        
        print(f"\n🎯 Exit Scenarios: {len(exit_scenarios)} companies")
        for scenario in exit_scenarios:
            print(f"  {scenario['company']}:")
            if 'scenarios' in scenario:
                scens = scenario['scenarios']
                if 'bull' in scens:
                    print(f"    - Has bull/bear/base scenarios ✓")
        
        # Check for scenario comparison slide
        scenario_slide = None
        for slide in results.get('slides', []):
            if slide.get('type') == 'scenario_comparison':
                scenario_slide = slide
                break
        
        if scenario_slide:
            print("\n📈 Scenario Comparison Slide: FOUND")
            content = scenario_slide.get('content', {})
            exit_scenarios_in_slide = content.get('exit_scenarios', [])
            print(f"  - Exit scenarios in slide: {len(exit_scenarios_in_slide)}")
            if exit_scenarios_in_slide:
                print("  - Sample scenario:")
                print(f"    {exit_scenarios_in_slide[0]}")
        else:
            print("\n⚠️ Scenario Comparison Slide: NOT FOUND")
        
        # Check companies data
        companies = orchestrator.shared_data.get('companies', [])
        print(f"\n🏢 Companies: {len(companies)}")
        for company in companies:
            name = company.get('company')
            revenue = company.get('revenue') or company.get('inferred_revenue')
            valuation = company.get('valuation') or company.get('inferred_valuation')
            business_model = company.get('business_model')
            
            print(f"  {name}:")
            print(f"    - Revenue: ${revenue:,.0f}" if revenue else "    - Revenue: None")
            print(f"    - Valuation: ${valuation:,.0f}" if valuation else "    - Valuation: None")
            print(f"    - Business Model: {business_model}")
            
            # Check for inferred values
            if not company.get('revenue') and company.get('inferred_revenue'):
                print(f"    - Using inferred revenue ✓")
            if not company.get('valuation') and company.get('inferred_valuation'):
                print(f"    - Using inferred valuation ✓")
        
        # Check for business model issues
        generic_models = [c for c in companies if c.get('business_model', '').lower() in ['saas', 'software', 'unknown']]
        if generic_models:
            print(f"\n⚠️ Generic business models found: {len(generic_models)} companies")
            for c in generic_models:
                print(f"  - {c.get('company')}: '{c.get('business_model')}'")
        
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        
        issues = []
        
        # Check for common issues
        if not pwerm_results:
            issues.append("❌ No PWERM results generated")
        elif not any('bull' in p for p in pwerm_results.values() if isinstance(p, dict)):
            issues.append("❌ PWERM results missing bull/bear/base scenarios")
        else:
            print("✅ PWERM service integration working")
        
        if not exit_scenarios:
            issues.append("❌ No exit scenarios in shared_data")
        else:
            print("✅ Exit scenarios properly stored")
        
        if not scenario_slide:
            issues.append("❌ Scenario comparison slide not generated")
        elif not content.get('exit_scenarios'):
            issues.append("❌ Scenario comparison slide missing exit_scenarios data")
        else:
            print("✅ Scenario comparison slide properly generated")
        
        if generic_models:
            issues.append(f"⚠️ {len(generic_models)} companies have generic business models")
        
        if any(not (c.get('revenue') or c.get('inferred_revenue')) for c in companies):
            issues.append("❌ Some companies missing revenue (actual or inferred)")
        else:
            print("✅ All companies have revenue values")
        
        if issues:
            print("\n⚠️ Issues found:")
            for issue in issues:
                print(f"  {issue}")
        else:
            print("\n🎉 All services properly integrated!")
        
    else:
        print("\n❌ FAILED - No results or error occurred")
        if result:
            print(f"Error: {result.get('error')}")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(test_service_integration())