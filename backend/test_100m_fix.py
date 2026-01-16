#!/usr/bin/env python3
"""Test $100M ARR slide generation fix"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_100m_chart():
    """Test the Path to $100M ARR chart generation"""
    orchestrator = UnifiedMCPOrchestrator()
    
    print("Testing Path to $100M ARR chart generation...")
    print("=" * 60)
    
    # Test with Omnea and StackOne data
    test_companies = [
        {
            'company': 'Omnea',
            'revenue': 8_900_000,  # $8.9M
            'inferred_revenue': 8_900_000,
            'stage': 'Series B',
            'growth_rate': 1.5,  # 50% YoY
            'category': 'saas'
        },
        {
            'company': 'StackOne',
            'revenue': 4_700_000,  # $4.7M
            'inferred_revenue': 4_700_000,
            'stage': 'Series A',
            'growth_rate': 2.5,  # 150% YoY
            'category': 'ai_first'
        }
    ]
    
    # Set shared data
    orchestrator.shared_data = {'companies': test_companies}
    
    # Generate deck
    result = await orchestrator._execute_deck_generation({})
    
    # Find the Path to $100M slide
    slides = result.get('slides', [])
    path_slide = None
    
    for slide in slides:
        if 'Path to' in slide.get('content', {}).get('title', ''):
            path_slide = slide
            break
    
    if path_slide:
        print("✅ Found Path to $100M ARR slide")
        content = path_slide['content']
        chart_data = content.get('chart_data', {})
        datasets = chart_data.get('data', {}).get('datasets', [])
        
        print(f"\nSlide Title: {content.get('title')}")
        print(f"Subtitle: {content.get('subtitle')}")
        
        print("\nChart Data:")
        for dataset in datasets:
            label = dataset.get('label', 'Unknown')
            data = dataset.get('data', [])
            print(f"\n  {label}:")
            print(f"    Data points: {data}")
            
            # Validate data
            if data:
                print(f"    Starting ARR: ${data[0]:.1f}M")
                print(f"    Final ARR: ${data[-1]:.1f}M")
                
                # Check for issues
                if data[0] < 1:
                    print(f"    ❌ ERROR: Starting value too low (${data[0]:.2f}M)")
                elif data[0] > 100:
                    print(f"    ❌ ERROR: Starting value too high (${data[0]:.1f}M)")
                else:
                    print(f"    ✅ Starting value looks correct")
                
                # Check growth trajectory
                if all(data[i] >= data[i-1] for i in range(1, len(data))):
                    print(f"    ✅ Growth trajectory is monotonic")
                else:
                    print(f"    ❌ ERROR: Growth trajectory has dips")
                
                # Check if it reaches/approaches $100M
                if max(data) >= 100:
                    years_to_100m = next((i for i, v in enumerate(data) if v >= 100), None)
                    print(f"    ✅ Reaches $100M in year {years_to_100m}")
                else:
                    print(f"    ⚠️  Doesn't reach $100M (max: ${max(data):.1f}M)")
        
        # Check Y-axis options
        y_options = chart_data.get('options', {}).get('scales', {}).get('y', {})
        print(f"\nY-axis configuration:")
        print(f"  Type: {y_options.get('type', 'unknown')}")
        print(f"  Title: {y_options.get('title', {}).get('text', 'unknown')}")
        
        return True
    else:
        print("❌ Path to $100M ARR slide not found!")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_100m_chart())
    sys.exit(0 if success else 1)
