import asyncio
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test():
    orch = UnifiedMCPOrchestrator()
    result = await orch.process_request({
        'prompt': 'Analyze @Mercury for investment',
        'output_format': 'analysis'
    })
    
    # Check key calculation results
    if 'results' in result:
        results = result['results']
        print('=== CALCULATION CHECK ===')
        
        # Check if we have company data
        if 'company-data-fetcher' in results:
            companies = results['company-data-fetcher'].get('companies', [])
            if companies:
                company = companies[0]
                print(f'Company: {company.get("company")}')
                print(f'Revenue: ${company.get("revenue", 0):,.0f}')
                print(f'Valuation: ${company.get("valuation", 0):,.0f}')
                print(f'Growth Rate: {company.get("growth_rate", 0):.1%}')
                print(f'Is YC: {company.get("is_yc", False)}')
                
                # Check cap table
                cap_table = company.get('cap_table', {})
                if cap_table and not isinstance(cap_table, dict) or 'error' not in cap_table:
                    print(f'\nCap Table:')
                    if isinstance(cap_table, dict):
                        for holder, pct in cap_table.items():
                            if holder != 'error':
                                print(f'  {holder}: {pct}%')
                
                # Check valuation
                if 'estimated_valuation' in company:
                    est_val = company['estimated_valuation']
                    print(f'\nValuation Analysis:')
                    print(f'  Estimated: ${est_val.get("estimated_valuation", 0):,.0f}')
                    print(f'  Method: {est_val.get("primary_method", "Unknown")}')
                    print(f'  Multiple: {est_val.get("revenue_multiple", 0):.1f}x')
                
                # Check investment metrics
                if 'investor_metrics' in company:
                    metrics = company['investor_metrics']
                    print(f'\nInvestor Metrics:')
                    print(f'  MOIC: {metrics.get("moic", 0):.1f}x')
                    print(f'  IRR: {metrics.get("irr", 0):.1%}')
                    print(f'  Fund Fit: {metrics.get("fund_fit_score", 0):.1f}/10')
        
        # Check valuation engine results
        if 'valuation-engine' in results:
            val_results = results['valuation-engine']
            print(f'\nValuation Engine:')
            print(f'  Status: {"Success" if not val_results.get("error") else "Error"}')
            if 'valuation' in val_results:
                val = val_results['valuation']
                print(f'  PWERM: ${val.get("pwerm", {}).get("enterprise_value", 0):,.0f}')
                print(f'  DCF: ${val.get("dcf", {}).get("enterprise_value", 0):,.0f}')
    else:
        print('No results found')
        print('Keys:', result.keys())

asyncio.run(test())