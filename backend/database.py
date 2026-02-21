from supabase import create_client, Client
from config import settings
import logging

logger = logging.getLogger(__name__)

_supabase: Client | None = None

def get_supabase_client() -> Client | None:
    """
    Get or initialize the Supabase client.
    Returns None if credentials are missing.
    """
    global _supabase
    if _supabase is None:
        if not settings.supabase_url or not settings.supabase_service_key:
            logger.warning("Supabase credentials not found. Persistence disabled.")
            return None
        try:
            _supabase = create_client(settings.supabase_url, settings.supabase_service_key)
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            return None
    return _supabase

async def save_challenge_session(
    challenge_id: str,
    title: str,
    category: str,
    difficulty: str,
    model: str,
    username: str,
    accuracy: float,
    time_seconds: float,
    total_tokens: int,
    total_turns: int,
    total_cost: float,
    composite_score: int,
    accuracy_score: int,
    speed_score: int,
    token_score: int,
    turn_score: int,
    messages: list[dict]
) -> str | None:
    """
    Save the challenge session and conversation logs to Supabase.
    Returns the session ID (UUID) on success, or None on failure.
    """
    supabase = get_supabase_client()
    if not supabase:
        return None

    try:
        # 1. Insert Session
        session_data = {
            "challenge_id": challenge_id,
            "title": title,
            "category": category,
            "difficulty": difficulty,
            "model": model,
            "username": username,
            "accuracy": accuracy,
            "time_seconds": time_seconds,
            "total_tokens": total_tokens,
            "total_turns": total_turns,
            "total_cost": total_cost,
            "composite_score": composite_score,
            "accuracy_score": accuracy_score,
            "speed_score": speed_score,
            "token_score": token_score,
            "turn_score": turn_score,
        }
        
        response = supabase.table("challenge_sessions").insert(session_data).execute()
        if not response.data or len(response.data) == 0:
            logger.error("Failed to insert challenge session")
            return None
            
        session_id = response.data[0]["id"]

        # 2. Insert Conversation Logs (Bulk)
        logs_data = []
        for i, msg in enumerate(messages):
            logs_data.append({
                "session_id": session_id,
                "role": msg.get("role", "unknown"),
                "content": msg.get("content", ""),
                "turn_number": i + 1
            })
            
        if logs_data:
            supabase.table("conversation_logs").insert(logs_data).execute()
            
        return session_id

    except Exception as e:
        logger.error(f"Error saving to Supabase: {e}")
        return None

async def save_prompt_feedback(session_id: str, feedback: str) -> bool:
    """
    Save prompt feedback text for an existing challenge session.
    Returns True on success, False on failure.
    """
    supabase = get_supabase_client()
    if not supabase:
        return False

    try:
        response = (
            supabase.table("challenge_sessions")
            .update({"prompt_feedback": feedback})
            .eq("id", session_id)
            .execute()
        )
        return bool(response.data)
    except Exception as e:
        logger.error(f"Error saving prompt feedback: {e}")
        return False


async def count_user_challenge_sessions_today(username: str, challenge_id: str) -> int:
    """Count how many times a user has played a specific challenge today."""
    supabase = get_supabase_client()
    if not supabase:
        return 0
    try:
        from datetime import date, timezone
        today = date.today().isoformat()
        response = (
            supabase.table("challenge_sessions")
            .select("id", count="exact")
            .eq("username", username)
            .eq("challenge_id", challenge_id)
            .gte("created_at", today)
            .execute()
        )
        return response.count or 0
    except Exception as e:
        logger.error(f"Error counting daily sessions: {e}")
        return 0


async def get_username_by_auth0_id(auth0_id: str) -> str | None:
    """Fetch the chosen username for an Auth0 user. Returns None if not set."""
    supabase = get_supabase_client()
    if not supabase:
        return None
    try:
        response = (
            supabase.table("usernames")
            .select("username")
            .eq("auth0_id", auth0_id)
            .limit(1)
            .execute()
        )
        if response.data and len(response.data) > 0:
            return response.data[0]["username"]
        return None
    except Exception as e:
        logger.error(f"Error fetching username: {e}")
        return None


async def is_username_taken(username: str) -> bool:
    """Check if a username is already in use (case-insensitive)."""
    supabase = get_supabase_client()
    if not supabase:
        return False
    try:
        response = (
            supabase.table("usernames")
            .select("id")
            .ilike("username", username)
            .limit(1)
            .execute()
        )
        return bool(response.data and len(response.data) > 0)
    except Exception as e:
        logger.error(f"Error checking username: {e}")
        return False


async def set_username(auth0_id: str, username: str) -> bool:
    """
    Store a username for an Auth0 user.
    Uses upsert keyed on auth0_id so calling it again updates the name.
    Returns True on success.
    """
    supabase = get_supabase_client()
    if not supabase:
        return False
    try:
        supabase.table("usernames").upsert(
            {"auth0_id": auth0_id, "username": username},
            on_conflict="auth0_id",
        ).execute()
        return True
    except Exception as e:
        logger.error(f"Error setting username: {e}")
        return False


async def get_leaderboard(
    challenge_id: str = None, 
    limit: int = 50,
    sort_by: str = "composite_score", 
    ascending: bool = False
) -> list[dict]:
    """
    Fetch leaderboard entries.
    """
    supabase = get_supabase_client()
    if not supabase:
        return []

    try:
        query = supabase.table("challenge_sessions").select("*")
        
        if challenge_id:
            query = query.eq("challenge_id", challenge_id)
            
        # Mapping sort keys to DB columns if needed (currently they match)
        order_col = sort_by
        
        query = query.order(order_col, desc=not ascending).limit(limit)
        
        response = query.execute()
        return response.data
    except Exception as e:
        logger.error(f"Error fetching leaderboard: {e}")
        return []
