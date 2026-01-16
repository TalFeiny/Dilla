"""
Diagnostic test for ModelRouter
Tests circuit breaker state, client initialization, and model availability
"""
import asyncio
import logging
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.model_router import ModelRouter, ModelCapability

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def test_diagnostic():
    """Run diagnostic tests on ModelRouter"""
    logger.info("=" * 80)
    logger.info("MODEL ROUTER DIAGNOSTIC TEST")
    logger.info("=" * 80)
    
    # Create router
    router = ModelRouter()
    
    logger.info("\n1. Checking API keys...")
    logger.info(f"ANTHROPIC_API_KEY: {'✅ Present' if router.anthropic_key else '❌ Missing'}")
    logger.info(f"OPENAI_API_KEY: {'✅ Present' if router.openai_key else '❌ Missing'}")
    logger.info(f"GROQ_API_KEY: {'✅ Present' if router.groq_key else '❌ Missing'}")
    logger.info(f"GOOGLE_API_KEY: {'✅ Present' if router.google_key else '❌ Missing'}")
    
    logger.info("\n2. Checking circuit breaker state...")
    logger.info(f"Circuit breakers: {router.circuit_breaker_until}")
    logger.info(f"Error counts: {router.error_counts}")
    
    logger.info("\n3. Initializing clients...")
    await router._init_clients_if_needed()
    
    logger.info("\n4. Checking client initialization...")
    logger.info(f"Clients initialized: {router._clients_initialized}")
    logger.info(f"Anthropic client: {'✅ Initialized' if router.anthropic_client else '❌ Not initialized'}")
    logger.info(f"OpenAI client: {'✅ Initialized' if router.openai_client else '❌ Not initialized'}")
    logger.info(f"Groq client: {'✅ Initialized' if router.groq_client else '❌ Not initialized'}")
    
    logger.info("\n5. Checking circuit breaker state after init...")
    logger.info(f"Circuit breakers: {router.circuit_breaker_until}")
    logger.info(f"Error counts: {router.error_counts}")
    
    logger.info("\n6. Testing get_model_order for ANALYSIS capability...")
    models = router._get_model_order(ModelCapability.ANALYSIS, None)
    logger.info(f"Models for ANALYSIS: {models}")
    
    logger.info("\n7. Testing with preferred model claude-sonnet-4-5...")
    models = router._get_model_order(ModelCapability.ANALYSIS, ["claude-sonnet-4-5"])
    logger.info(f"Models for ANALYSIS with preferred claude-sonnet-4-5: {models}")
    
    # Check circuit breaker for claude-sonnet-4-5
    logger.info("\n8. Checking circuit breaker for claude-sonnet-4-5...")
    is_broken = router._is_circuit_broken("claude-sonnet-4-5")
    logger.info(f"claude-sonnet-4-5 is broken: {is_broken}")
    
    if models:
        logger.info("\n9. Testing actual model call...")
        try:
            result = await router.get_completion(
                prompt="Say 'Diagnostic test successful'",
                capability=ModelCapability.ANALYSIS,
                max_tokens=100,
                preferred_models=["claude-sonnet-4-5"]
            )
            logger.info(f"✅ Model call successful!")
            logger.info(f"Model used: {result.get('model')}")
            logger.info(f"Response: {result.get('response')}")
        except Exception as e:
            logger.error(f"❌ Model call failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    logger.info("\n" + "=" * 80)
    logger.info("DIAGNOSTIC TEST COMPLETE")
    logger.info("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_diagnostic())

