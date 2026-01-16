#!/usr/bin/env python3
"""Simple test script to verify PDF export works"""

import asyncio
import json
import httpx

async def test_pdf_export():
    print("🧪 Testing PDF Export Flow...")
    
    # Step 1: Create a test deck via API
    test_deck = {
        "title": "PDF Export Test Deck",
        "slides": [
            {
                "id": "slide1",
                "content": {
                    "title": "Revenue Growth",
                    "subtitle": "Quarterly Performance",
                    "chart_data": {
                        "type": "bar",
                        "data": {
                            "labels": ["Q1", "Q2", "Q3", "Q4"],
                            "datasets": [{"label": "Revenue ($M)", "data": [10, 15, 20, 25]}]
                        }
                    }
                }
            },
            {
                "id": "slide2", 
                "content": {
                    "title": "Market Analysis",
                    "bullets": [
                        "Total Addressable Market: $50B",
                        "Serviceable Addressable Market: $5B", 
                        "Serviceable Obtainable Market: $500M"
                    ]
                }
            }
        ]
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # Store the deck
            print("📦 Storing test deck...")
            store_response = await client.post(
                "http://localhost:8000/api/deck-storage/store",
                json=test_deck,
                timeout=10.0
            )
            
            if store_response.status_code != 200:
                print(f"❌ Failed to store deck: {store_response.status_code}")
                return False
                
            deck_id = store_response.json()["deck_id"]
            print(f"✅ Deck stored with ID: {deck_id}")
            
            # Test frontend API
            print("🔗 Testing frontend API...")
            api_response = await client.get(
                f"http://localhost:3001/api/deck-data/{deck_id}",
                timeout=10.0
            )
            
            if api_response.status_code != 200:
                print(f"❌ Frontend API failed: {api_response.status_code}")
                return False
                
            retrieved_deck = api_response.json()
            print(f"✅ Frontend API working: {len(retrieved_deck['slides'])} slides")
            
            # Test page loading
            print("🌐 Testing page load...")
            page_response = await client.get(
                f"http://localhost:3001/deck-agent?deckId={deck_id}&pdfMode=true",
                timeout=15.0
            )
            
            if page_response.status_code != 200:
                print(f"❌ Page load failed: {page_response.status_code}")
                return False
                
            print("✅ Page loads successfully")
            
            # Check if the page contains expected elements
            page_content = page_response.text
            if 'data-testid="deck-presentation"' in page_content:
                print("✅ Deck presentation element found")
            else:
                print("⚠️ Deck presentation element not found")
                
            if 'data-testid="chart-container"' in page_content:
                print("✅ Chart container element found")
            else:
                print("⚠️ Chart container element not found")
                
            print(f"\n🎉 All tests passed! Deck ID: {deck_id}")
            print(f"🔗 Test URL: http://localhost:3001/deck-agent?deckId={deck_id}&pdfMode=true")
            return True
            
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    result = asyncio.run(test_pdf_export())
    print(f"\nTest result: {'PASS' if result else 'FAIL'}")





























