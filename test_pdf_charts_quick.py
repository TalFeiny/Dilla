#!/usr/bin/env python3
"""Quick test to verify PDF export and chart rendering"""

import requests
import json
import sys

def test_pdf_export():
    """Test PDF export with a simple deck containing charts"""
    
    print("🧪 Testing PDF Export and Chart Rendering...")
    
    # Create a test deck with various chart types
    test_deck = {
        "title": "PDF Chart Test",
        "slides": [
            {
                "id": "slide1",
                "content": {
                    "title": "Bar Chart Test",
                    "chart_data": {
                        "type": "bar",
                        "data": {
                            "labels": ["Q1", "Q2", "Q3", "Q4"],
                            "datasets": [{
                                "label": "Revenue ($M)",
                                "data": [10, 15, 20, 25]
                            }]
                        }
                    }
                }
            },
            {
                "id": "slide2",
                "content": {
                    "title": "Line Chart Test",
                    "chart_data": {
                        "type": "line",
                        "data": {
                            "labels": ["Jan", "Feb", "Mar", "Apr"],
                            "datasets": [{
                                "label": "Growth",
                                "data": [5, 8, 12, 18]
                            }]
                        }
                    }
                }
            },
            {
                "id": "slide3",
                "content": {
                    "title": "Pie Chart Test",
                    "chart_data": {
                        "type": "pie",
                        "data": {
                            "labels": ["A", "B", "C"],
                            "datasets": [{
                                "data": [30, 40, 30]
                            }]
                        }
                    }
                }
            }
        ]
    }
    
    try:
        # Test 1: Export to PDF
        print("\n📄 Testing PDF export...")
        response = requests.post(
            "http://localhost:8000/api/export/deck",
            json={
                "deck_data": test_deck,
                "format": "pdf"
            },
            timeout=60
        )
        
        if response.status_code == 200:
            pdf_size = len(response.content)
            print(f"✅ PDF export successful! Size: {pdf_size:,} bytes ({pdf_size/1024:.1f} KB)")
            
            # Save PDF for inspection
            with open("/tmp/test_deck.pdf", "wb") as f:
                f.write(response.content)
            print(f"💾 PDF saved to /tmp/test_deck.pdf")
            
            if pdf_size > 1000:  # PDF should be at least 1KB
                print("✅ PDF appears to have content")
            else:
                print("⚠️ PDF is very small, may be empty")
        else:
            print(f"❌ PDF export failed: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return False
        
        # Test 2: Check if frontend can render charts
        print("\n📊 Testing chart rendering on frontend...")
        frontend_response = requests.get("http://localhost:3001/deck-agent", timeout=10)
        
        if frontend_response.status_code == 200:
            print("✅ Frontend is accessible")
            
            # Check if chart libraries are mentioned in the page
            page_content = frontend_response.text
            if "chart" in page_content.lower() or "recharts" in page_content.lower():
                print("✅ Chart rendering libraries detected")
            else:
                print("⚠️ Chart libraries not detected in page source")
        else:
            print(f"⚠️ Frontend check failed: {frontend_response.status_code}")
        
        print("\n🎉 Basic tests completed!")
        print("\nTo verify charts are rendering:")
        print("1. Open http://localhost:3001/deck-agent")
        print("2. Generate a deck with charts")
        print("3. Export to PDF and check if charts appear")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend. Is it running on port 8000?")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_pdf_export()
    sys.exit(0 if success else 1)










