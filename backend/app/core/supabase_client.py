"""
Supabase client accessor.

Thin wrapper around DatabasePool.get_supabase_client() so the rest of
the codebase can do:

    from app.core.supabase_client import get_supabase_client
"""

from typing import Optional
from supabase import Client

from app.core.database_pool import db_pool


def get_supabase_client() -> Optional[Client]:
    """Return the shared Supabase client (lazy-initialised)."""
    return db_pool.get_supabase_client()
