#!/usr/bin/env python3
"""
Test streaming functionality to verify the infinite loop fix
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime


async def test_streaming():
    """Test the streaming endpoint"""
    url = "http://localhost:8000/api/agent/unified-brain"
    
    # Test data
    payload = {
        "prompt": "Compare @Ramp and @Mercury for Series B investment",
        "output_format": "spreadsheet",
        "stream": True,
        "context": {}
    }
    
    print(f"[{datetime.now().isoformat()}] Starting streaming test...")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print("-" * 50)
    
    timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
    
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as response:
                print(f"Response status: {response.status}")
                
                if response.status != 200:
                    text = await response.text()
                    print(f"Error response: {text}")
                    return
                
                # Read streaming response
                update_count = 0
                complete_received = False
                done_received = False
                
                async for line in response.content:
                    if not line:
                        continue
                    
                    text = line.decode('utf-8').strip()
                    if not text:
                        continue
                    
                    # Process SSE data
                    if text.startswith('data: '):
                        data = text[6:]
                        update_count += 1
                        
                        if data == '[DONE]':
                            done_received = True
                            print(f"\n[{datetime.now().isoformat()}] Received [DONE] signal")
                            break
                        
                        try:
                            parsed = json.loads(data)
                            msg_type = parsed.get('type', 'unknown')
                            
                            # Log different message types
                            if msg_type == 'start':
                                print(f"[{update_count}] START: {parsed.get('message')}")
                            elif msg_type == 'progress':
                                print(f"[{update_count}] PROGRESS: {parsed.get('message')}")
                            elif msg_type == 'skill_chain':
                                print(f"[{update_count}] SKILL_CHAIN: {parsed.get('total_count')} skills")
                            elif msg_type == 'skill_start':
                                print(f"[{update_count}] SKILL_START: {parsed.get('skill')}")
                            elif msg_type == 'skill_complete':
                                print(f"[{update_count}] SKILL_COMPLETE: {parsed.get('skill')}")
                            elif msg_type == 'complete':
                                complete_received = True
                                print(f"[{update_count}] COMPLETE: {parsed.get('message')}")
                                # Check if result has data
                                if 'result' in parsed:
                                    result = parsed['result']
                                    if isinstance(result, dict):
                                        print(f"  Result keys: {list(result.keys())}")
                                        if 'commands' in result:
                                            print(f"  Commands: {len(result['commands'])} items")
                            elif msg_type == 'error':
                                print(f"[{update_count}] ERROR: {parsed.get('message')}")
                            else:
                                print(f"[{update_count}] {msg_type}: {str(parsed)[:100]}...")
                                
                        except json.JSONDecodeError as e:
                            print(f"[{update_count}] Failed to parse JSON: {e}")
                            print(f"  Raw data: {data[:100]}...")
                
                # Summary
                print("\n" + "=" * 50)
                print(f"Stream completed!")
                print(f"Total updates received: {update_count}")
                print(f"Complete message received: {complete_received}")
                print(f"Done signal received: {done_received}")
                
                if not done_received:
                    print("WARNING: Stream ended without [DONE] signal!")
                    return False
                
                return True
                
    except asyncio.TimeoutError:
        print(f"\n[ERROR] Stream timed out after 30 seconds - possible infinite loop!")
        return False
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        return False


async def main():
    """Main test function"""
    print("Testing streaming functionality for infinite loop fix...")
    print("=" * 50)
    
    success = await test_streaming()
    
    if success:
        print("\n✅ SUCCESS: Streaming completed without infinite loop!")
        sys.exit(0)
    else:
        print("\n❌ FAILED: Streaming encountered issues (timeout or incomplete)")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())