#!/usr/bin/env python3
"""
Test PDF Export with Playwright and Complex Charts
Tests if PDF export properly renders complex charts using Playwright
"""

import asyncio
import json
from datetime import datetime
from app.services.deck_export_service import DeckExportService
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test deck with complex charts
test_deck_data = {
    "metadata": {
        "created_at": datetime.now().isoformat(),
        "fund_name": "Test Fund",
        "version": "1.0"
    },
    "slides": [
        # Title slide
        {
            "type": "title",
            "order": 0,
            "content": {
                "title": "PDF Export Test",
                "subtitle": "Testing Complex Charts",
                "date": datetime.now().strftime("%B %Y")
            }
        },
        
        # Probability Cloud Chart (Complex D3.js chart)
        {
            "type": "chart",
            "order": 1,
            "content": {
                "title": "Probability Cloud Analysis",
                "chart_type": "probability_cloud",
                "chart_data": {
                    "scenarios": [
                        {
                            "name": "Base Case",
                            "color": "#4A5568",
                            "probability": 0.40,
                            "data": [
                                {"exit_value": 10000000, "return_multiple": 0.5},
                                {"exit_value": 50000000, "return_multiple": 2.5},
                                {"exit_value": 100000000, "return_multiple": 5.0},
                                {"exit_value": 500000000, "return_multiple": 25.0},
                                {"exit_value": 1000000000, "return_multiple": 50.0}
                            ]
                        },
                        {
                            "name": "Upside Case",
                            "color": "#48BB78",
                            "probability": 0.25,
                            "data": [
                                {"exit_value": 10000000, "return_multiple": 0.8},
                                {"exit_value": 50000000, "return_multiple": 4.0},
                                {"exit_value": 100000000, "return_multiple": 8.0},
                                {"exit_value": 500000000, "return_multiple": 40.0},
                                {"exit_value": 1000000000, "return_multiple": 80.0}
                            ]
                        }
                    ],
                    "breakpoints": [
                        {"value": 100000000, "label": "$100M Exit", "color": "#9B2C2C"},
                        {"value": 500000000, "label": "$500M Exit", "color": "#2D3748"}
                    ]
                }
            }
        },
        
        # Side by Side Sankey (Complex chart)
        {
            "type": "chart",
            "order": 2,
            "content": {
                "title": "Cap Table Evolution",
                "chart_type": "side_by_side_sankey",
                "chart_data": {
                    "left_chart": {
                        "title": "Mercury",
                        "nodes": [
                            {"id": "founders", "label": "Founders"},
                            {"id": "seed", "label": "Seed"},
                            {"id": "seriesA", "label": "Series A"},
                            {"id": "seriesB", "label": "Series B"},
                            {"id": "exit", "label": "Exit"}
                        ],
                        "links": [
                            {"source": "founders", "target": "seed", "value": 60},
                            {"source": "seed", "target": "seriesA", "value": 45},
                            {"source": "seriesA", "target": "seriesB", "value": 35},
                            {"source": "seriesB", "target": "exit", "value": 25}
                        ]
                    },
                    "right_chart": {
                        "title": "Brex",
                        "nodes": [
                            {"id": "founders", "label": "Founders"},
                            {"id": "seed", "label": "Seed"},
                            {"id": "seriesA", "label": "Series A"},
                            {"id": "seriesB", "label": "Series B"},
                            {"id": "exit", "label": "Exit"}
                        ],
                        "links": [
                            {"source": "founders", "target": "seed", "value": 65},
                            {"source": "seed", "target": "seriesA", "value": 50},
                            {"source": "seriesA", "target": "seriesB", "value": 40},
                            {"source": "seriesB", "target": "exit", "value": 30}
                        ]
                    }
                }
            }
        },
        
        # Regular line chart (should work normally)
        {
            "type": "chart",
            "order": 3,
            "content": {
                "title": "Path to $100M ARR",
                "chart_type": "line",
                "chart_data": {
                    "labels": ["Year 1", "Year 2", "Year 3", "Year 4", "Year 5"],
                    "datasets": [
                        {
                            "label": "Mercury",
                            "data": [5, 15, 35, 65, 100],
                            "borderColor": "#4A5568",
                            "backgroundColor": "rgba(74, 85, 104, 0.1)"
                        },
                        {
                            "label": "Brex",
                            "data": [8, 22, 45, 75, 110],
                            "borderColor": "#48BB78",
                            "backgroundColor": "rgba(72, 187, 120, 0.1)"
                        }
                    ]
                }
            }
        }
    ]
}

async def test_pdf_export():
    """Test PDF export with complex charts"""
    try:
        # Check Playwright availability
        try:
            from playwright.async_api import async_playwright
            logger.info("✓ Playwright is installed")
        except ImportError:
            logger.error("✗ Playwright not installed. Run: pip install playwright && playwright install chromium")
            return False
            
        # Initialize service
        export_service = DeckExportService()
        
        # Test 1: Check if complex charts are detected
        logger.info("\nTest 1: Checking complex chart detection...")
        chart_images = await export_service._prerender_complex_charts(test_deck_data)
        
        if chart_images:
            logger.info(f"✓ Pre-rendered {len(chart_images)} complex charts")
            for key in chart_images.keys():
                logger.info(f"  - {key}: {len(chart_images[key][:50])}... bytes")
        else:
            logger.warning("✗ No charts were pre-rendered")
        
        # Test 2: Export to PDF
        logger.info("\nTest 2: Exporting to PDF...")
        pdf_bytes = await export_service.export_to_pdf_async(test_deck_data)
        
        if pdf_bytes:
            # Save PDF for inspection
            output_file = "/tmp/test_pdf_export.pdf"
            with open(output_file, "wb") as f:
                f.write(pdf_bytes)
            
            file_size = len(pdf_bytes) / 1024  # KB
            logger.info(f"✓ PDF generated successfully: {file_size:.1f} KB")
            logger.info(f"✓ Saved to: {output_file}")
            
            # Check if file has reasonable size (should be > 100KB with charts)
            if file_size > 100:
                logger.info("✓ PDF has reasonable size (includes chart images)")
            else:
                logger.warning("⚠ PDF seems small, charts might not be included")
            
            return True
        else:
            logger.error("✗ Failed to generate PDF")
            return False
            
    except Exception as e:
        logger.error(f"✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

async def check_playwright_browsers():
    """Check if Playwright browsers are installed"""
    try:
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            try:
                # Try to launch chromium
                browser = await p.chromium.launch(headless=True)
                await browser.close()
                logger.info("✓ Chromium browser is installed and working")
                return True
            except Exception as e:
                logger.error(f"✗ Chromium not available: {e}")
                logger.info("  Run: playwright install chromium")
                return False
    except ImportError:
        logger.error("✗ Playwright not installed")
        return False

async def main():
    """Main test runner"""
    logger.info("=" * 60)
    logger.info("PDF Export Test Suite")
    logger.info("=" * 60)
    
    # Check prerequisites
    logger.info("\nChecking prerequisites...")
    browsers_ok = await check_playwright_browsers()
    
    if not browsers_ok:
        logger.error("\n✗ Prerequisites not met. Please install required components.")
        return
    
    # Run tests
    success = await test_pdf_export()
    
    if success:
        logger.info("\n" + "=" * 60)
        logger.info("✓ ALL TESTS PASSED - PDF Export is working!")
        logger.info("=" * 60)
    else:
        logger.info("\n" + "=" * 60)
        logger.error("✗ TESTS FAILED - PDF Export needs fixing")
        logger.info("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())