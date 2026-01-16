#!/usr/bin/env python3
"""
Export deck to PDF using sample data
"""

from app.services.deck_export_service import DeckExportService

# Sample deck structure with minimal data
deck_slides = [
    {
        "type": "title",
        "content": {
            "title": "Investment Analysis Report",
            "subtitle": "Analysis of 2 companies",
            "date": "September 2025"
        }
    },
    {
        "type": "summary",
        "content": {
            "title": "Executive Summary",
            "bullets": [
                "Anam: Seed stage, $5.0M ARR at 15.2x revenue multiple",
                "unosecur: Seed stage, $425K ARR at 99.3x revenue multiple",
                "Combined TAM opportunity: $542.5B",
                "Proposed deployment: $8.0M across 2 companies"
            ]
        }
    },
    {
        "type": "company_comparison",
        "content": {
            "title": "Company Overview & Financials",
            "companies": [
                {
                    "name": "Anam",
                    "business_model": "Real-time photorealistic AI personas",
                    "metrics": {
                        "Stage": "Seed",
                        "Revenue": "$5.0M",
                        "Valuation": "$76M",
                        "Team Size": "16 employees"
                    }
                },
                {
                    "name": "unosecur", 
                    "business_model": "AI-powered identity security platform",
                    "metrics": {
                        "Stage": "Seed",
                        "Revenue": "$425K",
                        "Valuation": "$42M",
                        "Team Size": "10 employees"
                    }
                }
            ]
        }
    }
]

# Export to PDF
exporter = DeckExportService()
pdf_bytes = exporter.export_to_pdf(deck_slides)

# Save to file
with open('investment_deck.pdf', 'wb') as f:
    f.write(pdf_bytes)
    
print('PDF saved to: backend/investment_deck.pdf')
print(f'File size: {len(pdf_bytes):,} bytes')