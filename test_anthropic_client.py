#!/usr/bin/env python3
"""Test Anthropic client to see what's actually happening"""

import asyncio
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

async def test():
    from anthropic import AsyncAnthropic
    
    # Simulate what the model router does
    api_key = os.getenv("ANTHROPIC_API_KEY", "test-key")
    print(f"Creating client with key: {'Present' if api_key and api_key != 'test-key' else 'Missing'}")
    
    client = AsyncAnthropic(api_key=api_key)
    print(f"Client type: {type(client)}")
    print(f"Client: {client}")
    print(f"Has messages: {hasattr(client, 'messages')}")
    
    if hasattr(client, 'messages'):
        print(f"Messages type: {type(client.messages)}")
        print(f"Has create: {hasattr(client.messages, 'create')}")
        print(f"Messages dir: {[x for x in dir(client.messages) if not x.startswith('_')][:10]}")
        
        # Try to actually call it (will fail with bad key, but should show the structure)
        try:
            result = await client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=10,
                messages=[{"role": "user", "content": "hi"}]
            )
            print("SUCCESS!")
        except Exception as e:
            print(f"Call failed (expected with test key): {type(e).__name__}: {e}")
    else:
        print("❌ NO MESSAGES ATTRIBUTE!")
        print(f"Available attributes: {[x for x in dir(client) if not x.startswith('_')]}")

if __name__ == "__main__":
    asyncio.run(test())

