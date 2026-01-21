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

# Add backend to Python path
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Set Vercel environment variable
os.environ["VERCEL"] = "1"

# Change to backend directory for .env loading and relative imports
original_cwd = os.getcwd()
os.chdir(str(BACKEND_DIR))

try:
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv('.env')
    load_dotenv('.env.local', override=True)
    
    # Import the app from backend/api/index.py
    # Since we're in backend/ directory now, we can import api.index
    import api.index as backend_api
    app = backend_api.app
    
finally:
    # Restore original directory (Vercel may not care, but good practice)
    os.chdir(original_cwd)

# Vercel expects 'app' to be exported
__all__ = ['app']
