"""Test LLM calls to verify ModelRouter lazy initialization works"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

# Load environment variables
load_dotenv('backend/.env.local')
load_dotenv('backend/.env')

async def test_model_router():
    from app.services.model_router import get_model_router, ModelCapability
    
    print("Testing ModelRouter lazy initialization...")
    
    # Get the singleton router (this should NOT initialize clients yet)
    router = get_model_router()
    print(f"✅ ModelRouter instantiated successfully")
    print(f"   _clients_initialized: {router._clients_initialized}")
    print(f"   anthropic_client: {router.anthropic_client}")
    print(f"   openai_client: {router.openai_client}")
    
    # Now try to make an actual LLM call
    print("\nTesting LLM call...")
    try:
        response = await router.get_completion(
            prompt="Say 'Hello, this is a test'",
            capability=ModelCapability.ANALYSIS,
            preferred_models=["claude-sonnet-4-5", "gpt-4-turbo"],
            max_tokens=50,
            temperature=0.7
        )
        
        print(f"✅ LLM call successful!")
        print(f"   Response: {response}")
        print(f"   _clients_initialized after call: {router._clients_initialized}")
    except Exception as e:
        print(f"❌ LLM call failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_model_router())
