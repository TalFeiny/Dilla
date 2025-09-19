#!/usr/bin/env python3
"""Detailed test showing each step of the calculation"""

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

orchestrator = UnifiedMCPOrchestrator()

# Test with realistic YC company data
test_company = {
    'company': 'NosoLabs',
    'is_yc': True,
    'yc_batch': 'S25',
    'safe_cap': 7_142_857,  # YC S25 $500k at $7.14M cap
    'stage': 'Seed',
    'business_model': 'saas',
    'revenue': 500,  # What we extract: might be 500 or 500k
    'valuation': 7_142_857,
    'growth_rate': 1.5  # 50% growth
}

print("="*60)
print("STEP-BY-STEP CALCULATION")
print("="*60)

# Step 1: Revenue conversion
revenue = test_company['revenue']
print(f"1. Input revenue: {revenue}")

if revenue > 0 and revenue < 100:  # Likely millions
    print(f"   → Detected as millions: {revenue}M")
    revenue = revenue * 1_000_000
elif revenue > 0 and revenue < 10_000:  # Likely thousands
    print(f"   → Detected as thousands: {revenue}K")
    revenue = revenue * 1_000

print(f"   → Converted revenue: ${revenue:,.0f}")

# Step 2: Growth rate
growth_rate = test_company['growth_rate']
print(f"\n2. Input growth rate: {growth_rate}")
if growth_rate > 10:
    print(f"   → Detected as percentage: {growth_rate}%")
    growth_rate = 1 + (growth_rate / 100)
elif growth_rate < 1 and growth_rate > 0:
    print(f"   → Detected as decimal: {growth_rate}")
    growth_rate = 1 + growth_rate
print(f"   → Annual growth multiplier: {growth_rate}x ({(growth_rate-1)*100:.0f}% per year)")

# Step 3: Revenue projection
years = 5
print(f"\n3. Projecting {years} years forward:")
for year in range(1, years + 1):
    year_revenue = revenue * (growth_rate ** year)
    print(f"   Year {year}: ${year_revenue:,.0f}")

projected_revenue = revenue * (growth_rate ** years)
print(f"   → Final projected revenue: ${projected_revenue:,.0f}")

# Step 4: Exit valuations
multiples = [3, 10, 20]  # SaaS multiples
print(f"\n4. Exit valuations (SaaS multiples):")
for mult in multiples:
    exit_val = projected_revenue * mult
    print(f"   {mult}x revenue = ${exit_val:,.0f}")

# Step 5: Investment returns
investment = 1_000_000
valuation = test_company['valuation']
ownership_entry = (investment / (valuation + investment)) * 100
ownership_exit = ownership_entry * 0.51  # Assume 49% dilution

print(f"\n5. Investment returns ($1M investment):")
print(f"   Entry ownership: {ownership_entry:.1f}%")
print(f"   Exit ownership: {ownership_exit:.1f}%")

for mult in multiples:
    exit_val = projected_revenue * mult
    proceeds = (ownership_exit / 100) * exit_val
    moic = proceeds / investment
    irr = ((proceeds / investment) ** (1/years)) - 1
    print(f"\n   {mult}x multiple scenario:")
    print(f"     Exit valuation: ${exit_val:,.0f}")
    print(f"     Your proceeds: ${proceeds:,.0f}")
    print(f"     MOIC: {moic:.2f}x")
    print(f"     IRR: {irr*100:.0f}%")

print("="*60)
print("\nPROBLEM DIAGNOSIS:")
if revenue < 1_000_000:
    print("⚠️  Revenue seems too low for a funded startup")
    print(f"   Current: ${revenue:,.0f}")
    print(f"   Expected: $500K-$2M for YC company")
if projected_revenue < 10_000_000:
    print("⚠️  5-year projected revenue seems too low")
    print(f"   Current: ${projected_revenue:,.0f}")
    print(f"   Expected: $10M-$50M for successful YC company")