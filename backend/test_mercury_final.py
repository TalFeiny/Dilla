import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_mercury_cap_table():
    orch = UnifiedMCPOrchestrator()
    result = await orch.process_request({
        'prompt': 'Analyze @Mercury (YC W17) for investment',
        'output_format': 'analysis'
    })
    
    print('=== MERCURY CAP TABLE ANALYSIS ===\n')
    
    # Navigate the result structure
    if not result.get('success'):
        print(f"Error: {result.get('error')}")
        return
    
    # Get the companies data
    companies = []
    if 'results' in result:
        results = result['results']
        
        # Check different possible locations
        if 'data' in results and isinstance(results['data'], dict):
            # Format handler structure
            if 'companies' in results['data']:
                companies = results['data']['companies']
            elif 'skills' in results['data']:
                skills = results['data']['skills']
                if 'company-data-fetcher' in skills:
                    companies = skills['company-data-fetcher'].get('companies', [])
        
        # Check if companies are at the top level
        if not companies and 'companies' in results:
            companies = results['companies']
        
        # Check direct skill results
        if not companies:
            for key in results:
                if isinstance(results[key], dict) and 'companies' in results[key]:
                    companies = results[key]['companies']
                    break
    
    # Also check in the main result
    if not companies and 'entities' in result:
        entities = result['entities']
        if 'companies' in entities:
            # This gives us company names, now get the data
            company_names = entities['companies']
            print(f"Found companies: {company_names}")
    
    # Check skill chain results
    if not companies and 'skill_chain' in result:
        print(f"Skill chain executed: {result['skill_chain']}")
    
    # Print what we found
    print(f"Found {len(companies)} companies in results")
    
    if not companies:
        print("\nDEBUG: Result structure:")
        print(f"  Keys: {list(result.keys())}")
        if 'results' in result:
            print(f"  Results keys: {list(result['results'].keys())}")
            if 'data' in result['results']:
                print(f"  Data type: {type(result['results']['data'])}")
                if isinstance(result['results']['data'], dict):
                    print(f"  Data keys: {list(result['results']['data'].keys())[:10]}")
        return
    
    # Process Mercury data
    mercury = companies[0] if companies else {}
    
    print(f'\nCompany: {mercury.get("company", "Mercury")}')
    print(f'Is YC: {mercury.get("is_yc", "Unknown")}')
    print(f'YC Batch: {mercury.get("yc_batch", "Not detected")}')
    
    # Show key metrics
    if mercury:
        print(f'\n=== KEY METRICS ===')
        print(f'Revenue: ${mercury.get("revenue", 0)/1e6:.1f}M')
        print(f'Valuation: ${mercury.get("valuation", 0)/1e9:.1f}B')
        print(f'Total Raised: ${mercury.get("total_raised", 0)/1e6:.0f}M')
        print(f'Growth Rate: {mercury.get("growth_rate", 0)*100:.0f}%')
        
        # Show cap table
        cap_table = mercury.get('cap_table', {})
        if cap_table and not isinstance(cap_table, str):
            print(f'\n=== CAP TABLE ===')
            if 'current_cap_table' in cap_table:
                current = cap_table['current_cap_table']
                for holder, pct in sorted(current.items(), key=lambda x: x[1], reverse=True):
                    print(f'  {holder}: {pct:.1f}%')
            elif isinstance(cap_table, dict) and 'error' not in cap_table:
                # Direct cap table
                for holder, pct in sorted(cap_table.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0, reverse=True):
                    if isinstance(pct, (int, float)):
                        print(f'  {holder}: {pct:.1f}%')
        
        # Show YC SAFE conversion
        if mercury.get('is_yc'):
            print(f'\n=== YC SAFE CONVERSION ===')
            print(f'YC Check Size: ${mercury.get("yc_check_size", 500000):,.0f}')
            print(f'YC Ownership Target: {mercury.get("yc_ownership", 0.07)*100:.1f}%')
            print(f'SAFE Discount: {mercury.get("safe_discount", 0.20)*100:.0f}%')
            
            # Check if SAFE converted
            if cap_table and 'Y Combinator' in str(cap_table):
                print('Status: SAFE Converted at Series A')
            else:
                print('Status: SAFE Pending Conversion')

asyncio.run(test_mercury_cap_table())