#!/usr/bin/env python3
"""Test deck generation with late-stage companies (Series E, F, G)"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_late_stage_deck():
    """Test deck generation with late-stage Series F company"""
    print("Testing deck generation for late-stage company...")
    
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test with a prompt for late-stage company
    prompt = "Generate an investment deck for @SpaceX"
    output_format = "deck"
    
    print("\n1. Generating deck for SpaceX (Series F+)...")
    result = await orchestrator.process_request(
        prompt=prompt,
        output_format=output_format
    )
    
    if result.get("error"):
        print(f"❌ Error: {result['error']}")
        return
    
    # Check if data was fetched successfully
    companies = result.get("data", {}).get("companies", [])
    if companies:
        company = companies[0]
        print(f"\n✅ Company fetched: {company.get('company')}")
        print(f"   Stage: {company.get('stage')}")
        print(f"   Revenue: ${company.get('revenue', 0):,.0f} (inferred: ${company.get('inferred_revenue', 0):,.0f})")
        print(f"   Valuation: ${company.get('valuation', 0):,.0f} (inferred: ${company.get('inferred_valuation', 0):,.0f})")
        print(f"   Funding rounds: {len(company.get('funding_rounds', []))}")
        
        # Check if Stage enum handled properly
        stage = company.get('stage')
        if stage:
            stage_enum = orchestrator._get_stage_enum(stage)
            print(f"   Stage enum mapping: {stage} -> {stage_enum}")
        
        # Check if deck slides were generated
        slides = result.get("data", {}).get("slides", [])
        if slides:
            print(f"\n✅ Deck generated with {len(slides)} slides")
            for i, slide in enumerate(slides[:3]):  # Show first 3 slides
                print(f"   Slide {i+1}: {slide.get('title', 'Untitled')}")
        else:
            print("\n⚠️  No slides generated")
    else:
        print("\n❌ No company data returned")
    
    print("\n2. Testing Series E, F, G stage mappings...")
    test_stages = ["Series E", "Series F", "Series G", "Series H"]
    for stage_str in test_stages:
        enum_val = orchestrator._get_stage_enum(stage_str)
        normalized = orchestrator.gap_filler._normalize_stage_key(stage_str)
        print(f"   {stage_str}: normalized='{normalized}', enum={enum_val}")

if __name__ == "__main__":
    asyncio.run(test_late_stage_deck())