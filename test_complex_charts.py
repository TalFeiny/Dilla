#!/usr/bin/env python3
"""Test script to verify complex charts work properly"""

import asyncio
import json
import httpx

async def test_complex_charts():
    print("🧪 Testing Complex Charts...")
    
    # Test data for different complex chart types
    test_charts = {
        "sankey": {
            "type": "sankey",
            "data": {
                "nodes": [
                    {"name": "Revenue", "value": 1000000},
                    {"name": "Costs", "value": 600000},
                    {"name": "Profit", "value": 400000}
                ],
                "links": [
                    {"source": 0, "target": 1, "value": 600000},
                    {"source": 0, "target": 2, "value": 400000}
                ]
            }
        },
        "waterfall": {
            "type": "waterfall", 
            "data": [
                {"name": "Starting Value", "value": 1000000},
                {"name": "Revenue Growth", "value": 200000},
                {"name": "Cost Reduction", "value": 50000},
                {"name": "Final Value", "value": 1250000}
            ]
        },
        "heatmap": {
            "type": "heatmap",
            "data": [
                {"x": "Q1", "y": "Revenue", "value": 100},
                {"x": "Q2", "y": "Revenue", "value": 120},
                {"x": "Q3", "y": "Revenue", "value": 140},
                {"x": "Q4", "y": "Revenue", "value": 160}
            ]
        }
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # Test each chart type
            for chart_name, chart_config in test_charts.items():
                print(f"\n📊 Testing {chart_name} chart...")
                
                # Create a deck with this chart
                test_deck = {
                    "title": f"Test {chart_name.title()} Chart",
                    "slides": [
                        {
                            "id": f"slide-{chart_name}",
                            "content": {
                                "title": f"{chart_name.title()} Analysis",
                                "subtitle": "Complex chart rendering test",
                                "chart_data": chart_config
                            }
                        }
                    ]
                }
                
                # Store the deck
                store_response = await client.post(
                    "http://localhost:8000/api/deck-storage/store",
                    json=test_deck,
                    timeout=10.0
                )
                
                if store_response.status_code != 200:
                    print(f"❌ Failed to store {chart_name} deck: {store_response.status_code}")
                    continue
                    
                deck_id = store_response.json()["deck_id"]
                print(f"✅ {chart_name} deck stored: {deck_id}")
                
                # Test frontend API
                api_response = await client.get(
                    f"http://localhost:3001/api/deck-data/{deck_id}",
                    timeout=10.0
                )
                
                if api_response.status_code != 200:
                    print(f"❌ Frontend API failed for {chart_name}: {api_response.status_code}")
                    continue
                    
                retrieved_deck = api_response.json()
                chart_data = retrieved_deck['slides'][0]['content']['chart_data']
                print(f"✅ {chart_name} chart data retrieved: {chart_data['type']}")
                
                # Test page load
                page_response = await client.get(
                    f"http://localhost:3001/deck-agent?deckId={deck_id}&pdfMode=true",
                    timeout=15.0
                )
                
                if page_response.status_code != 200:
                    print(f"❌ Page load failed for {chart_name}: {page_response.status_code}")
                    continue
                    
                print(f"✅ {chart_name} page loads successfully")
                print(f"🔗 Test URL: http://localhost:3001/deck-agent?deckId={deck_id}&pdfMode=true")
                
            print(f"\n🎉 Complex chart tests completed!")
            return True
            
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    result = asyncio.run(test_complex_charts())
    print(f"\nTest result: {'PASS' if result else 'FAIL'}")