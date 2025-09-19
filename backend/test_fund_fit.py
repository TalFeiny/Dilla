#!/usr/bin/env python3
"""Test fund fit and investment decision logic"""

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

orchestrator = UnifiedMCPOrchestrator()

# Your fund parameters (example)
FUND_SIZE = 100_000_000  # $100M fund
TARGET_OWNERSHIP = 0.10  # 10% target
FUND_RETURNER_THRESHOLD = 3.0  # Need 3x to return fund
MIN_CHECK = 500_000
MAX_CHECK = 5_000_000

# Test company
test_company = {
    'company': 'NosoLabs',
    'is_yc': True,
    'yc_batch': 'S25',
    'safe_cap': 7_142_857,
    'stage': 'Seed',
    'business_model': 'saas',
    'revenue': 500,  # $500k
    'valuation': 7_142_857,
    'growth_rate': 1.5
}

result = orchestrator._calculate_investor_advice(test_company)

print("="*60)
print("FUND INVESTMENT DECISION: NosoLabs")
print("="*60)

# Extract scenarios
base_case = result['scenarios'][1] if len(result['scenarios']) > 1 else result['scenarios'][0]
bull_case = result['scenarios'][2] if len(result['scenarios']) > 2 else base_case

print("FUND PARAMETERS:")
print(f"  Fund Size: ${FUND_SIZE:,.0f}")
print(f"  Target Check: ${MIN_CHECK:,.0f} - ${MAX_CHECK:,.0f}")
print(f"  Target Ownership: {TARGET_OWNERSHIP*100:.0f}%")
print(f"  Fund Returner Need: {FUND_RETURNER_THRESHOLD}x")

print("\nCOMPANY METRICS:")
print(f"  Current Revenue: $500K")
print(f"  Valuation: ${test_company['valuation']:,.0f}")
print(f"  Growth Rate: {(test_company['growth_rate']-1)*100 if test_company['growth_rate'] > 1 else test_company['growth_rate']*100:.0f}%")

print("\nINVESTMENT ANALYSIS:")
investment = result['investment_amount']
ownership = result['ownership_at_entry']
print(f"  Proposed Investment: ${investment:,.0f}")
print(f"  Entry Ownership: {ownership:.1f}%")
print(f"  Exit Ownership: {result['ownership_at_exit']:.1f}%")

print("\nRETURN SCENARIOS:")
print(f"  Base Case: {base_case['moic']:.1f}x MOIC, {base_case['irr']*100:.0f}% IRR")
print(f"  Bull Case: {bull_case['moic']:.1f}x MOIC, {bull_case['irr']*100:.0f}% IRR")

# FUND-SPECIFIC DECISION LOGIC
print("\n" + "="*60)
print("INVESTMENT DECISION:")
print("="*60)

# Decision factors
factors = {
    'ownership': ownership >= TARGET_OWNERSHIP * 100 * 0.7,  # At least 70% of target
    'moic': base_case['moic'] >= 3.0,  # 3x minimum
    'fund_returner': bull_case['moic'] * (investment/FUND_SIZE) >= 0.5,  # Could return 50% of fund
    'check_size': MIN_CHECK <= investment <= MAX_CHECK,
    'yc_premium': test_company.get('is_yc', False),  # YC companies have higher success rate
}

print("\nDECISION FACTORS:")
print(f"  ✓ Ownership sufficient ({ownership:.1f}% vs {TARGET_OWNERSHIP*100:.0f}% target): {'YES' if factors['ownership'] else 'NO'}")
print(f"  ✓ Base case MOIC > 3x ({base_case['moic']:.1f}x): {'YES' if factors['moic'] else 'NO'}")
print(f"  ✓ Fund returner potential: {'YES' if factors['fund_returner'] else 'NO'}")
print(f"  ✓ Check size in range: {'YES' if factors['check_size'] else 'YES'}")
print(f"  ✓ YC company premium: {'YES' if factors['yc_premium'] else 'NO'}")

# Score it
score = sum(factors.values())
total = len(factors)

print(f"\nSCORE: {score}/{total}")

# Make recommendation
if score >= 4:
    recommendation = "STRONG BUY - High conviction investment"
    action = f"Invest ${investment:,.0f} immediately"
elif score >= 3:
    recommendation = "BUY - Good risk/reward"
    action = f"Invest ${investment:,.0f} after quick diligence"
elif score >= 2:
    recommendation = "MAYBE - Needs more diligence"
    action = "Deep dive on traction and team"
else:
    recommendation = "PASS - Doesn't meet fund criteria"
    action = "Pass or wait for better terms"

print(f"\nRECOMMENDATION: {recommendation}")
print(f"ACTION: {action}")

# Specific concerns
print("\nKEY CONCERNS:")
if base_case['moic'] < 3:
    print(f"  ⚠️  Base case MOIC too low ({base_case['moic']:.1f}x) - need 3x minimum")
if ownership < TARGET_OWNERSHIP * 100:
    print(f"  ⚠️  Ownership too low ({ownership:.1f}%) - negotiate for more")
if base_case['exit_valuation'] < 100_000_000:
    print(f"  ⚠️  Exit size too small (${base_case['exit_valuation']/1e6:.0f}M) - not a fund returner")

# What would make it investable
print("\nWHAT WOULD CHANGE OUR MIND:")
if base_case['moic'] < 3:
    needed_val = investment * 3 / (result['ownership_at_exit']/100)
    print(f"  • Need exit valuation of ${needed_val:,.0f} for 3x MOIC")
    print(f"  • Or negotiate valuation down to ${test_company['valuation']*0.7:,.0f}")
if ownership < TARGET_OWNERSHIP * 100:
    needed_investment = TARGET_OWNERSHIP * test_company['valuation']
    print(f"  • Increase check size to ${needed_investment:,.0f} for {TARGET_OWNERSHIP*100:.0f}% ownership")

print("="*60)