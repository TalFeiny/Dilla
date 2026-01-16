#!/usr/bin/env python3
"""
Test the new Playwright-based PDF export with real data
"""

import asyncio
import json
from app.services.deck_export_service import DeckExportService

# Create test deck data with multiple slides
test_deck_data = {
    "slides": [
        {
            "type": "title",
            "content": {
                "title": "Investment Analysis Report",
                "subtitle": "Q1 2024 Portfolio Review",
                "date": "January 2024"
            }
        },
        {
            "type": "company",
            "content": {
                "title": "Lunio - Company Profile",
                "metrics": {
                    "Valuation": "$15M",
                    "Revenue": "$2.5M ARR",
                    "Growth Rate": "180% YoY",
                    "Burn Rate": "$250K/mo",
                    "Runway": "18 months",
                    "Team Size": "25 employees"
                },
                "investment_thesis": "Lunio is revolutionizing ad fraud prevention with ML-powered detection that saves enterprises millions in wasted ad spend."
            }
        },
        {
            "type": "chart",
            "content": {
                "title": "Revenue Growth Trajectory",
                "chart_data": {
                    "type": "line",
                    "title": "Monthly Recurring Revenue (MRR)",
                    "data": {
                        "labels": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                        "datasets": [
                            {
                                "label": "Lunio MRR",
                                "data": [120, 135, 155, 178, 195, 220, 245, 280, 310, 350, 385, 420],
                                "borderColor": "rgb(99, 102, 241)",
                                "tension": 0.4
                            },
                            {
                                "label": "Competitor MRR",
                                "data": [100, 105, 110, 115, 122, 128, 135, 142, 150, 158, 165, 173],
                                "borderColor": "rgb(236, 72, 153)",
                                "tension": 0.4
                            }
                        ]
                    }
                }
            }
        },
        {
            "type": "comparison",
            "content": {
                "title": "Side-by-Side Company Comparison",
                "companies": [
                    {
                        "name": "Lunio",
                        "valuation": 15000000,
                        "revenue": 2500000,
                        "stage": "Series A"
                    },
                    {
                        "name": "Competitor X",
                        "valuation": 45000000,
                        "revenue": 5000000,
                        "stage": "Series B"
                    }
                ]
            }
        },
        {
            "type": "chart",
            "content": {
                "title": "Exit Scenario Analysis",
                "chart_data": {
                    "type": "bar",
                    "title": "Projected Returns by Scenario",
                    "data": {
                        "labels": ["Bear Case", "Base Case", "Bull Case"],
                        "datasets": [
                            {
                                "label": "Lunio",
                                "data": [45, 150, 450],
                                "backgroundColor": "rgba(99, 102, 241, 0.8)"
                            },
                            {
                                "label": "Competitor X",
                                "data": [90, 225, 675],
                                "backgroundColor": "rgba(236, 72, 153, 0.8)"
                            }
                        ]
                    }
                }
            }
        },
        {
            "type": "investment_thesis",
            "content": {
                "title": "Investment Recommendation",
                "thesis_points": [
                    "Strong product-market fit with 180% YoY growth",
                    "Experienced team with deep domain expertise",
                    "Clear path to profitability within 18 months",
                    "Defensive moat through proprietary ML algorithms",
                    "Multiple strategic exit opportunities"
                ],
                "key_metrics": {
                    "Recommended Investment": "$2M",
                    "Target Ownership": "13.3%",
                    "Expected IRR": "45%",
                    "Exit Timeline": "3-5 years"
                }
            }
        }
    ]
}

def test_export():
    """Test the new PDF export"""
    service = DeckExportService()
    
    print("Testing PDF export with Playwright...")
    
    try:
        # Export to PDF
        pdf_bytes = service.export_to_pdf(test_deck_data)
        
        # Save to file
        with open('/Users/admin/code/dilla-ai/backend/test_deck_output.pdf', 'wb') as f:
            f.write(pdf_bytes)
        
        print(f"✅ PDF exported successfully! Size: {len(pdf_bytes):,} bytes")
        print("📄 Saved to: test_deck_output.pdf")
        
        # Also test PPTX export
        pptx_bytes = service.export_to_pptx(test_deck_data)
        with open('/Users/admin/code/dilla-ai/backend/test_deck_output.pptx', 'wb') as f:
            f.write(pptx_bytes)
        print(f"✅ PPTX exported successfully! Size: {len(pptx_bytes):,} bytes")
        
    except Exception as e:
        print(f"❌ Error during export: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_export()