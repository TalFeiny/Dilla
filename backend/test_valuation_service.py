#!/usr/bin/env python3
"""Test ValuationEngineService scenario generation"""

from app.services.valuation_engine_service import ValuationEngineService, ValuationRequest, Stage

service = ValuationEngineService()
request = ValuationRequest(
    company_name='TestCompany',
    stage=Stage.SERIES_B,
    revenue=10_000_000,  # $10M revenue
    growth_rate=2.0,  # 200% YoY
    last_round_valuation=100_000_000,  # $100M valuation
    total_raised=30_000_000,
    business_model='SaaS'
)

scenarios = service._generate_exit_scenarios(request)
print(f'Generated {len(scenarios)} scenarios:')
for s in scenarios[:5]:
    print(f'  {s.scenario}: Exit ${s.exit_value/1e6:.0f}M in {s.time_to_exit} years (prob: {s.probability*100:.0f}%)')

# Show bear/base/bull grouping
sorted_scenarios = sorted(scenarios, key=lambda x: x.exit_value)
bear = sorted_scenarios[:len(sorted_scenarios)//3]
base = sorted_scenarios[len(sorted_scenarios)//3:2*len(sorted_scenarios)//3]
bull = sorted_scenarios[2*len(sorted_scenarios)//3:]

print(f'\nBear scenarios (avg exit: ${sum(s.exit_value for s in bear)/len(bear)/1e6:.0f}M):')
for s in bear:
    print(f'  ${s.exit_value/1e6:.0f}M in {s.time_to_exit}y')

print(f'\nBase scenarios (avg exit: ${sum(s.exit_value for s in base)/len(base)/1e6:.0f}M):')  
for s in base:
    print(f'  ${s.exit_value/1e6:.0f}M in {s.time_to_exit}y')
    
print(f'\nBull scenarios (avg exit: ${sum(s.exit_value for s in bull)/len(bull)/1e6:.0f}M):')
for s in bull[:3]:
    print(f'  ${s.exit_value/1e6:.0f}M in {s.time_to_exit}y')