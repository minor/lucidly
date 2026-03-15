"""LLM-based test case parsing and generation for interview challenges."""

import ast
import json
import re
import logging
from pathlib import Path

from llm import LLM
from config import settings
from challenges import Challenge, RepoContext
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
    test_ids: list[str],
    changed_files: list[dict],
) -> str | None:
    """
    Given PR-fixed test IDs and the PR's changed files, return the repo-relative
    path of the most likely source file under test.

    Strategy: for each test file name stem in the test IDs (e.g. 'test_parser' →
    'parser'), find the first changed non-test file whose stem matches.
    Returns None if no match or only test files changed.
    """
    # Collect candidate stems from test node IDs
    # e.g. "tests/test_parser.py::test_tokenize" → stem "parser"
    stems: list[str] = []
    for node_id in test_ids:
        path_part = node_id.split("::")[0]
        stem = Path(path_part).stem  # e.g. "test_parser"
        if stem.startswith("test_"):
            stem = stem[len("test_"):]
        elif stem.endswith("_test"):
            stem = stem[: -len("_test")]
        if stem:
            stems.append(stem)

    for cf in changed_files:
        fname = cf.get("filename", "")
        # Skip test files
        if "test" in Path(fname).stem.lower():
            continue
        if any(Path(fname).stem == s for s in stems):
            return fname

    return None


def _extract_functions_for_tests(
    source: str,
    test_ids: list[str],
    test_cases: list[dict] | None = None,
) -> str:
    """
    Extract only the top-level functions from `source` that are exercised by
    `test_ids` (and optionally by function calls in `test_cases[*].input`).

    Strategy:
    1. Collect candidate names from test node IDs:
       e.g. "test_tokenize" → candidate "tokenize"
    2. If test_cases provided, scan inputs for bare function calls
       (word followed by '(' not preceded by '.') as secondary candidates.
    3. Parse source with ast, find FunctionDef nodes whose name is in candidates.
    4. Deduplicate while preserving order.
    5. Fall back to full source if nothing matched.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    # Step 1: names from test IDs
    candidates: list[str] = []
    seen: set[str] = set()
    for node_id in test_ids:
        func_part = node_id.split("::")[-1]  # e.g. "test_tokenize"
        if func_part.startswith("test_"):
            name = func_part[len("test_"):]
        elif func_part.endswith("_test"):
            name = func_part[: -len("_test")]
        else:
            name = func_part
        if name and name not in seen:
            candidates.append(name)
            seen.add(name)

    # Step 2: secondary names from test_case inputs (bare calls only)
    if test_cases:
        for tc in test_cases:
            inp = tc.get("input", "")
            # Match word( not preceded by a dot (avoid obj.method())
            for m in re.finditer(r"(?<!\.)(\b[a-zA-Z_]\w*)\s*\(", inp):
                name = m.group(1)
                if name not in seen:
                    candidates.append(name)
                    seen.add(name)

    # Step 3: extract matching FunctionDef nodes
    extracted: list[str] = []
    extracted_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in candidates:
            if node.name not in extracted_names:
                extracted.append(ast.get_source_segment(source, node) or "")
                extracted_names.add(node.name)

    if not extracted:
        return source

    return "\n\n".join(extracted)


async def build_challenge_from_issue(
    issue: dict,
    changed_files: list[dict],
    test_files: list[dict],        # replaces test_file_contents: list[str]
    ci_annotations: list[dict],
    base_source_files: list[dict],
    user_id: str | None = None,
    pr_owner: str | None = None,
    pr_repo: str | None = None,
    base_sha: str | None = None,
    head_sha: str | None = None,
    is_merged: bool = False,
) -> Challenge:
    """
    Given a Linear issue + GitHub PR data, return a populated Challenge.
    Tries to use existing tests first; falls back to LLM generation.
    CI annotations (from check run failures) are included in the LLM prompt when available.
    For merged PRs with repo context, enriches the challenge with repo_context and
    targeted starter_code extracted from the PR-fixed source functions.
    """
    title = issue.get("title", "")
    description = issue.get("description", "") or ""

    test_cases: list[dict] = []
    source = "llm_generated"

    for tf in test_files:
        test_content = tf.get("content", "") if isinstance(tf, dict) else tf
        parsed = await parse_test_cases_from_file(test_content)
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

    # For merged PRs: use the actual buggy source files as starter code.
    # For open PRs: extract function stubs from the diff.
    if base_source_files:
        starter_code = "\n\n".join(f["content"] for f in base_source_files)
    else:
        starter_code = _extract_stubs(changed_files)

    challenge = Challenge(
        id="",
        title=title,
        description=description,
        category="debug",
        difficulty="medium",
        starter_code=starter_code,
        test_suite=[{"input": tc["input"], "expected_output": tc["expected_output"]} for tc in test_cases],
    )

    # ---- GitHub repo-context enrichment (merged PRs only) ----
    challenge.user_id = user_id
    challenge.test_files = test_files

    if is_merged and pr_owner and pr_repo and base_sha and head_sha:
        try:
            integration = await get_integration(user_id, "github")
            token = integration["access_token"]
            fixed_test_ids = await discover_pr_fixed_tests(
                token, pr_owner, pr_repo, base_sha, head_sha, test_files
            )
            file_path = _select_source_file(fixed_test_ids, changed_files)
            if file_path:
                src_entry = next(
                    (f for f in base_source_files if f["filename"] == file_path),
                    None,
                )
                if src_entry:
                    # Convert TestCase objects to dicts for _extract_functions_for_tests
                    tc_dicts = [
                        {"input": tc.input, "expected_output": tc.expected_output}
                        if hasattr(tc, "input") else tc
                        for tc in (challenge.test_suite or [])
                    ]
                    challenge.starter_code = _extract_functions_for_tests(
                        src_entry["content"],
                        fixed_test_ids,
                        test_cases=tc_dicts,
                    )
                    challenge.repo_context = RepoContext(
                        owner=pr_owner,
                        repo=pr_repo,
                        base_sha=base_sha,
                        file_path=file_path,
                        challenge_test_ids=fixed_test_ids,
                    )
        except Exception as exc:
            logging.getLogger(__name__).warning(
                "repo-context enrichment failed: %s", exc, exc_info=True
            )
    # ----------------------------------------------------------

    return challenge


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
