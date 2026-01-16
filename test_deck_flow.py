#!/usr/bin/env python3
"""Test script to trace deck generation flow and identify issues"""

import asyncio
import json
import sys

import pytest

sys.path.append('/Users/admin/code/dilla-ai/backend')


@pytest.mark.asyncio
async def test_deck_generation():
    print("\n=== TESTING DECK GENERATION FLOW ===\n")
    
    # Test the unified brain endpoint directly
    import httpx
    
    test_prompt = "Compare @Inven and @Farsight for investment"
    
    print("1. Testing unified brain endpoint...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://localhost:8000/api/agent/unified-brain",
                json={
                    "prompt": test_prompt,
                    "output_format": "deck",
                    "context": {}
                },
                timeout=60.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check what we got back
                print(f"✓ Response received: {response.status_code}")
                print(f"  Success: {data.get('success')}")
                
                result = data.get('result', {})
                print(f"  Format: {result.get('format')}")
                
                slides = result.get('slides', [])
                print(f"  Slides count: {len(slides)}")
                
                # Analyze each slide
                print("\n2. Analyzing slides...")
                for idx, slide in enumerate(slides):
                    slide_type = slide.get('type')
                    content = slide.get('content', {})
                    
                    print(f"\n  Slide {idx+1}: {slide_type}")
                    print(f"    Title: {content.get('title', 'No title')}")
                    
                    # Check for chart data
                    if content.get('chart_data'):
                        chart_data = content['chart_data']
                        print(f"    ✓ Has chart: {chart_data.get('type')}")
                        data = chart_data.get('data', {})
                        if data:
                            print(f"      Labels: {data.get('labels', [])[:3]}...")
                            datasets = data.get('datasets', [])
                            print(f"      Datasets: {len(datasets)}")
                            if datasets and datasets[0].get('data'):
                                print(f"      First dataset has {len(datasets[0]['data'])} data points")
                    
                    # Check for devices (Sankey diagrams)
                    if content.get('devices'):
                        devices = content['devices']
                        print(f"    ✓ Has devices: {len(devices)}")
                        for device in devices:
                            print(f"      Device type: {device.get('type')}")
                            if device.get('type') == 'side_by_side_sankey':
                                c1_data = device.get('company1_data', {})
                                c2_data = device.get('company2_data', {})
                                print(f"      Company 1 nodes: {len(c1_data.get('nodes', []))}")
                                print(f"      Company 1 links: {len(c1_data.get('links', []))}")
                                print(f"      Company 2 nodes: {len(c2_data.get('nodes', []))}")
                                print(f"      Company 2 links: {len(c2_data.get('links', []))}")
                    
                    # Check for empty slides
                    if not content.get('chart_data') and not content.get('devices') and not content.get('bullets') and not content.get('companies'):
                        print(f"    ⚠ EMPTY SLIDE!")
                
                # Check specific problematic slides
                print("\n3. Checking problematic slides...")
                
                # Find cap table slide
                cap_table_slides = [s for s in slides if s.get('type') == 'cap_table_comparison']
                if cap_table_slides:
                    cap_slide = cap_table_slides[0]
                    content = cap_slide.get('content', {})
                    print("\n  Cap Table Slide:")
                    print(f"    Metrics: {json.dumps(content.get('metrics', {}), indent=6)}")
                    devices = content.get('devices', [])
                    if devices:
                        for device in devices:
                            if device.get('type') == 'side_by_side_sankey':
                                print(f"    Sankey data present: Yes")
                                c1_data = device.get('company1_data', {})
                                if c1_data:
                                    print(f"    Company 1 Sankey nodes sample:")
                                    for node in c1_data.get('nodes', [])[:3]:
                                        print(f"      - {node}")
                else:
                    print("  ✗ No cap table slide found!")
                
                # Find business model slide
                biz_slides = [s for s in slides if 'business' in s.get('type', '').lower() or 'business' in s.get('content', {}).get('title', '').lower()]
                if biz_slides:
                    for biz_slide in biz_slides:
                        content = biz_slide.get('content', {})
                        print(f"\n  Business Model Slide: {content.get('title')}")
                        companies = content.get('companies', [])
                        if companies:
                            print(f"    Companies data: {len(companies)} companies")
                            for comp in companies[:2]:
                                print(f"      - {comp.get('company')}: {comp.get('what_they_do', 'No description')[:100]}...")
                        else:
                            print(f"    ✗ No companies data!")
                
                # Find scenario analysis  
                scenario_slides = [s for s in slides if 'scenario' in s.get('type', '').lower()]
                if scenario_slides:
                    print(f"\n  Scenario Analysis Slides: {len(scenario_slides)}")
                    for scen_slide in scenario_slides:
                        content = scen_slide.get('content', {})
                        if content.get('chart_data'):
                            print(f"    ✓ Has chart data")
                        else:
                            print(f"    ✗ No chart data!")
                
            else:
                print(f"✗ Request failed: {response.status_code}")
                print(f"  Error: {response.text}")
                
        except Exception as e:
            print(f"✗ Exception: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_deck_generation())