import json

with open('pwerm_deel_response.json', 'r') as f:
    data = json.load(f)

# Get the actual competitors found
competitors = data.get('market_research', {}).get('competitors', [])
exit_comparables = data.get('market_research', {}).get('exit_comparables', [])

print('=== DEEL SEARCH - KEY FINDINGS ===')
print()

# Look for Deel-specific data
company_intel = data.get('market_research', {}).get('company_intelligence', {})
if company_intel:
    print('Company Intelligence:')
    for key, value in company_intel.items():
        if value and value != 'Not found':
            print(f'  {key}: {value}')
    print()

# Show actual competitor companies found
print('=== ACTUAL COMPETITORS FOUND BY TAVILY ===')
if competitors:
    for comp in competitors[:10]:
        if comp.get('name'):
            print(f"- {comp.get('name')}: {comp.get('description', '')[:100]}...")
else:
    print('No competitors found')
print()

# Show exit comparables with actual company names
print('=== EXIT COMPARABLES WITH COMPANY NAMES ===')
real_exits = [e for e in exit_comparables if e.get('company') and e.get('company') != 'None']
if real_exits:
    for comp in real_exits[:10]:
        print(f"Company: {comp.get('company')}")
        print(f"  Multiple: {comp.get('ev_revenue_multiple', 0)}x")
        print(f"  Type: {comp.get('type', '')}")
        print(f"  Date: {comp.get('date', '')}")
        print()
else:
    print('No real company exits found with names')

# Check openai_analysis for extracted data
openai_analysis = data.get('market_research', {}).get('openai_analysis', {})
if openai_analysis and openai_analysis.get('extracted_multiples'):
    print('\n=== CLAUDE EXTRACTED MULTIPLES ===')
    for mult in openai_analysis.get('extracted_multiples', [])[:5]:
        print(f"- {mult.get('company', 'Unknown')}: {mult.get('multiple', 0)}x ({mult.get('type', '')})")

# Show raw search snippets that mention Deel
print('\n=== RAW SEARCH RESULTS MENTIONING DEEL ===')
raw_results = data.get('market_research', {}).get('raw_exit_results', [])
for result in raw_results:
    content = result.get('content', '')
    if 'Deel' in content or 'deel' in content.lower():
        print(f"Title: {result.get('title', '')}")
        print(f"Content: {content[:300]}...")
        print()