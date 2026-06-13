from __future__ import annotations

from typing import TYPE_CHECKING

from config import SUPABASE_ANON_KEY, SUPABASE_URL


if TYPE_CHECKING:
    from supabase import Client


_PLACEHOLDER_VALUES = {
    "",
    "your_supabase_url_here",
    "your_supabase_anon_key_here",
}


def is_supabase_configured() -> bool:
    """Return True only when both public Supabase settings are present."""
    return (
        SUPABASE_URL.lower() not in _PLACEHOLDER_VALUES
        and SUPABASE_ANON_KEY.lower() not in _PLACEHOLDER_VALUES
    )


def get_supabase_client() -> Client:
    """Create an isolated Supabase client using the public anonymous key."""
    if not is_supabase_configured():
        raise RuntimeError(
            "Supabase is not configured. Set SUPABASE_URL and "
            "SUPABASE_ANON_KEY in .env locally or Streamlit secrets in the cloud."
        )

    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError(
            "The Supabase Python package is not installed. Run "
            "`pip install -r requirements.txt`."
        ) from exc

    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
