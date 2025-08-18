import json

with open('pwerm_deel_response_new.json', 'r') as f:
    data = json.load(f)

# Extract the exit comparables
exit_comparables = data.get('market_research', {}).get('exit_comparables', [])

print("=== UPDATED EXTRACTION - M&A DEALS FOUND ===\n")

# Show deals with actual company names
deals_with_names = [d for d in exit_comparables if d.get('company') and d.get('company') != 'None' and d.get('company') != 'Unknown']

if deals_with_names:
    print(f"Found {len(deals_with_names)} deals with company names:\n")
    for i, deal in enumerate(deals_with_names[:15], 1):
        print(f"{i}. {deal.get('acquirer', 'Unknown')} acquired {deal.get('target', deal.get('company', 'Unknown'))}")
        if deal.get('deal_value', 0) > 0:
            print(f"   Deal Value: ${deal.get('deal_value', 0):,.0f}M")
        if deal.get('ev_revenue_multiple', 0) > 0:
            print(f"   Revenue Multiple: {deal.get('ev_revenue_multiple', 0):.1f}x")
        print(f"   Type: {deal.get('type', 'Unknown')}")
        print(f"   Source: {deal.get('source', 'Unknown')[:80]}...")
        print()
else:
    print("No deals with company names found in the updated extraction")
    print(f"\nTotal exit comparables found: {len(exit_comparables)}")
    if exit_comparables:
        print("\nShowing first 5 results:")
        for i, deal in enumerate(exit_comparables[:5], 1):
            print(f"\n{i}. Company: {deal.get('company', 'None')}")
            print(f"   Multiple: {deal.get('ev_revenue_multiple', 0):.1f}x")
            print(f"   Source: {deal.get('source', 'Unknown')[:80]}...")

# Check if Claude found any deals
openai_analysis = data.get('market_research', {}).get('openai_analysis', {})
if openai_analysis.get('extracted_multiples'):
    print("\n=== CLAUDE EXTRACTED DEALS ===")
    for mult in openai_analysis.get('extracted_multiples', [])[:5]:
        print(f"- {mult.get('company', 'Unknown')}: {mult.get('multiple', 0)}x ({mult.get('type', '')})")