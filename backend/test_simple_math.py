#!/usr/bin/env python3
"""Direct test of investment advice calculation"""

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

orchestrator = UnifiedMCPOrchestrator()

# Test data for a YC company
test_company = {
    'company': 'NosoLabs',
    'is_yc': True,
    'yc_batch': 'S25',
    'safe_cap': 7_142_857,  # YC S25 $500k at $7.14M cap
    'stage': 'Seed',
    'business_model': 'saas',
    'revenue': 500,  # This might be in thousands
    'valuation': 7_142_857,
    'growth_rate': 1.5  # 50% annual growth
}

# Calculate investor advice
result = orchestrator._calculate_investor_advice(test_company)

print("="*60)
print("TEST COMPANY: NosoLabs (YC S25)")
print("="*60)
print(f"Input Revenue: ${test_company['revenue']:,.0f}")
print(f"Input Valuation: ${test_company['valuation']:,.0f}")
print(f"Input Growth Rate: {test_company['growth_rate']}")
print("-"*60)
print("INVESTOR ADVICE:")
print(f"Investment Amount: ${result['investment_amount']:,.0f}")
print(f"Entry Ownership: {result['ownership_at_entry']:.1f}%")
print(f"Exit Ownership: {result['ownership_at_exit']:.1f}%")
print("-"*60)
print("SCENARIOS:")
for scenario in result['scenarios']:
    print(f"\n{scenario['scenario']}:")
    print(f"  Exit Valuation: ${scenario['exit_valuation']:,.0f}")
    print(f"  MOIC: {scenario['moic']:.2f}x")
    print(f"  IRR: {scenario['irr']*100:.0f}%")

# Check if math is reasonable
base_case = result['scenarios'][1] if len(result['scenarios']) > 1 else result['scenarios'][0]
moic = base_case['moic']
irr = base_case['irr'] * 100
exit_val = base_case['exit_valuation']

print("-"*60)
print("SANITY CHECKS:")
print(f"✓ MOIC > 1x? {moic > 1}: MOIC = {moic:.2f}x")
print(f"✓ IRR > 0%? {irr > 0}: IRR = {irr:.0f}%")
print(f"✓ Exit > $10M? {exit_val > 10_000_000}: Exit = ${exit_val:,.0f}")

if moic < 1 or irr < 0 or exit_val < 10_000_000:
    print("\n❌ MATH IS STILL BROKEN!")
else:
    print("\n✅ MATH LOOKS REASONABLE!")