#!/usr/bin/env python3
"""Test script to verify all output formats are working correctly"""

import asyncio
import json
from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator

async def test_formats():
    orchestrator = UnifiedMCPOrchestrator()
    
    # Test prompt that triggers valuation
    test_prompt = "Compare @Deel and @Ramp for Series B investment"
    
    formats_to_test = ['matrix', 'spreadsheet', 'deck', 'docs', 'default']
    
    for format_name in formats_to_test:
        print(f"\n{'='*60}")
        print(f"Testing format: {format_name}")
        print('='*60)
        
        try:
            result = await orchestrator.process_request(
                prompt=test_prompt,
                output_format=format_name,
                context={}
            )
            
            # Check result structure
            if isinstance(result, dict):
                print(f"✅ {format_name}: Returns dict")
                
                # Check for key fields based on format
                if format_name == 'matrix':
                    if 'matrix' in result:
                        print(f"  ✅ Has 'matrix' field")
                        if 'columns' in result['matrix'] and 'rows' in result['matrix']:
                            print(f"  ✅ Has columns/rows structure")
                            # Check for scenarios in the matrix
                            rows = result['matrix'].get('rows', [])
                            has_scenarios = any('Scenario' in str(row) for row in rows)
                            if has_scenarios:
                                print(f"  ✅ Contains scenario data")
                        if 'metadata' in result:
                            print(f"  ✅ Has metadata")
                    else:
                        print(f"  ❌ Missing 'matrix' field")
                        print(f"  Keys found: {list(result.keys())[:5]}")
                
                elif format_name == 'spreadsheet':
                    # Should have format field set to 'spreadsheet'
                    if result.get('format') == 'spreadsheet':
                        print(f"  ✅ Format field = 'spreadsheet'")
                    if 'data' in result:
                        print(f"  ✅ Has 'data' field")
                    if 'citations' in result:
                        print(f"  ✅ Has 'citations' field")
                
                elif format_name in ['deck', 'docs']:
                    # Should have format field matching
                    if result.get('format') == format_name:
                        print(f"  ✅ Format field = '{format_name}'")
                    if 'data' in result:
                        print(f"  ✅ Has 'data' field")
                
                else:  # default
                    if 'format' in result:
                        print(f"  ✅ Has 'format' field: {result['format']}")
                    if 'data' in result:
                        print(f"  ✅ Has 'data' field")
                
                # Check for valuation data
                if 'data' in result:
                    data = result['data']
                    if 'valuation-engine' in data:
                        val_data = data['valuation-engine']
                        if 'scenarios' in val_data:
                            scenarios = val_data['scenarios']
                            if 'bear' in scenarios and 'base' in scenarios and 'bull' in scenarios:
                                print(f"  ✅ Has bear/base/bull scenarios")
                            else:
                                print(f"  ⚠️  Scenarios present but missing bear/base/bull")
                        else:
                            print(f"  ⚠️  No scenarios in valuation data")
                
            else:
                print(f"⚠️  {format_name}: Returns {type(result).__name__} instead of dict")
                
        except Exception as e:
            print(f"❌ {format_name}: Error - {str(e)}")

if __name__ == "__main__":
    print("Testing All Output Formats")
    print("="*60)
    asyncio.run(test_formats())
    print("\n" + "="*60)
    print("Format Testing Complete")