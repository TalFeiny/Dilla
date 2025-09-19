import sys
sys.path.append('.')
from app.services.intelligent_gap_filler import IntelligentGapFiller
import asyncio

# Create gap filler instance
gap_filler = IntelligentGapFiller()

# Test what ACTUALLY gets called in the orchestrator flow
test_company = {
    'company': 'Dwelly',
    'stage': 'Series A', 
    'business_model': 'ai_first',
    'revenue': None,
    'gross_margin': None,
    'category': 'ai_first',
    'search_results': {},  # Simulate having search results
    'funding_rounds': [],
    'team_size': 25,
    'pricing_tiers': {'has_enterprise': True}
}

print('=== TRACING THE ACTUAL FLOW ===')
print(f'Initial revenue: {test_company.get("revenue")}')
print(f'Initial gross_margin: {test_company.get("gross_margin")}')

# Step 1: What the orchestrator calls for inference
print('\n1. Orchestrator calls infer_from_stage_benchmarks...')
async def test_inference():
    inferences = await gap_filler.infer_from_stage_benchmarks(
        test_company,
        ['revenue', 'gross_margin', 'growth_rate']
    )
    
    print('   Inferred fields:')
    for field, result in inferences.items():
        if hasattr(result, 'value'):
            print(f'   - {field}: {result.value}')
    
    # Apply inferences like orchestrator does
    for field, inference in inferences.items():
        if hasattr(inference, 'value'):
            current = test_company.get(field)
            if current is None or current == 0:
                test_company[field] = inference.value
                print(f'   Applied {field} = {inference.value}')
    
    return inferences

inferences = asyncio.run(test_inference())

print(f'\nAfter inference:')
print(f'  revenue: {test_company.get("revenue")}')
print(f'  gross_margin: {test_company.get("gross_margin")}')

# Show the actual inferred revenue with adjustments
if 'revenue' in inferences and hasattr(inferences['revenue'], 'value'):
    print(f'  Revenue was inferred with value: {inferences["revenue"].value}')
    print(f'  Reasoning: {inferences["revenue"].reasoning}')

# Step 2: What extract_compute_intensity does
print('\n2. Orchestrator calls extract_compute_intensity...')
compute_data = gap_filler.extract_compute_intensity(test_company)
print(f'   Computed gross_margin: {compute_data["gross_margin"]}%')

# This is what orchestrator should do but check if it does:
test_company['gross_margin'] = compute_data['gross_margin'] / 100
print(f'   Should set root gross_margin to: {test_company["gross_margin"]}')

# Step 3: What synthesize_investment_case sees
print('\n3. Later, synthesize_investment_case is called...')
print(f'   It sees revenue: {test_company.get("revenue")}')
print(f'   It sees gross_margin: {test_company.get("gross_margin")}')

# Check what actually happens
result = gap_filler.synthesize_investment_case(test_company)
print(f'   Final inferred revenue: ${result["revenue_analysis"]["inferred_revenue"]:,.0f}')
