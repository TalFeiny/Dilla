"""
Test configuration and fixtures for the backend tests.
"""

import pytest
import os
from pathlib import Path
from dotenv import load_dotenv


@pytest.fixture(scope="session", autouse=True)
def load_test_env():
    """Load environment variables for tests."""
    # Ensure .env is loaded before any tests run
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        try:
            load_dotenv(env_path, override=True)
        except PermissionError:
            # Some CI sandboxes restrict access to .env files; skip loading when not permitted.
            pass
    
    # Set test-specific environment variables
    os.environ.setdefault("ENVIRONMENT", "test")
    os.environ.setdefault("DEBUG", "true")
    
    # Ensure we have required variables for testing
    if not os.getenv("SECRET_KEY"):
        os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only-min-32-chars"


@pytest.fixture
def test_settings():
    """Provide test settings."""
    from app.core.config import settings
    return settings


@pytest.fixture
def mock_supabase():
    """Mock Supabase client for tests."""
    class MockSupabaseClient:
        def table(self, table_name):
            return MockTable()
    
    class MockTable:
        def select(self, *args):
            return self
        
        def eq(self, *args):
            return self
        
        def execute(self):
            return MockResponse()
    
    class MockResponse:
        data = []
    
    return MockSupabaseClient()


@pytest.fixture
def mock_openai():
    """Mock OpenAI API for tests."""
    class MockOpenAI:
        def __init__(self):
            self.api_key = "test-key"
    
    return MockOpenAI()
