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
        id="two-sum",
        title="Two Sum",
        description=(
            "Write a Python function `two_sum(nums, target)` that takes a list of "
            "integers and a target integer. Return the indices of the two numbers "
            "that add up to the target.\n\n"
            "You may assume each input has exactly one solution, and you may not use "
            "the same element twice. Return the answer as a list of two indices."
        ),
        category="function",
        difficulty="easy",
        test_suite=[
            TestCase(input="two_sum([2, 7, 11, 15], 9)", expected_output="[0, 1]"),
            TestCase(input="two_sum([3, 2, 4], 6)", expected_output="[1, 2]"),
            TestCase(input="two_sum([3, 3], 6)", expected_output="[0, 1]"),
            TestCase(input="two_sum([1, 5, 3, 7], 8)", expected_output="[1, 2]"),
            TestCase(input="two_sum([-1, 0, 1, 2], 1)", expected_output="[0, 3]"),
        ],
    ),
    Challenge(
        id="fizzbuzz",
        title="FizzBuzz",
        description=(
            "Write a Python function `fizzbuzz(n)` that returns a list of strings "
            "from 1 to n. For multiples of 3, use 'Fizz'. For multiples of 5, use "
            "'Buzz'. For multiples of both, use 'FizzBuzz'. Otherwise, use the "
            "number as a string."
        ),
        category="function",
        difficulty="easy",
        test_suite=[
            TestCase(input="fizzbuzz(3)", expected_output="['1', '2', 'Fizz']"),
            TestCase(input="fizzbuzz(5)", expected_output="['1', '2', 'Fizz', '4', 'Buzz']"),
            TestCase(input="fizzbuzz(15)[-1]", expected_output="'FizzBuzz'"),
            TestCase(input="fizzbuzz(1)", expected_output="['1']"),
            TestCase(input="len(fizzbuzz(100))", expected_output="100"),
        ],
    ),
    Challenge(
        id="debug-lis",
        title="Debug: Longest Increasing Subsequence",
        description=(
            "The following function is supposed to return the length of the longest "
            "STRICTLY increasing subsequence, but it has a subtle bug. It produces "
            "correct results for many inputs but fails on others.\n\n"
            "Find and fix the bug. Your fixed function must be named "
            "`longest_increasing_subsequence`."
        ),
        category="function",
        difficulty="easy",
        starter_code=(
            "import bisect\n\n"
            "def longest_increasing_subsequence(nums):\n"
            "    if not nums:\n"
            "        return 0\n"
            "    tails = []\n"
            "    for num in nums:\n"
            "        pos = bisect.bisect_right(tails, num)\n"
            "        if pos == len(tails):\n"
            "            tails.append(num)\n"
            "        else:\n"
            "            tails[pos] = num\n"
            "    return len(tails)\n"
        ),
        target_code=(
            "import bisect\n\n"
            "def longest_increasing_subsequence(nums):\n"
            "    if not nums:\n"
            "        return 0\n"
            "    tails = []\n"
            "    for num in nums:\n"
            "        pos = bisect.bisect_left(tails, num)\n"
            "        if pos == len(tails):\n"
            "            tails.append(num)\n"
            "        else:\n"
            "            tails[pos] = num\n"
            "    return len(tails)\n"
        ),
        test_suite=[
            # These pass even with the bug (no duplicates):
            TestCase(
                input="longest_increasing_subsequence([10, 9, 2, 5, 3, 7, 101, 18])",
                expected_output="4",
            ),
            TestCase(
                input="longest_increasing_subsequence([1, 2, 3, 4, 5])",
                expected_output="5",
            ),
            # These EXPOSE the bug (duplicates):
            TestCase(
                input="longest_increasing_subsequence([7, 7, 7, 7, 7])",
                expected_output="1",
            ),
            TestCase(
                input="longest_increasing_subsequence([3, 1, 2, 1, 2, 3])",
                expected_output="3",
            ),
            TestCase(
                input="longest_increasing_subsequence([1, 1, 1, 2, 2, 3])",
                expected_output="3",
            ),
            TestCase(
                input="longest_increasing_subsequence([])",
                expected_output="0",
            ),
        ],
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
