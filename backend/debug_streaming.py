#!/usr/bin/env python3
"""
Debug the streaming issue by calling the orchestrator directly
"""

import asyncio
import logging
from app.services.unified_mcp_orchestrator import get_unified_orchestrator

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_direct():
    """Test the orchestrator directly without HTTP"""
    print("Testing orchestrator directly...")
    
    orchestrator = get_unified_orchestrator()
    
    # Clear cache
    orchestrator._tavily_cache.clear()
    
    print("Starting process_request_stream...")
    
    try:
        update_count = 0
        async for update in orchestrator.process_request_stream(
            prompt="Compare @Ramp and @Mercury for Series B investment",
            output_format="spreadsheet",
            context={}
        ):
            update_count += 1
            update_type = update.get('type', 'unknown')
            print(f"[{update_count}] {update_type}: {update.get('message', '')[:100]}")
            
            if update_type == 'complete':
                print("Complete received!")
                break
            elif update_type == 'error':
                print(f"Error: {update.get('message')}")
                break
                
            # Safety check
            if update_count > 100:
                print("Too many updates, breaking...")
                break
                
        print(f"Total updates: {update_count}")
        
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_direct())