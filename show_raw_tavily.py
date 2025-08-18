import json

with open('pwerm_deel_response.json', 'r') as f:
    data = json.load(f)

# Get ALL the raw search results from different queries
market_research = data.get('market_research', {})

print("=== RAW TAVILY SEARCH QUERIES AND RESULTS ===\n")

# Show the raw results stored in different fields
raw_company_results = market_research.get('raw_company_results', [])
raw_exit_results = market_research.get('raw_exit_results', [])

print(f"COMPANY SEARCH RESULTS ({len(raw_company_results)} results):")
print("=" * 80)
for i, result in enumerate(raw_company_results[:3]):
    print(f"\nResult {i+1}:")
    print(f"Title: {result.get('title', '')}")
    print(f"URL: {result.get('url', '')}")
    print(f"Content snippet: {result.get('content', '')[:400]}...")
    print("-" * 40)

print(f"\n\nEXIT/M&A SEARCH RESULTS ({len(raw_exit_results)} results):")
print("=" * 80)
for i, result in enumerate(raw_exit_results[:5]):
    print(f"\nResult {i+1}:")
    print(f"Title: {result.get('title', '')}")
    print(f"URL: {result.get('url', '')}")
    print(f"Content snippet: {result.get('content', '')[:400]}...")
    print("-" * 40)

# Check if there's a direct tavily_search field
tavily_search = market_research.get('tavily_search', {})
if tavily_search:
    print("\n\nDIRECT TAVILY SEARCH DATA:")
    print("=" * 80)
    if tavily_search.get('answer'):
        print(f"TAVILY ANSWER: {tavily_search['answer'][:500]}...")
    if tavily_search.get('results'):
        print(f"\nFound {len(tavily_search['results'])} direct results")

# Show what search queries were likely used
print("\n\nLIKELY SEARCH QUERIES USED:")
print("=" * 80)
print('Based on the PWERM script, these queries were probably used:')
print('1. "Deel" competitors "SaaS-HR Tech"')
print('2. "Deel" "total funding" "amount raised" valuation latest')
print('3. "SaaS-HR Tech" companies "acquired" "for $" million billion')
print('4. "HR Tech" acquisition deals "bought" "sold"')
print('5. "HR Tech" exits acquisitions valuation')