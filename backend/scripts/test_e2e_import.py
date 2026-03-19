#!/usr/bin/env python3
"""
Synthetic E2E test for the Linear → GitHub → challenge generation pipeline.

Defines a fake Linear issue and a fake GitHub PR diff inline — no real tokens needed.
Tests both paths:
  - existing_tests: a test file is "found" alongside the diff
  - llm_generated:  no test file, LLM generates from the diff

Usage (from backend/):
  uv run python scripts/test_e2e_import.py
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("OPENAI_API_KEY", os.environ.get("OPENAI_API_KEY", ""))

from integrations.generate import build_challenge_from_issue

# ---------------------------------------------------------------------------
# Synthetic Linear issue
# ---------------------------------------------------------------------------

SYNTHETIC_ISSUE = {
    "id": "SYNTH-1",
    "identifier": "ENG-42",
    "title": "Fix off-by-one in paginate()",
    "description": (
        "The `paginate` function returns one extra item on the last page. "
        "For example, `paginate([1,2,3,4,5], page=3, size=2)` returns `[5, None]` instead of `[5]`."
    ),
    "branchName": "eng-42-fix-paginate",
    "url": "https://linear.app/myteam/issue/ENG-42",
    "attachments": {"nodes": []},
}

# ---------------------------------------------------------------------------
# Synthetic GitHub PR diff
# ---------------------------------------------------------------------------

SYNTHETIC_CHANGED_FILES = [
    {
        "filename": "src/pagination.py",
        "patch": (
            "@@ -8,10 +8,10 @@\n"
            " \n"
            " \n"
            "-def paginate(items, page, size):\n"
            "-    \"\"\"Return one page of items (1-indexed). Off-by-one: includes extra item.\"\"\"\n"
            "-    return items[(page - 1) * size : page * size + 1]\n"
            "+def paginate(items, page, size):\n"
            "+    \"\"\"Return one page of items (1-indexed).\"\"\"\n"
            "+    return items[(page - 1) * size : page * size]\n"
        ),
    }
]

# ---------------------------------------------------------------------------
# Synthetic test file (used for the "existing_tests" path)
# ---------------------------------------------------------------------------

SYNTHETIC_TEST_FILE = """\
from src.pagination import paginate


def test_first_page():
    assert paginate([1, 2, 3, 4, 5], page=1, size=2) == [1, 2]


def test_middle_page():
    assert paginate([1, 2, 3, 4, 5], page=2, size=2) == [3, 4]


def test_last_page():
    assert paginate([1, 2, 3, 4, 5], page=3, size=2) == [5]


def test_empty_page_beyond_range():
    assert paginate([1, 2, 3], page=5, size=2) == []
"""


async def run_scenario(name: str, test_file_contents: list[str]):
    print(f"\n{'='*60}")
    print(f"Scenario: {name}")
    print(f"{'='*60}")
    print(f"Issue:    {SYNTHETIC_ISSUE['identifier']} — {SYNTHETIC_ISSUE['title']}")
    print(f"Changed:  {[f['filename'] for f in SYNTHETIC_CHANGED_FILES]}")
    print(f"Test files provided: {len(test_file_contents)}")

    challenge = await build_challenge_from_issue(
        SYNTHETIC_ISSUE,
        SYNTHETIC_CHANGED_FILES,
        test_file_contents,
    )

    print(f"\nTitle:        {challenge['title']}")
    print(f"Source:       {challenge['source']}")
    print(f"Starter code:\n  {challenge['starter_code'] or '(none)'}")
    print(f"\nTest cases ({len(challenge['test_cases'])}):")
    for tc in challenge["test_cases"]:
        print(f"  input:    {tc['input']}")
        print(f"  expected: {tc['expected_output']}")

    return challenge


async def main():
    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: Set OPENAI_API_KEY — the LLM is needed to parse/generate test cases.")
        sys.exit(1)

    # Path 1: test file exists → parse from real tests
    result_a = await run_scenario(
        "existing_tests — test file found alongside PR",
        test_file_contents=[SYNTHETIC_TEST_FILE],
    )
    assert result_a["source"] == "existing_tests"

    # Path 2: no test file → LLM generates from diff + description
    result_b = await run_scenario(
        "llm_generated — no test file, generate from diff",
        test_file_contents=[],
    )
    assert result_b["source"] == "llm_generated"

    print(f"\n{'='*60}")
    print("Both scenarios completed successfully.")
    print("\nFull JSON (existing_tests path):")
    print(json.dumps(result_a, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
