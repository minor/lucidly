"""Token storage for OAuth integrations using Supabase."""
import logging
from database import get_supabase_client

logger = logging.getLogger(__name__)


def get_integration(user_id: str, provider: str) -> str | None:
    """Return the stored access token for a provider, or None if not connected."""
    supabase = get_supabase_client()
    if not supabase:
        return None
    try:
        resp = (
            supabase.table("user_integrations")
            .select("access_token")
            .eq("user_id", user_id)
            .eq("provider", provider)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]["access_token"]
        return None
    except Exception as e:
        logger.error("get_integration error: %s", e)
        return None


def get_refresh_token(user_id: str, provider: str) -> str | None:
    """Return the stored refresh token for a provider, or None if not available."""
    supabase = get_supabase_client()
    if not supabase:
        return None
    try:
        resp = (
            supabase.table("user_integrations")
            .select("refresh_token")
            .eq("user_id", user_id)
            .eq("provider", provider)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]["refresh_token"]
        return None
    except Exception as e:
        logger.error("get_refresh_token error: %s", e)
        return None


def upsert_integration(user_id: str, provider: str, access_token: str, refresh_token: str | None = None) -> None:
    """Store or update an OAuth token for a provider."""
    supabase = get_supabase_client()
    if not supabase:
        raise RuntimeError("Supabase unavailable")
    supabase.table("user_integrations").upsert(
        {
            "user_id": user_id,
            "provider": provider,
            "access_token": access_token,
            "refresh_token": refresh_token,
        },
        on_conflict="user_id,provider",
    ).execute()
