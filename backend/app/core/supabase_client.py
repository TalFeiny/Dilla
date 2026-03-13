"""
Supabase client accessor.

Thin wrapper so the rest of the codebase can do:

    from app.core.supabase_client import get_supabase_client

Delegates to the single SupabaseService in database.py — there is
only ONE Supabase client instance for the whole app.
"""

from typing import Optional
from supabase import Client

from app.core.database import get_supabase_service


def get_supabase_client() -> Optional[Client]:
    """Return the shared Supabase client (lazy-initialised)."""
    return get_supabase_service().get_client()
