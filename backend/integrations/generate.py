"""LLM-based test case parsing and generation for interview challenges."""

import ast
import json
import re
import logging
from pathlib import Path

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


def _select_source_file(
    pr_fixed_test_ids: list[str],
    base_source_files: list[dict],
) -> dict:
    """Select the most relevant source file based on test file stem matching."""
    if not base_source_files:
        raise ValueError("base_source_files is empty")
    if not pr_fixed_test_ids:
        return base_source_files[0]

    scores: dict[str, int] = {f["filename"]: 0 for f in base_source_files}
    for node_id in pr_fixed_test_ids:
        test_file = node_id.split("::")[0]  # "tests/test_parser.py"
        test_stem = Path(test_file).stem     # "test_parser"
        if test_stem.startswith("test_"):
            test_stem = test_stem[5:]        # "parser"
        for source_file in base_source_files:
            src_stem = Path(source_file["filename"]).stem
            if src_stem == test_stem:
                scores[source_file["filename"]] += 1

    best_score = max(scores.values())
    if best_score == 0:
        return base_source_files[0]

    # On tie, use first file in original order that has the best score
    for f in base_source_files:
        if scores[f["filename"]] == best_score:
            return f

    return base_source_files[0]


def _extract_functions_for_tests(
    pr_fixed_test_ids: list[str],
    source_content: str,
    test_cases: list[dict] | None = None,
) -> str | None:
    """
    Extract the function definitions from source_content that are exercised
    by the PR-fixed test IDs (primary) and test case inputs (secondary).
    Returns None if extraction fails or yields nothing.
    """
    # 1. Collect candidate function names from test node IDs
    name_candidates: set[str] = set()
    for node_id in pr_fixed_test_ids:
        test_fn = node_id.split("::")[-1]  # "test_tokenize_operators_attached"
        if test_fn.startswith("test_"):
            name_candidates.add(test_fn[5:])
        # Also try the base name part before first underscore after "test_"
        # e.g. "test_tokenize_basic" → "tokenize"
        stripped = test_fn[5:] if test_fn.startswith("test_") else test_fn
        first_word = stripped.split("_")[0]
        if first_word:
            name_candidates.add(first_word)

    # Secondary: regex on test case inputs — re.match requires '(' right after the
    # identifier, so 'obj.method(x)' does NOT match (no '(' after 'obj').
    if test_cases:
        for tc in test_cases:
            m = re.match(r"^([A-Za-z_]\w*)\s*\(", tc.get("input", "").strip())
            if m:
                name_candidates.add(m.group(1))

    if not name_candidates:
        return None

    # 2. Parse source file
    try:
        tree = ast.parse(source_content)
    except SyntaxError:
        return None

    source_lines = source_content.splitlines()

    # 3. Find matching top-level functions (last occurrence wins for duplicates)
    matched: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in name_candidates:
                start = (
                    node.decorator_list[0].lineno
                    if node.decorator_list
                    else node.lineno
                )
                end = node.end_lineno
                matched[node.name] = "\n".join(source_lines[start - 1 : end])

    if not matched:
        return None

    # Preserve original source order; deduplicate by tracking emitted names
    seen: set[str] = set()
    ordered: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in matched and node.name not in seen:
                seen.add(node.name)
                ordered.append(matched[node.name])

    return "\n\n".join(ordered)


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

    for tf in test_files:
        parsed = await parse_test_cases_from_file(tf["content"])
        test_cases.extend(parsed)
    if test_cases:
        source = "existing_tests"

    if not test_cases:
        diff_text = "\n".join(
            f"--- {f['filename']}\n{f.get('patch', '')}"
            for f in changed_files
        )
        failures_text = _format_ci_failures(ci_annotations or [])
        test_cases = await generate_test_cases_from_diff(title, description, diff_text, failures_text)

    # Determine starter_code and repo_context
    repo_context: dict | None = None
    starter_code: str = _extract_stubs(changed_files)

    if is_merged and base_source_files and pr_owner and pr_repo and base_sha and head_sha:
        # Get GitHub token for discovery
        github_token = get_integration(user_id, "github") if user_id else None

        # Discover PR-fixed tests via Modal
        challenge_test_ids: list[str] = []
        if github_token:
            try:
                challenge_test_ids = await discover_pr_fixed_tests(
                    github_token, pr_owner, pr_repo, base_sha, head_sha, test_files
                )
            except Exception as e:
                logger.warning("discover_pr_fixed_tests failed: %s", e)
                challenge_test_ids = []

        # Select source file based on PR-fixed test stems
        selected_file = _select_source_file(challenge_test_ids, base_source_files)
        file_path = selected_file["filename"]
        source_content = selected_file["content"]

        # Extract functions exercised by PR-fixed tests (test_cases used as secondary name source)
        extracted = _extract_functions_for_tests(challenge_test_ids, source_content, test_cases)
        if extracted:
            starter_code = extracted
        else:
            starter_code = _extract_stubs(changed_files)

        repo_context = {
            "owner": pr_owner,
            "repo": pr_repo,
            "base_sha": base_sha,
            "file_path": file_path,
            "challenge_test_ids": challenge_test_ids,
        }
    elif base_source_files:
        # Non-merged PR with base source files — use full source as starter code
        starter_code = "\n\n".join(f["content"] for f in base_source_files)

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
