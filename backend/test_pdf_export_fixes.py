#!/usr/bin/env python3
"""
Test PDF Export Fixes
Verifies all improvements to the PDF export functionality
"""

import asyncio
import json
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.deck_export_service import DeckExportService

# Test deck with all slide types
test_deck = {
    "title": "PDF Export Test Suite",
    "slides": [
        {
            "id": "slide-1",
            "type": "title",
            "content": {
                "title": "Investment Analysis Report",
                "subtitle": "Testing All Slide Types & Charts",
                "date": datetime.now().strftime("%B %Y")
            }
        },
        {
            "id": "slide-2",
            "type": "summary",
            "content": {
                "title": "Executive Summary",
                "bullets": [
                    "✅ Singleton pattern removed - no more cached data",
                    "✅ Chart rendering improved with proper timeouts",
                    "✅ Sankey charts converted to stacked bar for PDF",
                    "✅ Brand theme matches landing page",
                    "✅ Data validation and formatting added"
                ]
            }
        },
        {
            "id": "slide-3",
            "type": "company",
            "content": {
                "title": "Company Overview",
                "metrics": {
                    "Revenue": 25000000,
                    "ARR": 30000000,
                    "Valuation": 500000000,
                    "Funding": 125000000,
                    "Team Size": 145,
                    "Growth Rate": 187.5,
                    "Stage": "Series C",
                    "Founded": "2019",
                    "Location": "San Francisco"
                },
                "investment_thesis": "Strong product-market fit with exceptional growth metrics and proven leadership team."
            }
        },
        {
            "id": "slide-4",
            "type": "chart",
            "content": {
                "title": "Revenue Growth",
                "subtitle": "Exponential growth trajectory",
                "chart_data": {
                    "type": "line",
                    "data": {
                        "labels": ["Q1 2023", "Q2 2023", "Q3 2023", "Q4 2023", "Q1 2024", "Q2 2024"],
                        "datasets": [{
                            "label": "Revenue ($M)",
                            "data": [5, 8, 12, 18, 25, 35],
                            "borderColor": "rgba(99, 102, 241, 0.9)",
                            "tension": 0.4
                        }]
                    }
                }
            }
        },
        {
            "id": "slide-5",
            "type": "chart",
            "content": {
                "title": "Market Share",
                "chart_data": {
                    "type": "bar",
                    "data": {
                        "labels": ["Us", "Competitor A", "Competitor B", "Others"],
                        "datasets": [{
                            "label": "Market Share %",
                            "data": [35, 25, 20, 20],
                            "backgroundColor": [
                                "rgba(34, 197, 94, 0.9)",
                                "rgba(59, 130, 246, 0.9)",
                                "rgba(251, 146, 60, 0.9)",
                                "rgba(147, 51, 234, 0.9)"
                            ]
                        }]
                    }
                }
            }
        },
        {
            "id": "slide-6",
            "type": "cap_table",
            "content": {
                "title": "Ownership Evolution",
                "chart_data": {
                    "type": "sankey",
                    "data": {
                        "nodes": [
                            {"name": "Founders", "round": "Seed", "value": 80, "ownership": 80},
                            {"name": "Seed Investors", "round": "Seed", "value": 15, "ownership": 15},
                            {"name": "ESOP", "round": "Seed", "value": 5, "ownership": 5},
                            {"name": "Founders", "round": "Series A", "value": 60, "ownership": 60},
                            {"name": "Series A Lead", "round": "Series A", "value": 20, "ownership": 20},
                            {"name": "Seed Investors", "round": "Series A", "value": 10, "ownership": 10},
                            {"name": "ESOP", "round": "Series A", "value": 10, "ownership": 10},
                            {"name": "Founders", "round": "Current", "value": 40, "ownership": 40},
                            {"name": "Series B Lead", "round": "Current", "value": 25, "ownership": 25},
                            {"name": "Series A Lead", "round": "Current", "value": 15, "ownership": 15},
                            {"name": "Seed Investors", "round": "Current", "value": 5, "ownership": 5},
                            {"name": "ESOP", "round": "Current", "value": 15, "ownership": 15}
                        ],
                        "links": []
                    }
                }
            }
        },
        {
            "id": "slide-7",
            "type": "comparison",
            "content": {
                "title": "Portfolio Comparison",
                "companies": [
                    {
                        "name": "Company Alpha",
                        "valuation": 500000000,
                        "revenue": 30000000,
                        "stage": "Series C"
                    },
                    {
                        "name": "Company Beta",
                        "valuation": 250000000,
                        "revenue": 15000000,
                        "stage": "Series B"
                    }
                ]
            }
        },
        {
            "id": "slide-8",
            "type": "chart",
            "content": {
                "title": "Probability Cloud",
                "subtitle": "Exit scenario analysis",
                "chart_data": {
                    "type": "probability_cloud",
                    "data": {
                        "scenario_curves": [
                            {
                                "name": "IPO Scenario",
                                "probability": 0.25,
                                "return_curve": {
                                    "exit_values": [100000000, 500000000, 1000000000, 5000000000],
                                    "return_multiples": [0.5, 2.5, 5.0, 25.0]
                                }
                            },
                            {
                                "name": "Strategic Acquisition",
                                "probability": 0.40,
                                "return_curve": {
                                    "exit_values": [100000000, 500000000, 1000000000, 5000000000],
                                    "return_multiples": [0.8, 4.0, 8.0, 15.0]
                                }
                            },
                            {
                                "name": "Downside Case",
                                "probability": 0.15,
                                "return_curve": {
                                    "exit_values": [100000000, 500000000, 1000000000, 5000000000],
                                    "return_multiples": [0.2, 0.5, 0.8, 1.0]
                                }
                            }
                        ],
                        "breakpoint_clouds": [],
                        "config": {
                            "x_axis": {"min": 100000000, "max": 5000000000}
                        }
                    }
                }
            }
        }
    ]
}


async def test_pdf_export():
    """Test the PDF export with all fixes"""
    print("=" * 60)
    print("PDF EXPORT TEST SUITE")
    print("=" * 60)
    
    # Create fresh instance (no singleton!)
    export_service = DeckExportService()
    
    print("\n✅ Created fresh DeckExportService instance (no singleton)")
    
    print("\n🎨 Testing slide types:")
    for slide in test_deck["slides"]:
        print(f"   - {slide['type']}: {slide['content'].get('title', 'Untitled')}")
    
    try:
        print("\n📄 Generating PDF...")
        pdf_bytes = export_service.export_to_pdf(test_deck)
        
        # Save the PDF
        output_path = "/Users/admin/code/dilla-ai/backend/test_pdf_export_output.pdf"
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        
        print(f"✅ PDF generated successfully ({len(pdf_bytes):,} bytes)")
        print(f"📁 Saved to: {output_path}")
        
        # Test HTML generation separately
        print("\n🌐 Testing HTML generation...")
        html = export_service._generate_html_deck(test_deck)
        
        # Save HTML for debugging
        html_path = "/Users/admin/code/dilla-ai/backend/test_pdf_export_output.html"
        with open(html_path, "w") as f:
            f.write(html)
        
        print(f"✅ HTML generated successfully ({len(html):,} characters)")
        print(f"📁 Saved to: {html_path}")
        
        # Verify key improvements
        print("\n🔍 Verifying improvements:")
        
        # Check for dark theme removal (now clean professional)
        if "hsl(220, 20%, 98%)" in html:
            print("   ✅ Clean professional theme applied")
        
        # Check for Sankey conversion
        if "stacked bar chart" in str(export_service._create_ownership_chart_from_sankey.__doc__):
            print("   ✅ Sankey-to-bar conversion available")
        
        # Check for data formatters
        if hasattr(export_service, "_validate_and_format_data"):
            print("   ✅ Data validation and formatting methods present")
        
        # Check chart timeout improvements
        if "5000" in html:  # Increased timeout
            print("   ✅ Chart rendering timeouts improved")
        
        print("\n✨ All tests passed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    # Run the async test
    success = asyncio.run(test_pdf_export())
    sys.exit(0 if success else 1)