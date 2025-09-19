#!/usr/bin/env python3
"""Test liquidation preference impact on returns"""

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

orchestrator = UnifiedMCPOrchestrator()

# Test company with funding history
test_company = {
    'company': 'NosoLabs',
    'is_yc': True,
    'stage': 'Seed',
    'business_model': 'saas',
    'revenue': 500,  # $500k
    'valuation': 7_142_857,
    'growth_rate': 1.5,
    'total_raised': 2_500_000,  # $2.5M raised so far
    'funding_rounds': [
        {'round': 'Pre-Seed', 'amount': 500_000},
        {'round': 'YC', 'amount': 500_000},
        {'round': 'Seed', 'amount': 1_500_000}
    ],
    'cap_table': {
        'Founders': 55,
        'YC': 7,
        'Pre-Seed Investors': 8,
        'Seed Investors': 15,
        'Employees': 15
    }
}

result = orchestrator._calculate_investor_advice(test_company)

print("="*60)
print("LIQUIDATION PREFERENCE ANALYSIS")
print("="*60)
print(f"Company: {test_company['company']}")
print(f"Total Raised: ${test_company['total_raised']:,.0f}")
print(f"Our Investment: ${result['investment_amount']:,.0f}")
print(f"Our Ownership: {result['ownership_at_entry']:.1f}% → {result['ownership_at_exit']:.1f}%")
print("-"*60)

for scenario in result['scenarios']:
    print(f"\n{scenario['scenario']} (Exit: ${scenario['exit_valuation']:,.0f}):")
    print(f"  Without Preferences: ${scenario.get('proceeds_without_pref', 0):,.0f}")
    print(f"  With Preferences: ${scenario['proceeds']:,.0f}")
    
    diff = scenario['proceeds'] - scenario.get('proceeds_without_pref', scenario['proceeds'])
    if diff > 0:
        print(f"  Impact: +${diff:,.0f} (preference helps us)")
    elif diff < 0:
        print(f"  Impact: -${abs(diff):,.0f} (others' preferences hurt us)")
    else:
        print(f"  Impact: Neutral")
    
    print(f"  MOIC: {scenario['moic']:.2f}x")
    print(f"  IRR: {scenario['irr']*100:.0f}%")

print("-"*60)
print(f"Recommendation: {result['recommendation']}")
print(f"Fund Fit: {result['fund_fit']}")

# Show key insights
print("\nKEY INSIGHTS:")
base = result['scenarios'][1] if len(result['scenarios']) > 1 else result['scenarios'][0]
if base.get('liquidation_preference_impact') == 'negative':
    print("⚠️  Liquidation preference stack ahead of us reduces returns")
    print("   Consider negotiating for pari passu or senior preferences")
elif base.get('liquidation_preference_impact') == 'positive':
    print("✓  Our liquidation preference protects downside")
else:
    print("→  Liquidation preferences have minimal impact at these exit values")