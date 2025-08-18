import json

with open('pwerm_deel_response.json', 'r') as f:
    data = json.load(f)
    
# Extract Tavily search results
market_research = data.get('market_research', {})
exit_comparables = market_research.get('exit_comparables', [])[:10]
competitors = market_research.get('competitors', [])[:5]
company_intelligence = market_research.get('company_intelligence', {})
market_dynamics = market_research.get('market_dynamics', {})

print('=== EXIT COMPARABLES FROM TAVILY ===')
for comp in exit_comparables:
    print(f"Company: {comp.get('company')}")
    print(f"  Valuation: ${comp.get('valuation', 0)}M")
    print(f"  Revenue: ${comp.get('revenue', 0)}M")
    print(f"  Multiple: {comp.get('ev_revenue_multiple', 0)}x")
    print(f"  Date: {comp.get('date', 'Unknown')}")
    print(f"  Type: {comp.get('type', 'Unknown')}")
    print(f"  Source: {comp.get('source', 'Unknown')[:100]}...")
    print()

print('\n=== COMPETITORS FOUND ===')
for comp in competitors:
    print(f"- {comp.get('name')} | {comp.get('description', '')[:80]}...")

print('\n=== COMPANY INTELLIGENCE ===')
print(f"Revenue: {company_intelligence.get('revenue', 'Not found')}")
print(f"Valuation: {company_intelligence.get('valuation', 'Not found')}")
print(f"Growth Rate: {company_intelligence.get('growth_rate', 'Not found')}")
print(f"Funding: {company_intelligence.get('funding', 'Not found')}")

print('\n=== MARKET DYNAMICS ===')
print(f"Market Size: {market_dynamics.get('market_size', 'Not found')}")
print(f"Growth Rate: {market_dynamics.get('growth_rate', 'Not found')}")