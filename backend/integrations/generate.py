"""LLM-based test case parsing and generation for interview challenges."""

import json
import re
import logging
from llm import LLM
from config import settings

logger = logging.getLogger(__name__)

_PARSE_SYSTEM = """You are a test case extractor. Given Python test code, extract each test assertion as a JSON array of objects with keys "input" and "expected_output".
- "input" must be a Python expression that calls the function under test (e.g. `foo(1, 2)`)
- "expected_output" must be a Python literal of the expected return value (e.g. `[1, 2]`, `"hello"`, `42`, `None`)
- For void functions (no return value / `assert result is None`), use `"None"` as expected_output
- Output ONLY valid JSON array, no markdown, no explanation."""

_GENERATE_SYSTEM = """You are a test case generator for coding challenges. Given a bug description and code diff, generate test cases as a JSON array of objects with keys "input" and "expected_output".
- "input": a Python function call expression
- "expected_output": the expected return value as a Python literal, or "None" for void functions
- Generate 3-5 meaningful test cases that cover the described bug and edge cases
- Output ONLY valid JSON array, no markdown, no explanation."""


def _extract_json(text: str) -> list[dict]:
    """Extract JSON array from LLM response, stripping any markdown fences."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    parsed = json.loads(text)
    if not isinstance(parsed, list):
        raise ValueError("Expected JSON array")
    return [{"input": str(item["input"]), "expected_output": str(item["expected_output"])} for item in parsed]


async def parse_test_cases_from_file(test_file_content: str) -> list[dict]:
    """Parse existing pytest/unittest file into {input, expected_output} pairs."""
    llm = LLM(model=settings.default_model, system_prompt=_PARSE_SYSTEM)
    response = await llm.generate(
        f"Extract test cases from this test file:\n\n```python\n{test_file_content}\n```"
    )
    try:
        return _extract_json(response.response_text)
    except Exception as e:
        logger.warning("Failed to parse test cases from file: %s", e)
        return []


async def generate_test_cases_from_diff(title: str, description: str, diff_text: str) -> list[dict]:
    """Generate test cases from issue description and PR diff."""
    llm = LLM(model=settings.default_model, system_prompt=_GENERATE_SYSTEM)
    prompt = f"Issue: {title}\n\nDescription:\n{description}\n\nCode diff:\n```diff\n{diff_text}\n```"
    response = await llm.generate(prompt)
    try:
        return _extract_json(response.response_text)
    except Exception as e:
        logger.warning("Failed to generate test cases from diff: %s", e)
        return []


async def build_challenge_from_issue(
    issue: dict,
    changed_files: list[dict],
    test_file_contents: list[str],
) -> dict:
    """
    Given a Linear issue + GitHub PR data, return a populated challenge dict.
    Tries to use existing tests first; falls back to LLM generation.
    """
    title = issue.get("title", "")
    description = issue.get("description", "") or ""

    test_cases: list[dict] = []
    source = "llm_generated"

    for test_content in test_file_contents:
        parsed = await parse_test_cases_from_file(test_content)
        test_cases.extend(parsed)
    if test_cases:
        source = "existing_tests"

    if not test_cases:
        diff_text = "\n".join(
            f"--- {f['filename']}\n{f.get('patch', '')}"
            for f in changed_files
        )
        test_cases = await generate_test_cases_from_diff(title, description, diff_text)

    starter_code = _extract_stubs(changed_files)

    return {
        "title": title,
        "description": description,
        "starter_code": starter_code,
        "test_cases": test_cases,
        "source": source,
    }


def _extract_stubs(changed_files: list[dict]) -> str:
    """Extract function signatures from diff patches as stub starter code."""
    stubs = []
    for f in changed_files:
        patch = f.get("patch", "")
        for line in patch.splitlines():
            if line.startswith("+") and re.match(r"\+\s*def ", line):
                sig = line.lstrip("+").rstrip()
                stubs.append(sig)
                stubs.append("    pass")
                stubs.append("")
    return "\n".join(stubs).strip()
