"""
Vercel FastAPI entrypoint at root level
Vercel automatically detects index.py, app.py, or server.py at the root
This file imports the FastAPI app from the backend directory.
"""
import sys
import os
from pathlib import Path

# Get the backend directory path
ROOT_DIR = Path(__file__).parent
BACKEND_DIR = ROOT_DIR / "backend"

# Add backend to Python path (required for backend's relative imports)
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

# Import the app from backend/api/index.py using direct file import
# This ensures all backend relative imports work correctly
import importlib.util
backend_api_index_path = BACKEND_DIR / "api" / "index.py"
spec = importlib.util.spec_from_file_location("backend_api_index", backend_api_index_path)
backend_api_index = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backend_api_index)
app = backend_api_index.app

# Vercel expects 'app' to be exported
__all__ = ['app']
