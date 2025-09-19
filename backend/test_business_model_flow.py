#!/usr/bin/env python3
"""Test that business model flows through the entire valuation pipeline"""

import asyncio
from app.services.valuation_engine_service import ValuationEngineService, ValuationRequest, Stage, ValuationMethod
from app.services.intelligent_gap_filler import IntelligentGapFiller

async def test_valuation():
    engine = ValuationEngineService()
    gap_filler = IntelligentGapFiller()
    
    print('Testing Business Model → Valuation Flow')
    print('=' * 60)
    
    # Test data
    companies = [
        {
            'name': 'Dwelly',
            'description': 'AI-powered roll-up consolidating fragmented home services market',
            'revenue': 10_000_000,
            'growth_rate': 1.2,
            'expected_model': 'rollup',
            'expected_multiple_range': (3, 6)  # Roll-ups get 3-6x
        },
        {
            'name': 'ArtificialSocieties',
            'description': 'Foundation model infrastructure for autonomous AI agents',
            'revenue': 10_000_000,
            'growth_rate': 3.0,
            'expected_model': 'ai_first',
            'expected_multiple_range': (15, 30)  # AI-first gets 15-30x
        },
        {
            'name': 'RegularSaaS',
            'description': 'Cloud-based project management software platform',
            'revenue': 10_000_000,
            'growth_rate': 1.5,
            'expected_model': 'saas',
            'expected_multiple_range': (8, 12)  # SaaS gets 8-12x
        }
    ]
    
    for company in companies:
        # Detect business model
        detected_model = gap_filler._detect_company_category({
            'company': company['name'],
            'description': company['description']
        })
        
        # Create valuation request
        request = ValuationRequest(
            company_name=company['name'],
            stage=Stage.SERIES_A,
            revenue=company['revenue'],
            growth_rate=company['growth_rate'],
            business_model=detected_model,
            method=ValuationMethod.COMPARABLES
        )
        
        # Get valuation
        result = await engine.calculate_valuation(request)
        revenue_multiple = result.fair_value / company['revenue']
        
        # Check if multiple is in expected range
        min_mult, max_mult = company['expected_multiple_range']
        status = '✅' if min_mult <= revenue_multiple <= max_mult else '❌'
        
        print(f"\n{company['name']}:")
        print(f"  Model detected: {detected_model} (expected: {company['expected_model']})")
        print(f"  Valuation: ${result.fair_value:,.0f}")
        print(f"  Revenue Multiple: {revenue_multiple:.1f}x")
        print(f"  Expected Range: {min_mult}-{max_mult}x")
        print(f"  Status: {status}")

if __name__ == '__main__':
    asyncio.run(test_valuation())