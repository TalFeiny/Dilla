"""
Vercel serverless function entrypoint for FastAPI app
Vercel automatically detects FastAPI apps when 'app' is exported
"""
from app.main import app

# Export the FastAPI app - Vercel's Python runtime will handle it automatically
