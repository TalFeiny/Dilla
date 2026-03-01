from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
import logging
import json
from dotenv import load_dotenv

# Load environment variables (try .env.local first, then .env)
from pathlib import Path
import os

# Load environment variables (.env.local takes precedence)
load_dotenv('.env')  # Load .env first (baseline)
load_dotenv('.env.local', override=True)  # Then override with .env.local if it exists

from app.api.router_fixed import api_router
from app.routers.deck_storage import router as deck_storage_router
# from app.api.websocket import manager, websocket_service
# from app.api.stripe_subscriptions import router as stripe_router
# from app.routers.deal_sourcing import router as deal_sourcing_router
# from app.api.endpoints.grpo import router as grpo_router
# from app.api.intelligent_orchestration import router as orchestration_router
from app.core.config import settings
# Enhanced logging configuration
from app.core.logging_config import logger, setup_logging
# Lazy import to prevent startup errors
from app.core.error_handlers import (
    http_exception_handler,
    validation_exception_handler,
    general_exception_handler,
    APIError,
    api_error_handler
)

# Configure enhanced logging with rotation
if not logging.getLogger().handlers:
    setup_logging(
        level="INFO",
        enable_json=False,
        enable_console=True
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Dilla AI Backend...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    # Initialize cell action registry so all actions are available immediately
    try:
        from app.services.cell_action_registry import get_registry
        get_registry().initialize_core_services()
        logger.info("Cell action registry initialized")
    except Exception as e:
        logger.error(f"Failed to initialize cell action registry: {e}")
    yield
    logger.info("Shutting down Dilla AI Backend...")


_is_production = settings.ENVIRONMENT != "development"

app = FastAPI(
    title="Dilla AI Backend",
    description="FastAPI backend for Dilla AI platform with WebSocket support",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
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
    "https://dilla.ai",
    "https://dilla-ai.com",
    "https://www.dilla-ai.com",
]

# Add production origins from environment
if os.getenv("PRODUCTION_ORIGIN"):
    allowed_origins.append(os.getenv("PRODUCTION_ORIGIN"))
if os.getenv("ALLOWED_ORIGINS"):
    allowed_origins.extend(os.getenv("ALLOWED_ORIGINS").split(","))

# Only allow all origins in development
if settings.ENVIRONMENT == "development" and settings.DEBUG:
    allowed_origins = ["*"]

# Backend API secret — frontend must send this header to talk to the backend.
# Without it, anyone who finds the Railway URL can call every endpoint.
# Set BACKEND_API_SECRET in both the backend and frontend env vars.
BACKEND_API_SECRET = (os.getenv("BACKEND_API_SECRET") or "").strip() or None


class BackendGateMiddleware(BaseHTTPMiddleware):
    """Reject requests without the correct X-Backend-Secret header in production."""

    # Paths that must remain open (health checks, CORS preflight)
    OPEN_PATHS = ("/health", "/api/health", "/api/email/inbound", "/api/debug-gate")

    async def dispatch(self, request: Request, call_next):
        # Always allow in development, OPTIONS preflight, and health checks
        if (
            not _is_production
            or not BACKEND_API_SECRET
            or request.method == "OPTIONS"
            or request.url.path in self.OPEN_PATHS
        ):
            return await call_next(request)

        if request.headers.get("X-Backend-Secret") != BACKEND_API_SECRET:
            got = (request.headers.get("X-Backend-Secret") or "")[:8]
            expected = (BACKEND_API_SECRET or "")[:8]
            logger.warning(
                f"Gate rejected: got={got}... expected={expected}... "
                f"path={request.url.path} method={request.method} "
                f"has_header={'X-Backend-Secret' in request.headers}"
            )
            return JSONResponse({"error": "Unauthorized"}, status_code=403)

        return await call_next(request)


# Gate middleware runs BEFORE CORS so unauthenticated requests never reach handlers
app.add_middleware(BackendGateMiddleware)

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
# app.include_router(stripe_router)
# app.include_router(deal_sourcing_router)
# app.include_router(grpo_router, prefix="/api")
# app.include_router(orchestration_router)


@app.get("/api/debug-gate")
async def debug_gate(request: Request):
    """Temporary debug endpoint — bypasses gate to diagnose secret mismatch. DELETE after fixing."""
    got_raw = request.headers.get("X-Backend-Secret") or ""
    expected_raw = BACKEND_API_SECRET or ""
    return {
        "got_prefix": got_raw[:12],
        "got_len": len(got_raw),
        "got_repr_tail": repr(got_raw[-5:]) if got_raw else "empty",
        "expected_prefix": expected_raw[:12],
        "expected_len": len(expected_raw),
        "expected_repr_tail": repr(expected_raw[-5:]) if expected_raw else "empty",
        "match": got_raw == expected_raw,
        "is_production": _is_production,
        "secret_set_on_backend": bool(BACKEND_API_SECRET),
    }


@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/ws")
async def websocket_info():
    """WebSocket information endpoint"""
    return {"status": "available"}


@app.get("/health")
async def health_check():
    """Health check endpoint - kept lightweight for Railway health checks"""
    return {"status": "healthy"}


# @app.websocket("/ws")
# async def websocket_endpoint_simple(websocket: WebSocket):
#     """Simple WebSocket endpoint without authentication"""
#     pass


# @app.websocket("/ws/{client_id}")
# async def websocket_endpoint(websocket: WebSocket, client_id: str):
#     """WebSocket endpoint for real-time communication with client ID"""
#     pass