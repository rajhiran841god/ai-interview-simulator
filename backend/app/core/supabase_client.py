"""
Single point of contact for Supabase. Nothing else in the codebase should
import the supabase SDK directly — go through get_supabase() so the
storage/auth provider can be swapped later without touching business logic
(Architecture Review Gate #3: Provider Independence).
"""
from functools import lru_cache
from supabase import create_client, Client

from app.core.config import settings


@lru_cache
def get_supabase() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)


@lru_cache
def get_supabase_admin() -> Client:
    """Service-role client — server-side privileged operations only.
    Never expose this client or its key to the frontend."""
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
