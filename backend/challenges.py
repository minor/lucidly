"""In-memory challenge store with challenges loaded from JSON."""

from pydantic import BaseModel, Field


class TestCase(BaseModel):
    input: str
    expected_output: str


class ProductPart(BaseModel):
    part: int
    title: str
    description: str


class RepoContext(BaseModel):
    owner: str
    repo: str
    base_sha: str
    file_paths: list[str]        # repo-relative paths of all changed source files
    challenge_test_ids: list[str]  # PR-fixed test node IDs; empty = run full suite
    github_token: str | None = None  # embedded at challenge-creation time for evaluation
    # Legacy single-file field — kept for backward compat with existing DB rows
    file_path: str | None = None


class Challenge(BaseModel):
    id: str
    title: str
    description: str
    category: str  # UI, function, debug, system, data, product
    difficulty: str  # easy, medium, hard
    target_code: str | None = None
    test_suite: list[TestCase] | None = None
    starter_code: str | None = None
    image_url: str | None = None
    embed_url: str | None = None
    html_url: str | None = None
    product_parts: list[ProductPart] | None = None
    agent_context: str | None = None
    # GitHub repo-context fields (populated for merged-PR challenges)
    user_id: str | None = None
    repo_context: RepoContext | None = None
    test_files: list[dict] = Field(default_factory=list)  # [{path, content}] at HEAD SHA


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