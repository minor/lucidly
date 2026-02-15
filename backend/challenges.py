"""In-memory challenge store with 3 challenges."""

from pydantic import BaseModel


class TestCase(BaseModel):
    input: str
    expected_output: str


class Challenge(BaseModel):
    id: str
    title: str
    description: str
    category: str  # ui, function, debug, system, data
    difficulty: str  # easy, medium, hard
    target_code: str | None = None
    test_suite: list[TestCase] | None = None
    starter_code: str | None = None
    image_url: str | None = None  # URL or path to challenge visual (image/gif)
    embed_url: str | None = None  # URL to embed as live page (e.g. for animated UIs)
    html_url: str | None = None  # Path to HTML file to render as reference


# ---------------------------------------------------------------------------
# Challenge Loader
# ---------------------------------------------------------------------------

import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def load_challenges_from_json() -> list[Challenge]:
    """Load challenges from local JSON file."""
    json_path = Path(__file__).parent / "challenges.json"
    if not json_path.exists():
        logger.error(f"challenges.json not found at {json_path}")
        return []
        
    try:
        with open(json_path, "r") as f:
            data = json.load(f)
            return [Challenge(**item) for item in data]
    except Exception as e:
        logger.error(f"Failed to load challenges: {e}")
        return []

# Load once at startup
ALL_CHALLENGES = load_challenges_from_json()

def get_all_challenges() -> list[Challenge]:
    return ALL_CHALLENGES


def get_challenge_by_id(challenge_id: str) -> Challenge | None:
    for c in ALL_CHALLENGES:
        if c.id == challenge_id:
            return c
    return None