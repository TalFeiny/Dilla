from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
import logging
import json
from dotenv import load_dotenv

# Load environment variables (try .env.local first, then .env)
from pathlib import Path
import os

env_path = Path('.env.local')
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

from app.api.router_fixed import api_router
# from app.api.websocket import manager, websocket_service
# from app.api.stripe_subscriptions import router as stripe_router
# from app.routers.deal_sourcing import router as deal_sourcing_router
# from app.api.endpoints.grpo import router as grpo_router
# from app.api.intelligent_orchestration import router as orchestration_router
from app.core.config import settings
from app.core.database import supabase_service
from app.core.error_handlers import (
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler,
    APIError,
    api_error_handler
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Dilla AI Backend...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    yield
    logger.info("Shutting down Dilla AI Backend...")


app = FastAPI(
    title="Dilla AI Backend",
    description="FastAPI backend for Dilla AI platform with WebSocket support",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add exception handlers
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(Exception, general_exception_handler)

# CORS middleware with proper security
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001", 
    "http://localhost:8000",
]

# Add production origins from environment
if os.getenv("PRODUCTION_ORIGIN"):
    allowed_origins.append(os.getenv("PRODUCTION_ORIGIN"))
if os.getenv("ALLOWED_ORIGINS"):
    allowed_origins.extend(os.getenv("ALLOWED_ORIGINS").split(","))

# Only allow all origins in development
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
# app.include_router(stripe_router)
# app.include_router(deal_sourcing_router)
# app.include_router(grpo_router, prefix="/api")
# app.include_router(orchestration_router)


@app.get("/")
async def root():
    return {
        "message": "Dilla AI Backend API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health",
        "websocket": "/ws"
    }


@app.get("/ws")
async def websocket_info():
    """WebSocket information endpoint"""
    return {
        "status": "available",
        "message": "WebSocket endpoint available. Connect using WebSocket protocol.",
        "url": "ws://localhost:8000/ws",
        "example": "const ws = new WebSocket('ws://localhost:8000/ws')",
        "protocols": ["chat", "streaming", "updates"]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "services": {
            "database": "connected" if supabase_service.get_client() else "disconnected",
            "websocket": "available",
            "api": "running"
        }
    }


# @app.websocket("/ws")
# async def websocket_endpoint_simple(websocket: WebSocket):
#     """Simple WebSocket endpoint without authentication"""
#     pass


# @app.websocket("/ws/{client_id}")
# async def websocket_endpoint(websocket: WebSocket, client_id: str):
#     """WebSocket endpoint for real-time communication with client ID"""
#     pass