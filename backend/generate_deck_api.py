#!/usr/bin/env python3
"""Generate deck via direct API call"""
import requests
import json
from pathlib import Path
from datetime import datetime

def generate_deck_and_pdf():
    """Generate deck via API and save PDF"""
    
    # API endpoint
    url = "http://localhost:8000/api/agent/unified-brain"
    
    # Request payload
    payload = {
        "prompt": "Create comprehensive investment deck for @Vega and @73Strings. These are AI companies - Vega does AI security analytics, 73Strings does AI for alternative asset data extraction. Fund context: $234M fund with $109M remaining.",
        "output_format": "deck",
        "context": {
            "fund_size": 234000000,
            "remaining_capital": 109000000,
            "target_ownership": 0.15
        },
        "stream": False,
        "options": {
            "show_citations": True
        }
    }
    
    print("="*70)
    print("🚀 GENERATING INVESTMENT DECK VIA API")
    print("="*70)
    print(f"\nCalling API endpoint: {url}")
    print(f"Companies: @Vega (AI Security), @73Strings (Alt Asset AI)")
    print(f"Fund: $234M with $109M to deploy")
    
    try:
        # Make API request
        print("\n⏳ Generating deck (this may take 30-60 seconds)...")
        response = requests.post(url, json=payload, timeout=180)
        
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            print(response.text)
            return False
        
        # Parse response
        result = response.json()
        
        # Check for errors
        if 'error' in result:
            print(f"❌ Error: {result['error']}")
            return False
        
        # Extract deck data
        deck_data = result.get('deck_data', {})
        slides = deck_data.get('slides', [])
        companies = result.get('companies', [])
        
        print(f"\n✅ Generated {len(slides)} slides")
        print(f"✅ Analyzed {len(companies)} companies")
        
        # Show company details
        if companies:
            print("\n📊 Company Details:")
            for company in companies:
                name = company.get('company', 'Unknown')
                business = company.get('business_model', 'Unknown')
                valuation = company.get('latest_valuation', 0)
                funding = company.get('total_funding', 0)
                
                print(f"\n  {name}:")
                print(f"    Business: {business}")
                print(f"    Valuation: ${valuation:,.0f}")
                print(f"    Total Funding: ${funding:,.0f}")
                
                # Show investors
                funding_rounds = company.get('funding_rounds', [])
                for round_data in funding_rounds:
                    investors = round_data.get('investors', [])
                    if investors:
                        print(f"    {round_data.get('round', 'Unknown')} Investors: {', '.join(investors[:3])}")
        
        # Show slide titles
        if slides:
            print("\n📑 Deck Contents:")
            for i, slide in enumerate(slides, 1):
                title = slide.get('content', {}).get('title', 'Untitled')
                print(f"   {i:2}. {title}")
        
        # Now export to PDF via the export endpoint
        if slides:
            print("\n📄 Exporting to PDF...")
            export_url = "http://localhost:8000/api/export/deck"
            export_payload = {
                "deck_data": deck_data,
                "format": "pdf",
                "options": {
                    "include_notes": True,
                    "include_citations": True,
                    "include_charts": True
                }
            }
            
            export_response = requests.post(export_url, json=export_payload, timeout=60)
            
            if export_response.status_code == 200:
                # Save PDF
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                filename = f"Vega_73Strings_Investment_Deck_{timestamp}.pdf"
                
                with open(filename, 'wb') as f:
                    f.write(export_response.content)
                
                file_size = len(export_response.content) / 1024
                print(f"\n✅ PDF SAVED SUCCESSFULLY!")
                print(f"📍 File: {Path(filename).absolute()}")
                print(f"📊 Size: {file_size:.1f} KB")
                print(f"\n🎉 Open with: open {Path(filename).absolute()}")
            else:
                print(f"❌ PDF Export failed: {export_response.status_code}")
                print(export_response.text)
        
        # Save JSON for debugging
        json_filename = f"deck_data_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        with open(json_filename, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n💾 JSON data saved: {json_filename}")
        
        return True
        
    except requests.exceptions.Timeout:
        print("❌ Request timed out. The API might be processing a complex request.")
        print("   Try running again or check the backend logs.")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = generate_deck_and_pdf()
    exit(0 if success else 1)