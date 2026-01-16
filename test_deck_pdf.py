#!/usr/bin/env python3
"""
Test script to generate deck and export to PDF
"""
import requests
import json
from datetime import datetime
from pathlib import Path

def generate_and_export_deck():
    """Generate deck via API and export to PDF"""
    
    # Step 1: Generate deck
    print("🎯 Generating deck...")
    api_url = "http://localhost:8000/api/agent/unified-brain"
    
    payload = {
        "prompt": "Compare @Cursor and @Perplexity for my 122m fund, in year 3 with 63m to deploy, with 0.2 dpi, 4.7tvpi, one unicorn one small m&A a few profitable but not venture scale companies",
        "output_format": "deck",
        "context": {}
    }
    
    try:
        response = requests.post(api_url, json=payload, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        print(f"✅ Deck generated successfully!")
        
        # Check if we have deck data
        if result.get('success') and result.get('result'):
            deck_data = result['result']
            
            # Check if it's a deck format
            if deck_data.get('format') == 'deck' and 'slides' in deck_data:
                slides = deck_data.get('slides', [])
                print(f"📊 Deck has {len(slides)} slides")
                
                # Step 2: Export to PDF
                print("📄 Exporting to PDF...")
                export_url = "http://localhost:8000/api/export/deck"
                
                export_payload = {
                    "deck_data": deck_data,
                    "format": "pdf"
                }
                
                export_response = requests.post(export_url, json=export_payload, timeout=60)
                
                if export_response.status_code == 200:
                    # Save PDF
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                    filename = f"Investment_Deck_{timestamp}.pdf"
                    
                    with open(filename, 'wb') as f:
                        f.write(export_response.content)
                    
                    file_size = len(export_response.content) / 1024
                    print(f"\n✅ PDF SAVED SUCCESSFULLY!")
                    print(f"📍 File: {Path(filename).absolute()}")
                    print(f"📊 Size: {file_size:.1f} KB")
                    
                    return filename
                else:
                    print(f"❌ PDF Export failed: {export_response.status_code}")
                    print(export_response.text)
                    return None
            else:
                print("❌ No deck format found in response")
                print(f"Response format: {deck_data.get('format', 'unknown')}")
                print(f"Available keys: {list(deck_data.keys())}")
                return None
        else:
            print("❌ No successful result from API")
            print(f"Success: {result.get('success')}")
            print(f"Error: {result.get('error', 'No error message')}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

if __name__ == "__main__":
    generate_and_export_deck()
