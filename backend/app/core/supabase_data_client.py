"""
Shared Supabase client for the persistent engine stores (Decision Log
#006 — storage-layer infrastructure, not an engine change). Separate
from app/core/supabase_client.py's frontend-facing auth client — this
one uses the SERVICE_ROLE_KEY (server-side, bypasses row-level
security) since these tables are written by the backend/voice worker
processes, not directly by end users.
"""

from functools import lru_cache
from typing import Any

from supabase import create_client, Client

from app.core.config import settings


@lru_cache
def get_data_client() -> Client:
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def as_json_dict(row: Any, key: str) -> dict[str, Any]:
    """
    Type-narrowing helper: postgrest's .execute() types both entire
    rows and individual JSONB columns as a generic JSON-shaped union
    (str | int | float | list | dict | None), even though a query
    row is always genuinely a dict at runtime, and a JSONB column
    storing a Pydantic model_dump() is always genuinely a dict too.
    Takes `Any` deliberately — that's what postgrest's real return
    type actually is — and validates fully at runtime instead of
    scattering individual isinstance checks or type-ignore comments
    across 5 different files.
    """
    if not isinstance(row, dict):
        raise TypeError(
            f"Expected a row object (dict), got {type(row).__name__}. "
            "This indicates an unexpected query result shape."
        )
    value = row[key]
    if not isinstance(value, dict):
        raise TypeError(
            f"Expected a JSON object for column '{key}', got {type(value).__name__}. "
            "This indicates corrupted or unexpected data in the database."
        )
    return value
