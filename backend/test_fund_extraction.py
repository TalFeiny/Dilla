#!/usr/bin/env python3
"""
Test that fund context extraction works without hardcoded defaults
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.unified_mcp_orchestrator import UnifiedMCPOrchestrator


async def test_fund_extraction():
    """Test that fund context is properly extracted from user prompts"""
    
    orchestrator = UnifiedMCPOrchestrator()
    
    test_cases = [
        {
            "prompt": "analyze @Ramp and @Mercury for our 456m fund with 276m left to deploy",
            "expected_fund_size": 456_000_000,
            "expected_remaining": 276_000_000
        },
        {
            "prompt": "look at @Deel from perspective of 150M seed fund, 100M remaining",
            "expected_fund_size": 150_000_000,
            "expected_remaining": 100_000_000
        },
        {
            "prompt": "evaluate @Cursor for 1.2B growth fund with 800m to invest",
            "expected_fund_size": 1_200_000_000,
            "expected_remaining": 800_000_000
        }
    ]
    
    for i, test in enumerate(test_cases):
        print(f"\n=== Test Case {i+1} ===")
        print(f"Prompt: {test['prompt']}")
        
        try:
            # Extract entities
            entities = await orchestrator._extract_companies_and_fund(test["prompt"])
            
            # Check fund context
            fund_context = entities.get('fund_context', {})
            fund_size = fund_context.get('fund_size')
            remaining = fund_context.get('remaining_capital')
            
            print(f"Extracted fund_size: ${fund_size/1e6:.0f}M" if fund_size else "No fund_size extracted")
            print(f"Extracted remaining: ${remaining/1e6:.0f}M" if remaining else "No remaining extracted")
            
            # Validate
            if fund_size != test['expected_fund_size']:
                print(f"❌ FAILED: Expected ${test['expected_fund_size']/1e6:.0f}M, got ${fund_size/1e6:.0f}M" if fund_size else "None")
            else:
                print(f"✅ PASSED: Fund size correctly extracted")
                
            if remaining != test['expected_remaining']:
                print(f"❌ FAILED: Expected ${test['expected_remaining']/1e6:.0f}M remaining, got ${remaining/1e6:.0f}M" if remaining else "None")
            else:
                print(f"✅ PASSED: Remaining capital correctly extracted")
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_fund_extraction())