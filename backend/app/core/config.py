from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path
import os

ENV_PATH = Path(__file__).parent.parent.parent / ".env"
ENV_FILE_FOR_PYDANTIC = (
    str(ENV_PATH) if ENV_PATH.exists() and os.access(ENV_PATH, os.R_OK) else None
)


class Settings(BaseSettings):
    PROJECT_NAME: str = "Dilla AI"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    
    # Database
    SUPABASE_URL: Optional[str] = Field(None, env="SUPABASE_URL")
    SUPABASE_SERVICE_KEY: Optional[str] = Field(None, env="SUPABASE_SERVICE_KEY")
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = Field(None, env="SUPABASE_SERVICE_ROLE_KEY")
    SUPABASE_ANON_KEY: Optional[str] = Field(None, env="SUPABASE_ANON_KEY")
    NEXT_PUBLIC_SUPABASE_URL: Optional[str] = Field(None, env="NEXT_PUBLIC_SUPABASE_URL")
    NEXT_PUBLIC_SUPABASE_ANON_KEY: Optional[str] = Field(None, env="NEXT_PUBLIC_SUPABASE_ANON_KEY")
    
    # Security
    SECRET_KEY: str = Field(..., env="SECRET_KEY")  # Required — no default, must be set in .env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://localhost:8000",
            "https://dilla.ai",
            "https://dilla-ai.com",
            "https://www.dilla-ai.com",
        ]
    )
    
    # External APIs
    OPENAI_API_KEY: Optional[str] = Field(None, env="OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")
    TAVILY_API_KEY: Optional[str] = Field(None, env="TAVILY_API_KEY")
    FIRECRAWL_API_KEY: Optional[str] = Field(None, env="FIRECRAWL_API_KEY")
    CLAUDE_API_KEY: Optional[str] = Field(None, env="CLAUDE_API_KEY")
    GOOGLE_API_KEY: Optional[str] = Field(None, env="GOOGLE_API_KEY")

    # Email integration (Resend + Cloudflare Email Workers)
    RESEND_API_KEY: Optional[str] = Field(None, env="RESEND_API_KEY")
    EMAIL_WEBHOOK_SECRET: Optional[str] = Field(None, env="EMAIL_WEBHOOK_SECRET")
    EMAIL_FROM_DOMAIN: str = Field("dilla.ai", env="EMAIL_FROM_DOMAIN")
    
    # Model configuration for extraction with fallbacks
    PRIMARY_EXTRACTION_MODEL: str = Field("claude-sonnet-4-5", env="PRIMARY_EXTRACTION_MODEL")
    FALLBACK_MODEL_1: str = Field("gpt-5", env="FALLBACK_MODEL_1")
    FALLBACK_MODEL_2: str = Field("gpt-5", env="FALLBACK_MODEL_2")
    FALLBACK_MODEL_3: str = Field("claude-sonnet-4-5", env="FALLBACK_MODEL_3")
    
    # Python execution
    PYTHON_PATH: str = Field("python3", env="PYTHON_PATH")
    
    # Redis
    REDIS_URL: Optional[str] = Field(None, env="REDIS_URL")
    
    # Backend-agnostic storage and data (default: Supabase)
    STORAGE_PROVIDER: str = Field("supabase", env="STORAGE_PROVIDER")
    DATA_BACKEND: str = Field("supabase", env="DATA_BACKEND")
    COMPANY_DATA_BACKEND: Optional[str] = Field(None, env="COMPANY_DATA_BACKEND")  # None = use DATA_BACKEND
    STORAGE_BUCKET: str = Field("documents", env="STORAGE_BUCKET")
    STORAGE_PREFIX: str = Field("", env="STORAGE_PREFIX")
    
    # Feature flags
    ENABLE_STREAMING: bool = Field(True, env="ENABLE_STREAMING")
    ENABLE_WEBSOCKET: bool = Field(True, env="ENABLE_WEBSOCKET")
    ENABLE_MULTI_AGENT: bool = Field(True, env="ENABLE_MULTI_AGENT")
    ENABLE_RL_AGENT: bool = Field(True, env="ENABLE_RL_AGENT")
    
    # Environment
    ENVIRONMENT: str = Field("development", env="ENVIRONMENT")
    DEBUG: bool = Field(True, env="DEBUG")
    
    class Config:
        env_file = ENV_FILE_FOR_PYDANTIC
        env_file_encoding = 'utf-8'
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env


# Force reload of environment variables
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Calculate absolute path to .env file
# Path resolution from backend/app/core/config.py
# __file__ = /Users/admin/code/dilla-ai/backend/app/core/config.py
# parent.parent.parent = /Users/admin/code/dilla-ai/backend
# So this points to: backend/.env ✅ CORRECT
env_path = ENV_PATH

if env_path.exists() and os.access(env_path, os.R_OK):
    try:
        load_dotenv(env_path, override=True)
        logger.info(f"Loaded .env from: {env_path}")
    except PermissionError as exc:
        logger.warning(f"Unable to read .env file at {env_path}: {exc}")
else:
    logger.warning("No .env file found in backend/")

settings = Settings()

# Startup validation: Check for critical API keys
def validate_startup_config():
    """Validate critical API keys at startup and log warnings"""
    logger.info("=" * 80)
    logger.info("🔍 STARTUP VALIDATION: Checking API key configuration...")
    logger.info("=" * 80)
    
    missing_keys = []
    warnings = []
    
    # Check Tavily
    if not settings.TAVILY_API_KEY:
        missing_keys.append("TAVILY_API_KEY")
        warnings.append("🔴 TAVILY_API_KEY is missing - Tavily searches will not work")
    else:
        tavily_key = settings.TAVILY_API_KEY
        key_preview = tavily_key[:10] + "..." + tavily_key[-4:] if len(tavily_key) > 14 else "***"
        logger.info(f"✅ TAVILY_API_KEY configured: {key_preview}")
    
    # Check LLM API keys
    llm_keys = {
        "ANTHROPIC_API_KEY": settings.ANTHROPIC_API_KEY,
        "OPENAI_API_KEY": settings.OPENAI_API_KEY,
        "GOOGLE_API_KEY": settings.GOOGLE_API_KEY,
    }
    
    # Also check environment for keys not in settings
    import os
    additional_keys = {
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
        "TOGETHER_API_KEY": os.getenv("TOGETHER_API_KEY"),
        "PERPLEXITY_API_KEY": os.getenv("PERPLEXITY_API_KEY"),
        "ANYSCALE_API_KEY": os.getenv("ANYSCALE_API_KEY"),
    }
    
    available_llm_keys = []
    for key_name, key_value in {**llm_keys, **additional_keys}.items():
        if key_value:
            available_llm_keys.append(key_name)
        else:
            missing_keys.append(key_name)
    
    if not available_llm_keys:
        warnings.append("🔴 NO LLM API KEYS configured - ModelRouter will not work!")
        warnings.append("   At least one of the following is required:")
        warnings.append("   - ANTHROPIC_API_KEY")
        warnings.append("   - OPENAI_API_KEY")
        warnings.append("   - GOOGLE_API_KEY")
        warnings.append("   - GROQ_API_KEY")
        warnings.append("   - TOGETHER_API_KEY")
        warnings.append("   - PERPLEXITY_API_KEY")
        warnings.append("   - ANYSCALE_API_KEY")
    else:
        logger.info(f"✅ LLM API keys configured: {', '.join(available_llm_keys)}")
    
    # Log warnings
    if warnings:
        logger.warning("=" * 80)
        logger.warning("⚠️  STARTUP VALIDATION WARNINGS")
        logger.warning("=" * 80)
        for warning in warnings:
            logger.warning(warning)
        logger.warning("=" * 80)
        logger.warning(f"Missing keys: {', '.join(missing_keys)}")
        logger.warning("=" * 80)
    else:
        logger.info("✅ All critical API keys are configured")

# Run validation at module load
validate_startup_config()