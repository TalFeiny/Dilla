import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_mercury_cap_table():
    orch = UnifiedMCPOrchestrator()
    result = await orch.process_request({
        'prompt': 'Analyze @Mercury banking for investment - they are YC W17',
        'output_format': 'analysis'
    })
    
    print('=== MERCURY CAP TABLE ANALYSIS ===\n')
    
    if 'results' in result:
        results = result['results']
        
        # Handle the structured format
        if 'data' in results:
            # New format
            data = results['data']
            if 'companies' in data:
                companies = data['companies']
            else:
                companies = results.get('companies', [])
        elif 'company-data-fetcher' in results:
            # Old format
            companies = results['company-data-fetcher'].get('companies', [])
            if companies:
                mercury = companies[0]
                print(f'Company: {mercury.get("company")}')
                print(f'YC Batch: {mercury.get("yc_batch", "Not detected")}')
                print(f'Is YC: {mercury.get("is_yc", False)}')
                print(f'YC Check Size: ${mercury.get("yc_check_size", 0):,.0f}')
                print(f'Latest Valuation: ${mercury.get("valuation", 0)/1e9:.1f}B')
                print(f'Total Raised: ${mercury.get("total_raised", 0)/1e6:.0f}M')
                
                # Show funding rounds
                print('\n=== FUNDING ROUNDS ===')
                funding = mercury.get('funding_analysis', {}).get('rounds', [])
                for round_data in funding:
                    print(f"\n{round_data.get('round', 'Unknown')}:")
                    print(f"  Amount: ${round_data.get('amount', 0)/1e6:.1f}M")
                    print(f"  Investors: {', '.join(round_data.get('investors', []))}")
                
                # Show cap table evolution
                print('\n=== CAP TABLE EVOLUTION ===')
                cap_table = mercury.get('cap_table', {})
                
                if isinstance(cap_table, dict):
                    # Check for Sankey data
                    if 'sankey_data' in cap_table:
                        print('\nSankey Chart Data (for visualization):')
                        sankey = cap_table['sankey_data']
                        print('Nodes:', json.dumps(sankey.get('nodes', []), indent=2))
                        print('\nLinks (ownership flow):')
                        for link in sankey.get('links', []):
                            print(f"  {link['source']} -> {link['target']}: {link['value']}%")
                    
                    # Show current cap table
                    if 'current_cap_table' in cap_table:
                        print('\n=== CURRENT CAP TABLE (Post-Series C) ===')
                        current = cap_table['current_cap_table']
                        sorted_holders = sorted(current.items(), key=lambda x: x[1], reverse=True)
                        for holder, pct in sorted_holders:
                            print(f'  {holder}: {pct:.1f}%')
                    
                    # Show YC SAFE conversion details
                    if 'has_pending_safes' in cap_table:
                        print(f'\nPending SAFEs: {cap_table["has_pending_safes"]}')
                    
                    # Show cap table history snapshots
                    if 'history' in cap_table:
                        print('\n=== CAP TABLE SNAPSHOTS ===')
                        for snapshot in cap_table.get('history', []):
                            print(f"\n{snapshot.get('round_name')}:")
                            print(f"  Pre-money: ${snapshot.get('pre_money_valuation', 0)/1e6:.0f}M")
                            print(f"  Investment: ${snapshot.get('investment_amount', 0)/1e6:.0f}M")
                            print(f"  Post-money: ${snapshot.get('post_money_valuation', 0)/1e6:.0f}M")
                            
                            # Show ownership changes
                            if 'post_money_ownership' in snapshot:
                                print("  Post-money ownership:")
                                for holder, pct in snapshot['post_money_ownership'].items():
                                    if pct > 0:
                                        print(f"    {holder}: {pct:.1f}%")
                
                # Show liquidation preferences
                print('\n=== LIQUIDATION PREFERENCES ===')
                if 'waterfall' in mercury:
                    waterfall = mercury['waterfall']
                    print(f'Exit Value Tested: ${waterfall.get("exit_value", 0)/1e9:.1f}B')
                    if 'distributions' in waterfall:
                        for dist in waterfall['distributions']:
                            print(f'  {dist["stakeholder"]}: ${dist["amount"]/1e6:.0f}M ({dist["percentage"]:.1f}%)')
                
                # Investment recommendation
                print('\n=== INVESTMENT ANALYSIS ===')
                if 'investor_metrics' in mercury:
                    metrics = mercury['investor_metrics']
                    print(f'Entry Valuation: ${metrics.get("entry_valuation", 0)/1e9:.1f}B')
                    print(f'Target MOIC: {metrics.get("moic", 0):.1f}x')
                    print(f'Expected IRR: {metrics.get("irr", 0):.1%}')
                    print(f'Fund Fit Score: {metrics.get("fund_fit_score", 0):.1f}/10')
                    print(f'Recommendation: {metrics.get("recommendation", "N/A")}')

asyncio.run(test_mercury_cap_table())