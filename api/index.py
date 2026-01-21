"""
Vercel FastAPI entrypoint at root level
This file is required because Vercel builds from the root directory
and looks for entrypoints in api/index.py, api/app.py, etc.

This file sets up the Python path and imports the FastAPI app from backend.
"""
import sys
import os
from pathlib import Path

# Get the backend directory path
ROOT_DIR = Path(__file__).parent.parent
BACKEND_DIR = ROOT_DIR / "backend"

# Add backend to Python path (don't change directory - more reliable in serverless)
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Set Vercel environment variable
os.environ["VERCEL"] = "1"

# Load environment variables from backend directory
from dotenv import load_dotenv
env_file = BACKEND_DIR / ".env"
env_local_file = BACKEND_DIR / ".env.local"

if env_file.exists():
    load_dotenv(env_file)
if env_local_file.exists():
    load_dotenv(env_local_file, override=True)

# Import the app from backend/api/index.py
# Using direct import path since backend is in sys.path
from api.index import app

# Vercel expects 'app' to be exported
__all__ = ['app']
