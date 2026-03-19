"""LLM-based test case parsing and generation for interview challenges."""

import json
import logging
import re

from llm import LLM
from config import settings
from integrations.github_runner import discover_pr_fixed_tests
from integrations.store import get_integration

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


def _format_ci_failures(annotations: list[dict]) -> str:
    """Format CI failure annotations into a readable string for the LLM prompt."""
    if not annotations:
        return ""
    lines = ["CI test failures:"]
    for a in annotations:
        title = a.get("title") or a.get("path", "unknown test")
        message = a.get("message", "")
        lines.append(f"- {title}: {message}" if message else f"- {title}")
    return "\n".join(lines)


async def generate_test_cases_from_diff(
    title: str, description: str, diff_text: str, ci_failures: str = ""
) -> list[dict]:
    """Generate test cases from issue description, PR diff, and optional CI failure info."""
    llm = LLM(model=settings.default_model, system_prompt=_GENERATE_SYSTEM)
    prompt = f"Issue: {title}\n\nDescription:\n{description}\n\nCode diff:\n```diff\n{diff_text}\n```"
    if ci_failures:
        prompt += f"\n\n{ci_failures}"
    response = await llm.generate(prompt)
    try:
        return _extract_json(response.response_text)
    except Exception as e:
        logger.warning("Failed to generate test cases from diff: %s", e)
        return []


async def build_challenge_from_issue(
    issue: dict,
    changed_files: list[dict],
    test_files: list[dict],          # [{path, content}] — renamed from test_file_contents
    ci_annotations: list[dict] | None = None,
    base_source_files: list[dict] | None = None,
    user_id: str | None = None,
    pr_owner: str | None = None,
    pr_repo: str | None = None,
    base_sha: str | None = None,
    head_sha: str | None = None,
    is_merged: bool = False,
) -> dict:
    """
    Given a Linear issue + GitHub PR data, return a populated challenge dict.
    For merged PRs with base_source_files: discovers PR-fixed tests on Modal,
    uses them to select the source file and extract target functions as starter_code.
    Falls back to _extract_stubs if discovery fails or yields no functions.
    repo_context is always set on the merged PR path (even on fallback).
    """
    title = issue.get("title", "")
    description = issue.get("description", "") or ""

    test_cases: list[dict] = []
    source = "llm_generated"

    # Determine starter_code and repo_context
    repo_context: dict | None = None
    starter_code: str = _extract_stubs(changed_files)

    if is_merged and base_source_files and pr_owner and pr_repo and base_sha and head_sha:
        # Repo-context path: test_cases are not needed — eval runs real pytest tests
        # and results are reported by test node ID directly.

        # Get GitHub token for discovery
        github_token = get_integration(user_id, "github") if user_id else None

        # Discover PR-fixed tests via Modal
        challenge_test_ids: list[str] = []
        if github_token:
            try:
                challenge_test_ids = await discover_pr_fixed_tests(
                    github_token, pr_owner, pr_repo, base_sha, head_sha, test_files
                )
                logger.info(
                    "[generate] discover_pr_fixed_tests returned %d test(s): %s",
                    len(challenge_test_ids),
                    challenge_test_ids or "(none — will run full suite)",
                )
            except Exception as e:
                logger.warning("discover_pr_fixed_tests failed: %s", e)
                challenge_test_ids = []
        else:
            logger.warning("[generate] no github_token — skipping test discovery, will run full suite")

        # Use ALL changed source files — build multi-file starter code
        file_paths = [f["filename"] for f in base_source_files]
        if len(base_source_files) == 1:
            starter_code = base_source_files[0]["content"]
        else:
            starter_code = "\n\n".join(
                f"# === FILE: {f['filename']} ===\n{f['content']}"
                for f in base_source_files
            )
        logger.info("[generate] using %d source file(s) as starter_code: %s", len(file_paths), file_paths)

        repo_context = {
            "owner": pr_owner,
            "repo": pr_repo,
            "base_sha": base_sha,
            "file_paths": file_paths,
            "challenge_test_ids": challenge_test_ids,
        }
    elif base_source_files:
        # Non-merged PR with base source files — use full source as starter code
        starter_code = "\n\n".join(f["content"] for f in base_source_files)

    # For non-repo-context challenges, generate test_cases via LLM
    if not repo_context:
        for tf in test_files:
            parsed = await parse_test_cases_from_file(tf["content"])
            test_cases.extend(parsed)
        if test_cases:
            source = "existing_tests"
        else:
            diff_text = "\n".join(
                f"--- {f['filename']}\n{f.get('patch', '')}"
                for f in changed_files
            )
            failures_text = _format_ci_failures(ci_annotations or [])
            test_cases = await generate_test_cases_from_diff(title, description, diff_text, failures_text)

    result: dict = {
        "title": title,
        "description": description,
        "starter_code": starter_code,
        "test_cases": test_cases,
        "source": source,
        "test_files": test_files,
    }
    if user_id:
        result["user_id"] = user_id
    if repo_context:
        result["repo_context"] = repo_context

    return result


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
