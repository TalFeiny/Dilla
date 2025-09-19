#!/usr/bin/env python3
"""Direct test of cap table generation"""

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator
from app.services.pre_post_cap_table import PrePostCapTable

# Test cap table directly
cap_table_service = PrePostCapTable()

# YC company funding rounds
funding_rounds = [
    {
        'round': 'YC',
        'amount': 500_000,
        'valuation': 7_142_857,  # $500k on $7.14M cap
        'investors': ['Y Combinator']
    }
]

company_context = {
    'company_name': 'NosoLabs',
    'geography': 'San Francisco',
    'is_yc': True,
    'founding_year': 2025
}

company_data = {
    **company_context,
    'funding_rounds': funding_rounds
}
result = cap_table_service.calculate_full_cap_table_history(company_data)

print("="*60)
print("CAP TABLE GENERATION TEST")
print("="*60)
print(f"Company: {company_context['company_name']}")
print(f"YC Company: {company_context['is_yc']}")
print(f"Geography: {company_context['geography']}")
print("-"*60)

if 'current_cap_table' in result:
    cap_table = result['current_cap_table']
    print("CURRENT CAP TABLE:")
    total = 0
    for holder, ownership in cap_table.items():
        print(f"  {holder:30s}: {ownership:6.2f}%")
        total += ownership
    print("-"*40)
    print(f"  {'TOTAL':30s}: {total:6.2f}%")
    
    # Check YC ownership
    yc_ownership = cap_table.get('Y Combinator', cap_table.get('YC', 0))
    if yc_ownership:
        print(f"\n✅ YC Ownership: {yc_ownership:.1f}%")
        if 6 <= yc_ownership <= 8:
            print("   Correct range (6-8%)")
        else:
            print(f"   ⚠️ Unusual: expected ~7%, got {yc_ownership:.1f}%")
    else:
        print("\n❌ YC not in cap table!")
        
if 'rounds' in result:
    print("\nROUND DETAILS:")
    for round_detail in result['rounds']:
        print(f"  {round_detail['round']}:")
        print(f"    Pre-money: ${round_detail['pre_money']:,.0f}")
        print(f"    Investment: ${round_detail['investment']:,.0f}")
        print(f"    Post-money: ${round_detail['post_money']:,.0f}")
        print(f"    Dilution: {round_detail['dilution']*100:.1f}%")

print("="*60)

# Now test through orchestrator
print("\nTesting through orchestrator...")
orchestrator = UnifiedMCPOrchestrator()

test_company = {
    'company': 'NosoLabs',
    'is_yc': True,
    'yc_batch': 'S25',
    'stage': 'Seed',
    'funding_rounds': funding_rounds,
    'total_raised': 500_000,
    'geography': 'San Francisco'
}

# Generate cap table through orchestrator's method
cap_result = orchestrator._generate_basic_cap_table(test_company)
if cap_result:
    print("\n✅ Orchestrator cap table generated:")
    total = 0
    for holder, pct in cap_result.items():
        print(f"  {holder:30s}: {pct:6.2f}%")
        total += pct
    print("-"*40)
    print(f"  {'TOTAL':30s}: {total:6.2f}%")
else:
    print("\n❌ Orchestrator failed to generate cap table")