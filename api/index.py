"""
Vercel FastAPI entrypoint
Vercel auto-detects Python files in api/ directory
"""
import sys
import os
from pathlib import Path

# Setup paths
ROOT_DIR = Path(__file__).parent.parent
BACKEND_DIR = ROOT_DIR / "backend"

# Add backend to Python path
sys.path.insert(0, str(BACKEND_DIR))

# Change to backend directory for relative imports
os.chdir(str(BACKEND_DIR))

# Set Vercel flag
os.environ["VERCEL"] = "1"

# Load environment variables
from dotenv import load_dotenv
load_dotenv('.env')
load_dotenv('.env.local', override=True)

# Import app from main.py and create Vercel-compatible version without lifespan
from app.main import app as main_app
from fastapi import FastAPI

# Create new app instance without lifespan for Vercel
app = FastAPI(
    title=main_app.title,
    description=main_app.description,
    version=main_app.version,
    docs_url=main_app.docs_url,
    redoc_url=main_app.redoc_url
)

# Copy all routes and middleware from main app
for route in main_app.routes:
    app.routes.append(route)

for middleware in main_app.user_middleware:
    app.user_middleware.append(middleware)

# Copy exception handlers
for exc_type, handler in main_app.exception_handlers.items():
    app.exception_handlers[exc_type] = handler

__all__ = ['app']
