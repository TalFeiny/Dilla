from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


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
    SECRET_KEY: str = Field(..., env="SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:8000",
            "https://dilla.ai"
        ]
    )
    
    # External APIs
    OPENAI_API_KEY: Optional[str] = Field(None, env="OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = Field(None, env="ANTHROPIC_API_KEY")
    TAVILY_API_KEY: Optional[str] = Field(None, env="TAVILY_API_KEY")
    FIRECRAWL_API_KEY: Optional[str] = Field(None, env="FIRECRAWL_API_KEY")
    CLAUDE_API_KEY: Optional[str] = Field(None, env="CLAUDE_API_KEY")
    GOOGLE_API_KEY: Optional[str] = Field(None, env="GOOGLE_API_KEY")
    
    # Model configuration for extraction with fallbacks
    PRIMARY_EXTRACTION_MODEL: str = Field("claude-3-5-sonnet-20241022", env="PRIMARY_EXTRACTION_MODEL")
    FALLBACK_MODEL_1: str = Field("claude-3-sonnet-20240229", env="FALLBACK_MODEL_1")
    FALLBACK_MODEL_2: str = Field("gpt-4-turbo-preview", env="FALLBACK_MODEL_2")
    FALLBACK_MODEL_3: str = Field("gemini-1.5-pro", env="FALLBACK_MODEL_3")
    
    # Python execution
    PYTHON_PATH: str = Field("python3", env="PYTHON_PATH")
    
    # Redis
    REDIS_URL: Optional[str] = Field(None, env="REDIS_URL")
    
    # Feature flags
    ENABLE_STREAMING: bool = Field(True, env="ENABLE_STREAMING")
    ENABLE_WEBSOCKET: bool = Field(True, env="ENABLE_WEBSOCKET")
    ENABLE_MULTI_AGENT: bool = Field(True, env="ENABLE_MULTI_AGENT")
    ENABLE_RL_AGENT: bool = Field(True, env="ENABLE_RL_AGENT")
    
    # Environment
    ENVIRONMENT: str = Field("development", env="ENVIRONMENT")
    DEBUG: bool = Field(True, env="DEBUG")
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env


# Force reload of environment variables
import os
from dotenv import load_dotenv
load_dotenv(override=True)

settings = Settings()