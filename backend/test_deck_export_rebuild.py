#!/usr/bin/env python3
"""
Test the rebuilt deck export service with comprehensive data
Including Sankey diagrams, side-by-side comparisons, and enhanced visualizations
"""

import asyncio
import json
from datetime import datetime
from app.services.deck_export_service import DeckExportService

# Create comprehensive test deck data
test_deck_data = {
    "metadata": {
        "created_at": datetime.now().isoformat(),
        "fund_name": "TechVentures Fund III",
        "version": "2.0"
    },
    "slides": [
        # Slide 1: Title Slide
        {
            "type": "title",
            "order": 0,
            "content": {
                "title": "Investment Analysis Report",
                "subtitle": "AI Infrastructure Portfolio Review",
                "date": datetime.now().strftime("%B %Y")
            }
        },
        
        # Slide 2: Executive Summary
        {
            "type": "summary",
            "order": 1,
            "content": {
                "title": "Executive Summary",
                "bullets": [
                    "Analyzing 2 high-growth AI infrastructure companies for Series B investment",
                    "Combined portfolio value potential: $2.5B by 2028 (15x MOIC)",
                    "Focus on GPU compute and AI voice automation sectors",
                    "Both companies showing 200%+ YoY growth with strong unit economics"
                ]
            }
        },
        
        # Slide 3: Company Profiles Side-by-Side
        {
            "type": "side_by_side",
            "order": 2,
            "content": {
                "title": "Company Comparison",
                "left": {
                    "subtitle": "Vocca AI",
                    "metrics": {
                        "Valuation": "$150M",
                        "Revenue": "$8M ARR",
                        "Growth": "250% YoY",
                        "Gross Margin": "75%",
                        "Burn Multiple": "0.8x"
                    },
                    "bullets": [
                        "AI voice agents for healthcare",
                        "30% of calls fully automated",
                        "$2M monthly burn rate",
                        "18 months runway"
                    ]
                },
                "right": {
                    "subtitle": "OffDeal",
                    "metrics": {
                        "Valuation": "$200M",
                        "Revenue": "$12M ARR",
                        "Growth": "180% YoY",
                        "Gross Margin": "82%",
                        "Burn Multiple": "0.6x"
                    },
                    "bullets": [
                        "M&A document automation",
                        "Serves 50+ PE firms",
                        "$1.5M monthly burn",
                        "24 months runway"
                    ]
                }
            }
        },
        
        # Slide 4: Revenue Growth Chart
        {
            "type": "chart",
            "order": 3,
            "content": {
                "title": "Revenue Growth Trajectory",
                "chart_data": {
                    "type": "line",
                    "data": {
                        "labels": ["Q1 2023", "Q2 2023", "Q3 2023", "Q4 2023", "Q1 2024", "Q2 2024", "Q3 2024", "Q4 2024E"],
                        "datasets": [
                            {
                                "label": "Vocca AI",
                                "data": [0.5, 0.8, 1.2, 1.8, 2.5, 3.5, 5.0, 8.0],
                                "borderColor": "rgb(99, 102, 241)",
                                "backgroundColor": "rgba(99, 102, 241, 0.1)",
                                "tension": 0.4,
                                "fill": True
                            },
                            {
                                "label": "OffDeal",
                                "data": [1.0, 1.5, 2.2, 3.0, 4.2, 5.8, 8.0, 12.0],
                                "borderColor": "rgb(236, 72, 153)",
                                "backgroundColor": "rgba(236, 72, 153, 0.1)",
                                "tension": 0.4,
                                "fill": True
                            }
                        ]
                    },
                    "options": {
                        "scales": {
                            "y": {
                                "title": {
                                    "display": True,
                                    "text": "ARR ($M)"
                                }
                            },
                            "x": {
                                "title": {
                                    "display": True,
                                    "text": "Quarter"
                                }
                            }
                        }
                    }
                }
            }
        },
        
        # Slide 5: Cap Table Comparison with Sankey-like visualization
        {
            "type": "cap_table",
            "order": 4,
            "content": {
                "title": "Cap Table Evolution",
                "companies": [
                    {
                        "name": "Vocca AI",
                        "cap_table": {
                            "rounds": [
                                {"round": "Founding", "founders": 100.0, "investors": 0.0, "employees": 0.0},
                                {"round": "Seed", "founders": 75.0, "investors": 20.0, "employees": 5.0},
                                {"round": "Series A", "founders": 55.0, "investors": 35.0, "employees": 10.0},
                                {"round": "Series B (Proposed)", "founders": 42.0, "investors": 46.0, "employees": 12.0}
                            ]
                        },
                        "highlights": [
                            "Strong founder retention at 42%",
                            "Employee pool growing steadily",
                            "Our investment: 12% for $18M"
                        ]
                    },
                    {
                        "name": "OffDeal",
                        "cap_table": {
                            "rounds": [
                                {"round": "Founding", "founders": 100.0, "investors": 0.0, "employees": 0.0},
                                {"round": "Seed", "founders": 70.0, "investors": 25.0, "employees": 5.0},
                                {"round": "Series A", "founders": 48.0, "investors": 42.0, "employees": 10.0},
                                {"round": "Series B (Proposed)", "founders": 35.0, "investors": 52.0, "employees": 13.0}
                            ]
                        },
                        "highlights": [
                            "Founders at 35% post-Series B",
                            "Strong investor interest",
                            "Our investment: 10% for $20M"
                        ]
                    }
                ]
            }
        },
        
        # Slide 6: Market TAM Analysis
        {
            "type": "chart",
            "order": 5,
            "content": {
                "title": "Market Opportunity (TAM Analysis)",
                "chart_data": {
                    "type": "bar",
                    "data": {
                        "labels": ["Traditional TAM", "Labor TAM", "Serviceable (SAM)", "Obtainable (SOM)"],
                        "datasets": [
                            {
                                "label": "Vocca AI - Healthcare Voice",
                                "data": [10000, 30000, 4500, 450],
                                "backgroundColor": "rgba(99, 102, 241, 0.8)"
                            },
                            {
                                "label": "OffDeal - M&A Automation",
                                "data": [20000, 50000, 7000, 700],
                                "backgroundColor": "rgba(236, 72, 153, 0.8)"
                            }
                        ]
                    },
                    "options": {
                        "scales": {
                            "y": {
                                "title": {
                                    "display": True,
                                    "text": "Market Size ($M)"
                                },
                                "type": "logarithmic"
                            }
                        },
                        "plugins": {
                            "title": {
                                "display": True,
                                "text": "Labor Budget Arbitrage Opportunity"
                            }
                        }
                    }
                }
            }
        },
        
        # Slide 7: Valuation Multiples
        {
            "type": "chart",
            "order": 6,
            "content": {
                "title": "Valuation Analysis",
                "chart_data": {
                    "type": "bar",
                    "data": {
                        "labels": ["Current Multiple", "Industry Avg", "Top Quartile", "Our Target"],
                        "datasets": [
                            {
                                "label": "Vocca AI (x ARR)",
                                "data": [18.75, 15.0, 25.0, 22.0],
                                "backgroundColor": "rgba(99, 102, 241, 0.8)"
                            },
                            {
                                "label": "OffDeal (x ARR)",
                                "data": [16.67, 12.0, 20.0, 18.0],
                                "backgroundColor": "rgba(236, 72, 153, 0.8)"
                            }
                        ]
                    }
                }
            }
        },
        
        # Slide 8: Exit Scenarios
        {
            "type": "side_by_side",
            "order": 7,
            "content": {
                "title": "Exit Scenario Analysis",
                "left": {
                    "subtitle": "Vocca AI Returns",
                    "chart_data": {
                        "type": "bar",
                        "data": {
                            "labels": ["Bear (3x)", "Base (10x)", "Bull (25x)"],
                            "datasets": [
                                {
                                    "label": "MOIC",
                                    "data": [3, 10, 25],
                                    "backgroundColor": ["rgba(239, 68, 68, 0.8)", "rgba(99, 102, 241, 0.8)", "rgba(34, 197, 94, 0.8)"]
                                }
                            ]
                        }
                    },
                    "metrics": {
                        "Investment": "$18M",
                        "Bear Return": "$54M",
                        "Base Return": "$180M",
                        "Bull Return": "$450M",
                        "IRR Range": "25-65%"
                    }
                },
                "right": {
                    "subtitle": "OffDeal Returns",
                    "chart_data": {
                        "type": "bar",
                        "data": {
                            "labels": ["Bear (2.5x)", "Base (8x)", "Bull (20x)"],
                            "datasets": [
                                {
                                    "label": "MOIC",
                                    "data": [2.5, 8, 20],
                                    "backgroundColor": ["rgba(239, 68, 68, 0.8)", "rgba(236, 72, 153, 0.8)", "rgba(34, 197, 94, 0.8)"]
                                }
                            ]
                        }
                    },
                    "metrics": {
                        "Investment": "$20M",
                        "Bear Return": "$50M",
                        "Base Return": "$160M",
                        "Bull Return": "$400M",
                        "IRR Range": "20-55%"
                    }
                }
            }
        },
        
        # Slide 9: Investment Thesis
        {
            "type": "investment_thesis",
            "order": 8,
            "content": {
                "title": "Investment Recommendation",
                "thesis_points": [
                    "Both companies demonstrate strong product-market fit with 200%+ growth",
                    "Labor budget arbitrage thesis validated: replacing $2-3 of labor with $1 of AI",
                    "Vertical SaaS approach (healthcare, M&A) provides defensibility",
                    "GPU cost ratios improving: Vocca at 35%, OffDeal at 7.5% of revenue",
                    "Strong founder teams with domain expertise and high retention"
                ],
                "key_metrics": {
                    "Total Investment": "$38M",
                    "Blended Ownership": "11%",
                    "Expected MOIC": "9x (Base Case)",
                    "Target Exit": "2028-2030",
                    "Portfolio IRR": "45%+"
                }
            }
        },
        
        # Slide 10: Next Steps
        {
            "type": "content",
            "order": 9,
            "content": {
                "title": "Next Steps & Timeline",
                "bullets": [
                    "Week 1-2: Complete technical due diligence on both companies",
                    "Week 3: Negotiate term sheets with target valuations",
                    "Week 4-5: Legal due diligence and documentation",
                    "Week 6: Investment committee approval",
                    "Week 7-8: Close investments and board seat negotiations",
                    "Ongoing: Monthly board meetings and quarterly portfolio reviews"
                ]
            }
        }
    ]
}

async def test_export():
    """Test the deck export service"""
    service = DeckExportService()
    
    print("Testing Deck Export Service Rebuild...")
    print("=" * 50)
    
    # Test PPTX Export
    print("\n1. Testing PowerPoint Export...")
    try:
        pptx_bytes = service.export_to_pptx(test_deck_data)
        with open("test_deck_output.pptx", "wb") as f:
            f.write(pptx_bytes)
        print("   ✓ PowerPoint export successful")
        print(f"   ✓ File size: {len(pptx_bytes):,} bytes")
        print("   ✓ Saved as: test_deck_output.pptx")
    except Exception as e:
        print(f"   ✗ PowerPoint export failed: {e}")
    
    # Test PDF Export
    print("\n2. Testing PDF Export...")
    try:
        pdf_bytes = service.export_to_pdf(test_deck_data)
        with open("test_deck_output.pdf", "wb") as f:
            f.write(pdf_bytes)
        print("   ✓ PDF export successful")
        print(f"   ✓ File size: {len(pdf_bytes):,} bytes")
        print("   ✓ Saved as: test_deck_output.pdf")
    except Exception as e:
        print(f"   ✗ PDF export failed: {e}")
    
    # Test HTML Generation
    print("\n3. Testing HTML Generation...")
    try:
        html_content = service._generate_html_deck(test_deck_data)
        with open("test_deck_output.html", "w") as f:
            f.write(html_content)
        print("   ✓ HTML generation successful")
        print(f"   ✓ HTML size: {len(html_content):,} characters")
        print("   ✓ Saved as: test_deck_output.html")
    except Exception as e:
        print(f"   ✗ HTML generation failed: {e}")
    
    # Verify slide types
    print("\n4. Verifying Slide Types...")
    slide_types = set()
    for slide in test_deck_data["slides"]:
        slide_types.add(slide["type"])
    
    print(f"   ✓ Total slides: {len(test_deck_data['slides'])}")
    print(f"   ✓ Unique slide types: {', '.join(sorted(slide_types))}")
    
    # Check for special features
    print("\n5. Special Features Check:")
    has_cap_table = any(s["type"] == "cap_table" for s in test_deck_data["slides"])
    has_side_by_side = any(s["type"] == "side_by_side" for s in test_deck_data["slides"])
    has_charts = any(s.get("content", {}).get("chart_data") for s in test_deck_data["slides"])
    
    print(f"   {'✓' if has_cap_table else '✗'} Cap Table Comparison")
    print(f"   {'✓' if has_side_by_side else '✗'} Side-by-Side Layouts")
    print(f"   {'✓' if has_charts else '✗'} Advanced Charts")
    
    print("\n" + "=" * 50)
    print("Test Complete! Check the output files:")
    print("  - test_deck_output.pptx")
    print("  - test_deck_output.pdf")
    print("  - test_deck_output.html")

if __name__ == "__main__":
    # Run synchronously instead of async to avoid Playwright issues
    import sys
    sys.path.insert(0, '/Users/admin/code/dilla-ai/backend')
    
    service = DeckExportService()
    
    print("Testing Deck Export Service Rebuild...")
    print("=" * 50)
    
    # Test PPTX Export
    print("\n1. Testing PowerPoint Export...")
    try:
        pptx_bytes = service.export_to_pptx(test_deck_data)
        with open("test_deck_output.pptx", "wb") as f:
            f.write(pptx_bytes)
        print("   ✓ PowerPoint export successful")
        print(f"   ✓ File size: {len(pptx_bytes):,} bytes")
        print("   ✓ Saved as: test_deck_output.pptx")
    except Exception as e:
        print(f"   ✗ PowerPoint export failed: {e}")
    
    # Test PDF Export
    print("\n2. Testing PDF Export...")
    try:
        pdf_bytes = service.export_to_pdf(test_deck_data)
        with open("test_deck_output.pdf", "wb") as f:
            f.write(pdf_bytes)
        print("   ✓ PDF export successful")
        print(f"   ✓ File size: {len(pdf_bytes):,} bytes")
        print("   ✓ Saved as: test_deck_output.pdf")
    except Exception as e:
        print(f"   ✗ PDF export failed: {e}")
    
    # Test HTML Generation
    print("\n3. Testing HTML Generation...")
    try:
        html_content = service._generate_html_deck(test_deck_data)
        with open("test_deck_output.html", "w") as f:
            f.write(html_content)
        print("   ✓ HTML generation successful")
        print(f"   ✓ HTML size: {len(html_content):,} characters")
        print("   ✓ Saved as: test_deck_output.html")
    except Exception as e:
        print(f"   ✗ HTML generation failed: {e}")
    
    print("\n" + "=" * 50)
    print("Test Complete! Check the output files:")