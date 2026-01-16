#!/usr/bin/env python3
"""Minimal test to verify deck generation works"""

import asyncio
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test():
    orch = UnifiedMCPOrchestrator()
    
    # Test with mock company data
    companies = [{
        'company': 'TestCo',
        'valuation': 100_000_000,
        'revenue': 10_000_000,
        'inferred_revenue': 10_000_000,
        'inferred_valuation': 100_000_000,
        'stage': 'Series A',
        'sector': 'SaaS',
        'business_model': 'B2B SaaS',
        'gross_margin': 0.75,
        'growth_rate': 1.5,
        'team_size': 50
    }]
    
    # Test slide generation
    slides = orch._generate_slides({'companies': companies})
    
    print(f"Generated {len(slides)} slides")
    
    for i, slide in enumerate(slides):
        print(f"\nSlide {i+1}:")
        if 'content' in slide:
            content = slide['content']
            if 'title' in content:
                print(f"  Title: {content['title']}")
            if 'metrics' in content:
                print(f"  Metrics: {content.get('metrics')}")
            if 'chart_data' in content and 'data' in content['chart_data']:
                data = content['chart_data']['data']
                if 'datasets' in data:
                    for ds in data['datasets']:
                        print(f"  Dataset {ds.get('label')}: {ds.get('data')}")

asyncio.run(test())