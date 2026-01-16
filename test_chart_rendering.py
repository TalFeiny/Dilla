#!/usr/bin/env python3
"""
Test script to verify complex chart pre-rendering works
"""

import asyncio
import sys
import os

# Add the backend directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.chart_renderer_service import chart_renderer

async def test_chart_rendering():
    """Test that complex charts can be rendered to PNG"""
    
    print("Testing Chart Renderer Service...")
    
    # Test Sankey chart
    sankey_data = {
        "type": "sankey",
        "title": "Test Sankey Chart",
        "data": {
            "nodes": [
                {"name": "Source A", "value": 100},
                {"name": "Source B", "value": 80},
                {"name": "Target X", "value": 120},
                {"name": "Target Y", "value": 60}
            ],
            "links": [
                {"source": 0, "target": 2, "value": 70},
                {"source": 0, "target": 3, "value": 30},
                {"source": 1, "target": 2, "value": 50},
                {"source": 1, "target": 3, "value": 30}
            ]
        }
    }
    
    print("Testing Sankey chart rendering...")
    result = await chart_renderer.render_tableau_chart("sankey", sankey_data)
    
    if result:
        print(f"✅ Sankey chart rendered successfully ({len(result)} characters)")
    else:
        print("❌ Sankey chart rendering failed")
        return False
    
    # Test Heatmap chart
    heatmap_data = {
        "type": "heatmap",
        "title": "Test Heatmap Chart",
        "data": [
            {"x": "Q1", "y": "Company A", "value": 85},
            {"x": "Q2", "y": "Company A", "value": 92},
            {"x": "Q1", "y": "Company B", "value": 78},
            {"x": "Q2", "y": "Company B", "value": 88}
        ]
    }
    
    print("Testing Heatmap chart rendering...")
    result = await chart_renderer.render_tableau_chart("heatmap", heatmap_data)
    
    if result:
        print(f"✅ Heatmap chart rendered successfully ({len(result)} characters)")
    else:
        print("❌ Heatmap chart rendering failed")
        return False
    
    # Test Waterfall chart
    waterfall_data = {
        "type": "waterfall",
        "title": "Test Waterfall Chart",
        "data": [
            {"name": "Start", "value": 100},
            {"name": "Add", "value": 50},
            {"name": "Subtract", "value": -20},
            {"name": "Add More", "value": 30},
            {"name": "End", "value": 160}
        ]
    }
    
    print("Testing Waterfall chart rendering...")
    result = await chart_renderer.render_tableau_chart("waterfall", waterfall_data)
    
    if result:
        print(f"✅ Waterfall chart rendered successfully ({len(result)} characters)")
    else:
        print("❌ Waterfall chart rendering failed")
        return False
    
    print("\n🎉 All chart rendering tests passed!")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_chart_rendering())
    sys.exit(0 if success else 1)
