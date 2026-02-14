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


# ---------------------------------------------------------------------------
# Seed library — 3 challenges
# ---------------------------------------------------------------------------

SEED_CHALLENGES: list[Challenge] = [
    Challenge(
        id="build-landing-page",
        title="Build this UI: Landing Page",
        description=(
            "Recreate this landing page UI."
        ),
        category="ui",
        difficulty="medium",
        embed_url="https://treehacks.com/",
    ),
    Challenge(
        id="build-snake-game",
        title="Build this UI: Snake Game",
        description=(
            "Recreate this snake game. Match the look and behavior shown in the "
            "reference animation: grid-based movement, growing when eating, "
            "and game-over on collision. Use HTML, CSS, and JavaScript."
        ),
        category="ui",
        difficulty="medium",
        image_url="https://media.giphy.com/media/13GIgrGdslD9o0/giphy.gif",
    ),
    Challenge(
        id="nyt-front-page-scraper",
        title="NYT Front Page Scraper",
        description=(
            "Build a web scraper that grabs all the articles on the NYT front page "
            "(https://www.nytimes.com). Extract article titles, URLs, and optionally "
            "summaries or bylines. Return structured data (e.g. JSON or list of dicts). "
            "Use Python with requests/BeautifulSoup, or another language of your choice."
        ),
        category="data",
        difficulty="medium",
    ),
]


def get_all_challenges() -> list[Challenge]:
    return SEED_CHALLENGES


def get_challenge_by_id(challenge_id: str) -> Challenge | None:
    for c in SEED_CHALLENGES:
        if c.id == challenge_id:
            return c
    return None
