#!/usr/bin/env python3
"""Test comprehensive functionality including valuation, cap table, and charts"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Now import after path is set
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_comprehensive():
    """Test all major components"""
    
    print("🚀 Testing comprehensive functionality")
    print("=" * 80)
    
    # Initialize orchestrator
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test with a valuation request
    test_prompt = "Value @Ramp using PWERM and create cap table snapshot"
    
    print(f"📝 Testing with prompt: {test_prompt}")
    print("-" * 80)
    
    try:
        # Process the request
        result = await orchestrator.process_request(
            prompt=test_prompt,
            output_format="analysis",
            context={
                "fund_size": 100_000_000,  # $100M fund
                "check_size_min": 1_000_000,  # $1M min
                "check_size_max": 10_000_000,  # $10M max
                "stage_focus": ["Series A", "Series B"],
                "sector_focus": ["fintech", "SaaS", "AI"]
            }
        )
        
        print("\n✅ Request processed successfully!")
        
        # Check skill chain execution
        if 'skill_chain' in result:
            skills = result['skill_chain'].get('skills', [])
            print(f"\n📋 Skills in chain: {len(skills)}")
            for skill in skills:
                print(f"  - {skill['name']}")
        
        # Check results
        if 'results' in result:
            results = result['results']
            
            # Look for valuation results
            if 'valuation' in results:
                val = results['valuation']
                print(f"\n💰 IPEV-Compliant Valuation Results:")
                # Check if valuation has the actual valuation data structure
                if 'valuation' in val and isinstance(val['valuation'], dict):
                    val_data = val['valuation']
                    print(f"  - Primary method: {val_data.get('method_used', 'Unknown')}")
                    print(f"  - Fair value: ${val_data.get('fair_value', 0):,.0f}")
                    print(f"  - DLOM discount: {val_data.get('dlom_discount', 0):.0%}")
                    
                    # Show methodology if present
                    if 'methodology' in val_data:
                        meth = val_data['methodology']
                        print(f"\n📊 IPEV Methodology:")
                        print(f"  - Standard: {meth.get('standard', 'Unknown')}")
                        print(f"  - Weighted average: ${meth.get('weighted_average_valuation', 0):,.0f}")
                        
                        # Show all methods used
                        if 'all_methods_used' in meth:
                            print(f"\n📈 All IPEV Methods Applied:")
                            for method_name, method_data in meth['all_methods_used'].items():
                                print(f"  - {method_name.upper()}: ${method_data.get('fair_value', 0):,.0f}")
                                print(f"    Method: {method_data.get('method', '')}")
                        
                        # Show data sources
                        if 'data_sources' in meth:
                            print(f"\n📚 Data Sources:")
                            for source in meth['data_sources'][:3]:  # Show first 3
                                print(f"  - {source}")
                    
                    if 'scenarios' in val_data:
                        print(f"\n🎯 PWERM Scenarios: {len(val_data['scenarios'])}")
                else:
                    # Fallback to old format (for backward compatibility)
                    print(f"  - PWERM valuation: ${val.get('pwerm_valuation', 0):,.0f}")
                    print(f"  - DCF valuation: ${val.get('dcf_valuation', 0):,.0f}")
                    print(f"  - Comps valuation: ${val.get('comps_valuation', 0):,.0f}")
                    print(f"  - Weighted average: ${val.get('weighted_valuation', 0):,.0f}")
            
            # Look for cap table
            if 'cap_table' in results:
                cap = results['cap_table']
                print(f"\n📊 Cap Table Snapshot:")
                if 'shareholders' in cap:
                    for holder in cap['shareholders'][:5]:  # Top 5
                        print(f"  - {holder.get('name')}: {holder.get('ownership', 0):.2%}")
                
                if 'history' in cap:
                    print(f"\n📈 Cap Table History: {len(cap['history'])} rounds")
            
            # Look for charts
            if 'charts' in results:
                charts = results['charts']
                print(f"\n📉 Charts Generated: {len(charts)}")
                for chart in charts:
                    print(f"  - {chart.get('title', 'Untitled')}: {chart.get('type', 'unknown')}")
            
            # Look for company data
            if 'companies' in results:
                companies = results['companies']
                if companies:
                    company = companies[0]
                    print(f"\n🏢 Company Data:")
                    print(f"  - Name: {company.get('company')}")
                    print(f"  - Website: {company.get('website_url', 'Not found')}")
                    print(f"  - Website scraped: {'website_analysis' in company}")
                    
                    # Check if website was analyzed
                    if 'website_analysis' in company:
                        web = company['website_analysis']
                        print(f"\n🌐 Website Analysis:")
                        print(f"  - Customers found: {len(web.get('customers', []))}")
                        print(f"  - Pricing extracted: {bool(web.get('pricing'))}")
                        print(f"  - Team size: {web.get('team_size', 'Unknown')}")
        
        # Check errors
        if 'errors' in result and result['errors']:
            print(f"\n⚠️ Errors encountered:")
            for error in result['errors']:
                print(f"  - {error}")
        
        # Save full result
        with open('test_comprehensive_result.json', 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n💾 Full result saved to test_comprehensive_result.json")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_comprehensive())