"""
Vercel FastAPI entrypoint
Vercel doesn't support lifespan events, so we create the app without it

This file uses static imports that Vercel's bundler can detect.
We add backend/ to sys.path but avoid os.chdir() which breaks static analysis.
"""
import sys
import os
from pathlib import Path

# Calculate paths statically (Vercel can trace these)
ROOT_DIR = Path(__file__).parent.parent
BACKEND_DIR = ROOT_DIR / "backend"

# Add backend to Python path for app.* imports (static operation)
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Set Vercel flag
os.environ["VERCEL"] = "1"

# Load environment variables from backend directory (absolute paths)
from dotenv import load_dotenv
env_file = BACKEND_DIR / ".env"
env_local_file = BACKEND_DIR / ".env.local"

if env_file.exists():
    load_dotenv(env_file, override=False)
if env_local_file.exists():
    load_dotenv(env_local_file, override=True)

# Import after setting Vercel flag and path setup
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

from app.api.router_fixed import api_router
from app.routers.deck_storage import router as deck_storage_router
from app.core.config import settings
from app.core.logging_config import logger, setup_logging
from app.core.error_handlers import (
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler,
    APIError,
    api_error_handler
)

# Configure logging
if not logging.getLogger().handlers:
    setup_logging(level="INFO", enable_json=False, enable_console=True)

# Create FastAPI app WITHOUT lifespan for Vercel compatibility
app = FastAPI(
    title="Dilla AI Backend",
    description="FastAPI backend for Dilla AI platform",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add exception handlers
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(Exception, general_exception_handler)

# CORS middleware
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:8000",
]

if os.getenv("PRODUCTION_ORIGIN"):
    allowed_origins.append(os.getenv("PRODUCTION_ORIGIN"))
if os.getenv("ALLOWED_ORIGINS"):
    allowed_origins.extend(os.getenv("ALLOWED_ORIGINS").split(","))

if settings.ENVIRONMENT == "development" and settings.DEBUG:
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix="/api")
app.include_router(deck_storage_router)

@app.get("/")
async def root():
    return {
        "message": "Dilla AI Backend API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/health")
async def health_check():
    try:
        from app.core.database import supabase_service
        db_status = "connected" if supabase_service.get_client() else "disconnected"
    except Exception as e:
        logger.error(f"Supabase health check failed: {e}")
        db_status = "error"
    
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "services": {
            "database": db_status,
            "api": "running"
        }
    }

# Vercel expects 'app' to be exported
__all__ = ['app']
